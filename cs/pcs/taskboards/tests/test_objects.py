#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import sqlapi, testcase

from cs.pcs.taskboards import objects


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.unit
class TestObjects(unittest.TestCase):
    def test_get_valid_board_object_ids_eval_rule_for_projects(self):
        "Evaluate rule for projects: 'cdbpcs: Valid Projects for Taskboards'"

        char = "''"
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            char = "chr(1)"
        rule = mock.MagicMock(autospec=objects.Rule)
        with mock.patch.object(rule, "stmt", return_value="statement_*_statement"):
            root = mock.MagicMock()
            root.alias = "table_alias"
            with mock.patch.object(rule, "_GetNode", return_value=root):
                with mock.patch.object(objects.Rule, "ByKeys", return_value=rule):
                    result = objects.get_valid_board_object_ids(
                        objects.Project, objects.PERS_TEAM_BOARD_RULE
                    )
                    expected = "statement_taskboard_oid_statement"
                    objects.Rule.ByKeys.assert_called_once_with(
                        name=objects.PERS_TEAM_BOARD_RULE
                    )
                    rule.stmt.assert_called_once_with(
                        objects.Project,
                        add_expr=(
                            f"table_alias.taskboard_oid != {char} AND "
                            "table_alias.taskboard_oid IS NOT NULL"
                        ),
                    )
                    self.assertEqual(
                        result,
                        expected,
                        "The given rule returns an unexpected statement.",
                    )

    def test_get_valid_board_object_ids_eval_rule_for_tasks(self):
        "Evaluate rule for tasks: 'cdbpcs: Valid Projects for Taskboards'"

        char = "''"
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            char = "chr(1)"
        rule = mock.MagicMock(autospec=objects.Rule)
        with mock.patch.object(rule, "stmt", return_value="statement_*_statement"):
            root = mock.MagicMock()
            root.alias = "table_alias"
            with mock.patch.object(rule, "_GetNode", return_value=root):
                with mock.patch.object(objects.Rule, "ByKeys", return_value=rule):
                    result = objects.get_valid_board_object_ids(
                        objects.Task, objects.PERS_TEAM_BOARD_RULE
                    )
                    expected = "statement_taskboard_oid_statement"
                    objects.Rule.ByKeys.assert_called_once_with(
                        name=objects.PERS_TEAM_BOARD_RULE
                    )
                    rule.stmt.assert_called_once_with(
                        objects.Task,
                        add_expr=(
                            f"table_alias.taskboard_oid != {char} AND "
                            "table_alias.taskboard_oid IS NOT NULL"
                        ),
                    )
                    self.assertEqual(result, expected)

    @mock.patch.object(objects, "auth", persno="my_test_user")
    @mock.patch.object(objects.TeamMember, "GetTableName", return_value="team_table")
    @mock.patch.object(objects.Project, "GetTableName", return_value="project_table")
    def test_get_board_condition_of_project(self, P_GetTableName, T_GetTableName, auth):
        """Get SQL statement searching for all board ids form boards,
        that are assigned to projects, where active user is part of the team."""

        char = "''"
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            char = "chr(1)"
        result = objects._get_board_condition(objects.Project)
        expected = (
            "SELECT a.taskboard_oid FROM project_table a, team_table t "
            "WHERE a.cdb_project_id = t.cdb_project_id "
            f"AND a.taskboard_oid IS NOT NULL AND a.taskboard_oid != {char} "
            "AND t.cdb_person_id = 'my_test_user'"
        )
        P_GetTableName.assert_called_once()
        T_GetTableName.assert_called_once()
        self.assertEqual(result, expected)

    @mock.patch.object(objects, "get_valid_board_object_ids", return_value="ids")
    @mock.patch.object(objects, "_get_board_condition", return_value="condition")
    def test_get_project_board_condition(self, board_condition, valid_board_ids):
        "Create SQL condition to get all project boards."
        result = objects.get_project_board_condition()
        expected = (
            "((cdb_object_id IN (condition) AND cdb_object_id IN (ids)) "
            "OR (cdb_object_id IN (condition) AND cdb_object_id IN (ids)))"
        )
        board_condition_calls = [mock.call(objects.Project), mock.call(objects.Task)]
        calls = [
            mock.call(objects.Project, objects.PROJECT_BOARD_RULE),
            mock.call(objects.Task, objects.PROJECT_BOARD_RULE),
        ]
        board_condition.assert_has_calls(board_condition_calls, any_order=False)
        valid_board_ids.assert_has_calls(calls, any_order=False)
        self.assertEqual(result, expected)
