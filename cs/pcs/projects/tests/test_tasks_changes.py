#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter

import datetime
import unittest

import mock
import pytest
from cdb import auth, testcase

from cs.pcs.projects import Project, tasks_changes
from cs.pcs.projects.tasks import Task
from cs.pcs import helpers


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TasksChanges(unittest.TestCase):
    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_ORACLE
    )
    def test_get_split_count_ora(self, SQLdbms):
        "returns oracle split count"
        self.assertEqual(
            tasks_changes.get_split_count(),
            helpers.SPLIT_COUNT_ORACLE,
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_MSSQL
    )
    def test_get_split_count_mssql(self, SQLdbms):
        "returns mssql split count"
        self.assertEqual(
            tasks_changes.get_split_count(),
            helpers.SPLIT_COUNT_MSSQL,
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_SQLITE
    )
    def test_get_split_count_sqlite(self, SQLdbms):
        "returns sqlite split count"
        self.assertEqual(
            tasks_changes.get_split_count(),
            helpers.SPLIT_COUNT_SQLITE,
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_POSTGRES
    )
    def test_get_split_count_postgres(self, SQLdbms):
        "returns postgressql split count"
        self.assertEqual(
            tasks_changes.get_split_count(),
            helpers.SPLIT_COUNT_POSTGRES,
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(tasks_changes.sqlapi, "RecordSet2")
    @mock.patch.object(tasks_changes, "PROJECT_ID", "")
    def test_load_project_tasks_to_cache_no_pid(self, RecordSet2):
        "does nothing if PROJECT_ID is falsy"
        self.assertIsNone(tasks_changes.load_project_tasks_to_cache())
        RecordSet2.assert_not_called()

    @mock.patch.object(tasks_changes, "TASK_CACHE", {})
    @mock.patch.object(
        tasks_changes.sqlapi,
        "RecordSet2",
        return_value=[
            {"task_id": 1, "name": "uno"},
            {"task_id": 2, "name": "dos"},
        ],
    )
    @mock.patch.object(tasks_changes, "get_split_count", return_value="bat")
    @mock.patch.object(tasks_changes, "format_in_condition", return_value="bass")
    @mock.patch.object(tasks_changes, "CHANGES")
    @mock.patch.object(tasks_changes, "PROJECT_ID", "foo")
    def test_load_project_tasks_to_cache_changes(
        self,
        CHANGES,
        format_in_condition,
        get_split_count,
        RecordSet2,
    ):
        "fills TASK_CACHE with changed tasks"
        self.assertIsNone(tasks_changes.load_project_tasks_to_cache())
        self.assertEqual(
            tasks_changes.TASK_CACHE,
            {
                1: tasks_changes.OrderedDict(task_id=1, name="uno"),
                2: tasks_changes.OrderedDict(task_id=2, name="dos"),
            },
        )
        format_in_condition.assert_called_once_with("task_id", CHANGES.keys(), "bat")
        get_split_count.assert_called_once_with()
        RecordSet2.assert_has_calls(
            [
                mock.call(
                    "cdbpcs_task",
                    "cdb_project_id = 'foo' AND ce_baseline_id = '' AND bass",
                )
            ]
        )
        self.assertEqual(RecordSet2.call_count, 1)

    @mock.patch.object(tasks_changes, "TASK_CACHE", {})
    @mock.patch.object(
        tasks_changes.sqlapi,
        "RecordSet2",
        return_value=[
            {"task_id": 1, "name": "uno"},
            {"task_id": 2, "name": "dos"},
        ],
    )
    @mock.patch.object(tasks_changes, "CHANGES", False)
    @mock.patch.object(tasks_changes, "PROJECT_ID", "foo")
    def test_load_project_tasks_to_cache_all(self, RecordSet2):
        "fills TASK_CACHE with all tasks"
        self.assertIsNone(tasks_changes.load_project_tasks_to_cache())
        self.assertEqual(
            tasks_changes.TASK_CACHE,
            {
                1: tasks_changes.OrderedDict(task_id=1, name="uno"),
                2: tasks_changes.OrderedDict(task_id=2, name="dos"),
            },
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_task",
            "cdb_project_id = 'foo' AND ce_baseline_id = ''",
        )

    @mock.patch.object(tasks_changes, "PROJECT_ID", "bar")
    def test_set_project_id(self):
        "sets global PROJECT_ID"
        self.assertIsNone(tasks_changes.set_project_id("foo"))
        self.assertEqual(tasks_changes.PROJECT_ID, "foo")

    @mock.patch.object(tasks_changes, "CHANGES", {})
    def test_add_changes_missing_key(self):
        "fails to add to global CHANGES if key is missing"
        with self.assertRaises(KeyError) as error:
            tasks_changes.add_changes("foo", a=1)

        self.assertEqual(str(error.exception), "'foo'")

    @mock.patch.object(tasks_changes, "CHANGES", {"foo": {}, "bar": {}})
    def test_add_changes(self):
        "adds to global CHANGES"
        self.assertIsNone(tasks_changes.add_changes("foo", a=1))
        self.assertIsNone(tasks_changes.add_changes("foo", a=2))
        self.assertIsNone(tasks_changes.add_changes("foo", b=3))
        self.assertIsNone(
            tasks_changes.add_changes("bar", cdb_project_id="X", ce_baseline_id="Y")
        )
        self.assertEqual(
            tasks_changes.CHANGES,
            {"foo": {"a": 2, "b": 3, "only_system_attributes": False}, "bar": {}},
        )

    @mock.patch.object(tasks_changes, "CHANGES")
    @mock.patch.object(tasks_changes, "TASK_CACHE")
    def test_clear_caches(self, TASK_CACHE, CHANGES):
        "clears caches"
        self.assertIsNone(tasks_changes.clear_caches())
        TASK_CACHE.clear.assert_called_once_with()
        CHANGES.clear.assert_called_once_with()

    @mock.patch.object(tasks_changes, "update_modified_tasks")
    @mock.patch.object(tasks_changes, "CHANGES", {})
    def test_apply_changes_to_db_none(self, update_modified_tasks):
        "call update with empty list"
        tasks_changes.apply_changes_to_db()
        update_modified_tasks.assert_called_once_with([])

    @mock.patch.object(tasks_changes, "update_modified_tasks")
    @mock.patch.object(tasks_changes, "CHANGES", {"a": {"A": 1}, "b": {"B": 2}})
    def test_apply_changes_to_db(self, update_modified_tasks):
        "updates recorded changed in DB"
        tasks_changes.apply_changes_to_db()
        update_modified_tasks.assert_called_once_with(
            [
                ("a", {"A": 1}, None),
                ("b", {"B": 2}, None),
            ]
        )

    @mock.patch.object(tasks_changes, "load_project_tasks_to_cache")
    @mock.patch.object(tasks_changes, "TASK_CACHE", {})
    def test_get_changelists_empty_cache(self, load_cache):
        "fails if cache is empty"
        with self.assertRaises(KeyError) as error:
            tasks_changes.get_changelists(
                [
                    ("foo", {}, None),
                ]
            )

        self.assertEqual(str(error.exception), "'foo'")
        load_cache.assert_called_once_with()

    @mock.patch.object(tasks_changes, "load_project_tasks_to_cache")
    @mock.patch.object(tasks_changes, "TASK_CACHE", {"bar": {}})
    def test_get_changelists_missing_in_cache(self, load_cache):
        "fails if tasks_to_insert entry is missing in cache"
        with self.assertRaises(KeyError) as error:
            tasks_changes.get_changelists(
                [
                    ("foo", {}, None),
                ]
            )

        self.assertEqual(str(error.exception), "'foo'")
        load_cache.assert_called_once_with()

    @mock.patch.object(
        Task,
        "MakeChangeControlAttributes",
        return_value={"cdb_mdate": "m_date", "cdb_mpersno": "m_persno"},
    )
    @mock.patch.object(tasks_changes, "load_project_tasks_to_cache")
    @mock.patch.object(
        tasks_changes.sqlapi,
        "make_literal",
        side_effect=lambda a, b, c: f"'{c}'",
    )
    @mock.patch.object(tasks_changes.util, "tables", {"cdbpcs_task": "TableInfo"})
    @mock.patch.object(
        tasks_changes,
        "TASK_CACHE",
        {
            "foo": {
                "task_id": "foo_key",
                "cdb_adate": "a_date",
                "cdb_apersno": "a_persno",
                "cdb_mdate": "m_date",
                "cdb_mpersno": "m_persno",
                "key": "foo",
                "a": "A",
                "cdb_object_id": "x1",
            },
            "bar": {
                "task_id": "bar_key",
                "cdb_adate": "a_date",
                "cdb_apersno": "a_persno",
                "cdb_mdate": "m_date",
                "cdb_mpersno": "m_persno",
                "key": "bar",
                "b": "B",  # ignored, not in first entry
                "a": "B",
                "cdb_object_id": "x2",
            },
        },
    )
    def test_get_changelists(self, make_literal, load_cache, ch_crtl):
        "returns lists to build SQL statements with"
        self.assertEqual(
            tasks_changes.get_changelists(
                [
                    ("bar", {"c": "b", "only_system_attributes": False}, None),
                    ("foo", {"c": "a", "only_system_attributes": True}, None),
                ]
            ),
            (
                ["c", "cdb_adate", "cdb_apersno", "cdb_mdate", "cdb_mpersno"],
                {
                    "foo": {
                        "cdb_mdate": "'m_date'",
                        "c": "'a'",
                        "cdb_apersno": "'a_persno'",
                        "cdb_adate": "'a_date'",
                        "cdb_mpersno": "'m_persno'",
                    },
                    "bar": {
                        "cdb_mdate": "'m_date'",
                        "c": "'b'",
                        "cdb_apersno": "'a_persno'",
                        "cdb_adate": "'a_date'",
                        "cdb_mpersno": "'m_persno'",
                    },
                },
            ),
        )
        make_literal.assert_has_calls(
            [
                mock.call("TableInfo", "c", "b"),
                mock.call("TableInfo", "cdb_adate", "a_date"),
                mock.call("TableInfo", "cdb_apersno", "a_persno"),
                mock.call("TableInfo", "cdb_mdate", "m_date"),
                mock.call("TableInfo", "cdb_mpersno", "m_persno"),
                mock.call("TableInfo", "c", "a"),
                mock.call("TableInfo", "cdb_adate", "a_date"),
                mock.call("TableInfo", "cdb_apersno", "a_persno"),
                mock.call("TableInfo", "cdb_mdate", "m_date"),
                mock.call("TableInfo", "cdb_mpersno", "m_persno"),
            ]
        )
        self.assertEqual(make_literal.call_count, 10)
        load_cache.assert_called_once_with()

    @mock.patch.object(tasks_changes, "clear_caches")
    def test_update_modified_tasks_empty(self, clear_caches):
        "does nothing when called with empty list"
        self.assertIsNone(tasks_changes.update_modified_tasks([]))
        clear_caches.assert_not_called()


@pytest.mark.integration
class TasksChangesIntegration(testcase.RollbackTestCase):
    PID = "integration test"

    def _setup_data(self):
        self.project = Project.Create(
            cdb_project_id=self.PID,
            ce_baseline_id="",
        )
        self.tasks = [
            Task.Create(
                cdb_project_id=self.PID,
                ce_baseline_id="",
                task_id=tid,
                task_name=tid,
                category="",
            )
            for tid in "ab"
        ]
        tasks_changes.set_project_id(self.PID)
        tasks_changes.load_project_tasks_to_cache()

    def assertTaskEqual(self, task, expected):
        task.Reload()
        self.assertDictContainsSubset(expected, dict(task))

    def _apply_changes(self, expected, direct=None, indirect=None):
        # a is changed directly and/or indirectly, b is always unchanged
        self._setup_data()
        a, b = self.tasks
        unchanged_b = dict(b)
        if direct:
            tasks_changes.add_changes(a.task_id, **direct)
        if indirect:
            tasks_changes.add_indirect_changes(a.task_id, **indirect)

        tasks_changes.apply_changes_to_db()
        self.assertTaskEqual(a, expected)
        self.assertTaskEqual(b, unchanged_b)

    def test_apply_changes_to_db_direct(self):
        # only direct changes, e.g. cdb_adate/apersno don't change
        self._apply_changes(
            {
                "days": 5,
                "task_name": "a changed",
                "effort_fcast": 0.11,
                "cdb_mpersno": auth.persno,
                "cdb_adate": None,
                "cdb_apersno": None,
            },
            direct={
                "days": 5,
                "task_name": "a changed",
                "effort_fcast": 0.11,
            },
        )

    def test_apply_changes_to_db_indirect(self):
        # only indirect changes, e.g. cdb_cdate/cpersno don't change
        self._apply_changes(
            {
                "start_time_fcast": datetime.date(2022, 8, 1),
                "task_name": "a changed",
                "effort_fcast": None,
                "cdb_mdate": None,
                "cdb_mpersno": None,
                "cdb_apersno": auth.persno,
            },
            indirect={
                "task_name": "a changed",
                "start_time_fcast": datetime.date(2022, 8, 1),
            },
        )

    @mock.patch("cs.pcs.projects.tasks_changes.PROJECT_ID", "foo")
    @mock.patch.object(tasks_changes, "clear_caches")
    @mock.patch.object(tasks_changes.sqlapi, "SQL")
    @mock.patch.object(tasks_changes.transactions, "Transaction")
    @mock.patch.object(
        tasks_changes,
        "get_changelists",
        return_value=(
            ["a", "b"],
            {
                "x": {"a": "'val_a_x'", "b": "'val_b_x'"},
                "y": {"a": "'val_a_y'", "b": "'val_b_y'"},
            },
        ),
    )
    def _update_modified_tasks(
        self, insert_stmt, get_changelists, Transaction, SQL, clear_caches
    ):
        self.assertIsNone(
            tasks_changes.update_modified_tasks(
                [
                    ("foo", {"a": "a_changed"}, None),
                    ("unchanged", {}, None),  # filtered out
                ]
            )
        )
        get_changelists.assert_called_once_with([("foo", {"a": "a_changed"}, None)])
        Transaction.assert_called_once_with()
        SQL.assert_called_once_with(insert_stmt)
        clear_caches.assert_called_once_with()

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_SQLITE
    )
    def test_update_modified_tasks_sqlite(self, SQLdbms):
        "issues DB deletes and inserts for SQLITE"
        stmt = (
            "WITH updated (\n"
            "    task_id, a, b\n"
            ") AS (VALUES\n"
            "    ('y', 'val_a_y', 'val_b_y'),\n"
            "    ('x', 'val_a_x', 'val_b_x')\n)"
            "\n\n"
            "UPDATE cdbpcs_task SET\n"
            "    a = (SELECT a FROM updated WHERE "
            "cdbpcs_task.task_id = updated.task_id),\n"
            "    b = (SELECT b FROM updated WHERE "
            "cdbpcs_task.task_id = updated.task_id)\n"
            "WHERE cdb_project_id = 'foo'\n"
            "AND task_id IN (SELECT task_id FROM updated)\n"
            "AND ce_baseline_id = ''\n"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_SQLITE is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_MSSQL
    )
    def test_update_modified_tasks_mssql(self, SQLdbms):
        "issues DB deletes and inserts for MSSQL"
        stmt = (
            "UPDATE cdbpcs_task\n"
            "SET\n"
            "    cdbpcs_task.a = updated.a,\n"
            "    cdbpcs_task.b = updated.b\n"
            "FROM cdbpcs_task JOIN (\n"
            "    SELECT 'y' AS task_id, 'val_a_y' AS a, 'val_b_y' AS b\n"
            "    UNION ALL\n"
            "    SELECT 'x' AS task_id, 'val_a_x' AS a, 'val_b_x' AS b\n"
            ") updated ON cdbpcs_task.task_id = updated.task_id\n"
            "WHERE cdbpcs_task.cdb_project_id = 'foo'\n"
            "AND cdbpcs_task.ce_baseline_id = ''\n"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_MSSQL is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_ORACLE
    )
    def test_update_modified_tasks_ora(self, SQLdbms):
        "issues DB deletes and inserts for ORACLE"
        stmt = (
            "UPDATE cdbpcs_task"
            "SET y = CASE"
            "    WHEN task_id = 'a' THEN 'val_a_y'"
            "    WHEN task_id = 'b' THEN 'val_b_y'"
            "END,"
            "x = CASE"
            "    WHEN task_id = 'a' THEN 'val_a_x'"
            "    WHEN task_id = 'b' THEN 'val_b_x'"
            "END"
            "WHERE cdb_project_id = 'foo'"
            "AND ce_baseline_id = ''\n"
            "AND task_id IN ('a', 'b')"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_ORACLE is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    @mock.patch("cs.pcs.projects.tasks_changes.PROJECT_ID", "foo")
    @mock.patch.object(tasks_changes, "clear_caches")
    @mock.patch.object(tasks_changes.sqlapi, "SQL")
    @mock.patch.object(tasks_changes.transactions, "Transaction")
    @mock.patch.object(
        tasks_changes,
        "get_changelists",
        return_value=(
            ["a", "b"],
            {
                "x": {"a": "'val_a_x'", "b": "'val_b_x'"},
                "y": {"a": "'val_a_y'", "b": "'val_b_y'"},
            },
        ),
    )
    def _update_modified_tasks(
        self, insert_stmt, get_changelists, Transaction, SQL, clear_caches
    ):
        self.assertIsNone(
            tasks_changes.update_modified_tasks(
                [
                    ("foo", {"a": "a_changed"}, None),
                    ("unchanged", {}, None),  # filtered out
                ]
            )
        )
        get_changelists.assert_called_once_with([("foo", {"a": "a_changed"}, None)])
        Transaction.assert_called_once_with()
        SQL.assert_called_once_with(insert_stmt)
        clear_caches.assert_called_once_with()

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_SQLITE
    )
    def test_update_modified_tasks_sqlite(self, SQLdbms):
        "issues DB deletes and inserts for SQLITE"
        stmt = (
            "WITH updated (\n"
            "    task_id, a, b\n"
            ") AS (VALUES\n"
            "    ('x', 'val_a_x', 'val_b_x'),\n"
            "    ('y', 'val_a_y', 'val_b_y')\n)"
            "\n\n"
            "UPDATE cdbpcs_task SET\n"
            "    a = (SELECT a FROM updated WHERE "
            "cdbpcs_task.task_id = updated.task_id),\n"
            "    b = (SELECT b FROM updated WHERE "
            "cdbpcs_task.task_id = updated.task_id)\n"
            "WHERE cdb_project_id = 'foo'\n"
            "AND task_id IN (SELECT task_id FROM updated)\n"
            "AND ce_baseline_id = ''\n"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_SQLITE is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_MSSQL
    )
    def test_update_modified_tasks_mssql(self, SQLdbms):
        "issues DB deletes and inserts for MSSQL"
        stmt = (
            "UPDATE cdbpcs_task\n"
            "SET\n"
            "    cdbpcs_task.a = updated.a,\n"
            "    cdbpcs_task.b = updated.b\n"
            "FROM cdbpcs_task JOIN (\n"
            "    SELECT 'x' AS task_id, 'val_a_x' AS a, 'val_b_x' AS b\n"
            "    UNION ALL\n"
            "    SELECT 'y' AS task_id, 'val_a_y' AS a, 'val_b_y' AS b\n"
            ") updated ON cdbpcs_task.task_id = updated.task_id\n"
            "WHERE cdbpcs_task.cdb_project_id = 'foo'\n"
            "AND cdbpcs_task.ce_baseline_id = ''\n"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_MSSQL is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    @mock.patch.object(
        tasks_changes.sqlapi, "SQLdbms", return_value=tasks_changes.sqlapi.DBMS_ORACLE
    )
    def test_update_modified_tasks_ora(self, SQLdbms):
        "issues DB deletes and inserts for ORACLE"
        stmt = (
            "UPDATE cdbpcs_task\n"
            "SET a = CASE\n"
            "    WHEN task_id = 'x' THEN 'val_a_x'\n"
            "    WHEN task_id = 'y' THEN 'val_a_y'\n"
            "    END,\n"
            "b = CASE\n"
            "    WHEN task_id = 'x' THEN 'val_b_x'\n"
            "    WHEN task_id = 'y' THEN 'val_b_y'\n"
            "    END\n"
            "WHERE cdb_project_id = 'foo'\n"
            "AND ce_baseline_id = ''\n"
            "AND task_id IN ('x', 'y')\n"
        )
        self._update_modified_tasks(stmt)
        # sqlapi.DBMS_ORACLE is called twice; once for partitioning
        # and once for determining the CTE to be used
        SQLdbms.assert_has_calls([mock.call(), mock.call()])

    def test_apply_changes_to_db_both(self):
        # both direct and indirect changes
        self._apply_changes(
            {
                "task_name": "a changed",
                "category": "foo",
                "cdb_mpersno": auth.persno,
                "cdb_apersno": auth.persno,
            },
            direct={
                "task_name": "a changed",
            },
            indirect={
                "category": "foo",
            },
        )

    def test_apply_changes_to_db_same(self):
        # calls with unchanged values still apply the changes
        # because old values are never read
        blacklisted = {
            "task_name": "a",
            "category": "",
        }
        self._apply_changes(
            {
                "task_name": "a",
                "category": "",
                "cdb_project_id": self.PID,
                "ce_baseline_id": "",
                "cdb_apersno": auth.persno,
                "cdb_mpersno": auth.persno,
            },
            direct=blacklisted,
            indirect=blacklisted,
        )

    def test_apply_changes_to_db_blacklisted(self):
        # only try to change blacklisted data -> no change
        blacklisted = {
            "cdb_project_id": "foo",
            "ce_baseline_id": "foo",
        }
        self._apply_changes(
            {
                "cdb_project_id": self.PID,
                "ce_baseline_id": "",
                "cdb_adate": None,
                "cdb_apersno": None,
                "cdb_mdate": None,
                "cdb_mpersno": None,
            },
            direct=blacklisted,
            indirect=blacklisted,
        )

    def test_apply_changes_to_db_none(self):
        # no change call
        self._apply_changes(
            {
                "cdb_project_id": self.PID,
                "ce_baseline_id": "",
                "cdb_adate": None,
                "cdb_apersno": None,
                "cdb_mdate": None,
                "cdb_mpersno": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
