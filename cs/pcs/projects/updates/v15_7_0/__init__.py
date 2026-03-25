#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi, transaction, transactions, util
from cdb.comparch import protocol
from cdb.comparch.updutils import TranslationCleaner
from cs.baselining.support import BaselineTools

from cs.pcs.msp.updates.v15_5_0 import revert_deleted_patch
from cs.pcs.projects.updates.helpers import initialize_sortable_id


class InitSortableIDBase:
    def run(self):
        if not util.column_exists(self.__table_name__, "cdbprot_zaehler"):
            protocol.logMessage("No need to migrate protocol ==> no cdbprot_zaehler")
            return

        with transaction.Transaction():
            initialize_sortable_id(self.__table_name__)


class InitSortableID_Project(InitSortableIDBase):
    """
    Initializes the new primary key ``cdbpcs_prj_prot.cdbprot_sortable_id``.
    """

    __table_name__ = "cdbpcs_prj_prot"


class InitSortableID_Task(InitSortableIDBase):
    """
    Initializes the new primary key ``cdbpcs_tsk_prot.cdbprot_sortable_id``.
    """

    __table_name__ = "cdbpcs_tsk_prot"


class InitializeBaseliningProjects:
    def run(self):
        BaselineTools.fix_baseline_object_ids(relation="cdbpcs_project")


class InitializeBaseliningTasks:
    def run(self):
        BaselineTools.fix_baseline_object_ids(relation="cdbpcs_task")


class InitializeBaseliningProposals:
    tables = [
        "pcs_project_proposals",
        "pcs_project_template_proposals",
        "pcs_task_proposals",
    ]

    def run(self):
        for table in self.tables:
            sqlapi.SQLupdate(
                f"{table}" " SET ce_baseline_id = ''" " WHERE ce_baseline_id IS NULL"
            )


class CleanTranslation:
    """
    Cleans the Turkish and Chinese languages from the translations for
    all cs.pcs modules as these languages are no more supported.
    """

    def run(self):
        modules = [
            "cs.pcs.projects",
            "cs.pcs.checklists",
            "cs.pcs.issues",
            "cs.pcs.projects_defects",
            "cs.pcs.projects_documents",
            "cs.pcs.projects_workflows",
            "cs.pcs.checklists_documents",
            "cs.pcs.dashboard",
            "cs.pcs.efforts",
            "cs.pcs.issues_documents",
            "cs.pcs.timeschedule",
            "cs.pcs.msp",
            "cs.pcs.taskboards",
            "cs.pcs.substitute",
        ]
        with transactions.Transaction():
            for module in modules:
                languages_to_clean = ["zh", "tr"]
                tc = TranslationCleaner(module, languages_to_clean)
                tc.run()


class DenyBaselineWriteAccess:
    """
    Make sure write access is denied for baselined projects and tasks
    """

    __module_id__ = "cs.pcs.projects"
    __entries__ = [
        ("cdb_acd", {"acd_id": "cs.pcs: Baselined Projects and Tasks"}),
        ("cdb_acd_access", {"acd_id": "cs.pcs: Baselined Projects and Tasks"}),
        ("cdb_acd_pred", {"acd_id": "cs.pcs: Baselined Projects and Tasks"}),
        ("cdb_predicate", {"predicate_name": "cs.pcs: Baselined Project"}),
        ("cdb_predicate", {"predicate_name": "cs.pcs: Baselined Task"}),
        ("cdb_term", {"predicate_name": "cs.pcs: Baselined Project"}),
        ("cdb_term", {"predicate_name": "cs.pcs: Baselined Task"}),
    ]

    def run(self):
        for table, kwargs in self.__entries__:
            revert_deleted_patch(self.__module_id__, table, **kwargs)


class UpdateFavoiteProjectsAndTasks:
    """
    The rest ID  of projects and project tasks after baselining is changed and now ending with '@'
    To keep the favorite projects and tasks we have to update the rest_id in cdbweb_favorites table
    """

    __update_stmt__ = """
        cdbweb_favorites SET rest_id = (rest_id {} '@')
        WHERE rest_name in ('project', 'project_task') AND rest_id not like '%@'
        """

    def run(self):
        sqlapi.SQLupdate(self.__update_stmt__.format(sqlapi.SQLstrcat()))
        protocol.logMessage("Favorite project and tasks rest IDs updated.")


class UpdateObjectRulesToExcludeBaselines(object):
    """
    Insert Terms for excluding Baselines to the Predicate of each Object Rule,
    where the Predicates are defined for Project or Project Task and no Term
    excludes Baselines from the Rule.
    """

    __select_stmt__ = """
        p.name, p.predicate_name, p.fqpyname, p.cdb_module_id,
        (
            SELECT COUNT(*)
            FROM cdb_pyterm pt
            WHERE pt.predicate_name = p.predicate_name
                AND pt.fqpyname = p.fqpyname
                AND pt.name = p.name
        ) term_count
        FROM cdb_pypredicate p
        LEFT JOIN cdb_pyterm t
            ON p.predicate_name = t.predicate_name
            AND p.fqpyname = t.fqpyname
            AND p.name = t.name
            AND t.attribute = 'ce_baseline_id'
        WHERE t.id IS NULL
            AND p.fqpyname IN (
                'cs.pcs.projects.tasks.Task',
                'cs.pcs.projects.Project'
            )
            AND (
                p.cdb_module_id LIKE 'cs.pcs%'
                OR p.cdb_module_id = 'cs.objdashboard'
            )

    """

    __insert_stmt__ = """
            INSERT INTO cdb_pyterm
            (
                name,
                fqpyname,
                predicate_name,
                cdb_module_id,
                id,
                attribute,
                operator,
                expression
            )
            VALUES (
                '{name}',
                '{fqpyname}',
                '{predicate_name}',
                '{cdb_module_id}',
                '{id}',
                'ce_baseline_id',
                '=',
                ''
            )
        """

    def run(self):

        t = sqlapi.SQLselect(self.__select_stmt__)
        t_rows = sqlapi.SQLrows(t)
        if t_rows:
            with transactions.Transaction():
                for i in range(t_rows):
                    name = sqlapi.SQLstring(t, 0, i)
                    predicate_name = sqlapi.SQLstring(t, 1, i)
                    fqpyname = sqlapi.SQLstring(t, 2, i)
                    cdb_module_id = sqlapi.SQLstring(t, 3, i)
                    # number of terms the predicate without ce_baseline_id term
                    term_count = sqlapi.SQLstring(t, 4, i)
                    sqlapi.SQL(
                        self.__insert_stmt__.format(
                            name=name,
                            fqpyname=fqpyname,
                            predicate_name=predicate_name,
                            cdb_module_id=cdb_module_id,
                            id=int(term_count) + 1,
                        )
                    )


pre = [InitSortableID_Project, InitSortableID_Task]
post = [
    CleanTranslation,
    DenyBaselineWriteAccess,
    InitializeBaseliningProjects,
    InitializeBaseliningTasks,
    InitializeBaseliningProposals,
    UpdateFavoiteProjectsAndTasks,
    UpdateObjectRulesToExcludeBaselines,
]


if __name__ == "__main__":
    CleanTranslation().run()
