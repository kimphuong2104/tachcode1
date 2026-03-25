#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from datetime import datetime

from cdb import sqlapi, transactions
from cdb.cdbuuid import create_sortable_id
from cdb.comparch import protocol

from cs.pcs.projects.common import format_in_condition
from cs.pcs.projects.project_status import Project
from cs.pcs.projects.tasks_status import Task

# Project, Task must be imported from where status classes are defined!
TASK_DISCARDED = Task.DISCARDED.status
TASK_FINISHED = Task.FINISHED.status
TASK_COMPLETED = Task.COMPLETED.status
TASK_FINAL = ", ".join(
    [
        str(TASK_FINISHED),
        str(TASK_COMPLETED),
    ]
)
PROJECT_NON_FINAL = ", ".join(
    [
        str(Project.NEW.status),
        str(Project.EXECUTION.status),
        str(Project.FROZEN.status),
    ]
)


class UpdateDiscardedTaskGroups:
    """
    E067897 Task group with finished or completed subtasks can be discarded

    Task groups containing finished or completed subtasks
    is an invalid combination that is no longer possible to create.

    This update fixes this in all non-final projects
    (those are considered archived).
    """

    __where__ = f"""status = {TASK_DISCARDED}
        AND EXISTS (
            SELECT 1 FROM cdbpcs_task subtasks
            WHERE subtasks.cdb_project_id = cdbpcs_task.cdb_project_id
            AND subtasks.parent_task = cdbpcs_task.task_id
            AND subtasks.ce_baseline_id = cdbpcs_task.ce_baseline_id
            AND subtasks.status IN ({TASK_FINAL})
        )
        AND EXISTS (
            SELECT 1 FROM cdbpcs_project
            WHERE cdbpcs_project.cdb_project_id = cdbpcs_task.cdb_project_id
            AND cdbpcs_project.ce_baseline_id = cdbpcs_task.ce_baseline_id
            AND status IN ({PROJECT_NON_FINAL})
        )
    """
    __update_pattern__ = "cdbpcs_task SET status={} WHERE {}"
    __protocol_pattern__ = """WITH protocol_entries {prot_cols} AS (
        SELECT
            '{sortable_id}',
            'caddok',
            {now},
            cdb_status_txt,
            '{finished_en}',
            cdb_project_id,
            task_id,
            {finished},
            status,
            cdb_objektart
        FROM cdbpcs_task
        WHERE {where}
    )
    INSERT INTO cdbpcs_tsk_prot {prot_cols}
    SELECT * FROM protocol_entries
    """

    __protocol_pattern_postgres__ = """WITH RECURSIVE protocol_entries {prot_cols} AS (
        SELECT
            '{sortable_id}',
            'caddok',
            {now}::timestamp,
            cdb_status_txt,
            '{finished_en}',
            cdb_project_id,
            task_id,
            {finished},
            status,
            cdb_objektart
        FROM cdbpcs_task
        WHERE {where}
    )
    INSERT INTO cdbpcs_tsk_prot {prot_cols}
    SELECT * FROM protocol_entries
    """

    __protocol_pattern_ora__ = """INSERT INTO cdbpcs_tsk_prot {prot_cols}
    WITH protocol_entries {prot_cols} AS (
        SELECT
            '{sortable_id}',
            'caddok',
            {now},
            cdb_status_txt,
            '{finished_en}',
            cdb_project_id,
            task_id,
            {finished},
            status,
            cdb_objektart
        FROM cdbpcs_task
        WHERE {where}
    )
    SELECT * FROM protocol_entries
    """
    __protocol_columns__ = """(
        cdbprot_sortable_id,
        cdbprot_persnum,
        cdbprot_zeit,
        cdbprot_altstat,
        cdbprot_neustat,
        cdb_project_id,
        task_id,
        cdbprot_newstate,
        cdbprot_oldstate,
        cdbprot_objektart
    )"""

    def run(self):
        uuids = [
            x.cdb_object_id
            for x in sqlapi.RecordSet2(
                "cdbpcs_task", self.__where__, columns=["cdb_object_id"]
            )
        ]

        if uuids:
            if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                prot_pattern = self.__protocol_pattern_ora__
            elif sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                prot_pattern = self.__protocol_pattern_postgres__
            else:
                prot_pattern = self.__protocol_pattern__

            with transactions.Transaction():
                update_stmt = self.__update_pattern__.format(
                    Task.FINISHED.status, format_in_condition("cdb_object_id", uuids)
                )
                sqlapi.SQLupdate(update_stmt)

                for uuid in uuids:
                    sortable_id = create_sortable_id()

                    protocol_stmt = prot_pattern.format(
                        sortable_id=sortable_id,
                        now=sqlapi.SQLdate_literal(datetime.now()),
                        finished_en="FINISHED",
                        finished=Task.FINISHED.status,
                        where=f"cdb_object_id = '{uuid}'",
                        prot_cols=self.__protocol_columns__,
                    )
                    sqlapi.SQL(protocol_stmt)

        protocol.logMessage(f"{len(uuids)} discarded tasks set to finished")


pre = []
post = [UpdateDiscardedTaskGroups]
