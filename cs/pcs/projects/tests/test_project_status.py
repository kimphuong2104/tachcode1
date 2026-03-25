#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


import unittest

import pytest
from cdb import testcase
from cdb.objects.references import ObjectCollection
from mock import MagicMock, Mock, PropertyMock, call, patch

from cs.pcs.projects import project_status, tasks_status

STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


@pytest.mark.unit
class ProjectStatus(testcase.RollbackTestCase):
    @patch.object(
        project_status.sqlapi, "RecordSet2", return_value=[{"statusnummer": 1}]
    )
    def test_get_target_status_no_translated(self, RecordSet2):
        "get number of translated OLC status"
        self.assertEqual(project_status.get_target_status_no("OLC", "one"), 1)
        RecordSet2.assert_called_once_with(
            "objektstati", "objektart = 'OLC' AND statusbez_de = 'one'"
        )

    @patch.object(
        project_status.sqlapi, "RecordSet2", side_effect=([], [{"statusnummer": 2}])
    )
    def test_get_target_status_no_untranslated(self, RecordSet2):
        "get number of untranslated OLC status"
        self.assertEqual(project_status.get_target_status_no("OLC", "two"), 2)
        RecordSet2.assert_has_calls(
            [
                call("objektstati", "objektart = 'OLC' AND statusbez_de = 'two'"),
                call("objektstati", "objektart = 'OLC' AND statusbezeich = 'two'"),
            ]
        )

    @patch.object(project_status.sqlapi, "RecordSet2", return_value=[])
    def test_get_target_status_not_existing(self, RecordSet2):
        "cannot get number of non-existing OLC status"
        with self.assertRaises(ValueError):
            project_status.get_target_status_no("OLC", "three")

    @patch.object(project_status.transactions, "Transaction", autospec=True)
    def test_setFrozen_ctx_error(self, Transaction):
        "does nothing if ctx.error is truthy"
        project = MagicMock(spec=project_status.Project)
        ctx = MagicMock(error=True)
        self.assertIsNone(project_status.Project.setFrozen(project, ctx))
        project.Checklists.Update.assert_not_called()
        project.ChecklistItems.Update.assert_not_called()
        project.Issues.Update.assert_not_called()
        project.Tasks.Update.assert_not_called()
        Transaction.assert_not_called()

    @patch.object(project_status.transactions, "Transaction", autospec=True)
    def test_setFrozen_0(self, Transaction):
        "!FROZEN sets cdbpcs_frozen flag to 0"
        project = MagicMock(spec=project_status.Project, status="other")
        project.FROZEN.status = 60
        ctx = MagicMock(error=None)
        self.assertIsNone(project_status.Project.setFrozen(project, ctx))
        project.Checklists.Update.assert_called_once_with(cdbpcs_frozen=0)
        project.ChecklistItems.Update.assert_called_once_with(cdbpcs_frozen=0)
        project.Issues.Update.assert_called_once_with(cdbpcs_frozen=0)
        project.Tasks.Update.assert_called_once_with(cdbpcs_frozen=0)
        Transaction.assert_called_once_with()

    @patch.object(project_status.transactions, "Transaction", autospec=True)
    def test_setFrozen_1(self, Transaction):
        "FROZEN sets cdbpcs_frozen flag to 1"
        project = MagicMock(spec=project_status.Project, status=60)
        project.FROZEN.status = 60
        ctx = MagicMock(error=None)
        self.assertIsNone(project_status.Project.setFrozen(project, ctx))
        project.Checklists.Update.assert_called_once_with(cdbpcs_frozen=1)
        project.ChecklistItems.Update.assert_called_once_with(cdbpcs_frozen=1)
        project.Issues.Update.assert_called_once_with(cdbpcs_frozen=1)
        project.Tasks.Update.assert_called_once_with(cdbpcs_frozen=1)
        Transaction.assert_called_once_with()

    @patch("cs.pcs.checklists.Checklist", autospec=True)
    def test_NEW(self, Checklist):
        "project -> NEW also resets non-discarded checklists"
        checklist_a = MagicMock(status="not discarded")
        checklist_b = MagicMock(status=Checklist.DISCARDED.status)
        project = MagicMock(spec=project_status.Project)
        project.TopLevelChecklists = [checklist_a, checklist_b]
        status = project_status.Project.NEW()
        self.assertEqual(
            status.FollowUpStateChanges(project), [(Checklist.NEW, [checklist_a], 0, 0)]
        )

    def test_EXECUTION_Constraints(self):
        "EXECUTION only if its parent is in EXECUTION"
        project = MagicMock(spec=project_status.Project)
        status = project_status.Project.EXECUTION()
        self.assertEqual(
            status.Constraints(project),
            [
                (
                    "MatchStateList",
                    [
                        [project.ParentProject],
                        [project.EXECUTION],
                        "pcs_proj_wf_rej_0",
                    ],
                )
            ],
        )

    def test_FROZEN_Constraints(self):
        "FROZEN only if subprojects are FROZEN, DISCARDED or COMPLETED"
        project = MagicMock(spec=project_status.Project)
        status = project_status.Project.FROZEN()
        self.assertEqual(
            status.Constraints(project),
            [
                (
                    "MatchStateList",
                    [
                        project.Subprojects,
                        [project.FROZEN, project.DISCARDED, project.COMPLETED],
                        "pcs_proj_wf_rej_1",
                    ],
                )
            ],
        )

    @patch("cs.pcs.checklists.Checklist", autospec=True)
    @patch("cs.pcs.issues.Issue", autospec=True)
    @patch("cs.pcs.projects.tasks.Task", autospec=True)
    def test_COMPLETED_FollowUpStateChanges(self, Task, Issue, Checklist):
        "COMPLETED also changes tasks, issues and checklists"
        project = MagicMock(spec=project_status.Project)
        status = project_status.Project.COMPLETED()

        def getEndStatus(arg):
            return ["end"]

        Issue.endStatus.side_effect = getEndStatus
        Checklist.endStatus.side_effect = getEndStatus
        project.TopTasks = [
            MagicMock(status="whatever"),
            MagicMock(status="end"),
            MagicMock(status=Task.FINISHED.status),
        ]
        project.Issues = [
            MagicMock(task_id="foo"),
            MagicMock(task_id=None, status="not end"),
            MagicMock(task_id=None, status="end"),
        ]
        project.TopLevelChecklists = [
            MagicMock(status="not end"),
            MagicMock(status="end"),
        ]
        self.assertEqual(
            status.FollowUpStateChanges(project),
            [
                (Task.COMPLETED, [project.TopTasks[2]], 0, 0),
                (Issue.COMPLETED, [project.Issues[1]], 0, 0),
                (Checklist.DISCARDED, [project.TopLevelChecklists[0]], 0, 0),
            ],
        )
        Issue.endStatus.assert_has_calls(2 * [call(False)])
        Checklist.endStatus.assert_has_calls(2 * [call(False)])
        self.assertEqual(Issue.endStatus.call_count, 2)
        self.assertEqual(Checklist.endStatus.call_count, 2)

    @patch("cs.pcs.checklists.Checklist", autospec=True)
    @patch("cs.pcs.issues.Issue", autospec=True)
    def test_DISCARDED_FollowUpStateChanges(self, Issue, Checklist):
        "DISCARDED also changes issues and checklists"
        project = MagicMock(spec=project_status.Project)
        status = project_status.Project.DISCARDED()

        def getEndStatus(arg):
            return ["end"]

        Issue.endStatus.side_effect = getEndStatus
        Checklist.endStatus.side_effect = getEndStatus
        project.Issues = [
            MagicMock(task_id="foo"),
            MagicMock(task_id=None, status="not end"),
            MagicMock(task_id=None, status="end"),
        ]
        project.TopLevelChecklists = [
            MagicMock(status="not end"),
            MagicMock(status="end"),
        ]
        self.assertEqual(
            status.FollowUpStateChanges(project),
            [
                (Issue.DISCARDED, [project.Issues[1]], 0, 0),
                (Checklist.DISCARDED, [project.TopLevelChecklists[0]], 0, 0),
            ],
        )
        Issue.endStatus.assert_has_calls(2 * [call(False)])
        Checklist.endStatus.assert_has_calls(2 * [call(False)])
        self.assertEqual(Issue.endStatus.call_count, 2)
        self.assertEqual(Checklist.endStatus.call_count, 2)

    def test_COMPLETED_post(self):
        "COMPLETED also changes unfinished tasks"
        from cs.pcs.projects import Project
        from cs.pcs.projects.tasks import Task

        project = Project.Create(
            cdb_project_id="P1",
            ce_baseline_id="",
            calendar_profile_id=STANDARD_PROFILE,
        )
        status = project_status.Project.COMPLETED()
        task1 = Task.Create(
            cdb_project_id="P1",
            task_id="T0",
            ce_baseline_id="",
            cdb_objektart="cdbpcs_task",
            parent_task="",
            status=Task.FINISHED.status,
        )
        task2 = Task.Create(
            cdb_project_id="P1",
            task_id="T1",
            ce_baseline_id="",
            cdb_objektart="cdbpcs_task",
            parent_task="",
            status=Task.NEW.status,
        )
        task3 = Task.Create(
            cdb_project_id="P1",
            task_id="T2",
            ce_baseline_id="",
            cdb_objektart="cdbpcs_task",
            parent_task="",
            status=Task.EXECUTION.status,
        )
        self.assertIsNone(status.pre(project, None))
        self.assertEqual(task1.status, Task.FINISHED.status)
        self.assertEqual(task2.status, Task.DISCARDED.status)
        self.assertEqual(task3.status, Task.DISCARDED.status)

    @patch("cs.pcs.projects.tasks.Task", autospec=True)
    def test_TO_NEW_FollowUpStateChanges_from_discarded(self, Task):
        "Project DISCARDED -> NEW also resets non-completed tasks"
        project = MagicMock(spec=project_status.Project)
        task_a = MagicMock(status=Task.DISCARDED.status)
        task_b = MagicMock(status=Task.FINISHED.status)
        task_c = MagicMock(status=Task.COMPLETED.status)
        project.TopTasks = [task_a, task_b, task_c]
        project.DISCARDED = MagicMock()
        transition = project_status.Project.TO_NEW()
        transition.SourceState = MagicMock(
            return_value=MagicMock(status=project.DISCARDED.status),
        )
        self.assertEqual(
            transition.FollowUpStateChanges(project), [(Task.NEW, [task_a], 0, 0)]
        )
        transition.SourceState.assert_called_once_with(project)

    @patch("cs.pcs.projects.tasks.Task", autospec=True)
    def test_TO_NEW_FollowUpStateChanges_from_not_discarded(self, Task):
        "Project !DISCARDED -> NEW also resets non-discarded tasks"
        project = MagicMock(spec=project_status.Project)
        task_a = MagicMock(status=Task.DISCARDED.status)
        task_b = MagicMock(status=Task.FINISHED.status)
        task_c = MagicMock(status=Task.COMPLETED.status)
        project.TopTasks = [task_a, task_b, task_c]
        project.DISCARDED = MagicMock()
        transition = project_status.Project.TO_NEW()
        transition.SourceState = MagicMock(
            return_value=MagicMock(status="not discarded"),
        )
        self.assertEqual(
            transition.FollowUpStateChanges(project),
            [(Task.NEW, [task_b, task_c], 0, 0)],
        )
        transition.SourceState.assert_called_once_with(project)

    @staticmethod
    def get_tasks():
        return ObjectCollection(tasks_status.Task, "cdbpcs_task", "status=0")

    def test__do_status_change_adjustments(self):
        "Do adjustments after status change"
        mock_class = Mock()
        mock_class.mock_method.return_value = None
        tasks = self.get_tasks()
        with patch.object(tasks, "KeywordQuery", return_value=tasks):
            with patch.object(
                project_status.Project,
                "Tasks",
                new_callable=PropertyMock,
                return_value=tasks,
            ):
                project = project_status.Project()

                # calling method
                project._do_status_change_adjustments(
                    ["foo"], {mock_class.mock_method: {"bar": "bass"}}
                )

                # checking calls
                tasks.KeywordQuery.assert_called_once_with(
                    cdb_object_id=["foo"], bar="bass"
                )
                mock_class.mock_method.assert_called_once_with(tasks)

    @patch.object(project_status.Project, "adjust_role_assignments")
    @patch.object(project_status.tasks_efforts, "aggregate_changes")
    def test__do_aggregation_adjustments_01(
        self, aggregate_changes, adjust_role_assignments
    ):
        "Do consistency calculations: project with top task and sub task"
        # create parent and sub task
        parent_task = tasks_status.Task()
        parent_task.task_id = "foo"
        parent_task.parent_task = ""
        sub_task = tasks_status.Task()
        sub_task.task_id = "bar"
        sub_task.parent_task = "foo"
        tasks = [sub_task, parent_task]

        with patch.object(
            project_status.Project,
            "Tasks",
            new_callable=PropertyMock,
            return_value=tasks,
        ):
            project = project_status.Project(cdb_project_id=1)
            project.is_group = 1
            # calling method
            project._do_aggregation_adjustments()

        # check method calls
        aggregate_changes.assert_called_once_with(project)
        adjust_role_assignments.assert_called_once_with()

    @patch.object(project_status.Project, "adjust_role_assignments")
    @patch.object(project_status.tasks_efforts, "aggregate_changes")
    def test__do_aggregation_adjustments_02(
        self, aggregate_changes, adjust_role_assignments
    ):
        "Do consistency calculations: project without tasks"

        with patch.object(
            project_status.Project, "Tasks", new_callable=PropertyMock, return_value=[]
        ):
            project = project_status.Project(cdb_project_id=1)
            project.is_group = 0
            # calling method
            project._do_aggregation_adjustments()

        # check method calls
        aggregate_changes.assert_called_once_with(project)
        adjust_role_assignments.assert_called_once_with()

    @patch.object(project_status.Project, "_do_aggregation_adjustments")
    @patch.object(project_status.Project, "recalculate")
    @patch.object(project_status.Project, "_do_status_change_adjustments")
    def test_do_status_updates(self, status_change, recalculate, aggregation):
        "Do adjustments and consistency calculations after status change"
        project = project_status.Project()
        # calling method
        project.ce_baseline_id = ""
        project.do_status_updates({"foo": (0, 180)})

        # checking calls
        status_change.assert_called_once_with(
            ["foo"], tasks_status.STATUS_CHANGE_ADJUSTMENTS
        )
        recalculate.assert_called_once_with()
        aggregation.assert_called_once_with()

    @patch.object(project_status.Project, "_do_aggregation_adjustments")
    @patch.object(project_status.Project, "recalculate")
    @patch.object(project_status.Project, "_do_status_change_adjustments")
    def test_do_status_updates(self, status_change, recalculate, aggregation):
        "Do adjustments and consistency calculations after status change"
        project = project_status.Project(calendar_profile_id=STANDARD_PROFILE)
        # calling method
        project.ce_baseline_id = ""
        project.do_status_updates({"foo": (0, 20)})

        # checking calls
        status_change.assert_called_once_with(
            ["foo"], tasks_status.STATUS_CHANGE_ADJUSTMENTS
        )
        recalculate.assert_not_called()
        aggregation.assert_called_once_with()

    @patch.object(project_status.Project, "recalculate")
    @patch.object(project_status.Project, "_do_status_change_adjustments")
    def test_do_status_updates_with_nonactive_baseline(
        self, status_change, recalculate
    ):
        "Do adjustments and consistency calculations after status change"
        project = project_status.Project()
        # calling method
        project.ce_baseline_id = "1"
        with self.assertRaises(Exception):
            project.do_status_updates({"foo": (0, 20)})

        # checking calls
        recalculate.assert_not_called()
        status_change.assert_not_called()

    @patch.object(project_status.Project, "has_ended", return_value=False)
    def test_accept_new_task_1(self, *args):
        "Project.accept_new_task: project has not ended"
        project = project_status.Project()
        project.accept_new_task()
        project.has_ended.assert_called_once_with()

    @patch.object(project_status.Project, "has_ended", return_value=True)
    def test_accept_new_task_2(self, *args):
        "Project.accept_new_task: project has ended"
        project = project_status.Project()
        project.project_name = "foo"
        with self.assertRaises(project_status.ue.Exception) as e:
            project.accept_new_task()
        msg = project_status.ue.Exception("pcs_err_new_task1", "foo")
        self.assertEqual(str(e.exception), msg.msg.getText("", True))
        project.has_ended.assert_called_once_with()

    @patch.object(project_status.Project, "endStatus", return_value=[200])
    def test_has_ended_1(self, end_status):
        "Project.has_ended: project has not ended"
        project = project_status.Project()
        project.status = 50
        self.assertFalse(project.has_ended())
        end_status.assert_called_once_with(False)

    @patch.object(project_status.Project, "endStatus", return_value=[200])
    def test_has_ended_2(self, end_status):
        "Project.has_ended: project has ended"
        project = project_status.Project()
        project.status = 200
        self.assertTrue(project.has_ended())
        end_status.assert_called_once_with(False)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
