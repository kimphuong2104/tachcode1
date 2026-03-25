#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=too-many-locals,too-many-nested-blocks

import logging

from cdb import cdbuuid, sqlapi, transactions, util
from cdb.platform.tools import CDBObjectIDFixer

from cs.pcs import projects
from cs.pcs.projects.common import partition
from cs.pcs.helpers import get_dbms_split_count


TABLE_NAMES_WITH_OID = [
    # Project
    "cdbpcs_project",
    "cdbpcs_prj_role",
    "cdbpcs_subject",
    "cdb_calendar_entry",
    # Tasks
    "cdbpcs_task",
    "cdbpcs_time_sheet",
    # Open Issues
    "cdbpcs_issue",
    # Checklists
    "cdbpcs_checklst",
    "cdbpcs_cl_item",
]

TABLE_NAMES_OF_RELATIONS = [
    # Project
    "cdbpcs_team",
    "cdbpcs_prj_acd",
    "cdbpcs_prj2doctmpl",
    "cdbpcs_prj_prot",
    # Tasks
    "cdbpcs_taskrel",
    "cdbpcs_task2doctmpl",
    "cdbpcs_doc2task",
    # Open Issues
    "cdbpcs_doc2iss",
    # Checklists
    "cdbpcs_doc2cl",
    "cdbpcs_doc2cli",
    "cdbpcs_cl2doctmpl",
    "cdbpcs_cli2doctmpl",
    # Folder
    "cdb_folder",
]

PROJECT_RELATED_TABLE_NAMES = TABLE_NAMES_WITH_OID + TABLE_NAMES_OF_RELATIONS


def delete_duplicated_project(cdb_project_id):
    for table in PROJECT_RELATED_TABLE_NAMES:
        stmt = f"""
            DELETE FROM {table}
            WHERE cdb_project_id = '{cdb_project_id}'
        """
        sqlapi.SQL(stmt)


def duplicate_project(old_pid, new_pid=None):

    with transactions.Transaction():
        old_project = projects.Project.KeywordQuery(
            cdb_project_id=old_pid, ce_baseline_id=""
        )[0]
        new_pid = (
            f"P{util.nextval('PROJECT_ID_SEQ'):06d}"
            if not new_pid
            else sqlapi.quote(new_pid)
        )

        for table in PROJECT_RELATED_TABLE_NAMES:
            table_info = util.tables[table]
            quoted_old_pid = sqlapi.quote(old_pid)
            if table in ["cdbpcs_project", "cdbpcs_task"]:
                where_condition = (
                    f"cdb_project_id = '{quoted_old_pid}' AND ce_baseline_id=''"
                )
            elif table == "cdbpcs_taskrel":
                # Do not duplicate task relships pointing to another project
                where_condition = "cdb_project_id = '{old_pid}' AND cdb_project_id2 = '{old_pid}'".format(
                    old_pid=quoted_old_pid
                )
            else:
                where_condition = f"cdb_project_id = '{quoted_old_pid}'"
            rows = sqlapi.RecordSet2(table, where_condition)
            # skip table if no project related entries exist
            if rows:
                keys = rows[0].keys()
                for part in partition(rows, get_dbms_split_count()):
                    row_stmt_parts = []
                    for row in part:
                        values = []
                        for key in keys:
                            # replace identifying keys for each row
                            if key in ["cdb_project_id", "cdb_project_id2"]:
                                val = new_pid
                            elif key in ["cdb_object_id", "cdbprot_sortable_id"]:
                                val = cdbuuid.create_uuid()
                            elif key == "project_name":
                                val = f"{old_project.project_name} - Duplicate"
                            else:
                                # take over other keys
                                val = row[key]
                            # format values correctly for sql stmt
                            val = sqlapi.make_literal(table_info, key, val)
                            values.append(val)

                        # encapsulate values for rows in ()
                        row_stmt_parts.append(f"({', '.join(values)})")

                    # Construct row stmts for multiple row insertion
                    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                        # Oracle seperates insert-tuples by space
                        insert_part_stmts = "\n".join(
                            [
                                f"INTO {table} ({', '.join(keys)}) VALUES {row_stmt_part}"
                                for row_stmt_part in row_stmt_parts
                            ]
                        )

                        stmt = f"""
                            INSERT ALL
                            {insert_part_stmts}
                            SELECT 1 FROM DUAL
                            """
                        sqlapi.SQL(stmt)

                    else:
                        # Mssql and sqlite seperate insert-tuples by comma
                        row_stmts = ",\n".join(row_stmt_parts)
                        stmt = f"""
                                INTO {table} ({", ".join(keys)})
                                VALUES {row_stmts}
                            """
                        sqlapi.SQLinsert(stmt)

        # Fill short link table cdb_object (used by ByID) with oids of new objects
        fixer = CDBObjectIDFixer(logging.info)
        fixer.run(TABLE_NAMES_WITH_OID)

        # Update tables that refer to project via cdb_object_id
        # cdbpcs_task_rel
        #     cdb_project_id, task_id: Successor
        #     cdb_project_id2, task_id2: Predecessor
        update_stmts = [
            f"""
            UPDATE cdbpcs_taskrel SET pred_task_oid = (
                SELECT cdb_object_id FROM cdbpcs_task
                WHERE cdbpcs_task.cdb_project_id = cdbpcs_taskrel.cdb_project_id2
                AND cdbpcs_task.task_id = cdbpcs_taskrel.task_id2
            ) WHERE cdb_project_id2 = '{new_pid}'
            """,
            f"""
            UPDATE cdbpcs_taskrel SET succ_task_oid = (
                SELECT cdb_object_id FROM cdbpcs_task
                WHERE cdbpcs_task.cdb_project_id = cdbpcs_taskrel.cdb_project_id
                AND cdbpcs_task.task_id = cdbpcs_taskrel.task_id
            ) WHERE cdb_project_id = '{new_pid}'
            """,
            f"""
            UPDATE cdbpcs_taskrel SET pred_project_oid = (
                SELECT cdb_object_id FROM cdbpcs_project
                WHERE cdbpcs_project.cdb_project_id = cdbpcs_taskrel.cdb_project_id2
            ) WHERE cdb_project_id2 = '{new_pid}'
            """,
            f"""
            UPDATE cdbpcs_taskrel SET succ_project_oid = (
                SELECT cdb_object_id FROM cdbpcs_project
                WHERE cdbpcs_project.cdb_project_id = cdbpcs_taskrel.cdb_project_id
            ) WHERE cdb_project_id = '{new_pid}'
            """,
        ]
        for update_stmt in update_stmts:
            sqlapi.SQL(update_stmt)

    # return newly created project
    return projects.Project.ByKeys(cdb_project_id=new_pid, ce_baseline_id="")
