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
from cs.pcs.projects import Project
from cs.pcs.projects.common import partition
from cs.pcs.projects.common.sql_duplicate_project import (
    delete_duplicated_project,
    duplicate_project,
)
from cs.pcs.resources.duplicate import load_query_pattern
from cs.pcs.resources.structure.plugins.ctes import get_query_pattern


def _get_split_count():
    db_type = sqlapi.SQLdbms()
    if db_type == sqlapi.DBMS_ORACLE:
        return 10
    elif db_type == sqlapi.DBMS_MSSQL:
        return 1000
    elif db_type == sqlapi.DBMS_SQLITE:
        return 500
    elif db_type == sqlapi.DBMS_POSTGRES:
        return 1000


TABLE_NAMES_WITH_OID = [
    # Demands
    'cdbpcs_prj_demand',
    # Allocations
    'cdbpcs_prj_alloc',
    # TimeSchedule
    'cdbpcs_time_schedule',
    # ResourceSchedule
    'cdbpcs_resource_schedule',
    # Resource Pool
    'cdbpcs_resource_pool',
    # Pool Memberships
    'cdbpcs_pool_assignment',
    # Resources
    'cdbpcs_resource',
]

TABLE_NAMES_WITH_PROJECT_ID_1 = [
    # Linkage between TimeSchedule and Project
    "cdbpcs_project2time_schedule",
    # Linkage between ResourceSchedule and Project
    "cdbpcs_project2res_schedule",
]

TABLE_NAMES_WITH_PROJECT_ID_2 = [
    # Demands
    'cdbpcs_prj_demand',
    # Allocations
    'cdbpcs_prj_alloc',
    # Planned Resources
    'cdbpcs_res_schedule',
    'cdbpcs_res_sched_pw',
    'cdbpcs_res_sched_pm',
    'cdbpcs_res_sched_pq',
    'cdbpcs_res_sched_ph',
]


def _delete_from_table_by_ids(table, ids_to_delete, key):
    # Delete entries from db table 'table' where given attribute 'key'
    # has a value in 'ids_to_delete' via SQL.
    for part in partition(ids_to_delete, _get_split_count()):

        stmt = f"""
            DELETE FROM {table}
            WHERE {key} IN ({', '.join([f"'{sqlapi.quote(p)}'" for p in part])})
        """
        sqlapi.SQL(stmt)


def delete_duplicated_project_with_resources(cdb_project_id):
    """
    Deletes Project with cs.resource specific objects via SQL.
    :param cdb_project_id: Project ID of the project to delete

    Uses `cs.pcs.projects.common.sql_duplicate_project.delete_duplicated_project`
    to delete the project and cs.pcs specific.
    Afterwards the following objects are deleted in given order:
    - Project's TimeSchedules
    - The TimeSchedules' Content (i.e. pinned element entries)
    - Linkage between TimeSchedule and ResourceSchedule
    - Project's ResourceSchedules (direct and combined)
    - ResourcePools pinned in ResourceSchedules (including their Pool Structure)
    - The ResourcePools' Pool Memberships
    - The ResourcePools' Resources
    - The ResourceSchedules' Content (i.e. pinned element entries)
    - Linkage between TimeSchedule and Project
    - Linkage between ResourceSchedule and Project
    - Projects's Demands
    - Project's Allocations
    - Project's Planned Resource Entries ('cdbpcs_res_schedule',
        'cdbpcs_res_sched_pw', 'cdbpcs_res_sched_pm', 'cdbpcs_res_sched_pq',
        'cdbpcs_res_sched_ph')
    """

    # NOTE: The order in which the duplicated entries are deleted is relevant!
    #       In order to determine some entries UUIDs of others (related) have
    #       to be determined first.
    quoted_pid = sqlapi.quote(cdb_project_id)
    delete_duplicated_project(quoted_pid)

    rows = _get_table_rows('cdbpcs_time_schedule', 'cdb_project_id', [quoted_pid])
    time_sched_uuids = _extract_value_from_rows(rows, 'cdb_object_id')
    _delete_from_table_by_ids('cdbpcs_time_schedule', time_sched_uuids, 'cdb_object_id')
    _delete_from_table_by_ids('cdbpcs_ts_content', time_sched_uuids, 'view_oid')

    rows = _get_table_rows('cdbpcs_resource_schedule', 'cdb_project_id', [quoted_pid])
    res_sched_uuids = _extract_value_from_rows(rows, 'cdb_object_id')

    rows = _get_table_rows('cdbpcs_time2res_schedule', 'time_schedule_oid', time_sched_uuids)
    combined_res_sched_uuids = _extract_value_from_rows(rows, 'resource_schedule_oid')
    _delete_from_table_by_ids(
        'cdbpcs_time2res_schedule',
        combined_res_sched_uuids,
        'resource_schedule_oid'
    )

    all_res_sched_uuids = list(set(res_sched_uuids + combined_res_sched_uuids))
    _delete_from_table_by_ids('cdbpcs_resource_schedule', all_res_sched_uuids, 'cdb_object_id')

    rows = _get_table_rows(
        'cdbpcs_rs_content',
        'view_oid',
        all_res_sched_uuids,
        "cdb_content_classname = 'cdbpcs_resource_pool'"
    )
    pool_oids = _extract_value_from_rows(rows, 'content_oid')
    _delete_from_table_by_ids('cdbpcs_rs_content', pool_oids, 'content_oid')

    structured_pool_oids = []
    for pool_oid in pool_oids:
        structured_pool_oids += [r['cdb_object_id'] for r in _resolve_pool_structure(pool_oid)]
    rows = _get_table_rows('cdbpcs_resource_pool', 'cdb_object_id', structured_pool_oids)
    res_pool_uuids = _extract_value_from_rows(rows, 'cdb_object_id')
    _delete_from_table_by_ids('cdbpcs_resource_pool', res_pool_uuids, 'cdb_object_id')

    pool_assignment_rows = _get_table_rows('cdbpcs_pool_assignment', 'pool_oid', res_pool_uuids)
    resource_oids = _extract_value_from_rows(pool_assignment_rows, 'resource_oid')
    _delete_from_table_by_ids('cdbpcs_pool_assignment', resource_oids, 'resource_oid')

    _delete_from_table_by_ids('cdbpcs_resource', resource_oids, 'cdb_object_id')
    _delete_from_table_by_ids('cdbpcs_rs_content', all_res_sched_uuids, 'view_oid')

    tables = TABLE_NAMES_WITH_PROJECT_ID_1 + TABLE_NAMES_WITH_PROJECT_ID_2
    for table in tables:
        stmt = f"""
            DELETE FROM {table}
            WHERE cdb_project_id = '{quoted_pid}'
        """
        sqlapi.SQL(stmt)


def _get_table_rows(table_name, key_to_check, list_of_values, extra=None):
    # Get all entries of table whose value at given key is in given list of values
    quoted_values = ', '.join([f"'{sqlapi.quote(val)}'" for val in list_of_values])
    where_condition = f"{key_to_check} IN ({quoted_values})"
    if extra:
        where_condition += f" AND {extra}"
    return sqlapi.RecordSet2(table_name, where_condition)


def _extract_value_from_rows(rows, attribute):
    return [r[attribute] for r in rows] if attribute else []


def _duplicate_table_rows(rows, table, new_pid, uuid_mapping):
    table_info = util.tables[table]

    # skip table if no project related entries exist
    if rows:
        keys = rows[0].keys()
        for part in partition(rows, _get_split_count()):
            row_stmt_parts = []
            for row in part:
                values = []
                for key in keys:
                    # replace identifying keys for each row
                    if key == "cdb_project_id":
                        val = new_pid
                    elif key == "cdb_object_id":
                        val = cdbuuid.create_uuid()
                        uuid_mapping[row[key]] = val
                    elif key in [
                        'parent_oid', 'pool_oid', 'resource_oid', 'original_resource_oid',
                        'view_oid', 'content_oid', 'time_schedule_oid',
                        'resource_schedule_oid', 'assignment_oid'
                    ]:
                        val = uuid_mapping[row[key]] if row[key] else None
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
    return uuid_mapping


def _resolve_pool_structure(pool_oid):
    query_pattern = get_query_pattern("pool_structure", load_query_pattern)
    query_str = query_pattern.format(oid=pool_oid)
    return sqlapi.RecordSet2(sql=query_str)


def duplicate_project_with_resources(old_pid, new_pid=None):
    """
    Duplicates Project with cs.resource specific objects via SQL.
    :param old_pid: Project ID of the project to duplicate
    :param new_pid: Project ID of the new duplicated project.
                    If not given a new Project ID is generated.

    Uses `cs.pcs.projects.common.sql_duplicate_project.duplicate_project`
    to duplicate the project and cs.pcs specific.
    Afterwards the following objects are duplicated in given order:
    - Project's TimeSchedules
    - The TimeSchedules' Content (i.e. pinned element entries)
    - Project's ResourceSchedules (direct and combined)
    - Linkage between TimeSchedule and ResourceSchedule
    - Linkage between TimeSchedule and Project
    - Linkage between ResourceSchedule and Project
    - ResourcePools pinned in ResourceSchedules (including their Pool Structure)
    - The ResourcePools' Pool Memberships
    - The ResourcePool's Resources
    - Projects's Demands
    - Project's Allocations
    - Project's Planned Resource Entries ('cdbpcs_res_schedule',
        'cdbpcs_res_sched_pw', 'cdbpcs_res_sched_pm', 'cdbpcs_res_sched_pq',
        'cdbpcs_res_sched_ph')
    - The ResourceSchedules' Content (i.e. pinned element entries)
    """
    new_prj = duplicate_project(old_pid, new_pid)
    # In case no new project id was given, duplicate_project generates one,
    # which we've to take over for further duplication
    if not new_pid:
        new_pid = new_prj.cdb_project_id
    old_prj = Project.KeywordQuery(cdb_project_id=old_pid, ce_baseline_id="")[0]
    # NOTE: The Order in which table entries are duplicated is important to
    #       build up a lookup table of uuids used as keys for linkage between
    #       tables
    uuid_mapping = {old_prj.cdb_object_id: new_prj.cdb_object_id}
    # Map old_prj.Tasks.cdb_object_id to new_prj.Tasks.cdb_object_id
    new_prj_task_id2oid = {t.task_id: t.cdb_object_id for t in new_prj.Tasks}
    old_prj_task_id2oid = {t.task_id: t.cdb_object_id for t in old_prj.Tasks}
    for tid in new_prj_task_id2oid:
        # Note: Duplicating Project keeps Tasks.task_ids the same,
        #       so we can use it as linking key here
        uuid_mapping[old_prj_task_id2oid[tid]] = new_prj_task_id2oid[tid]

    with transactions.Transaction():
        # TimeSchedules
        rows = _get_table_rows('cdbpcs_time_schedule', 'cdb_project_id', [old_pid])
        time_sched_uuids = _extract_value_from_rows(rows, 'cdb_object_id')
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_time_schedule', new_pid, uuid_mapping)

        # TimeSchedule Content
        rows = _get_table_rows('cdbpcs_ts_content', 'view_oid', time_sched_uuids)
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_ts_content', new_pid, uuid_mapping)

        # ResourceSchedules
        # Gather all RS UUIDs associated with project directly ...
        rows = _get_table_rows('cdbpcs_resource_schedule', 'cdb_project_id', [old_pid])
        res_sched_uuids = _extract_value_from_rows(rows, 'cdb_object_id')
        # ... and indirectly (Combined Schedules, linked via TS)
        ts2rs_rows = _get_table_rows('cdbpcs_time2res_schedule', 'time_schedule_oid', time_sched_uuids)
        combined_res_sched_uuids = _extract_value_from_rows(ts2rs_rows, 'resource_schedule_oid')
        # Join resource schedule and combined resource schedule UUIDs
        all_res_sched_uuids = list(set(res_sched_uuids + combined_res_sched_uuids))
        # Duplicate all RS (linked directly to Project and linked indirectly to Project via TS)
        rows = _get_table_rows('cdbpcs_resource_schedule', 'cdb_object_id', combined_res_sched_uuids)
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_resource_schedule', new_pid, uuid_mapping)
        # finally duplicate linkage between RS and TS
        uuid_mapping = _duplicate_table_rows(ts2rs_rows, 'cdbpcs_time2res_schedule', new_pid, uuid_mapping)

        for table in TABLE_NAMES_WITH_PROJECT_ID_1:
            # Note: Skips over any not yet encountered pinned objects in TS
            rows = _get_table_rows(table, 'cdb_project_id', [old_pid])
            uuid_mapping = _duplicate_table_rows(rows, table, new_pid, uuid_mapping)

        # linkage between schedules and pools
        rows = _get_table_rows(
            'cdbpcs_rs_content',
            'view_oid',
            all_res_sched_uuids,
            "cdb_content_classname = 'cdbpcs_resource_pool'"
        )
        pool_oids = _extract_value_from_rows(rows, 'content_oid')

        # resource pools
        # Resolve the pool structure first; pinning only top level pool also
        # shows sub pools as RS content
        structured_pool_oids = []
        for pool_oid in pool_oids:
            structured_pool_oids += [r['cdb_object_id'] for r in _resolve_pool_structure(pool_oid)]
        rows = _get_table_rows('cdbpcs_resource_pool', 'cdb_object_id', structured_pool_oids)
        res_pool_uuids = _extract_value_from_rows(rows, 'cdb_object_id')
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_resource_pool', new_pid, uuid_mapping)

        # link between Pool and Resources
        pool_assignment_rows = _get_table_rows('cdbpcs_pool_assignment', 'pool_oid', res_pool_uuids)
        resource_oids = _extract_value_from_rows(pool_assignment_rows, 'resource_oid')

        # Resources
        rows = _get_table_rows('cdbpcs_resource', 'cdb_object_id', resource_oids)
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_resource', new_pid, uuid_mapping)

        # Pool Assignment
        uuid_mapping = _duplicate_table_rows(
            pool_assignment_rows,
            'cdbpcs_pool_assignment',
            new_pid,
            uuid_mapping
        )

        for table in TABLE_NAMES_WITH_PROJECT_ID_2:
            rows = _get_table_rows(table, 'cdb_project_id', [old_pid])
            uuid_mapping = _duplicate_table_rows(rows, table, new_pid, uuid_mapping)

        # ResourceSchedule Content
        # Note: we skip all pinned objects not encountered prior...
        rows = _get_table_rows('cdbpcs_rs_content', 'view_oid', all_res_sched_uuids)
        uuid_mapping = _duplicate_table_rows(rows, 'cdbpcs_rs_content', new_pid, uuid_mapping)

        # Fill short link table cdb_object (used by ByID) with oids of new objects
        fixer = CDBObjectIDFixer(logging.info)
        fixer.run(TABLE_NAMES_WITH_OID)

    return Project.ByKeys(cdb_project_id=new_pid, ce_baseline_id="")
