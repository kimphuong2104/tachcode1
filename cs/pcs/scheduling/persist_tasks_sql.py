#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import os

from cdb import misc, sqlapi, transactions
from cdb.ddl import Table
from cdb.lru_cache import lru_cache

from cs.pcs.projects.tasks import Task


def write_task_changes_to_db(project_id, task_change_pages):
    logging.debug("write_task_changes_to_db: %s", task_change_pages)
    file_name, get_sql_fragments = _get_sql_pattern_and_fragments()
    shared_args = _get_page_args(project_id)

    with transactions.Transaction():
        for sql_fragments in get_sql_fragments(task_change_pages, **shared_args):
            try:
                page_args = dict(shared_args)
                page_args.update(sql_fragments)
                stmt = _load_query_pattern(file_name).format(**page_args)
            except KeyError:
                logging.exception("failed to construct SQL for pattern '%s'", file_name)
                raise
            sqlapi.SQL(stmt)


def _get_page_args(project_id):
    cca = Task.MakeChangeControlAttributes()
    return {
        "cdb_project_id": project_id,
        "cdb_adate": sqlapi.SQLdate_literal(cca["cdb_mdate"]),
        "cdb_apersno": f"'{cca['cdb_mpersno']}'",
    }


def _get_sql_pattern_and_fragments():
    SQL_CONSTANTS = {
        sqlapi.DBMS_MSSQL: ("update_many_tasks_mssql.sql", _get_sql_fragments_mssql),
        sqlapi.DBMS_ORACLE: ("update_many_tasks.sql", _get_sql_fragments),
        sqlapi.DBMS_SQLITE: ("update_many_tasks.sql", _get_sql_fragments),
        sqlapi.DBMS_POSTGRES: ("update_many_tasks.sql", _get_sql_fragments_postgres),
    }
    dbms = sqlapi.SQLdbms()
    try:
        return SQL_CONSTANTS[dbms]
    except KeyError:
        logging.exception("unsupported DBMS: '%s'", dbms)
        raise


@lru_cache(maxsize=20, clear_after_ue=False)
def _load_query_pattern(fname):
    """
    :param fname: The filename relative to this file's path.
    :type fname: unicode

    :returns: Contents of the file ``fname``, ``None`` if it does not exist.

    :raises RuntimeError: if ``fname`` tries to escape this file's path.
    :raises: if ``fname`` does not exist or is not readable.
    """
    base = os.path.abspath(os.path.dirname(__file__))
    fpath = misc.jail_filename(base, fname)

    if not os.path.isfile(fpath):
        return None

    with open(fpath, "r", encoding="utf8") as sqlf:
        return sqlf.read()


def _get_sql_fragments(task_change_pages, **_):
    SQL_FRAGMENT_WHEN = "WHEN task_id = '{}' THEN {}"
    SQL_FRAGMENT_SET = "{} = CASE\n        {}\n    END"
    SQL_FRAGMENT_WHEN_INDENT = "\n        "
    SQL_FRAGMENT_UPDATES = ",\n    "
    SQL_FRAGMENT_IDS = "', '"

    for task_ids, task_changes in task_change_pages:
        updates = [
            SQL_FRAGMENT_SET.format(
                field_name,
                SQL_FRAGMENT_WHEN_INDENT.join(
                    [
                        SQL_FRAGMENT_WHEN.format(
                            task_id,
                            task_changes[field_name].get(
                                task_id,
                                # fall back to field_name (original value)
                                field_name,
                            ),
                        )
                        for task_id in task_ids
                    ]
                ),
            )
            for field_name in task_changes
        ]

        yield {
            "updates": SQL_FRAGMENT_UPDATES.join(updates),
            "task_ids": SQL_FRAGMENT_IDS.join(task_ids),
        }


def _get_sql_fragments_postgres(task_change_pages, **_):
    SQL_FRAGMENT_WHEN = "WHEN task_id = '{}' THEN {}"
    SQL_FRAGMENT_SET = "{} = CASE\n        {}\n    END"
    SQL_FRAGMENT_WHEN_INDENT = "\n        "
    SQL_FRAGMENT_UPDATES = ",\n    "
    SQL_FRAGMENT_IDS = "', '"

    # it is required to retrieve the correct cast types
    table_info = Table("cdbpcs_task")

    for task_ids, task_changes in task_change_pages:
        updates = []
        for field_name in task_changes:
            col = table_info.getColumn(field_name)
            col_def = col.text().strip().split(" ", 1)[1].lower()

            # 'double precision' is an unusual type as it has two words
            if col_def.startswith("double precision"):
                col_type = "double precision"
            else:
                col_type = col_def.split(" ", 1)[0]

            updates.append(
                SQL_FRAGMENT_SET.format(
                    field_name,
                    SQL_FRAGMENT_WHEN_INDENT.join(
                        [
                            SQL_FRAGMENT_WHEN.format(
                                task_id,
                                f"{task_changes[field_name].get(task_id, field_name)}::{col_type}",
                            )
                            for task_id in task_ids
                        ]
                    ),
                )
            )
        yield {
            "updates": SQL_FRAGMENT_UPDATES.join(updates),
            "task_ids": SQL_FRAGMENT_IDS.join(task_ids),
        }


def _get_sql_fragments_mssql(task_change_pages, **kwargs):
    SQL_FRAGMENT_UPDATE = f"""
        UPDATE cdbpcs_task SET
            cdb_adate = {kwargs["cdb_adate"]},
            cdb_apersno = {kwargs["cdb_apersno"]},
            {{}}
        WHERE cdb_project_id = '{kwargs["cdb_project_id"]}'
            AND task_id = '{{}}'
            AND ce_baseline_id = ''
    """
    SQL_FRAGMENT_VALUE_SEP = ",\n            "
    SQL_FRAGMENT_KEYMAP = "{} = {}"

    for task_ids, task_changes in task_change_pages:
        updates = [
            SQL_FRAGMENT_UPDATE.format(
                SQL_FRAGMENT_VALUE_SEP.join(
                    [
                        SQL_FRAGMENT_KEYMAP.format(
                            field_name,
                            task_changes[field_name].get(
                                task_id,
                                # fall back to field_name (original value)
                                field_name,
                            ),
                        )
                        for field_name in task_changes
                    ]
                ),
                task_id,
            )
            for task_id in task_ids
        ]
        yield {
            "updates": "\n".join(updates),
        }
