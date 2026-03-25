#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter

import unittest

import pytest
from cdb import testcase
from mock import MagicMock, Mock, call, patch

from cs.pcs.checklists import Checklist
from cs.pcs.issues import Issue
from cs.pcs.projects import tasks_status
from cs.pcs.projects.project_status import Project


@pytest.mark.unit
class TaskStatus(testcase.RollbackTestCase):
    def _no_other_predecessors(self, pred_status, succ_status, calls):
        pred = tasks_status.Task()
        pred.status = pred_status
        successor = MagicMock(
            spec=tasks_status.Task,
        )
        successor.getPredecessors.return_value = [pred]
        successor.status = succ_status
        # call
        result = tasks_status.no_other_predecessors(successor)
        # check
        successor.getPredecessors.assert_has_calls(calls)
        return result

    def test_no_other_predecessors(self):
        result = self._no_other_predecessors(50, 20, [])
        self.assertEqual(result, None)
        result = self._no_other_predecessors(0, 0, [call("AA"), call("EA")])
        self.assertEqual(result, False)
        result = self._no_other_predecessors(20, 0, [call("AA"), call("EA")])
        self.assertEqual(result, False)
        result = self._no_other_predecessors(50, 0, [call("AA"), call("EA")])
        self.assertEqual(result, False)
        result = self._no_other_predecessors(180, 0, [call("AA"), call("EA")])
        self.assertEqual(result, True)
        result = self._no_other_predecessors(200, 0, [call("AA"), call("EA")])
        self.assertEqual(result, True)
        result = self._no_other_predecessors(250, 0, [call("AA"), call("EA")])
        self.assertEqual(result, True)

    @patch.object(tasks_status.util, "ErrorMessage", return_value="foo")
    def test_on_cdbpcs_cancel_task_pre_mask(self, _):
        task = MagicMock(
            spec=tasks_status.Task,
            has_ended=Mock(return_value=False),
        )
        ctx = MagicMock()
        self.assertIsNone(tasks_status.Task.on_cdbpcs_cancel_task_pre_mask(task, ctx))
        ctx.set.assert_called_once_with("operation_description", "foo")

    def test_on_cdbpcs_cancel_task_pre_mask_noop(self):
        task = MagicMock(
            spec=tasks_status.Task,
            has_ended=Mock(return_value=True),
        )
        with self.assertRaises(tasks_status.util.ErrorMessage) as error:
            tasks_status.Task.on_cdbpcs_cancel_task_pre_mask(task, None)

        self.assertEqual(
            str(error.exception),
            "Die Aufgabe ist bereits fertig/abgeschlossen/verworfen.",
        )

    def test_on_cdbpcs_cancel_task_now_noop(self):
        task = MagicMock(
            spec=tasks_status.Task,
            has_ended=Mock(return_value=True),
        )
        with self.assertRaises(tasks_status.util.ErrorMessage) as error:
            tasks_status.Task.on_cdbpcs_cancel_task_now(task, None)

        self.assertEqual(
            str(error.exception),
            "Die Aufgabe ist bereits fertig/abgeschlossen/verworfen.",
        )

    @patch.object(tasks_status, "operation")
    def test_on_cdbpcs_cancel_task_now(self, operation):
        sub_ended = MagicMock(
            spec=tasks_status.Task,
            is_group=False,
            has_ended=Mock(return_value=True),
        )
        sub_not_ended = MagicMock(
            spec=tasks_status.Task,
            is_group=False,
            has_ended=Mock(return_value=False),
        )
        subgroup_ended = MagicMock(
            spec=tasks_status.Task,
            is_group=True,
            has_ended=Mock(return_value=True),
        )
        subgroup_not_ended = MagicMock(
            spec=tasks_status.Task,
            is_group=True,
            has_ended=Mock(return_value=False),
        )
        task = MagicMock(
            spec=tasks_status.Task,
            OrderedSubTasks=[
                sub_ended,
                sub_not_ended,
                subgroup_ended,
                subgroup_not_ended,
            ],
            has_ended=Mock(return_value=False),
        )
        self.assertIsNone(tasks_status.Task.on_cdbpcs_cancel_task_now(task, None))

        sub_ended.ChangeState.assert_not_called()
        sub_not_ended.ChangeState.assert_called_once_with(task.DISCARDED.status)
        subgroup_ended.ChangeState.assert_not_called()
        subgroup_not_ended.ChangeState.assert_not_called()
        self.assertEqual(operation.call_count, 1)
        operation.assert_has_calls(
            [
                call("cdbpcs_cancel_task", subgroup_not_ended),
            ]
        )
        task.ChangeState.assert_called_once_with(task.FINISHED.status)

    @patch.object(tasks_status, "StateChangeHandler")
    def test_getTaskRelConstraintViolations(self, StateChangeHandler):
        "Task.getTaskRelConstraintViolations"
        task = MagicMock(
            spec=tasks_status.Task,
        )
        task._getTaskRelConstraints.return_value = [
            ("c1", ["one", 1]),
            ("c2", ["two", 2]),
            ("c3", ["three", 3]),
        ]
        StateChangeHandler.c3.return_value = ""

        self.assertEqual(
            tasks_status.Task.getTaskRelConstraintViolations(task, "foo"),
            [
                StateChangeHandler.c1.return_value,
                StateChangeHandler.c2.return_value,
            ],
        )

        task._getTaskRelConstraints.assert_called_once_with(task.status, "foo")
        StateChangeHandler.c1.assert_called_once_with("one", 1)
        StateChangeHandler.c2.assert_called_once_with("two", 2)
        StateChangeHandler.c3.assert_called_once_with("three", 3)

    def test_READY_Constraints(self):
        "Task.READY.Constraints"
        task = MagicMock(spec=tasks_status.Task)
        task.Checklist = MagicMock()
        status = tasks_status.Task.READY()
        status.status = "ready"
        self.assertEqual(
            status.Constraints(task),
            task._getTaskRelConstraints.return_value.__add__.return_value,
        )
        task._getTaskRelConstraints.assert_called_once_with("ready")
        task._getTaskRelConstraints.return_value.__add__.assert_called_once_with(
            [
                (
                    "MatchStateList",
                    [
                        [task.Project],
                        [Project.EXECUTION, Project.FROZEN],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [task.ParentTask],
                        [
                            tasks_status.Task.READY,
                            tasks_status.Task.EXECUTION,
                        ],
                        "pcstask_wf_rej_1",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Subtasks,
                        [
                            tasks_status.Task.NEW,
                            tasks_status.Task.READY,
                            tasks_status.Task.EXECUTION,
                            tasks_status.Task.DISCARDED,
                        ],
                        "pcstask_wf_rej_3",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Checklists,
                        [
                            Checklist.NEW,
                            Checklist.EVALUATION,
                            Checklist.DISCARDED,
                        ],
                        "pcstask_wf_rej_0",
                    ],
                ),
            ]
        )

    def test_EXECUTION_Constraints(self):
        "Task.EXECUTION.Constraints"
        task = MagicMock(spec=tasks_status.Task)
        status = tasks_status.Task.EXECUTION()
        self.assertEqual(
            status.Constraints(task),
            [
                (
                    "MatchStateList",
                    [
                        [task.Project],
                        [task.Project.EXECUTION, task.Project.FROZEN],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [task.ParentTask],
                        [
                            tasks_status.Task.READY,
                            tasks_status.Task.EXECUTION,
                            tasks_status.Task.DISCARDED,
                            tasks_status.Task.FINISHED,
                        ],
                        "pcstask_wf_rej_1",
                    ],
                ),
            ],
        )

    @patch.object(tasks_status.Task.READY, "status")
    @patch.object(tasks_status.Task.NEW, "status")
    def test_EXECUTION_FollowUpStateChanges(self, NEW_status, READY_status):
        "Task.EXECUTION.FollowUpStateChanges"
        task = MagicMock(spec=tasks_status.Task)
        subtask_a = MagicMock(status=NEW_status)
        subtask_b = MagicMock(status=READY_status)
        task.getInitialSubtasks.return_value = [subtask_a, subtask_b]
        task.getSuccessors.return_value = [subtask_a, subtask_b]
        task.ParentTask = "foo"
        status = tasks_status.Task.EXECUTION()
        self.assertEqual(
            status.FollowUpStateChanges(task),
            [
                (tasks_status.Task.EXECUTION, ["foo"], 0, 0),
                (tasks_status.Task.READY, [subtask_a], 0, 0),
                (tasks_status.Task.READY, [subtask_a], 0, 0),
            ],
        )
        task.getInitialSubtasks.assert_called_once_with()
        task.getSuccessors.assert_has_calls([call("AA")])
        self.assertEqual(task.getSuccessors.call_count, 1)

    @patch.object(Issue, "endStatus", return_value=["a"])
    @patch.object(Checklist, "endStatus", return_value=["b"])
    @patch.object(tasks_status.Task, "endStatus", return_value=["c"])
    def test_DISCARDED_FollowUpStateChanges(
        self, taskEndStatus, checklistEndStatus, issueEndStatus
    ):
        "Task.DISCARDED.FollowUpStateChanges"
        task = MagicMock(spec=tasks_status.Task)
        a = MagicMock(status="a")
        b = MagicMock(status="b")
        c = MagicMock(status="c")
        task.OrderedSubTasks = [a, b, c]
        task.Issues = [a, b, c]
        task.Checklists = [a, b, c]
        status = tasks_status.Task.DISCARDED()
        self.assertEqual(
            status.FollowUpStateChanges(task),
            [
                (tasks_status.Task.DISCARDED, [a, b], 0, 0),
                (Issue.DISCARDED, [b, c], 0, 0),
                (Checklist.DISCARDED, [a, c], 0, 0),
                (task.ParentTask.getFinalStatus.return_value, [task.ParentTask], 0, 0),
            ],
        )
        task.ParentTask.getFinalStatus.assert_called_once_with()
        taskEndStatus.assert_has_calls(3 * [call(False)])
        self.assertEqual(taskEndStatus.call_count, 3)
        issueEndStatus.assert_has_calls(3 * [call(False)])
        self.assertEqual(issueEndStatus.call_count, 3)
        checklistEndStatus.assert_has_calls(3 * [call(False)])
        self.assertEqual(checklistEndStatus.call_count, 3)

    @patch.object(tasks_status.sqlapi, "SQLstring", autospec=True)
    @patch.object(tasks_status.sqlapi, "SQLrows", autospec=True)
    @patch.object(tasks_status.sqlapi, "SQLselect", autospec=True)
    @patch("cdb.platform.olc.StateDefinition.ByKeys")
    def _DISCARDED_pre_mask(
        self, ctx, last_status, StateDefByKeys, SQLselect, SQLrows, SQLstring
    ):
        SQLstring.return_value = last_status

        def _get_state_def(statusnummer, objektart):
            return Mock(statusbezeich=f"{objektart}: {statusnummer}")

        StateDefByKeys.side_effect = _get_state_def
        task = MagicMock(
            spec=tasks_status.Task,
            cdb_project_id="foo",
            task_id="bar",
        )
        task.GetObjectKind.return_value = "OLC"
        status = tasks_status.Task.DISCARDED()
        self.assertIsNone(status.pre_mask(task, ctx))
        StateDefByKeys.assert_has_calls(
            [
                call(
                    statusnummer=tasks_status.Task.READY.status,
                    objektart=task.GetObjectKind.return_value,
                ),
                call(
                    statusnummer=tasks_status.Task.NEW.status,
                    objektart=task.GetObjectKind.return_value,
                ),
            ]
        )
        SQLselect.assert_called_once_with(
            "cdbprot_neustat FROM cdbpcs_tsk_prot WHERE "
            "cdb_project_id='foo' AND task_id='bar' AND cdbprot_neustat IN "
            "('OLC: 20', 'OLC: 0') ORDER BY cdbprot_sortable_id"
        )
        SQLrows.assert_called_once_with(SQLselect.return_value)
        SQLstring.assert_called_once_with(
            SQLselect.return_value,
            0,
            SQLrows.return_value - 1,
        )

    def test_DISCARDED_pre_mask_last_status_ready(self):
        "Task.DISCARDED.pre_mask (last protocol entry READY)"
        ctx = MagicMock(spec=["excl_state"])
        self._DISCARDED_pre_mask(ctx, "OLC: 20")
        ctx.excl_state.assert_not_called()

    def test_DISCARDED_pre_mask_last_status_not_ready(self):
        "Task.DISCARDED.pre_mask (last protocol entry not READY)"
        ctx = MagicMock(spec=["excl_state"])
        self._DISCARDED_pre_mask(ctx, "not ready")
        ctx.excl_state.assert_has_calls(
            [
                call(tasks_status.Task.EXECUTION.status),
                call(tasks_status.Task.READY.status),
            ]
        )

    @patch.object(Issue, "endStatus")
    @patch.object(Checklist, "endStatus")
    @patch.object(tasks_status.Task, "endStatus")
    def test_FINISHED_Constraints(
        self, taskEndStatus, checklistEndStatus, issueEndStatus
    ):
        "Task.FINISHED.Constraints"
        task = MagicMock(spec=tasks_status.Task)
        status = tasks_status.Task.FINISHED()
        status.status = "finished"
        self.assertEqual(
            status.Constraints(task),
            task._getTaskRelConstraints.return_value.__add__.return_value,
        )
        task._getTaskRelConstraints.assert_called_once_with("finished")
        task._getTaskRelConstraints.return_value.__add__.assert_called_once_with(
            [
                (
                    "MatchStateList",
                    [
                        [task.Project],
                        [Project.EXECUTION, Project.FROZEN, Project.DISCARDED],
                        "pcstask_wf_rej_5",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        [task.ParentTask],
                        [
                            tasks_status.Task.READY,
                            tasks_status.Task.EXECUTION,
                            tasks_status.Task.FINISHED,
                            tasks_status.Task.DISCARDED,
                        ],
                        "pcstask_wf_rej_1",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Subtasks,
                        taskEndStatus.return_value,
                        "pcstask_wf_rej_3",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Checklists,
                        checklistEndStatus.return_value,
                        "pcstask_wf_rej_0",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Issues,
                        issueEndStatus.return_value,
                        "pcstask_wf_rej_8",
                    ],
                ),
            ]
        )
        taskEndStatus.assert_called_once_with()
        checklistEndStatus.assert_called_once_with()
        issueEndStatus.assert_called_once_with()

    def test_FINISHED_FollowUpStateChanges(self):
        "Task.FINISHED.FollowUpStateChanges"
        task = MagicMock(spec=tasks_status.Task)
        task_new = MagicMock(status=tasks_status.Task.NEW.status)
        task_ready = MagicMock(status=tasks_status.Task.READY.status)
        task_other = MagicMock(status=99)  # neither NEW nor READY
        task.getSuccessors.return_value = [task_new, task_ready, task_other]
        status = tasks_status.Task.FINISHED()
        self.assertEqual(
            status.FollowUpStateChanges(task),
            [
                (tasks_status.Task.READY, [task_new, task_new], 0, 0),
                (tasks_status.Task.READY, [task_new], 0, 0),
                (
                    task.ParentTask.getFinalStatus.return_value,
                    [
                        task.ParentTask,
                    ],
                    0,
                    0,
                ),
            ],
        )
        task.getSuccessors.assert_has_calls(
            [
                call("AA"),
                call("EA"),
                call("EE"),
            ]
        )
        self.assertEqual(task.getSuccessors.call_count, 3)
        task_new.getPredecessors.assert_has_calls([call("AA"), call("EA")])
        self.assertEqual(task_new.getPredecessors.call_count, 4)
        task_ready.getPredecessors.assert_not_called()
        task_other.getPredecessors.assert_not_called()
        task.ParentTask.getFinalStatus.assert_called_once_with()

    def _FINISHED_post(self, start, end, now):
        task = MagicMock(
            spec=tasks_status.Task,
            start_time_act=start,
            end_time_act=end,
            percent_complet=99,
        )
        status = tasks_status.Task.FINISHED()
        self.assertIsNone(status.post(task, None))
        self.assertEqual(task.percent_complet, 100)
        task.adjust_values.assert_has_calls(
            [
                call(
                    adjust_parents=True,
                    effort_plan=True,
                    effort_fcast=task.auto_update_effort,
                    effort_act=True,
                    time_act=True,
                ),
                call(adjust_parents=True, percentage=True),
            ]
        )
        self.assertEqual(task.adjust_values.call_count, 2)
        return task

    @patch.object(Issue, "endStatus")
    @patch.object(Checklist, "endStatus")
    @patch.object(tasks_status.Task, "endStatus")
    def test_COMPLETED_Constraints(
        self, taskEndStatus, checklistEndStatus, issueEndStatus
    ):
        "Task.COMPLETED.Constraints"
        task = MagicMock(spec=tasks_status.Task)
        status = tasks_status.Task.COMPLETED()
        self.assertEqual(
            status.Constraints(task),
            [
                (
                    "MatchStateList",
                    [
                        task.Subtasks,
                        taskEndStatus.return_value,
                        "pcstask_wf_rej_3",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Checklists,
                        checklistEndStatus.return_value,
                        "pcstask_wf_rej_0",
                    ],
                ),
                (
                    "MatchStateList",
                    [
                        task.Issues,
                        issueEndStatus.return_value,
                        "pcstask_wf_rej_8",
                    ],
                ),
            ],
        )
        taskEndStatus.assert_called_once_with()
        checklistEndStatus.assert_called_once_with()
        issueEndStatus.assert_called_once_with()

    def test_COMPLETED_FollowUpStateChanges(self):
        "Task.COMPLETED.FollowUpStateChanges"
        task = MagicMock(spec=tasks_status.Task)
        status = tasks_status.Task.COMPLETED()
        self.assertEqual(
            status.FollowUpStateChanges(task),
            [(tasks_status.Task.COMPLETED, task.OrderedSubTasks, 0, 0)],
        )

    @patch.object(Checklist, "endStatus", return_value=["b"])
    @patch.object(tasks_status.Task, "endStatus", return_value=["a"])
    def test_TO_NEW_FollowUpStateChanges_from_DISCARDED(
        self, taskEndStatus, checklistEndStatus
    ):
        "Task.TO_NEW.FollowUpStateChanges from DISCARDED"
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.TO_NEW()
        transition.SourceState = MagicMock()
        transition.SourceState.return_value.status = tasks_status.Task.DISCARDED.status
        a = MagicMock(status="a")
        b = MagicMock(status="b")
        task.OrderedSubTasks = [a, b]
        task.Checklists = [a, b]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [
                (tasks_status.Task.NEW, [a], 0, 0),
                (Checklist.NEW, [b], 0, 0),
            ],
        )
        taskEndStatus.assert_has_calls(2 * [call(False)])
        self.assertEqual(taskEndStatus.call_count, 2)
        checklistEndStatus.assert_has_calls(2 * [call(False)])
        self.assertEqual(checklistEndStatus.call_count, 2)

    def test_TO_NEW_FollowUpStateChanges_from_others(self):
        "Task.TO_NEW.FollowUpStateChanges from other statuses"
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.TO_NEW()
        transition.SourceState = MagicMock()
        transition.SourceState.return_value.status = 99  # not DISCARDED
        task_new = MagicMock(status=tasks_status.Task.NEW.status)
        task_discarded = MagicMock(status=tasks_status.Task.DISCARDED.status)
        task.OrderedSubTasks = [task_new, task_discarded]
        cl_new = MagicMock(status=Checklist.NEW.status)
        cl_discarded = MagicMock(status=Checklist.DISCARDED.status)
        task.Checklists = [cl_new, cl_discarded]
        task_ready = MagicMock(status=task.READY.status)
        task.getSuccessors.return_value = [task_ready, task_discarded]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [
                (tasks_status.Task.NEW, [task_new], 0, 0),
                (Checklist.NEW, [cl_new], 0, 0),
                (tasks_status.Task.NEW, [task_ready, task_ready], 0, 0),
            ],
        )
        task.getSuccessors.assert_has_calls(
            [
                call("EA"),
                call("AA"),
            ]
        )
        self.assertEqual(task.getSuccessors.call_count, 2)

    def test_TO_READY_FollowUpStateChanges_from_NEW(self):
        "Task.TO_READY.FollowUpStateChanges from NEW"
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.TO_READY()
        transition.SourceState = MagicMock()
        transition.SourceState.return_value.status = tasks_status.Task.NEW.status
        task_new = MagicMock(status=tasks_status.Task.NEW.status)
        task_ready = MagicMock(status=tasks_status.Task.READY.status)
        task_discarded = MagicMock(status=tasks_status.Task.DISCARDED.status)
        task.getSuccessors.return_value = [task_ready, task_discarded]
        task.getInitialSubtasks.return_value = [task_new, task_ready]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [
                (tasks_status.Task.READY, [task_new], 0, 0),
                (tasks_status.Task.NEW, [task_ready, task_ready], 0, 0),
            ],
        )
        task.getInitialSubtasks.assert_called_once_with()
        task.getSuccessors.assert_has_calls(
            [
                call("EA"),
                call("AA"),
            ]
        )
        self.assertEqual(task.getSuccessors.call_count, 2)

    def _TO_READY_FollowUpStateChanges_EXECUTION_or_DISCARDED(self, source_status):
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.TO_READY()
        transition.SourceState = MagicMock()
        transition.SourceState.return_value.status = source_status
        task_new = MagicMock(status=tasks_status.Task.NEW.status)
        task_ready = MagicMock(status=tasks_status.Task.READY.status)
        task_exec1 = MagicMock(status=tasks_status.Task.EXECUTION.status)
        task_exec2 = MagicMock(status=tasks_status.Task.EXECUTION.status)
        task_discarded = MagicMock(status=tasks_status.Task.DISCARDED.status)
        task.getSuccessors.return_value = [task_ready, task_discarded]
        task.getInitialSubtasks.return_value = [
            task_new,
            task_ready,
            task_exec1,
        ]
        task.OrderedSubTasks = [task_ready, task_exec2]
        cl_new = MagicMock(status=Checklist.NEW.status)
        cl_evaluation = MagicMock(status=Checklist.EVALUATION.status)
        task.Checklists = [cl_new, cl_evaluation]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [
                (tasks_status.Task.READY, [task_new, task_exec1], 0, 0),
                (tasks_status.Task.NEW, [task_exec2], 0, 0),
                (Checklist.NEW, [cl_evaluation], 0, 0),
                (tasks_status.Task.NEW, [task_ready, task_ready], 0, 0),
            ],
        )
        task.getInitialSubtasks.assert_called_once_with()
        task.getSuccessors.assert_has_calls(
            [
                call("EA"),
                call("AA"),
            ]
        )
        self.assertEqual(task.getSuccessors.call_count, 2)

    def test_TO_READY_FollowUpStateChanges_from_EXECUTION(self):
        "Task.TO_READY.FollowUpStateChanges from EXECUTION"
        self._TO_READY_FollowUpStateChanges_EXECUTION_or_DISCARDED(
            tasks_status.Task.EXECUTION.status,
        )

    def test_TO_READY_FollowUpStateChanges_from_DISCARDED(self):
        "Task.TO_READY.FollowUpStateChanges from DISCARDED"
        self._TO_READY_FollowUpStateChanges_EXECUTION_or_DISCARDED(
            tasks_status.Task.DISCARDED.status,
        )

    def test_TO_READY_FollowUpStateChanges_from_others(self):
        "Task.TO_READY.FollowUpStateChanges from others"
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.TO_READY()
        transition.SourceState = MagicMock()
        # SourceState none of NEW, EXECUTION or DISCARDED
        transition.SourceState.return_value.status = 99
        task_ready = MagicMock(status=tasks_status.Task.READY.status)
        task_discarded = MagicMock(status=tasks_status.Task.DISCARDED.status)
        task.getSuccessors.return_value = [task_ready, task_discarded]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [
                (tasks_status.Task.NEW, [task_ready, task_ready], 0, 0),
            ],
        )
        task.getInitialSubtasks.assert_called_once_with()
        task.getSuccessors.assert_has_calls(
            [
                call("EA"),
                call("AA"),
            ]
        )
        self.assertEqual(task.getSuccessors.call_count, 2)

    def test_FINISHED_EXECUTION_FollowUpStateChanges(self):
        "Task.FINISHED_EXECUTION.FollowUpStateChanges"
        task = MagicMock(spec=tasks_status.Task)
        transition = tasks_status.Task.FINISHED_EXECUTION()
        task_ready = MagicMock(status=tasks_status.Task.READY.status)
        task_discarded = MagicMock(status=tasks_status.Task.DISCARDED.status)
        task.getSuccessors.return_value = [task_ready, task_discarded]
        self.assertEqual(
            transition.FollowUpStateChanges(task),
            [(tasks_status.Task.NEW, [task_ready], 0, 0)],
        )
        task.getSuccessors.assert_has_calls([call("EA")])
        self.assertEqual(task.getSuccessors.call_count, 1)

    @patch.object(
        tasks_status.Task,
        "MakeChangeControlAttributes",
        return_value={"cdb_mpersno": "foo"},
    )
    def test_TO_FINISHED_post(self, MakeChangeControlAttributes):
        "Task.TO_FINISHED.post"
        task = tasks_status.Task()
        transition = tasks_status.Task.TO_FINISHED()
        mocked_ctx = Mock(spec=["error"])
        mocked_ctx.error = None
        transition.post(task, mocked_ctx)

        self.assertEqual(task.cdb_finishedby, "foo")

    def test_add_status_change_adjustment(self):
        "Add additional status change adjustment"
        # trivial addition to dictionary
        pass

    def test_disable_status_change_adjustment(self):
        "Remove status change adjustment"
        # trivial removing from dictionary
        pass

    @patch.object(tasks_status.utils, "add_to_change_stack")
    def test_enable_update_lock(self, add_to_change_stack):
        "Enable update_lock"
        tasks_status.enable_update_lock("foo", 1, 2, a=3, b=4)
        add_to_change_stack.assert_called_once_with("foo")

    @patch.object(Project, "do_status_updates")
    @patch.object(tasks_status.utils, "remove_from_change_stack", return_value=["bass"])
    def test_disable_update_lock_01(self, remove_from_stack, do_status_updates):
        "Disable update lock: ids of changed objects returned"
        project = Project()
        with patch.object(
            tasks_status.Task, "get_projects_by_task_object_ids", return_value=[project]
        ):
            tasks_status.disable_update_lock("foo")

            # check calls
            remove_from_stack.assert_called_once_with("foo")
            tasks_status.Task.get_projects_by_task_object_ids.assert_called_once_with(
                ["bass"]
            )
            do_status_updates.assert_called_once_with(["bass"])

    @patch.object(Project, "do_status_updates")
    @patch.object(tasks_status.utils, "remove_from_change_stack", return_value=[])
    def test_disable_update_lock_02(self, remove_from_stack, do_status_updates):
        "Disable update lock: no changed objects"
        project = Project()
        with patch.object(
            tasks_status.Task, "get_projects_by_task_object_ids", return_value=[project]
        ):
            tasks_status.disable_update_lock("foo")

            # check calls
            remove_from_stack.assert_called_once_with("foo")
            tasks_status.Task.get_projects_by_task_object_ids.assert_not_called()
            do_status_updates.assert_not_called()

    @patch.object(tasks_status.Task, "has_ended", return_value=False)
    def test_accept_new_task_1(self, *args):
        "Task.accept_new_task: task has not ended"
        task = tasks_status.Task()
        task.accept_new_task()
        task.has_ended.assert_called_once_with()

    @patch.object(tasks_status.Task, "has_ended", return_value=True)
    def test_accept_new_task_2(self, *args):
        "Task.accept_new_task: task has ended"
        task = tasks_status.Task()
        task.task_name = "foo"
        with self.assertRaises(tasks_status.ue.Exception) as e:
            task.accept_new_task()
        msg = tasks_status.ue.Exception("pcs_err_new_task2", "foo")
        self.assertEqual(str(e.exception), msg.msg.getText("", True))
        task.has_ended.assert_called_once_with()

    @patch.object(tasks_status.Task, "get_status_txt", return_value="bar")
    @patch.object(tasks_status.Task, "has_ended", return_value=True)
    def test_accept_new_parent_task_1(self, *args):
        "Task.accept_new_parent_task: task in end status"
        task = tasks_status.Task()
        task.task_name = "foo"
        task.status = 200
        parent = tasks_status.Task()
        with self.assertRaises(tasks_status.ue.Exception) as e:
            task.accept_new_parent_task(parent)
        msg = tasks_status.ue.Exception("pcs_task_has_ended", "foo", "bar")
        self.assertEqual(str(e.exception), msg.msg.getText("", True))
        task.has_ended.assert_called_once_with()
        task.get_status_txt.assert_called_once_with(200)

    @patch.object(tasks_status.Task, "get_status_txt", return_value="bar")
    @patch.object(tasks_status.Task, "has_ended", return_value=False)
    def test_accept_new_parent_task_2(self, *args):
        "Task.accept_new_parent_task: parent not valid, task READY"
        task = tasks_status.Task()
        task.status = 20
        parent = tasks_status.Task()
        parent.status = 0
        parent.task_name = "foo"
        with self.assertRaises(tasks_status.ue.Exception) as e:
            task.accept_new_parent_task(parent)
        msg = tasks_status.ue.Exception(
            "pcs_reset_parent_task_status", "foo", "bar", "bar"
        )
        self.assertEqual(str(e.exception), msg.msg.getText("", True))
        task.has_ended.assert_called_once_with()
        parent.get_status_txt.assert_called_once_with(0)

    @patch.object(tasks_status.Task, "get_status_txt", return_value="bar")
    @patch.object(tasks_status.Task, "has_ended", return_value=False)
    def test_accept_new_parent_task_3(self, *args):
        "Task.accept_new_parent_task: parent not valid, task EXECUTION"
        task = tasks_status.Task()
        task.status = 50
        parent = tasks_status.Task()
        parent.status = 20
        parent.task_name = "foo"
        with self.assertRaises(tasks_status.ue.Exception) as e:
            task.accept_new_parent_task(parent)
        msg = tasks_status.ue.Exception(
            "pcs_advance_parent_task_status", "foo", "bar", "bar"
        )
        self.assertEqual(str(e.exception), msg.msg.getText("", True))
        task.has_ended.assert_called_once_with()
        parent.get_status_txt.assert_called_once_with(50)

    @patch.object(tasks_status.Task, "get_status_txt", return_value="bar")
    @patch.object(tasks_status.Task, "has_ended", return_value=False)
    def test_accept_new_parent_task_4(self, *args):
        "Task.accept_new_parent_task: parent is valid"
        task = tasks_status.Task()
        parent = tasks_status.Task()
        task.accept_new_parent_task(parent)
        task.has_ended.assert_called_once_with()
        task.get_status_txt.assert_not_called()

    @patch.object(tasks_status.Task, "endStatus", return_value=[200])
    def test_has_ended_1(self, end_status):
        "Task.has_ended: task has not ended"
        task = tasks_status.Task()
        task.status = 50
        self.assertFalse(task.has_ended())
        end_status.assert_called_once_with(False)

    @patch.object(tasks_status.Task, "endStatus", return_value=[200])
    def test_has_ended_2(self, end_status):
        "Task.has_ended: task has ended"
        task = tasks_status.Task()
        task.status = 200
        self.assertTrue(task.has_ended())
        end_status.assert_called_once_with(False)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
