#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module test_process

This is the documentation for the test_process module.
"""

import mock
import pytest

from cdb import constants
from cdb import testcase
from cdb import util
from cdb.objects.operations import operation

from cs.workflow.processes import Process
from cs.workflow.tasks import SystemTask
from cs.workflow.tasks import Task
from cs.workflow.taskgroups import TaskGroup
from cs.workflow.constraints import Constraint
from cs.workflow import briefcases
from cs.workflow import exceptions
from cs.workflow import processes


def setup_module():
    testcase.run_level_setup()


@testcase.rollback
@pytest.mark.parametrize("keep_owner, defaults, expected", [
    (True, None, ("sub_id", "Organisation")),
    (True, {"subject_id": "id", "subject_type": "Organisation"}, ("sub_id", "Organisation")),
    (False, {"subject_id": "id", "subject_type": "Organisation"}, ("id", "Organisation")),
    (False, None, ("pers_no", "Person"))])
def test_CreateFromTemplate(keep_owner, defaults, expected):
        template = Process.Create(
            cdb_process_id = "template_id",
            subject_id = "sub_id",
            subject_type = "Organisation"
        )

        with mock.patch.object(processes, "auth") as m:
            m.persno = "pers_no"
            new = Process.CreateFromTemplate(template.cdb_process_id, defaults=defaults, keep_owner=keep_owner)
        assert (new.subject_id, new.subject_type) == expected


@testcase.rollback
@pytest.mark.parametrize("test_defaults, defaults, expectation", [
    (True ,{"subject_id" : "id"}, ValueError),
    (True ,{"subject_type" : "Person"}, ValueError),
    (False, None, util.ErrorMessage)
])
def test_CreateFromTemplate_inconsistent_values(test_defaults, defaults, expectation):
    if test_defaults:
        with pytest.raises(expectation):
            Process.CreateFromTemplate(Process.CreateProcess().cdb_process_id, defaults=defaults)
    else:
        with pytest.raises(expectation):
            Process.CreateFromTemplate("no_template")


class TestReferences(testcase.RollbackTestCase):
    def test_get_root_process(self):
        root = Process.Create(cdb_process_id="test_root")
        root_task = Task.Create(
            cdb_process_id=root.cdb_process_id,
            task_id=root.cdb_process_id,
            cdb_classname="cdbwf_task_execution",
        )
        node = Process.Create(
            cdb_process_id="test_node",
            parent_task_object_id=root_task.cdb_object_id,
        )
        node_task = Task.Create(
            cdb_process_id=node.cdb_process_id,
            task_id=node.cdb_process_id,
            cdb_classname="cdbwf_task_execution",
        )
        leaf = Process.Create(
            cdb_process_id="test_leaf",
            parent_task_object_id=node_task.cdb_object_id,
        )

        for process in [root, node, leaf]:
            self.assertEqual(
                process._get_root_process().cdb_process_id,
                root.cdb_process_id
            )

        volatile = Process()
        self.assertEqual(
            volatile._get_root_process(),
            None
        )

    def _create_wf(self, parent, **kwargs):
        wfargs = {
            "cdb_process_id": Process.new_process_id(),
        }
        wfargs.update(kwargs)

        if parent:
            ptask = SystemTask.Create(
                cdb_process_id=parent,
                task_id=Task.new_task_id(),
            )
            wfargs["parent_task_object_id"] = ptask.cdb_object_id

        return Process.Create(**wfargs)

    def test_TerminatedParents_none(self):
        root = self._create_wf(
            parent=None,
            status=10,
            title="root",
        )
        leaf = self._create_wf(
            parent=root.cdb_process_id,
            status=20,
            title="leaf",
        )
        self.assertEqual(leaf.TerminatedParents, [])

    def test_TerminatedParents(self):
        root = self._create_wf(
            parent=None,
            status=10,
            title="root",
        )
        p40 = self._create_wf(
            parent=root.cdb_process_id,
            status=40,
            title="p40",
        )
        p30 = self._create_wf(
            parent=p40.cdb_process_id,
            status=30,
            title="p30",
        )
        p20 = self._create_wf(
            parent=p30.cdb_process_id,
            status=20,
            title="p20",
        )
        leaf = self._create_wf(
            parent=p20.cdb_process_id,
            status=20,
            title="leaf",
        )
        self.assertEqual(
            leaf.TerminatedParents.title,
            ["p40", "p30", "p20"]
        )



class TestSuccessfulFlag(testcase.RollbackTestCase):
    "test handling of cdbwf_process.completing_ok flag"

    def test_new_process(self):
        "completing_ok flag is 1 after creating a new process"
        pr = operation(
            constants.kOperationNew,
            Process,
            cdb_objektart="cdbwf_process")
        self.assertEqual(pr.completing_ok, 1)

    def test_activate_process(self):
        "completing_ok flag is 1 when process is ready"
        pr = operation(
            constants.kOperationNew,
            Process,
            cdb_objektart="cdbwf_process")
        self.assertEqual(pr.completing_ok, 1)
        pr.Update(completing_ok=None,
                  subject_id="caddok",
                  subject_type="Person")
        self.assertEqual(pr.completing_ok, None)
        pr.activate_process()
        self.assertEqual(pr.completing_ok, 1)

    def test_cancel_process(self):
        "completing_ok flag is 0 when process is canceled"
        pr = operation(
            constants.kOperationNew,
            Process,
            cdb_objektart="cdbwf_process")
        pr.cancel_process()
        self.assertEqual(pr.completing_ok, 0)

    def test_dismiss_process(self):
        "completing_ok flag is 0 when process is dismissed"
        pr = operation(
            constants.kOperationNew,
            Process,
            cdb_objektart="cdbwf_process")
        pr.dismiss_process()
        self.assertEqual(pr.completing_ok, 0)


class TestActivateProcess(testcase.PlatformTestCase):
    """ Test the method Process.activate_process """

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    def test_activate_process(self, Components, set_state):
        """ The process is activated, the first task is activated """
        pr = Process()
        Components.return_value = [mock.Mock(spec=Task)]

        pr.activate_process()

        set_state.assert_called_with(pr, Process.EXECUTION)
        pr.Components[0].activate_task.assert_called_once_with()

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Constraints")
    def test_process_constraint_violated(self, Constraints, set_state):
        """ If a process constraint is violated, the process is not started """
        pr = Process()

        constraint = mock.Mock(spec=Constraint)
        constraint.check_violation.side_effect = Exception
        Constraints.return_value = [constraint]

        try:
            pr.activate_process()
        except Exception:
            excepted = True
        else:
            excepted = False

        assert excepted
        set_state.assert_not_called()

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    def test_task_canceled(self, Components, set_state):
        """ If the task is cancelled the process is closed """
        pr = Process(cdb_process_id="TEST")

        task = mock.Mock(spec=Task)
        Components.return_value = [task]
        Components[0].activate_task.side_effect = (
            exceptions.TaskCancelledException
        )

        pr.activate_process()

        set_state.assert_called_with(pr, Process.COMPLETED)

    def test_get_violated_process_start_preconditions(self):
        from cs.workflow.tasks import TaskDataIncompleteException
        a = mock.MagicMock(spec=Task, title="A")
        a.AbsolutePath.return_value = 1
        a.check_process_start_preconditions.side_effect = (
            TaskDataIncompleteException("foo")
        )
        b = mock.MagicMock(spec=Task, title="B")
        b.AbsolutePath.return_value = 2
        b.check_process_start_preconditions.side_effect = (
            TaskDataIncompleteException("bar")
        )
        p = mock.MagicMock(
            spec=processes.Process,
            AllTasks=[a, b],
        )

        self.assertEqual(
            processes.Process.get_violated_process_start_preconditions(p),
            "1 A: foo\n2 B: bar",
        )

    def test_check_process_start_preconditions_fail(self):
        "raises if preconditions are not fulfilled"
        p = mock.MagicMock(spec=processes.Process)
        p.get_violated_process_start_preconditions.return_value = "foo"

        with self.assertRaises(processes.util.ErrorMessage) as err:
            processes.Process.check_process_start_preconditions(p)

        self.assertEqual(
            str(err.exception),
            "Der Workflow kann nicht gestartet werden, da die nachfolgenden "
            "Aufgaben nicht korrekt definiert sind:\\nfoo",
        )

    def test_check_process_start_preconditions(self):
        "check preconditions"
        p = mock.MagicMock(spec=processes.Process)
        p.get_violated_process_start_preconditions.return_value = ""

        self.assertIsNone(
            processes.Process.check_process_start_preconditions(p)
        )


class TestCancelProcess(testcase.PlatformTestCase):
    """ Test the method Process.cancel_process """

    @mock.patch.object(Process, "get_cancel_info_setting", return_value=False)
    @mock.patch("cs.workflow.processes.Process._cancel_info_messages")
    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    @mock.patch("cs.workflow.processes.Process.ProcessCompletion", spec=Task)
    def test_without_process_completion_no_info_cancel(
            self, ProcessCompletion, Components, set_state,
            _cancel_info_messages, get_cancel_info_setting
    ):
        """
        If the process doesn't have a completion task, it will be canceled,
        info messages are not deactivated.
        """
        task = mock.Mock(spec=Task)
        Components.Query.return_value = [task]

        ProcessCompletion.activate_task.side_effect = (
            exceptions.TaskClosedException
        )

        pr = Process()
        pr.cancel_process()

        task.cancel_task.assert_called_once_with("")
        set_state.assert_called_with(pr, Process.FAILED, comment="")
        get_cancel_info_setting.assert_called_with()
        _cancel_info_messages.assert_not_called()

    @mock.patch.object(Process, "get_cancel_info_setting", return_value=True)
    @mock.patch("cs.workflow.processes.Process._cancel_info_messages")
    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    @mock.patch("cs.workflow.processes.Process.ProcessCompletion", spec=Task)
    def test_without_process_completion_info_cancel(
            self, ProcessCompletion, Components, set_state,
            _cancel_info_messages, get_cancel_info_setting
    ):
        """
        If the process doesn't have a completion task, it will be canceled,
        info messages outside of the completion task are deactivated.
        """
        task = mock.Mock(spec=Task)
        Components.Query.return_value = [task]

        ProcessCompletion.activate_task.side_effect = (
            exceptions.TaskClosedException
        )

        pr = Process()
        pr.cancel_process()

        task.cancel_task.assert_called_once_with("")
        set_state.assert_called_with(pr, Process.FAILED, comment="")
        get_cancel_info_setting.assert_called_with()
        _cancel_info_messages.assert_called_with()

    @mock.patch.object(Process, "get_cancel_info_setting", return_value=False)
    @mock.patch("cs.workflow.processes.Process._cancel_info_messages")
    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    @mock.patch(
        "cs.workflow.processes.Process.ProcessCompletion",
        spec=TaskGroup
    )
    def test_with_process_completion_no_info_cancel(
            self, ProcessCompletion, Components, set_state,
            _cancel_info_messages, get_cancel_info_setting
    ):
        "The completion task is started, info messages are not deactivated."
        task = mock.Mock(spec=Task)
        Components.Query.return_value = [task]

        ProcessCompletion.status = TaskGroup.NEW.status
        ProcessCompletion.NEW = mock.Mock()
        ProcessCompletion.NEW.status = TaskGroup.NEW.status

        pr = Process()
        pr.cancel_process()

        task.cancel_task.assert_called_once_with("")
        assert not set_state.called
        assert ProcessCompletion.activate_task.called
        get_cancel_info_setting.assert_called_with()
        _cancel_info_messages.assert_not_called()

    @mock.patch.object(Process, "get_cancel_info_setting", return_value=True)
    @mock.patch("cs.workflow.processes.Process._cancel_info_messages")
    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.Components")
    @mock.patch(
        "cs.workflow.processes.Process.ProcessCompletion",
        spec=TaskGroup
    )
    def test_with_process_completion_info_cancel(
            self, ProcessCompletion, Components, set_state,
            _cancel_info_messages, get_cancel_info_setting
    ):
        "The completion task is started, info messages are deactivated."
        task = mock.Mock(spec=Task)
        Components.Query.return_value = [task]

        ProcessCompletion.status = TaskGroup.NEW.status
        ProcessCompletion.NEW = mock.Mock()
        ProcessCompletion.NEW.status = TaskGroup.NEW.status

        pr = Process()
        pr.cancel_process()

        task.cancel_task.assert_called_once_with("")
        set_state.assert_not_called()
        ProcessCompletion.activate_task.assert_called_once_with()
        get_cancel_info_setting.assert_called_with()
        _cancel_info_messages.assert_called_with()


class TestCloseProcess(testcase.PlatformTestCase):
    """ Test the method Process.close_process """

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch("cs.workflow.processes.Process.ProcessCompletion", spec=Task)
    def test_without_process_completion(self, ProcessCompletion, set_state):
        """
        If the process doesn't have a completion task, it will be closed
        """
        ProcessCompletion.activate_task.side_effect = (
            exceptions.TaskClosedException
        )

        pr = Process()
        pr.close_process()

        set_state.assert_called_with(pr, Process.COMPLETED)

    @mock.patch("cs.workflow.processes.set_state")
    @mock.patch(
        "cs.workflow.processes.Process.ProcessCompletion",
        spec=TaskGroup
    )
    def test_with_process_completion(self, ProcessCompletion, set_state):
        """ The completion task is started """
        ProcessCompletion.status = TaskGroup.NEW.status
        ProcessCompletion.NEW = mock.Mock()
        ProcessCompletion.NEW.status = TaskGroup.NEW.status

        pr = Process()
        pr.close_process()

        set_state.assert_not_called()
        ProcessCompletion.activate_task.assert_called_once_with()


class TestActivateTasks(testcase.PlatformTestCase):
    """ Test the method Process.activate_tasks """

    @mock.patch("cs.workflow.processes.Process.Components")
    def test_activate_tasks(self, Components):
        """ When the process is activated, the first task is activated """
        task = mock.Mock(spec=Task)
        Components.return_value = [task]

        pr = Process()
        pr.activate_tasks()

        Components[0].activate_task.assert_called_once_with()


class TestPropagateCancel(testcase.PlatformTestCase):
    """ Test the method Process.propagate_cancel """

    @mock.patch("cs.workflow.processes.Process.cancel_process")
    @mock.patch("cs.workflow.processes.Process.ProcessCompletion", spec=Task)
    def test_without_process_completion(
            self, ProcessCompletion, cancel_process
    ):
        """
        If the process doesn't have a completion task, it will be canceled
        """
        ProcessCompletion.activate_task.side_effect = (
            exceptions.TaskClosedException
        )

        pr = Process()
        pr.propagate_cancel(mock.sentinel.task, mock.sentinel.comment)

        cancel_process.assert_called_with(mock.sentinel.comment)

    @mock.patch(
        "cs.workflow.processes.Process.ProcessCompletion",
        spec=TaskGroup
    )
    def test_with_process_completion(self, ProcessCompletion):
        """ The completion task is started """
        ProcessCompletion.status = TaskGroup.NEW.status
        ProcessCompletion.NEW = mock.Mock()
        ProcessCompletion.NEW.status = TaskGroup.NEW.status

        pr = Process(cdb_process_id="TEST")
        pr.propagate_cancel(mock.sentinel.task, mock.sentinel.comment)

        ProcessCompletion.activate_task.assert_called_once_with()


class TestPropagateDone(testcase.PlatformTestCase):
    """ Test the method Process.propagate_done """

    @mock.patch(
        "cs.workflow.taskgroups.TaskGroup.has_finish_option",
        return_value=False
    )
    def test_propagate_done(self, has_finish_option):
        """ When a task is closed, the next one is activated """
        task = mock.Mock(spec=Task)
        task.Next.return_value = task

        pr = Process()
        pr.close_process = mock.Mock()

        pr.propagate_done(task)

        task.Next.activate_task.assert_called_once_with()

    def test_propagate_done_finished(self):
        """ If there are no more tasks, the process is closed """
        task = mock.Mock(spec=Task)
        task.Next = None

        pr = Process()
        pr.close_process = mock.Mock()

        pr.propagate_done(task)

        pr.close_process.assert_called_once_with()

    @mock.patch(
            "cs.workflow.taskgroups.TaskGroup.has_finish_option",
            return_value=False
    )
    def test_propagate_done_cancelled(self, TaskGroup):
        """ If the next Task is cancelled the process is closed """
        task = mock.Mock(spec=Task)
        task.Next.return_value = task

        task.Next.activate_task.side_effect = exceptions.TaskCancelledException

        pr = Process()
        pr.close_process = mock.Mock()

        pr.propagate_done(task)

        pr.close_process.assert_called_once_with()

    @mock.patch(
        "cs.workflow.taskgroups.TaskGroup.has_finish_option",
        return_value=False
    )
    def test_propagate_done_closed(self, has_finish_option):
        """ If the next Task is closed the the next one is activated"""
        task = mock.Mock(spec=Task)
        task.Next.return_value = task
        next_task = task.Next

        next_task.activate_task.side_effect = exceptions.TaskClosedException
        next_task.Next.return_value = task

        pr = Process()
        pr.propagate_done(task)

        next_task.Next.activate_task.assert_called_once_with()


class TestMakeAttachmentsBriefcase(testcase.PlatformTestCase):
    """ Test the method make_attachments_briefcase """

    @mock.patch.object(processes.briefcases, "Briefcase")
    @mock.patch.object(processes.briefcases, "BriefcaseLink")
    def test_without_attachments(
            self, BriefcaseLink, Briefcase
    ):
        """ If it doesn't exits, the attachment briefcase is created """
        pr = mock.Mock(spec=Process, AttachmentsBriefcase=None)
        Process.make_attachments_briefcase(pr)

        Briefcase.Create.assert_called_once_with(
            cdb_process_id=pr.cdb_process_id,
            briefcase_id=0,
            name="Anhänge")
        BriefcaseLink.Create.assert_called_once_with(
            cdb_process_id=pr.cdb_process_id,
            task_id='',
            briefcase_id=0,
            iotype=briefcases.IOType.info.value,  # @UndefinedVariable
            extends_rights=0)

    @mock.patch.object(processes.briefcases, "Briefcase")
    @mock.patch.object(processes.briefcases, "BriefcaseLink")
    def test_with_attachments(
            self, BriefcaseLink, Briefcase
    ):
        """ If it does exits, the attachment briefcase isn't created """
        pr = mock.Mock(spec=Process, AttachmentsBriefcase=1)
        Process.make_attachments_briefcase(pr)
        Briefcase.Create.assert_not_called()
        BriefcaseLink.Create.assert_not_called()
