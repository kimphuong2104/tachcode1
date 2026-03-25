#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cdb import sqlapi, testcase
from cs import taskmanager


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(taskmanager.sqlapi, "SQLdbms", return_value="foo")
    def test_get_collation_not_mssql(self, _):
        self.assertEqual(
            taskmanager.get_collation(),
            "",
        )

    @mock.patch("cdb.mssql.CollationDefault.get_default_collation")
    @mock.patch.object(
        taskmanager.sqlapi, "SQLdbms", return_value=taskmanager.sqlapi.DBMS_MSSQL
    )
    def test_get_collation_mssql(self, _, get_default_collation):
        self.assertEqual(
            taskmanager.get_collation(),
            "COLLATE {}".format(get_default_collation.return_value),
        )

    @mock.patch.object(taskmanager, "get_collation", return_value="COLLATION")
    @mock.patch.object(
        taskmanager.TaskHeaders, "getCombinedViewStatement", return_value=""
    )
    def test_generate_cs_tasks_headers_v_fallback(self, _, __):
        expected = (
            "SELECT"
            "\n                name COLLATION AS task_classname,"
            "\n                classname COLLATION AS classname,"
            "\n                '' COLLATION AS persno,"
            "\n                '' COLLATION AS cdb_object_id,"
            "\n                '' COLLATION AS subject_id,"
            "\n                '' COLLATION AS subject_type,"
            "\n                NULL AS deadline"
            "\n            FROM cs_tasks_class"
            "\n        "
        )
        self.assertEqual(
            taskmanager.generate_cs_tasks_headers_v(),
            expected,
        )

    @mock.patch.object(taskmanager, "get_collation", return_value="COLLATION")
    @mock.patch.object(taskmanager.TaskHeaders, "getCombinedViewStatement")
    def test_generate_cs_tasks_headers_v(self, getViewStmt, _):
        self.assertEqual(
            taskmanager.generate_cs_tasks_headers_v(),
            getViewStmt.return_value,
        )


@pytest.mark.unit
class TaskHeadersUnit(testcase.RollbackTestCase):
    @mock.patch.object(taskmanager.TaskHeaders, "_getViewStatement")
    @mock.patch.object(taskmanager.TaskClass, "Query", return_value=[4, 2])
    def test_getCombinedViewStatement(self, Query, _getStmt):
        def _get_stmt(i, t):
            return "{}-{}".format(i, t)

        _getStmt.side_effect = _get_stmt
        expected = "0-4\nUNION ALL 1-2"
        self.assertEqual(
            taskmanager.TaskHeaders.getCombinedViewStatement(),
            expected,
        )
        Query.assert_called_once_with()
        _getStmt.assert_has_calls(
            [
                mock.call(0, 4),
                mock.call(1, 2),
            ]
        )
        self.assertEqual(_getStmt.call_count, 2)

    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView.ByKeys")
    def test_compileToView(self, ByKeys):
        self.assertTrue(taskmanager.TaskHeaders.compileToView())
        ByKeys.assert_called_once_with(taskmanager.HEADER_VIEW)
        ByKeys.return_value.rebuild.assert_called_once_with()

    @testcase.without_error_logging
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView.ByKeys")
    def test_compileToView_fail_silently(self, ByKeys):
        ByKeys.return_value.rebuild.side_effect = RuntimeError
        self.assertFalse(taskmanager.TaskHeaders.compileToView())
        ByKeys.assert_called_once_with(taskmanager.HEADER_VIEW)
        ByKeys.return_value.rebuild.assert_called_once_with()

    @testcase.without_error_logging
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView.ByKeys")
    def test_compileToView_fail(self, ByKeys):
        ByKeys.return_value.rebuild.side_effect = RuntimeError

        with self.assertRaises(RuntimeError):
            taskmanager.TaskHeaders.compileToView(True)

        ByKeys.assert_called_once_with(taskmanager.HEADER_VIEW)
        ByKeys.return_value.rebuild.assert_called_once_with()


@pytest.mark.integration
class TaskHeadersIntegration(testcase.RollbackTestCase):
    def test_collation(self):
        if sqlapi.SQLdbms() != sqlapi.DBMS_MSSQL:
            self.skipTest("only relevant for MS SQL")

        from cdb.mssql import CollationDefault

        rows = CollationDefault.find_wrong_collations()

        own_tables = [
            row.table_name
            for row in sqlapi.RecordSet2(
                "cdbdd_table", "cdb_module_id='cs.taskmanager'"
            )
        ]
        broken = {row.table_name for row in rows if row.table_name in own_tables}

        self.assertEqual(
            len(broken),
            0,
            msg="views containing wrong collations: {}".format(
                [dict(row) for row in rows if row.table_name in broken]
            ),
        )

    def test__getViewStatement_test_class(self):
        self.skipTest("DBMSes order WHERE condition differently")
        task_class = taskmanager.TaskClass.ByKeys("Test Tasks")
        expected = (
            "\n            SELECT"
            "\n                'Test Tasks'  AS task_classname,"
            "\n                'cs_tasks_test_class'  AS classname,"
            "\n                angestellter5.personalnummer  AS persno,"
            "\n                cs_tasks_test_class.cdb_object_id"
            "  AS cdb_object_id,"
            "\n                ''  AS subject_id,"
            "\n                ''  AS subject_type,"
            "\n                NULL AS deadline"
            "\n            FROM"
            "\n                cs_tasks_test_class cs_tasks_test_class"
            "\n            INNER JOIN angestellter angestellter5 ON 1=1"
            "\n                "
            "\n         WHERE (cs_tasks_test_class.active=1) "
            "AND angestellter5.cdb_classname='angestellter'"
        )
        self.assertEqual(
            taskmanager.TaskHeaders._getViewStatement(5, task_class), expected
        )

    def test__getViewStatement_test_class_olc(self):
        self.skipTest("DBMSes order WHERE condition differently")
        task_class = taskmanager.TaskClass.ByKeys("Test Tasks (OLC)")
        expected = (
            "\n            SELECT"
            "\n                'Test Tasks (OLC)'  AS task_classname,"
            "\n                'cs_tasks_test_class_olc'  AS classname,"
            "\n                angestellterX.personalnummer  AS persno,"
            "\n                cs_tasks_test_class_olc.cdb_object_id"
            "  AS cdb_object_id,"
            "\n                cs_tasks_test_class_olc.subject_id,"
            "\n                cs_tasks_test_class_olc.subject_type,"
            "\n                cs_tasks_test_class_olc.deadline AS deadline"
            "\n            FROM"
            "\n                cs_tasks_test_class_olc cs_tasks_test_class_olc"
            "\n            INNER JOIN angestellter angestellterX ON 1=1"
            "\n                 LEFT JOIN cdbwf_role_cache cdbwf_role_cache"
            " ON ((cs_tasks_test_class_olc.subject_id="
            "cdbwf_role_cache.subject_id) AND "
            "(cs_tasks_test_class_olc.subject_type="
            "cdbwf_role_cache.subject_type) AND "
            "(cdbwf_role_cache.personalnummer=angestellterX.personalnummer)"
            " AND ((cs_tasks_test_class_olc.subject_type='Person') OR "
            "(cs_tasks_test_class_olc.subject_type='Common Role')))"
            "\n         WHERE ((cs_tasks_test_class_olc.status=0) AND "
            "(cdbwf_role_cache.personalnummer="
            "angestellterX.personalnummer)) AND "
            "angestellterX.cdb_classname='angestellter'"
        )
        self.assertEqual(
            taskmanager.TaskHeaders._getViewStatement("X", task_class), expected
        )

    def test_GetHeaders(self):
        condition = (
            "cdb_object_id IN ("
            "'337706ca-9ee5-11ec-a336-334b6053520d', "
            "'bf529417-9ee6-11ec-93ed-334b6053520d', "
            "'c3c9572b-9ee6-11ec-af67-334b6053520d')"
        )
        self.maxDiff = None
        self.assertEqual(
            taskmanager.TaskHeaders.GetHeaders(["caddok"], condition),
            {
                "bf529417-9ee6-11ec-93ed-334b6053520d": "Test Task (Custom Status Op)",
                "337706ca-9ee5-11ec-a336-334b6053520d": "Test Tasks (OLC)",
            },
        )


if __name__ == "__main__":
    unittest.main()
