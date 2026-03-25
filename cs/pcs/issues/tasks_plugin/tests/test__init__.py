#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.issues import Issue, tasks_plugin


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class IssueWithCsTasks(unittest.TestCase):
    def test_getCsTasksContexts(self):
        "resolves issue context"
        iss = mock.MagicMock(spec=Issue)
        self.assertEqual(
            tasks_plugin.IssueWithCsTasks.getCsTasksContexts(iss), [iss.Project]
        )

    def test_csTasksDelegate_get_default(self):
        "returns project manager"
        iss = mock.MagicMock(spec=Issue)
        self.assertEqual(
            tasks_plugin.IssueWithCsTasks.csTasksDelegate_get_default(iss),
            iss.csTasksDelegate_get_project_manager.return_value,
        )

    @mock.patch.object(tasks_plugin, "assert_team_member", autospec=True)
    def test_csTasksDelegate(self, assert_team_member):
        "supports delegating multiple tasks of a single project"
        iss = mock.MagicMock(spec=Issue)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks_plugin.IssueWithCsTasks.csTasksDelegate(iss, ctx),
        )
        assert_team_member.assert_called_once_with(ctx, iss.cdb_project_id)
        iss.Super.assert_called_once_with(tasks_plugin.IssueWithCsTasks)
        iss.Super.return_value.csTasksDelegate.assert_called_once_with(ctx)

    def test_preset_csTasksDelegate(self):
        "presets project when delegating multiple tasks of a single project"
        iss = mock.MagicMock(spec=Issue)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "foo"},
            ]
        )
        self.assertIsNone(
            tasks_plugin.IssueWithCsTasks.preset_csTasksDelegate(iss, ctx),
        )
        ctx.set.assert_called_once_with(
            "cdb_project_id",
            "foo",
        )
        iss.Super.assert_called_once_with(tasks_plugin.IssueWithCsTasks)
        iss.Super.return_value.preset_csTasksDelegate.assert_called_once_with(ctx)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_preset_csTasksDelegate_error(self, CDBMsg):
        "fails if ctx.objects contain multiple project IDs"
        iss = mock.MagicMock(spec=Issue)
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo"},
                {"cdb_project_id": "bar"},
            ]
        )
        with self.assertRaises(tasks_plugin.ue.Exception):
            tasks_plugin.IssueWithCsTasks.preset_csTasksDelegate(
                iss,
                ctx,
            )
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_delegate")
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)

    def test_getCsTasksBasePriority_medium(self):
        iss = mock.MagicMock(spec=Issue, priority="hoch")
        self.assertEqual(
            tasks_plugin.IssueWithCsTasks.getCsTasksBasePriority(iss),
            iss.PRIO_MEDIUM,
        )

    def test_getCsTasksBasePriority_high(self):
        iss = mock.MagicMock(spec=Issue, priority="kritisch")
        self.assertEqual(
            tasks_plugin.IssueWithCsTasks.getCsTasksBasePriority(iss),
            iss.PRIO_HIGH,
        )

    def test_getCsTasksBasePriority_low(self):
        iss = mock.MagicMock(spec=Issue, priority="whatever")
        self.assertEqual(
            tasks_plugin.IssueWithCsTasks.getCsTasksBasePriority(iss),
            iss.PRIO_LOW,
        )


if __name__ == "__main__":
    unittest.main()
