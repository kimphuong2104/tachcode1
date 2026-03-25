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

from cs.pcs.projects import tasks_plugin
from cs.pcs.projects.tasks import Task


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TaskWithCsTasks(unittest.TestCase):
    def test_getCsTasksContexts(self):
        "resolves task context"
        task = mock.MagicMock(spec=Task)
        self.assertEqual(
            tasks_plugin.TaskWithCsTasks.getCsTasksContexts(task), [task.Project]
        )

    def test_csTasksDelegate_get_default(self):
        "returns project manager"
        task = mock.MagicMock(spec=Task)
        self.assertEqual(
            tasks_plugin.TaskWithCsTasks.csTasksDelegate_get_default(task),
            task.csTasksDelegate_get_project_manager.return_value,
        )

    @mock.patch.object(tasks_plugin, "assert_single_project", autospec=True)
    @mock.patch.object(tasks_plugin, "assert_team_member", autospec=True)
    def test_csTasksDelegate(self, assert_team_member, assert_single_project):
        "supports delegating multiple tasks of a single project"
        task = mock.MagicMock(spec=Task)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks_plugin.TaskWithCsTasks.csTasksDelegate(task, ctx),
        )
        assert_single_project.assert_called_once_with(ctx)
        assert_team_member.assert_called_once_with(ctx, task.cdb_project_id)
        task.Super.assert_called_once_with(tasks_plugin.TaskWithCsTasks)
        task.Super.return_value.csTasksDelegate.assert_called_once_with(ctx)

    @mock.patch.object(
        tasks_plugin,
        "assert_single_project",
        autospec=True,
        return_value=["prj_id", "bid"],
    )
    def test_preset_csTasksDelegate(self, assert_single_project):
        "presets project when delegating multiple tasks of a single project"
        task = mock.MagicMock(spec=Task)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks_plugin.TaskWithCsTasks.preset_csTasksDelegate(task, ctx),
        )
        assert_single_project.assert_called_once_with(ctx)
        ctx.set.assert_has_calls(
            [
                mock.call("cdb_project_id", "prj_id"),
                mock.call("ce_baseline_id", "bid"),
            ]
        )
        task.Super.assert_called_once_with(tasks_plugin.TaskWithCsTasks)
        task.Super.return_value.preset_csTasksDelegate.assert_called_once_with(ctx)


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_assert_single_project_fail(self, CDBMsg):
        "fails for tasks of multiple projects"
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo", "ce_baseline_id": "foo_bl"},
                {"cdb_project_id": "bar", "ce_baseline_id": "bar_bl"},
            ]
        )
        with self.assertRaises(tasks_plugin.ue.Exception):
            tasks_plugin.assert_single_project(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_delegate")
        CDBMsg.return_value.addReplacement.assert_not_called()

    def test_assert_single_project(self):
        "returns project ID for multiple tasks of a single project"
        ctx = mock.MagicMock(
            objects=[
                {"cdb_project_id": "foo", "ce_baseline_id": "foo_bl"},
                {"cdb_project_id": "foo", "ce_baseline_id": "foo_bl"},
            ]
        )
        self.assertEqual(tasks_plugin.assert_single_project(ctx), ("foo", "foo_bl"))


if __name__ == "__main__":
    unittest.main()
