#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=consider-using-f-string

import sys
import traceback
from collections import defaultdict

from cdb import dberrors, sqlapi
from cdb.comparch import protocol

from cs.pcs.projects.scheduling import VALID_CONSTRAINTS_FOR_TASK_GROUPS
from cs.pcs.projects.tasks import ALLOWED_TASK_GROUP_DEPENDECIES


class UpdateTaskRelations:
    def run(self):
        # obsolete (cdbpcs_taskrel.gap has been removed in 15.8.0)
        pass


class UpdateTaskAttributes:
    def run(self):
        # 1) Update group tasks/ Sammelaufgaben
        sqlapi.SQLupdate(
            "cdbpcs_task SET automatic = auto_update_time WHERE is_group = 1"
        )
        # 2) Update normal tasks
        sqlapi.SQLupdate(
            "cdbpcs_task SET automatic = 0 , auto_update_time = 0 WHERE is_group = 0"
        )


class UpdateConstraintTypeOfTasks:
    """Constraint types:
    ASAP = "0"  # as soon as possible
    ALAP = "1"  # as late as possible
    MSO = "2"   # must start on
    MFO = "3"   # must finish on
    SNET = "4"  # start no earlier than
    SNLT = "5"  # start no later than
    FNET = "6"  # finish no earlier than
    FNLT = "7"  # finish no later than
    """

    def run(self):
        def updateTask(pid, tid, c_type, c_date):
            sqlapi.SQLupdate(
                """cdbpcs_task SET constraint_type = '{c_type}',
                                constraint_date = {c_date} WHERE constraint_type IS NULL
                                 AND cdb_project_id = '{pid}' AND task_id = '{tid}'""".format(
                    pid=pid, tid=tid, c_date=sqlapi.SQLdbms_date(c_date), c_type=c_type
                )
            )

        # determine tasks, that need a "Must finish on" constraint
        sqlapi.SQLupdate(
            """cdbpcs_task SET constraint_type = '3', constraint_date = end_time_fcast
            WHERE constraint_type IS NULL AND end_plan_fix = 1"""
        )

        # create dictionaries with projects, tasks and task relations
        predecessor_dict = defaultdict(list)
        pred_result = sqlapi.RecordSet2(
            sql="SELECT cdb_project_id2, task_id2, cdb_project_id, task_id FROM cdbpcs_taskrel"
        )
        for r in pred_result:
            predecessor_dict[(r.cdb_project_id, r.task_id)].append(
                (r.cdb_project_id2, r.task_id2)
            )
        parent_dict = {}
        project_result = sqlapi.RecordSet2(
            sql="SELECT cdb_project_id, start_time_fcast, end_time_fcast FROM cdbpcs_project"
        )
        for r in project_result:
            parent_dict[(r.cdb_project_id, "")] = r
        task_result = sqlapi.RecordSet2(
            sql="""SELECT task_name, cdb_project_id, task_id, parent_task,
                    start_time_fcast, end_time_fcast FROM cdbpcs_task"""
        )
        for r in task_result:
            parent_dict[(r.cdb_project_id, r.task_id)] = r

        # determine tasks, that need a "Start no earlier than" constraint
        for r in task_result:
            predecessors = predecessor_dict[(r.cdb_project_id, r.task_id)]
            parent = parent_dict[(r.cdb_project_id, r.parent_task)]
            if parent.start_time_fcast and r.start_time_fcast:
                if (
                    r.start_time_fcast < parent.start_time_fcast
                    or r.start_time_fcast > parent.start_time_fcast
                    and not predecessors
                ):
                    updateTask(
                        pid=r.cdb_project_id,
                        tid=r.task_id,
                        c_type="4",
                        c_date=r.start_time_fcast,
                    )
            elif not parent and not predecessors:
                updateTask(
                    pid=r.cdb_project_id,
                    tid=r.task_id,
                    c_type="4",
                    c_date=r.start_time_fcast,
                )

        # set all other tasks to "As soon as possible" constraint
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '0' WHERE constraint_type IS NULL"
        )


class CheckNotAllowedRelations:
    def run(self):
        stmt = """cdbpcs_task.cdb_project_id, cdbpcs_task.task_id, cdbpcs_task.task_name
            FROM cdbpcs_taskrel INNER JOIN cdbpcs_task
            ON cdbpcs_taskrel.cdb_project_id = cdbpcs_task.cdb_project_id
            AND cdbpcs_taskrel.task_id = cdbpcs_task.task_id
            WHERE cdbpcs_taskrel.rel_type NOT IN ({0}) AND cdbpcs_task.is_group = 1""".format(
            str(ALLOWED_TASK_GROUP_DEPENDECIES)[1:-1]
        )
        t = sqlapi.SQLselect(stmt)
        t_rows = sqlapi.SQLrows(t)
        if t_rows:
            message = (
                "The following task groups have relations which are not allowed:\n"
            )
            for i in range(sqlapi.SQLrows(t)):
                pid = sqlapi.SQLstring(t, 0, i)
                tid = sqlapi.SQLstring(t, 1, i)
                name = sqlapi.SQLstring(t, 2, i)
                message += (
                    " task '{0}' with cdb_project_id {1} and task_id {2}.\n".format(
                        name, pid, tid
                    )
                )
            message += (
                "Please delete offending relations or "
                "change the task groups to normal tasks."
            )
            protocol.logError(message)
            raise RuntimeError(
                """Task groups with incompatible relations have been found.
                This requires manual changes. Check error log for more information"""
            )


class CheckNotAllowedConstraints:
    def run(self):
        stmt = """cdbpcs_task.cdb_project_id, cdbpcs_task.task_id, cdbpcs_task.task_name
            FROM cdbpcs_task WHERE cdbpcs_task.is_group = 1
            AND cdbpcs_task.constraint_type NOT IN ({0})""".format(
            str(VALID_CONSTRAINTS_FOR_TASK_GROUPS)[1:-1]
        )
        t = sqlapi.SQLselect(stmt)
        t_rows = sqlapi.SQLrows(t)
        if t_rows:
            message = "The following task groups have constraint types which are not allowed:\n"
            for i in range(sqlapi.SQLrows(t)):
                pid = sqlapi.SQLstring(t, 0, i)
                tid = sqlapi.SQLstring(t, 1, i)
                name = sqlapi.SQLstring(t, 2, i)
                message += (
                    " task '{0}' with cdb_project_id {1} and task_id {2}.\n".format(
                        name, pid, tid
                    )
                )
            message += (
                "Please change the constraint types or change"
                " the task groups to normal tasks."
            )
            protocol.logError(message)
            raise RuntimeError(
                """Task groups with incompatible constraint types have been found.
                This requires manual changes. Check error log for more information"""
            )


class DropViewPCSSubjectAll:
    def run(self):
        """
        Before updating the view is dropped. It is intended to ensure
        that the new definition is applied.
        """
        try:
            sqlapi.SQL("DROP VIEW pcs_sharing_subjects_all")
        except dberrors.DBError as update_error:
            protocol.logWarning(
                "View pcs_aharing_subjects_all could not be dropped. Maybe view did not exist.",
                details_longtext=update_error.errmsg,
            )
            return
        except Exception:
            protocol.logError(
                "Error while dropping view pcs_sharing_all.",
                details_longtext="".join(traceback.format_exception(*sys.exc_info())),
            )
            return


class MigrateFolders:
    def run(self):
        """
        Migrate z_categ in cdb_folder
        """

        folders = sqlapi.RecordSet2(
            table="cdb_folder",
            updatable=1,
            sql="SELECT * FROM cdb_folder WHERE (z_categ1 != '' AND z_categ1 IS NOT NULL)",
        )
        main_categs = sqlapi.RecordSet2("cdb_doc_categ", "parent_id = ''")
        categ1_ids = {}
        categ1_names = {}
        for mc in main_categs:
            categ1_ids[mc.categ_id] = mc.name_d
            categ1_names[mc.name_d] = mc.categ_id
        sub_categs = sqlapi.RecordSet2("cdb_doc_categ", "parent_id != ''")
        categ_names = {}
        for c in sub_categs:
            if c.parent_id in categ1_ids:
                categ_names[(categ1_ids[c.parent_id], c.name_d)] = [
                    c.parent_id,
                    c.categ_id,
                ]

        for folder in folders:
            categ_name_d1 = folder["z_categ1"]
            if not categ_name_d1.isdigit():
                if folder.z_categ2:
                    categ_name_d2 = folder["z_categ2"]
                    try:
                        categ_ids = categ_names[(categ_name_d1, categ_name_d2)]
                        folder.update(z_categ1=categ_ids[0], z_categ2=categ_ids[1])
                    except KeyError:
                        protocol.logWarning(
                            "Missing category combination: %s, %s"
                            % (categ_name_d1, categ_name_d2),
                            details_longtext="Create the missing categories",
                        )

                else:
                    try:
                        folder.update(z_categ1=categ1_names[categ_name_d1])
                    except KeyError:
                        protocol.logWarning(
                            "Missing main category %s" % categ_name_d1,
                            details_longtext="Create the missing category",
                        )


pre = [DropViewPCSSubjectAll]
post = [
    UpdateTaskRelations,
    UpdateTaskAttributes,
    UpdateConstraintTypeOfTasks,
    CheckNotAllowedRelations,
    CheckNotAllowedConstraints,
    MigrateFolders,
]
