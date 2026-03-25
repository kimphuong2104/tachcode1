#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable-msg=E0213,E1103,E0102,E0203,W0212,W0621,W0201

import logging
from collections import OrderedDict, defaultdict

from cdb import sqlapi, transactions, util
from cdb.ddl import Table

from cs.pcs.projects.common import format_in_condition, partition
from cs.pcs.projects.schedule_sql import get_query_pattern
from cs.pcs.helpers import get_dbms_split_count

TASK_CACHE = defaultdict()
CHANGES = defaultdict(OrderedDict)
PROJECT_ID = ""
# blacklist for metadata changes (e.g. primary keys)
BLACKLIST = set(["cdb_project_id", "task_id", "ce_baseline_id"])
FILE_NAME_SQLITE = "merge_task_changes_sqlite"
FILE_NAME_ORACLE = "merge_task_changes_ora"
FILE_NAME_MSSQL = "merge_task_changes_mssql"
FILE_NAME_POSTGRES = "merge_task_changes_postgres"


def get_split_count():
    return get_dbms_split_count()


def load_project_tasks_to_cache():
    if not PROJECT_ID:
        return

    # since this is used to batch DB updates, we can not operate on baselines
    condition = f"cdb_project_id = '{PROJECT_ID}' AND ce_baseline_id = ''"

    if CHANGES:
        task_condition = format_in_condition(
            "task_id",
            CHANGES.keys(),
            get_split_count(),
        )
        condition = f"{condition} AND {task_condition}"

    for task in sqlapi.RecordSet2("cdbpcs_task", condition):
        TASK_CACHE[task["task_id"]] = OrderedDict(**task)


def set_project_id(project_id):
    # pylint: disable=global-statement
    global PROJECT_ID
    PROJECT_ID = project_id


def add_changes(task_id, **kwargs):
    filtered_args = {key: val for key, val in kwargs.items() if key not in BLACKLIST}
    if filtered_args:
        filtered_args["only_system_attributes"] = False
        CHANGES[task_id].update(**filtered_args)


def add_indirect_changes(task_id, **kwargs):
    filtered_args = {key: val for key, val in kwargs.items() if key not in BLACKLIST}
    if filtered_args:
        filtered_args["indirect_attributes"] = True
        CHANGES[task_id].update(**filtered_args)


def clear_caches():
    TASK_CACHE.clear()
    CHANGES.clear()


def apply_changes_to_db():
    tasks = []
    logging.debug("tasks_changes: apply %s changes", len(CHANGES))
    for task_id, task_changes in list(CHANGES.items()):
        tasks.append((task_id, task_changes, None))
    update_modified_tasks(tasks)


def get_changelists(tasks_to_insert):
    from cs.pcs.projects.tasks import Task

    load_project_tasks_to_cache()

    table_info = util.tables["cdbpcs_task"]
    cca = Task.MakeChangeControlAttributes()

    # determine all table colums, that will have changes
    keys_to_insert = set(["cdb_mdate", "cdb_mpersno", "cdb_adate", "cdb_apersno"])
    for _, task_to_create, _ in tasks_to_insert:
        keys_to_insert = keys_to_insert.union(set(task_to_create.keys()))
    if "only_system_attributes" in keys_to_insert:
        keys_to_insert.remove("only_system_attributes")
    if "indirect_attributes" in keys_to_insert:
        keys_to_insert.remove("indirect_attributes")
    keys_to_insert = list(keys_to_insert)
    keys_to_insert.sort()

    # construct the value tuples
    values_by_task_id = defaultdict(dict)
    for task_id, task_to_create, _ in tasks_to_insert:
        new_dict = OrderedDict(**TASK_CACHE[task_id])
        only_system_attributes = task_to_create.pop("only_system_attributes", True)
        if not only_system_attributes:
            # set 'changelog' values for direct changes
            new_dict.update(cdb_mdate=cca["cdb_mdate"], cdb_mpersno=cca["cdb_mpersno"])
        indirect_attributes = task_to_create.pop("indirect_attributes", False)
        if indirect_attributes:
            # set 'adjustment' values for indirect changes
            new_dict.update(cdb_adate=cca["cdb_mdate"], cdb_apersno=cca["cdb_mpersno"])
        new_dict.update(**task_to_create)

        for k in keys_to_insert:
            values_by_task_id[task_id][k] = sqlapi.make_literal(
                table_info, k, new_dict[k]
            )

    return keys_to_insert, values_by_task_id


def get_changelists_mssql(tasks_to_insert):
    keys_to_insert, values_by_task_id = get_changelists(tasks_to_insert)

    # construct values statement for each changed task
    values_to_insert = []
    for task_id, values in values_by_task_id.items():
        values_to_sql = [f"'{task_id}' AS task_id"]
        for k in keys_to_insert:
            values_to_sql.append(f"{values[k]} AS {k}")
        sql_values = ", ".join(values_to_sql)
        values_to_insert.append(f"    SELECT {sql_values}")

    # construct the set statements for update
    set_statements = []
    for k in keys_to_insert:
        set_statements.append("    cdbpcs_task.{key} = updated.{key}".format(key=k))

    return {
        "values_to_insert": "\n    UNION ALL\n".join(values_to_insert),
        "set_statements": ",\n".join(set_statements),
    }


def get_changelists_oracle(tasks_to_insert):
    keys_to_insert, values_by_task_id = get_changelists(tasks_to_insert)

    task_ids = values_by_task_id.keys()
    set_clauses = []
    for k in keys_to_insert:
        set_clause = f"{k} = CASE\n"
        for task_id in task_ids:
            set_clause += (
                f"    WHEN task_id = '{task_id}'"
                f" THEN {values_by_task_id[task_id][k]}\n"
            )
        set_clause += "    END"
        set_clauses.append(set_clause)

    return {
        "updates": ",\n".join(set_clauses),
        "task_ids": ", ".join([f"'{task_id}'" for task_id in task_ids]),
    }


def get_changelists_sqlite(tasks_to_insert):
    keys_to_insert, values_by_task_id = get_changelists(tasks_to_insert)

    # construct values statement for each changed task
    values_to_insert = []
    for task_id, values in values_by_task_id.items():
        values_to_sql = [f"'{task_id}'"]
        for k in keys_to_insert:
            values_to_sql.append(values[k])
        sql_values = ", ".join(values_to_sql)
        values_to_insert.append(f"    ({sql_values})")

    # construct the subselects statements for update
    sub_selects = []
    for key in keys_to_insert:
        sub_selects.append(
            f"    {key} = (SELECT {key} FROM updated WHERE "
            f"cdbpcs_task.task_id = updated.task_id)"
        )

    return {
        "keys_to_insert": ", ".join(["task_id"] + keys_to_insert),
        "values_to_insert": ",\n".join(values_to_insert),
        "sub_selects": ",\n".join(sub_selects),
    }


def get_changelists_postgres(tasks_to_insert):
    keys_to_insert, values_by_task_id = get_changelists(tasks_to_insert)

    # construct values statement for each changed task
    values_to_insert = []
    for task_id, values in values_by_task_id.items():
        values_to_sql = [f"'{task_id}'"]
        for k in keys_to_insert:
            values_to_sql.append(values[k])

        sql_values = ", ".join(values_to_sql)
        values_to_insert.append(f"    ({sql_values})")

    # it is required to retrieve the correct cast types
    table_info = Table("cdbpcs_task")

    # construct the subselects statements for update
    sub_selects = []
    for key in keys_to_insert:
        col = table_info.getColumn(key)
        col_def = col.text().strip().split(" ", 1)[1].lower()

        # 'double precision' is an unusual type as it has two words
        if col_def.startswith("double precision"):
            col_type = "double precision"
        else:
            col_type = col_def.split(" ", 1)[0]

        sub_selects.append(
            f"    {key} = (SELECT {key}::{col_type} FROM updated WHERE "
            f"cdbpcs_task.task_id = updated.task_id)"
        )

    return {
        "keys_to_insert": ", ".join(["task_id"] + keys_to_insert),
        "values_to_insert": ",\n".join(values_to_insert),
        "sub_selects": ",\n".join(sub_selects),
    }


def update_modified_tasks(tasks_to_insert):
    # remove tasks without changes from list
    tasks_to_insert = [x for x in tasks_to_insert if x[1]]

    if not tasks_to_insert:
        return

    with transactions.Transaction():
        for part_tasks_to_insert in partition(tasks_to_insert, get_split_count()):
            # update values
            file_name = ""
            kwargs = {"cdb_project_id": PROJECT_ID}
            db = sqlapi.SQLdbms()
            if db == sqlapi.DBMS_ORACLE:
                file_name = FILE_NAME_ORACLE
                kwargs.update(**get_changelists_oracle(part_tasks_to_insert))
            elif db == sqlapi.DBMS_MSSQL:
                file_name = FILE_NAME_MSSQL
                kwargs.update(**get_changelists_mssql(part_tasks_to_insert))
            elif db == sqlapi.DBMS_SQLITE:
                file_name = FILE_NAME_SQLITE
                kwargs.update(**get_changelists_sqlite(part_tasks_to_insert))
            elif db == sqlapi.DBMS_POSTGRES:
                file_name = FILE_NAME_POSTGRES
                kwargs.update(**get_changelists_postgres(part_tasks_to_insert))

            try:
                stmt = get_query_pattern(file_name).format(**kwargs)
            except KeyError:
                logging.exception(
                    "failed to construct SQL for pattern '%s'",
                    file_name,
                )
                raise
            sqlapi.SQL(stmt)

    clear_caches()
