#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest

from cs.pcs.scheduling import persist_tasks_sql


@mock.patch.object(
    persist_tasks_sql,
    "_get_sql_pattern_and_fragments",
    return_value=(None, lambda _, **__: [{}]),
)
@mock.patch.object(
    persist_tasks_sql, "_load_query_pattern", return_value="{unknown_key}"
)
def test_write_task_changes_to_db_raises(_, __):
    "[write_task_changes_to_db] fails if SQL pattern and fragments don't match"
    with pytest.raises(KeyError) as error:
        persist_tasks_sql.write_task_changes_to_db(None, None)
    assert str(error.value) == "'unknown_key'"


@mock.patch.object(
    persist_tasks_sql,
    "_get_sql_pattern_and_fragments",
    return_value=(None, lambda _, **__: [{"id": "uno"}, {"id": "dos"}]),
)
@mock.patch.object(
    persist_tasks_sql, "_load_query_pattern", return_value="{cdb_project_id} // {id}"
)
@mock.patch.object(persist_tasks_sql.sqlapi, "SQL")
def test_write_task_changes_to_db(SQL, _, __):
    "[write_task_changes_to_db]"
    assert persist_tasks_sql.write_task_changes_to_db("foo", None) is None
    assert SQL.call_count == 2
    SQL.assert_has_calls(
        [
            mock.call("foo // uno"),
            mock.call("foo // dos"),
        ]
    )


@mock.patch.object(persist_tasks_sql.sqlapi, "SQLdate_literal")
def test_get_page_args(SQLdate_literal):
    "[_get_page_args]"
    result = persist_tasks_sql._get_page_args("foo")
    assert result == {
        "cdb_project_id": "foo",
        "cdb_adate": SQLdate_literal.return_value,
        "cdb_apersno": "'caddok'",
    }


@pytest.mark.parametrize(
    "dbms,expected",
    [
        (
            persist_tasks_sql.sqlapi.DBMS_MSSQL,
            ("update_many_tasks_mssql.sql", persist_tasks_sql._get_sql_fragments_mssql),
        ),
        (
            persist_tasks_sql.sqlapi.DBMS_ORACLE,
            ("update_many_tasks.sql", persist_tasks_sql._get_sql_fragments),
        ),
        (
            persist_tasks_sql.sqlapi.DBMS_SQLITE,
            ("update_many_tasks.sql", persist_tasks_sql._get_sql_fragments),
        ),
        (
            persist_tasks_sql.sqlapi.DBMS_POSTGRES,
            ("update_many_tasks.sql", persist_tasks_sql._get_sql_fragments_postgres),
        ),
        ("unknown", KeyError),
        (persist_tasks_sql.sqlapi.DBMS_INFORMIX, KeyError),
        (persist_tasks_sql.sqlapi.DBMS_INGRES, KeyError),
        (persist_tasks_sql.sqlapi.DBMS_SYBASE, KeyError),
    ],
)
def test_get_sql_pattern_and_fragments(dbms, expected):
    "[_get_sql_pattern_and_fragments]"
    with (
        mock.patch.object(persist_tasks_sql.sqlapi, "SQLdbms", return_value=dbms),
        mock.patch.object(persist_tasks_sql.logging, "exception") as log_exc,
    ):
        if expected == KeyError:
            with pytest.raises(KeyError):
                persist_tasks_sql._get_sql_pattern_and_fragments()
            log_exc.assert_called_once_with("unsupported DBMS: '%s'", dbms)
        else:
            result = persist_tasks_sql._get_sql_pattern_and_fragments()
            assert result == expected


@mock.patch.object(persist_tasks_sql.os.path, "abspath", return_value="safe")
def test_load_query_pattern_raises(_):
    "[_load_query_pattern] raises if pattern is outside safe path"
    persist_tasks_sql._load_query_pattern.cache_clear()
    with pytest.raises(RuntimeError):
        persist_tasks_sql._load_query_pattern("/root")


@pytest.mark.parametrize("is_file", [True, False])
def test_load_query_pattern(is_file):
    "[_load_query_pattern]"
    persist_tasks_sql._load_query_pattern.cache_clear()
    with (
        mock.patch.object(persist_tasks_sql.os.path, "isfile", return_value=is_file),
        mock.patch("builtins.open") as mock_open,
    ):
        result = persist_tasks_sql._load_query_pattern("foo")

    if is_file:
        assert result == mock_open.return_value.__enter__.return_value.read.return_value
    else:
        assert result is None


def test_get_sql_fragments():
    "[_get_sql_fragments]"
    pages = [
        (["T1", "T2"], {"1": {"T1": "new1.1"}, "2": {"T2": "new1.2"}}),
        (["T1", "T3"], {"3": {"T1": "new1.3", "T3": "new3.3"}, "4": {"x": "o"}}),
    ]
    result = list(persist_tasks_sql._get_sql_fragments(pages, foo="bar"))
    assert result == [
        {
            "task_ids": "T1', 'T2",
            "updates": (
                "1 = CASE"
                "\n        WHEN task_id = 'T1' THEN new1.1"
                "\n        WHEN task_id = 'T2' THEN 1"
                "\n    END,"
                "\n    2 = CASE"
                "\n        WHEN task_id = 'T1' THEN 2"
                "\n        WHEN task_id = 'T2' THEN new1.2"
                "\n    END"
            ),
        },
        {
            "task_ids": "T1', 'T3",
            "updates": (
                "3 = CASE"
                "\n        WHEN task_id = 'T1' THEN new1.3"
                "\n        WHEN task_id = 'T3' THEN new3.3"
                "\n    END,"
                "\n    4 = CASE"
                "\n        WHEN task_id = 'T1' THEN 4"
                "\n        WHEN task_id = 'T3' THEN 4"
                "\n    END"
            ),
        },
    ]


def test_get_sql_fragments_mssql():
    "[_get_sql_fragments_mssql]"
    pages = [
        (["T1", "T2"], {"1": {"T1": "new1.1"}, "2": {"T2": "new1.2"}}),
        (["T1", "T3"], {"3": {"T1": "new1.3", "T3": "new3.3"}, "4": {"x": "o"}}),
    ]
    kwargs = {
        "foo": "bar",
        "cdb_adate": "ADATE",
        "cdb_apersno": "APERSNO",
        "cdb_project_id": "PID",
    }
    result = list(persist_tasks_sql._get_sql_fragments_mssql(pages, **kwargs))
    assert result == [
        {
            "updates": (
                "\n        UPDATE cdbpcs_task SET"
                "\n            cdb_adate = ADATE,"
                "\n            cdb_apersno = APERSNO,"
                "\n            1 = new1.1,"
                "\n            2 = 2"
                "\n        WHERE cdb_project_id = 'PID'"
                "\n            AND task_id = 'T1'"
                "\n            AND ce_baseline_id = ''"
                "\n    "
                "\n"
                "\n        UPDATE cdbpcs_task SET"
                "\n            cdb_adate = ADATE,"
                "\n            cdb_apersno = APERSNO,"
                "\n            1 = 1,"
                "\n            2 = new1.2"
                "\n        WHERE cdb_project_id = 'PID'"
                "\n            AND task_id = 'T2'"
                "\n            AND ce_baseline_id = ''"
                "\n    "
            ),
        },
        {
            "updates": (
                "\n        UPDATE cdbpcs_task SET"
                "\n            cdb_adate = ADATE,"
                "\n            cdb_apersno = APERSNO,"
                "\n            3 = new1.3,"
                "\n            4 = 4"
                "\n        WHERE cdb_project_id = 'PID'"
                "\n            AND task_id = 'T1'"
                "\n            AND ce_baseline_id = ''"
                "\n    "
                "\n"
                "\n        UPDATE cdbpcs_task SET"
                "\n            cdb_adate = ADATE,"
                "\n            cdb_apersno = APERSNO,"
                "\n            3 = new3.3,"
                "\n            4 = 4"
                "\n        WHERE cdb_project_id = 'PID'"
                "\n            AND task_id = 'T3'"
                "\n            AND ce_baseline_id = ''"
                "\n    "
            ),
        },
    ]
