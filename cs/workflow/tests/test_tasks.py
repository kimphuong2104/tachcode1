#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module test_tasks

This is the documentation for the test_tasks module.
"""

import mock
import unittest
import cdbwrapc

from datetime import date, timedelta

from cdb import auth
from cdb import sqlapi
from cdb import testcase
from cdb.objects.org import User
from cs.platform.org.user import AbsencePeriod
from cs.platform.org.user import UserSubstitute

from cs.workflow.processes import Process
from cs.workflow.tasks import InteractiveTask
from cs.workflow.tasks import RunLoopSystemTask
from cs.workflow.tasks import Tags
from cs.workflow.tasks import Task
from cs.workflow import tasks
from cs.workflow import exceptions
from cs.workflow import taskgroups
from cs.workflow import schemacomponents


def setup_module():
    testcase.run_level_setup()


class DummyContext(object):
    __ue_args__ = "ue_args"

    def __init__(self, root=True):
        self.root = root
        if self.root:
            setattr(self, self.__ue_args__, DummyContext(root=False))

    def get_attribute_names(self):
        if self.root:
            raise AttributeError("root ctx has not attribute "
                                 "'get_attribute_names'")

        return [k for k in list(vars(self)) if k != "root"]

    def keep(self, name, value):
        setattr(getattr(self, self.__ue_args__), name, value)


class TaskReferences(testcase.RollbackTestCase):
    def test_RootProcess(self):
        # integration test implemented in test_processes
        task = mock.MagicMock(spec=Task)
        self.assertEqual(
            Task.RootProcess.get_referenced(task),
            task.Process.RootProcess,
        )

    def test_TerminatedParents(self):
        # integration test implemented in test_processes
        task = mock.MagicMock(spec=Task)
        self.assertEqual(
            Task.TerminatedParents.get_referenced(task),
            task.Process.TerminatedParents,
        )

    @mock.patch.object(Tags, "Create")
    @mock.patch.object(Tags, "KeywordQuery")
    def test_copy_tags(self, KeywordQuery, Create):
        # unit test: copy tags
        ctx = mock.MagicMock()
        ctx.cdbtemplate.cdb_object_id = "foo"
        ctx.error = False
        a_tag = Tags(
            persno="foo_per",
            tag="foo_tag",
            task_object_id="bar"
        )
        KeywordQuery.return_value = [a_tag]
        task = Task(cdb_object_id="bar")

        # start test
        task.copy_tags(ctx)

        # checks
        KeywordQuery.assert_called_once_with(task_object_id="foo")
        Create.assert_called_once_with(
            persno="foo_per", tag="foo_tag", task_object_id="bar"
        )


class TaskEMailTestCase(testcase.RollbackTestCase):

    tasks = 0

    def _user(self, name):
        persno = "TEST_{}".format(name.upper())
        sqlapi.SQLinsert(
            "INTO cdb_usr_setting (setting_id, setting_id2, "
            "personalnummer, value, cdb_classname) VALUES "
            "('user.email_with_task', '', '{}', 1, "
            "'cdb_usr_setting')".format(persno))

        user = User.Create(
            personalnummer=persno,
            e_mail="{}@contact.de".format(name),
            name=name,
            active_account="1",
        )
        return user.personalnummer, (user.e_mail, user.name)

    def _substitute_user(self, user):

        # make the current user absent
        start = date.today() - timedelta(days=7)
        end = date.today() + timedelta(days=7)
        AbsencePeriod.Create(
            personalnummer=user,
            period_start=start,
            period_end=end
        )

        sub, sub_email = self._user("substitute")

        UserSubstitute.Create(
            personalnummer=user,
            substitute=sub,
            period_start=start,
            period_end=end
        )

        return sub_email


    def _task(self, wf_persno, task_persno):
        self.tasks += 1
        tid = "TEST-{}".format(self.tasks)

        Process.Create(
            cdb_process_id=tid,
            subject_id=wf_persno,
            subject_type="Person",
        )

        return Task.Create(
            cdb_process_id=tid,
            task_id=tid,
            cdb_classname="cdbwf_task_execution",
            subject_id=task_persno,
            subject_type="Person")

    def test_getNotificationReceiver(self):

        USER_A, A = self._user("a")
        USER_B, B = self._user("b")

        self.assertEqual(
            self._task(USER_A, USER_A).getNotificationReceiver(),
            [{"to": set([A])}])
        self.assertEqual(
            self._task(USER_B, USER_B).getNotificationReceiver(),
            [{"to": set([B])}])
        self.assertEqual(
            self._task(USER_A, USER_B).getNotificationReceiver(),
            [{"to": set([B])}])
        self.assertEqual(
            self._task(USER_B, USER_A).getNotificationReceiver(),
            [{"to": set([A])}])

        self.assertEqual(
            self._task("", "").getNotificationReceiver(),
            [{}])

        self.assertEqual(
            self._task(None, None).getNotificationReceiver(),
            [{}])

        # wf owner only gets one mail per ctx
        ctx = DummyContext()
        ctx.content_change_bobject = "x"

        with self.assertRaises(AttributeError):
            _ = ctx.ue_args.wf_owner_ok

        self.assertEqual(
            self._task(USER_A, USER_B).getNotificationReceiver(ctx),
            [{"cc": set([A]), "to": set([B])}])

        self.assertEqual(ctx.ue_args.wf_owner_ok, True)
        self.assertEqual(ctx.ue_args.get_attribute_names(), ["wf_owner_ok"])

        self.assertEqual(
            self._task(USER_A, USER_B).getNotificationReceiver(ctx),
            [{"to": set([B])}])

    def test_getNotificationReceiver_substituted(self):
        USER_A, A = self._user("a")
        USER_B, _ = self._user("b")
        C = self._substitute_user(USER_A)

        cdbwrapc.clearUserSubstituteCache()
        self.assertEqual(
            self._task(USER_B, USER_A).getNotificationReceiver(),
            [{"to": set([A, C])}])


class TaskPreconditionsTestCase(testcase.RollbackTestCase):
    def test_get_violated_process_start_preconditions_base_task(self):
        task = Task()
        ok = task.get_violated_process_start_preconditions()
        self.assertEqual(ok, "")

    def test_get_violated_process_start_preconditions_interactive_task(self):
        task = InteractiveTask()

        no_subject = task.get_violated_process_start_preconditions()
        self.assertEqual(no_subject,
                         "Das Feld 'Verantwortlich' ist nicht gefüllt.")

        task.Update(subject_id="caddok", subject_type="Person")
        task.Reload()
        ok = task.get_violated_process_start_preconditions()
        self.assertEqual(ok, "")

    def test_RunLoop_get_violated_process_start_preconditions(self):
        task = mock.MagicMock(
            spec=RunLoopSystemTask,
            __required_params_err_msgs__={None: ""},
        )
        task.CurrentCycle.get_violated_process_start_preconditions\
            .return_value = "foo"

        self.assertEqual(
            RunLoopSystemTask.get_violated_process_start_preconditions(task),
            "Die Aufgabe '{}' braucht die folgenden fehlenden Parameter: "
            "'' / foo".format(task.GetDescription.return_value),
        )
        task.CurrentCycle.get_violated_process_start_preconditions\
            .assert_called_once_with()


class TestOPStatusChange(unittest.TestCase):
    @mock.patch.object(tasks, "_run")
    def test_op_status_change_close(self, _run):
        task = InteractiveTask()
        ctx = mock.Mock()
        ctx.dialog.zielstatus_int = 20
        task.op_status_change(ctx)
        _run.assert_called_once_with("cdbwf_close_task", task, remark=ctx.dialog.remark)

    @mock.patch.object(tasks, "_run")
    def test_op_status_change_refuse(self, _run):
        task = InteractiveTask()
        ctx = mock.Mock()
        ctx.dialog.zielstatus_int = 30
        task.op_status_change(ctx)
        _run.assert_called_once_with("cdbwf_refuse_task", task, remark=ctx.dialog.remark)

    @mock.patch.object(tasks, "_run", side_effect=tasks.ElementsError)
    def test_op_status_change_failure(self, _):
        task = InteractiveTask()
        ctx = mock.Mock()
        ctx.dialog.zielstatus_int = 20
        with self.assertRaises(tasks.ElementsError):
            task.op_status_change(ctx)


class TestTaskActivateTask(unittest.TestCase):
    """Test the method Task.activate_task"""

    @mock.patch.object(Task, "Process", subject_id=auth.persno)
    @mock.patch("cs.workflow.tasks.set_state")
    @mock.patch.object(Task, "check_constraints", return_value=True)
    def test_activate_task(self, check_constraint, set_state, Process):
        """The task is activated"""
        task = Task()
        task.activate_task()

        set_state.assert_called_with(task, Task.EXECUTION)

    @mock.patch("cs.workflow.tasks.set_state")
    @mock.patch.object(Task, "check_constraints", return_value=False)
    def test_activate_task_constraint(self, check_constraint, set_state):
        """If the constraints are not satisfied, the task is cancelled"""
        task = Task()

        try:
            task.activate_task()
        except exceptions.TaskCancelledException:
            pass

        set_state.assert_called_with(task, Task.DISCARDED, comment='')


class TestTaskCancelTask(testcase.RollbackTestCase):
    """Test the method Task.cancel_task"""

    @mock.patch("cs.workflow.tasks.set_state")
    def test_cancel_task(self, set_state):
        """The task is canceled"""
        task = Task()

        task.cancel_task(mock.sentinel.comment)

        set_state.assert_called_with(task, Task.DISCARDED,
                                     comment=mock.sentinel.comment)

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.tasks.set_state")
    def test_cancel_run_loop_task_running_cycle(self, set_state_task,
                                                set_state_cycle):
        """The "run_loop" task with a running cycle is canceled"""
        manager = mock.Mock()  # to assert call order of multiple mocks
        manager.attach_mock(set_state_task, 'set_state_task')
        manager.attach_mock(set_state_cycle, 'set_state_cycle')

        task = RunLoopSystemTask(cdb_object_id="foo")
        cycle = Process.Create(
            cdb_process_id="foo",
            parent_task_object_id=task.cdb_object_id,
            status=Process.EXECUTION.status,
        )
        task.cancel_task(mock.sentinel.comment)

        manager.assert_has_calls([
            mock.call.set_state_task(
                task,
                Task.DISCARDED,
                comment=mock.sentinel.comment,
            ),
            # this MUST be called after discarding the task to prevent
            # a new cycle from being created!
            mock.call.set_state_cycle(
                cycle,
                cycle.FAILED,
                comment=mock.sentinel.comment,
            ),
        ])


class TestTaskCloseTask(unittest.TestCase):
    """Test the method Task.close_task"""

    @mock.patch("cs.workflow.tasks.set_state")
    @mock.patch.object(Task, "Parent", spec=taskgroups.TaskGroup)
    def test_close_task(self, Parent, set_state):
        """The task is closed"""
        task = Task()

        task.close_task(mock.sentinel.comment)

        set_state.assert_called_with(task, Task.COMPLETED,
                                     comment=mock.sentinel.comment)
        assert Parent.propagate_done.called


class TestTaskRefuseTask(unittest.TestCase):
    """Test the method Task.refuse_task"""

    @mock.patch("cs.workflow.tasks.set_state")
    @mock.patch.object(Task, "Parent", spec=taskgroups.TaskGroup)
    def test_refuse_task(self, Parent, set_state):
        """The task is refused"""
        task = Task()

        task.refuse_task(mock.sentinel.comment)

        set_state.assert_called_with(task, Task.REJECTED,
                                     comment=mock.sentinel.comment)
        assert Parent.propagate_refuse.called


class TestTaskGroupActivateTask(unittest.TestCase):
    """Test the method TaskGroup.activate_task"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "check_constraints",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "activate_subtasks")
    def test_activate_task(
            self, activate_subtasks, check_constraints, set_state
    ):
        """The task group is activated"""
        taskgroup = taskgroups.TaskGroup()
        taskgroup.activate_task()

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.EXECUTION
        )
        assert activate_subtasks.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "check_constraints",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    def test_activate_task_constraint_false(
            self, cancel_subtasks, check_constraints, set_state
    ):
        """
        If some constraint evaluates to False, the task group is not activated
        """
        taskgroup = taskgroups.TaskGroup()

        msg = None
        try:
            taskgroup.activate_task()
        except exceptions.TaskCancelledException as ex:
            msg = str(ex)

        assert msg is not None
        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.DISCARDED,
            comment=msg
        )
        assert cancel_subtasks.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "check_constraints",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "activate_subtasks",
                       side_effect=exceptions.TaskCancelledException)
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    def test_activate_task_subtasks_canceled(
            self, cancel_subtasks, activate_subtasks,
            check_constraints, set_state
    ):
        """
        If all the subtasks are canceled, the task group is also canceled
        """
        taskgroup = taskgroups.TaskGroup()

        msg = None
        try:
            taskgroup.activate_task()
        except exceptions.TaskCancelledException as ex:
            msg = str(ex)

        assert msg is not None
        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.DISCARDED,
            comment=msg
        )
        assert cancel_subtasks.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "check_constraints",
        return_value=True
    )
    @mock.patch.object(
        taskgroups.TaskGroup,
        "activate_subtasks",
        side_effect=exceptions.TaskClosedException
    )
    def test_activate_task_subtasks_closed(
            self, activate_subtasks, check_constraints, set_state
    ):
        """If all the subtasks are closed the task group is also closed"""
        taskgroup = taskgroups.TaskGroup()

        try:
            taskgroup.activate_task()
        except exceptions.TaskClosedException:
            pass

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )


class TestTaskGroupCancelTask(unittest.TestCase):
    """Test the method TaskGroup.cancel_task"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    def test_cancel_task(self, cancel_subtasks, set_state):
        """The task group is cancelled"""
        taskgroup = taskgroups.TaskGroup()

        taskgroup.cancel_task(mock.sentinel.comment)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.DISCARDED,
            comment=mock.sentinel.comment
        )
        assert cancel_subtasks.called


class TestTaskGroupCloseTask(unittest.TestCase):
    """Test the method TaskGroup.close_task"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    def test_close_task(self, set_state):
        """The task group is closed"""
        taskgroup = taskgroups.TaskGroup()

        taskgroup.close_task()

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )


class TestTaskGroupRefuseTask(unittest.TestCase):
    """Test the method TaskGroup.refuse_task"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    def test_cancel_task(self, set_state):
        """The task group is refused"""
        taskgroup = taskgroups.TaskGroup()

        taskgroup.refuse_task(mock.sentinel.comment)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.REJECTED,
            comment=mock.sentinel.comment
        )


class TestTaskGroupPropagateRefuse(unittest.TestCase):
    """Test the method Taskgroup.propagate_refuse"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    def test_propagate_refuse(self, cancel_subtasks, Parent, set_state):
        """
        The task is refused, the subtasks are cancelled, the parent task is
        refused
        """
        taskgroup = taskgroups.TaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_refuse(child, comment=mock.sentinel.comment)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.REJECTED,
            comment=mock.sentinel.comment
        )
        Parent.propagate_refuse.assert_called_with(
            taskgroup,
            mock.sentinel.comment
        )
        assert cancel_subtasks.called


class TestParallelTaskGroupPropagateDone(unittest.TestCase):
    """Test the method ParallelTaskGroup.propagate_done"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "allDone",
        return_value=False
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done(self, has_finish_option, allDone, set_state):
        """If some subtask is still running, nothing is done"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        assert not set_state.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "allDone",
        return_value=True
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done_all_done(
            self, has_finish_option, allDone, Parent, set_state
    ):
        """If all subtasks are done the task group is closed"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)

    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.TaskGroups",
                Query=mock.MagicMock(return_value=[]))
    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.Tasks",
                Query=mock.MagicMock(return_value=[]))
    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "allDone",
        return_value=False
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "has_finish_option",
        return_value=True
    )
    def test_propagate_done_finish_option(
            self, has_finish_option, allDone, Parent, set_state, TaskGroups,
            Tasks
    ):
        """If the child has the finish option the task group is closed"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)


class TestSequentialTaskGroupPropagateDone(unittest.TestCase):
    """Test the method SequentialTaskGroup.propagate_done"""

    @mock.patch.object(
        taskgroups.SequentialTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done(self, has_finish_option):
        """If there is a successor, the successor is activated"""
        taskgroup = taskgroups.SequentialTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        assert child.NextSibling.activate_task.called

    @mock.patch.object(taskgroups.SequentialTaskGroup, "cancel_task")
    @mock.patch.object(
        taskgroups.SequentialTaskGroup,
        "has_finish_option",
        return_value=False
    )
    @mock.patch.object(
        taskgroups.SequentialTaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_done_canceled(
            self, Parent, has_finish_option, cancel_task
    ):
        """
        If there is a successor and the successor is canceled while
        activating, then the task is also canceled
        """
        taskgroup = taskgroups.SequentialTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)

        child.NextSibling.activate_task.side_effect = (
            exceptions.TaskCancelledException
        )
        taskgroup.propagate_done(child)

        assert child.NextSibling.activate_task.called
        assert cancel_task.called
        assert Parent.propagate_cancel.called

    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.TaskGroups",
                Query=mock.MagicMock(return_value=[]))
    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.Tasks",
                Query=mock.MagicMock(return_value=[]))
    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(
        taskgroups.SequentialTaskGroup,
        "has_finish_option",
        return_value=True
    )
    def test_propagate_done_finish_option(
            self, has_finish_option, Parent, set_state, Tasks, TaskGroups
    ):
        """If the child has the finish option the task group is closed"""
        taskgroup = taskgroups.SequentialTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(
        taskgroups.SequentialTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done_no_successor(
            self, has_finish_option, Parent, set_state
    ):
        """If there is no successor the task group is closed"""
        taskgroup = taskgroups.SequentialTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        child.NextSibling = None
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)


class TestProcessCompletionTaskGroupPropagateDone(unittest.TestCase):
    """Test the method ProcessCompletionTaskGroup.propagate_done"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(taskgroups.ProcessCompletionTaskGroup, "Components")
    @mock.patch.object(
        taskgroups.ProcessCompletionTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done(self, has_finish_option, Components, set_state):
        """If some subtask is still running, nothing is done"""
        Components.__iter__.return_value = [mock.Mock(
            spec=schemacomponents.SchemaComponent,
            status=taskgroups.TaskGroup.EXECUTION.status,
            EXECUTION=taskgroups.TaskGroup.EXECUTION),
        ]

        taskgroup = taskgroups.ProcessCompletionTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        assert not set_state.called

    @mock.patch("cs.workflow.taskgroups.TaskGroup.Process")
    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(taskgroups.ProcessCompletionTaskGroup, "Components")
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "has_finish_option",
        return_value=False
    )
    def test_propagate_done_all_done(
            self, has_finish_option, Components, Parent, set_state, _Process
    ):
        """If all subtasks are done the task group is closed"""
        Components.__iter__.return_value = [mock.Mock(
            spec=schemacomponents.SchemaComponent,
            status=taskgroups.TaskGroup.COMPLETED.status,
            EXECUTION=taskgroups.TaskGroup.EXECUTION),
        ]

        taskgroup = taskgroups.ProcessCompletionTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        # _Process is mocked because completing_ok is accessed
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)

    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.TaskGroups",
                Query=mock.MagicMock(return_value=[]))
    # Workaround E027164
    @mock.patch("cs.workflow.taskgroups.TaskGroup.Tasks",
                Query=mock.MagicMock(return_value=[]))
    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    @mock.patch.object(
        taskgroups.ParallelTaskGroup,
        "has_finish_option",
        return_value=True
    )
    def test_propagate_done_finish_option(
            self, has_finish_option, Parent, set_state, Tasks, TaskGroups
    ):
        """If the child has the finish option the task group is closed"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_done(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)


class TestParallelTaskGroupPropagateCancel(unittest.TestCase):
    """Test the method ParallelTaskGroup.propagate_cancel"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=False)
    def test_propagate_cancel(self, allDone, allCancelled, set_state):
        """If some subtask is not closed, nothing is done"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        assert not set_state.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_cancel_all_done(
            self, Parent, allDone, allCancelled, set_state
    ):
        """
        If all subtasks are done, but some is not cancelled, the task group is
        normally closed
        """
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_cancel_all_cancelled(
            self, Parent, allDone, allCancelled, cancel_subtasks, set_state
    ):
        """If all subtasks are cancelled, the task group is cancelled"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.DISCARDED,
            comment=""
        )
        Parent.propagate_cancel.assert_called_with(taskgroup)


class TestSequentialTaskGroupPropagateCancel(unittest.TestCase):
    """Test the method SequentialTaskGroup.propagate_cancel"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_cancel(self, Parent, cancel_subtasks, set_state):
        """The task group is closed"""
        taskgroup = taskgroups.SequentialTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        assert Parent.propagate_cancel.called


class TestProcessCompletionTaskGroupPropagateCancel(unittest.TestCase):
    """Test the method ProcessCompletionTaskGroup.propagate_cancel"""

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=False)
    def test_propagate_cancel(self, allDone, allCancelled, set_state):
        """If some subtask is not closed, nothing is done"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        assert not set_state.called

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_cancel_all_done(
            self, Parent, allDone, allCancelled, set_state
    ):
        """
        If all subtasks are done, but some is not cancelled, the task group is
        normally closed
        """
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.COMPLETED
        )
        Parent.propagate_done.assert_called_with(taskgroup)

    @mock.patch("cs.workflow.taskgroups.set_state")
    @mock.patch.object(taskgroups.TaskGroup, "cancel_subtasks")
    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(
        taskgroups.TaskGroup,
        "Parent",
        spec=taskgroups.TaskGroup
    )
    def test_propagate_cancel_all_cancelled(
            self, Parent, allDone, allCancelled, cancel_subtasks, set_state
    ):
        """If all subtasks are cancelled, the task group is cancelled"""
        taskgroup = taskgroups.ParallelTaskGroup()

        child = mock.Mock(spec=schemacomponents.SchemaComponent)
        taskgroup.propagate_cancel(child)

        set_state.assert_called_with(
            taskgroup,
            taskgroups.TaskGroup.DISCARDED,
            comment=""
        )
        Parent.propagate_cancel.assert_called_with(taskgroup)


class TestTaskGroupCancelSubtasks(unittest.TestCase):
    """Test the method TaskGroup.cancel_subtasks"""

    @mock.patch.object(taskgroups.TaskGroup, "TaskGroups")
    @mock.patch.object(taskgroups.TaskGroup, "Tasks")
    def test_cancel_subtasks(self, Tasks, TaskGroups):
        """If the task group is cancelled, its subtasks are cancelled too"""
        child = mock.Mock(spec=Task)
        Tasks.Query.return_value = [child]
        TaskGroups.Query.return_value = [child]

        taskgroup = taskgroups.TaskGroup()
        taskgroup.cancel_subtasks("")

        assert child.cancel_task.called


class TestParallelTaskGroupActivateSubtasks(unittest.TestCase):
    """Test the method Taskgroup.activate_subtasks"""

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=False)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks(self, Components, allDone, allCancelled):
        """All the subtasks are activated"""
        child = mock.Mock(spec=Task)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ParallelTaskGroup()

        taskgroup.activate_subtasks()

        assert child.activate_task.called

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks_all_cancelled(
            self, Components, allDone, allCancelled
    ):
        """
        If all the subtasks are cancelled, also the task group is canceled
        """
        child = mock.Mock(spec=Task,
                          side_effect=exceptions.TaskCancelledException)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ParallelTaskGroup()

        raised = False
        try:
            taskgroup.activate_subtasks()
        except exceptions.TaskCancelledException:
            raised = True

        assert child.activate_task.called
        assert raised

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks_all_done(
            self, Components, allDone, allCancelled
    ):
        """If all the subtasks are closed, also the task group is closed"""
        child = mock.Mock(spec=Task,
                          side_effect=exceptions.TaskClosedException)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ParallelTaskGroup()

        raised = False
        try:
            taskgroup.activate_subtasks()
        except exceptions.TaskClosedException:
            raised = True

        assert child.activate_task.called
        assert raised


class TestSequentialTaskGroupActivateSubtasks(unittest.TestCase):
    """Test the method SequentialTaskGroup.activate_subtasks"""

    @mock.patch.object(taskgroups.SequentialTaskGroup, "First", spec=Task)
    def test_activate_subtasks(self, First):
        """The first subtask is activated"""
        taskgroup = taskgroups.SequentialTaskGroup()

        taskgroup.activate_subtasks()

        assert First.activate_task.called

    @mock.patch.object(taskgroups.SequentialTaskGroup, "First", spec=Task)
    def test_activate_subtasks_closed(self, First):
        """If the first subtask is closed, the next one is activated"""
        First.activate_task.side_effect = exceptions.TaskClosedException

        taskgroup = taskgroups.SequentialTaskGroup()

        taskgroup.activate_subtasks()

        assert First.activate_task.called
        assert First.Next.activate_task.called

    @mock.patch.object(taskgroups.SequentialTaskGroup, "First", spec=Task)
    def test_activate_subtasks_cancelled(self, First):
        """If the first subtask is cancelled, an exception is raised"""
        First.activate_task.side_effect = exceptions.TaskCancelledException

        taskgroup = taskgroups.SequentialTaskGroup()

        raised = False
        try:
            taskgroup.activate_subtasks()
        except exceptions.TaskCancelledException:
            raised = True

        assert First.activate_task.called
        assert raised


class TestProcessCompletionTaskGroupActivateSubtasks(unittest.TestCase):
    """Test the method ProcessCompletionTaskGroup.activate_subtasks"""

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=False)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks(self, Components, allDone, allCancelled):
        """All the subtasks are activated"""
        child = mock.Mock(spec=Task)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ProcessCompletionTaskGroup()

        taskgroup.activate_subtasks()

        assert child.activate_task.called

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=True
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks_all_cancelled(
            self, Components, allDone, allCancelled
    ):
        """
        If all the subtasks are cancelled, also the task group is canceled
        """
        child = mock.Mock(spec=Task,
                          side_effect=exceptions.TaskCancelledException)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ProcessCompletionTaskGroup()

        raised = False
        try:
            taskgroup.activate_subtasks()
        except exceptions.TaskCancelledException:
            raised = True

        assert child.activate_task.called
        assert raised

    @mock.patch.object(
        taskgroups.TaskGroup,
        "allCancelled",
        return_value=False
    )
    @mock.patch.object(taskgroups.TaskGroup, "allDone", return_value=True)
    @mock.patch.object(taskgroups.TaskGroup, "Components")
    def test_activate_subtasks_all_done(
            self, Components, allDone, allCancelled
    ):
        """If all the subtasks are closed, also the task group is closed"""
        child = mock.Mock(spec=Task,
                          side_effect=exceptions.TaskClosedException)
        Components.__iter__.return_value = [child]

        taskgroup = taskgroups.ProcessCompletionTaskGroup()

        raised = False
        try:
            taskgroup.activate_subtasks()
        except exceptions.TaskClosedException:
            raised = True

        assert child.activate_task.called
        assert raised


class TestRunLoopSystemTaskCopyCycle(unittest.TestCase):
    """Test the method RunLoopSystemTask.copy_cycle"""

    @mock.patch.object(Task, "ByKeys")
    def test_copy_cycle_error(self, ByKeys):
        runLoopSystemTask = mock.MagicMock(spec=RunLoopSystemTask)

        ctx = mock.MagicMock(error=True)

        self.assertIsNone(RunLoopSystemTask.copy_cycle(runLoopSystemTask, ctx))

        assert not ByKeys.called

    @mock.patch.object(Task, "ByKeys")
    def test_copy_cycle_no_subcycle(self, ByKeys):
        runLoopSystemTask = mock.MagicMock(spec=RunLoopSystemTask)

        ctx = mock.MagicMock(error=False)

        task = mock.MagicMock(spec=Task)
        task.CurrentCycle = False
        ByKeys.return_value = task

        with self.assertRaises(tasks.ElementsError):
            RunLoopSystemTask.copy_cycle(runLoopSystemTask, ctx)

        ByKeys.assert_called_once_with(
            cdb_process_id=ctx.cdbtemplate.cdb_process_id,
            task_id=ctx.cdbtemplate.task_id,
        )

    @mock.patch.object(Task, "ByKeys")
    @mock.patch.object(tasks, "_run")
    def test_copy_cycle_run_successfull(self, _run, ByKeys):
        runLoopSystemTask = mock.MagicMock(spec=RunLoopSystemTask)
        runLoopSystemTask.get_cycle_args.return_value = {"arg0": 0, "arg1": 1}

        ctx = mock.MagicMock(error=False)

        task = mock.MagicMock(spec=Task, CurrentCycle=mock.MagicMock())
        ByKeys.return_value = task

        _run.return_value = True

        self.assertIsNone(RunLoopSystemTask.copy_cycle(runLoopSystemTask, ctx))

        ByKeys.assert_called_once_with(
            cdb_process_id=ctx.cdbtemplate.cdb_process_id,
            task_id=ctx.cdbtemplate.task_id,
        )
        _run.assert_called_once_with(
            tasks.constants.kOperationCopy,
            task.CurrentCycle,
            **{"arg0": 0, "arg1": 1}
            )

    @mock.patch.object(Task, "ByKeys")
    @mock.patch.object(tasks, "_run",
                       side_effect=tasks.ElementsError("MyError"))
    def test_copy_cycle_run_exception(self, _run, ByKeys):
        runLoopSystemTask = mock.MagicMock(spec=RunLoopSystemTask)
        runLoopSystemTask.get_cycle_args.return_value = {"arg0": 0, "arg1": 1}

        ctx = mock.MagicMock(error=False)

        task = mock.MagicMock(spec=Task, CurrentCycle=mock.MagicMock())
        task.CurrentCycle.cdb_process_id = "currentCycle.process_id"
        ByKeys.return_value = task

        with self.assertRaises(tasks.ElementsError):
            with testcase.error_logging_disabled():
                RunLoopSystemTask.copy_cycle(runLoopSystemTask, ctx)

        ByKeys.assert_called_once_with(
            task_id=ctx.cdbtemplate.task_id,
            cdb_process_id=ctx.cdbtemplate.cdb_process_id,
        )
        _run.assert_called_once_with(
            tasks.constants.kOperationCopy,
            task.CurrentCycle,
            **{"arg0": 0, "arg1": 1}
            )


class TasknotifyAfterStateChange(unittest.TestCase):
    """Test the method Task.notifyAfterStateChange"""

    def test_notifyAfterStateChange_no_ctx(self):
        task = mock.MagicMock(spec=tasks.Task)

        tasks.Task.notifyAfterStateChange(task, None)

        task.Super.assert_called_once_with(tasks.Task)
        task.Super.return_value.notifyAfterStateChange.assert_called_once_with(None)

    def test_notifyAfterStateChange_no_error(self):
        task = mock.MagicMock(spec=tasks.Task)
        ctx = mock.MagicMock(error=False)

        tasks.Task.notifyAfterStateChange(task, ctx)

        task.Super.assert_called_once_with(tasks.Task)
        task.Super.return_value.notifyAfterStateChange.assert_called_once_with(ctx)

    def test_notifyAfterStateChange_with_error(self):
        task = mock.MagicMock(spec=tasks.Task)
        ctx = mock.MagicMock(error=True)

        tasks.Task.notifyAfterStateChange(task, ctx)

        task.Super.assert_not_called()
