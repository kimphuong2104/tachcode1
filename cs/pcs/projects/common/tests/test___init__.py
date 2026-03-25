#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,abstract-method

__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase
from cdb.objects.org import User

from cs.pcs.projects import Project, common


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test_partition_negative(self):
        with self.assertRaises(ValueError):
            next(common.partition("ABCDE", -1))

    def test_partition_zero(self):
        with self.assertRaises(ValueError):
            next(common.partition("ABCDE", 0))

    def test_partition(self):
        self.assertEqual(
            list(common.partition("ABCDE", 2)),
            ["AB", "CD", "E"],
        )

    def test_partition_large(self):
        self.assertEqual(
            list(common.partition("ABCDE", 10)),
            ["ABCDE"],
        )

    def test_format_in_condition_no_values(self):
        "valid but impossible condition"
        self.assertEqual(
            common.format_in_condition("foo", [], 3),
            "1=0",
        )

    def test_format_in_condition(self):
        "limits expressions in a single IN-clause"
        self.assertEqual(
            common.format_in_condition("foo", range(7), 3),
            "foo IN (0,1,2) OR foo IN (3,4,5) OR foo IN (6)",
        )

    @mock.patch.object(common.sqlapi, "RecordSet2", return_value="Something")
    def test_is_valid_resp(self, RecordSet2):
        "returns true, if entry can be found"
        self.assertTrue(common.is_valid_resp("foo", "bar", "baz"))
        RecordSet2.assert_called_once_with(
            "cdbpcs_resp_brows",
            "cdb_project_id = 'foo' "
            "AND subject_id = 'bar' "
            "AND subject_type = 'baz'",
        )

    @mock.patch.object(common.sqlapi, "RecordSet2", return_value="")
    def test_is_valid_resp_false(self, RecordSet2):
        "returns false, if no entry can be found"
        self.assertFalse(common.is_valid_resp("foo", "bar", "baz"))
        RecordSet2.assert_called_once_with(
            "cdbpcs_resp_brows",
            "cdb_project_id = 'foo' "
            "AND subject_id = 'bar' "
            "AND subject_type = 'baz'",
        )

    @mock.patch.object(common, "is_valid_resp", return_value=True)
    def test_assert_team_member(self, is_valid_resp):
        "simply returns, when user is part of team"
        mock_ctx = mock.MagicMock(
            dialog=mock.MagicMock(subject_id="foo_sid", subject_type="foo_st")
        )
        self.assertIsNone(common.assert_team_member(mock_ctx, "foo_pid"))
        is_valid_resp.assert_called_once_with("foo_pid", "foo_sid", "foo_st")

    @mock.patch.object(common, "is_valid_resp", return_value=False)
    def test_assert_team_member_error(self, is_valid_resp):
        "raises Error, when user is not part of team"
        mock_ctx = mock.MagicMock(
            dialog=mock.MagicMock(subject_id="foo_sid", subject_type="foo_st")
        )
        with self.assertRaises(common.ue.Exception):
            common.assert_team_member(mock_ctx, "foo_pid")
        is_valid_resp.assert_called_once_with("foo_pid", "foo_sid", "foo_st")

    @mock.patch.object(common, "is_valid_resp", return_value=True)
    def test_assert_valid_project_resp(self, is_valid_resp):
        "simply returns, if user is member of team"
        mock_ctx = mock.MagicMock(
            dialog=mock.MagicMock(
                cdb_project_id="foo_pid", subject_id="foo_sid", subject_type="foo_st"
            )
        )
        self.assertIsNone(common.assert_valid_project_resp(mock_ctx))

    @mock.patch.object(common, "is_valid_resp", return_value=False)
    def test_assert_valid_project_resp_no_resp(self, is_valid_resp):
        "simply retuns, if no user is given"
        mock_ctx = mock.MagicMock(
            dialog=mock.MagicMock(
                cdb_project_id="foo_pid",
                # no user/responsible given
                subject_id="",
                subject_type="",
            )
        )
        self.assertIsNone(common.assert_valid_project_resp(mock_ctx))

    @mock.patch.object(common, "is_valid_resp", return_value=False)
    def test_assert_valid_project_resp_error(self, is_valid_resp):
        "raises error, if user is not member of team"
        mock_ctx = mock.MagicMock(
            dialog=mock.MagicMock(
                cdb_project_id="foo_pid", subject_id="foo_sid", subject_type="foo_st"
            )
        )
        with self.assertRaises(common.ue.Exception):
            common.assert_valid_project_resp(mock_ctx)


@pytest.mark.integration
class UtilityIntegration(testcase.RollbackTestCase):
    def test_format_in_condition(self):
        base_condition = condition = "cdb_project_id='Ptest.msp.small'"
        all_tasks = common.sqlapi.RecordSet2("cdbpcs_task", base_condition)
        task_ids = [x.task_id for x in all_tasks]

        condition = f"{base_condition} AND ({common.format_in_condition('task_id', task_ids, 3)})"
        rset = common.sqlapi.RecordSet2("cdbpcs_task", condition)
        self.assertEqual(
            {x.task_id for x in rset},
            set(task_ids),
        )


@pytest.mark.integration
class TaskPluginIntegration(testcase.RollbackTestCase):

    ctx = mock.MagicMock()
    ctx.dialog.subject_id = "AB"
    ctx.dialog.subject_type = "Person"
    cdb_project_id = "A"

    def test_assert_team_member_error(self):
        "raise error, if user is not member of team"
        project = Project.Create(cdb_project_id=self.cdb_project_id, ce_baseline_id="")
        user = User.Create(personalnummer="ABB")
        project.createRole("AC").assignSubject(user)

        with self.assertRaises(common.ue.Exception):
            common.assert_team_member(self.ctx, self.cdb_project_id)

    def test_assert_team_member_success(self):
        "simply returns, if user is member of team"
        project = Project.Create(cdb_project_id=self.cdb_project_id, ce_baseline_id="")
        user = User.Create(personalnummer="AB")
        project.createRole("AC").assignSubject(user)

        self.assertIsNone(common.assert_team_member(self.ctx, self.cdb_project_id))

    def test_assert_team_member_no_user(self):
        "raises error, if no user is given to be checked for team membership"
        Project.Create(cdb_project_id=self.cdb_project_id, ce_baseline_id="")

        # remove subject_id and subject_type from to have no user/responsible
        self.ctx.dialog.subject_id = ""
        self.ctx.dialog.subject_type = ""

        with self.assertRaises(common.ue.Exception):
            common.assert_team_member(self.ctx, self.cdb_project_id)

        # reset ctx after test
        self.ctx.dialog.subject_id = "AB"
        self.ctx.dialog.subject_type = "Person"


if __name__ == "__main__":
    unittest.main()
