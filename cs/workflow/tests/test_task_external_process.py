#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from cdb import testcase
from mock import Mock, patch, MagicMock, PropertyMock
from cs.workflow import task_external_process
from cs.workflow import systemtasks


class TestUtility(testcase.RollbackTestCase):
    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    def test_refuse_task(self, mock_ByKeys):
        task = mock_ByKeys.return_value
        task_external_process.refuse_task(task, "test")
        task.addProtocol.assert_called_with(
            'Die Systemaufgabe wurde abgelehnt: test',
            'CANCEL'
        )
        task.refuse_task.assert_called_with("test")

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    def test_close_process(self, mock_ByKeys):
        task = mock_ByKeys.return_value
        other = MagicMock()
        task.Process.AllComponents.Query.return_value = [other]
        task_external_process.close_process(task)
        task.Update.assert_called()
        task.addProtocol.assert_called_with(
            'Der Workflow wurde abgeschlossen.',
            'DONE'
        )
        task.Process.close_process.assert_called()
        other.Update.assert_called()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    def test_cancel_process(self, mock_ByKeys):
        task = mock_ByKeys.return_value
        task_external_process.cancel_process(task, "test")
        task.addProtocol.assert_called_with(
            'Der Workflow wurde abgebrochen: test',
            'CANCEL'
        )
        task.Process.cancel_process.assert_called_with("test")

    def test_validate_parameters(self):
        task = MagicMock()

        required_params = PropertyMock(return_value=[])
        required_params.name.return_value = []
        task.Definition.Parameters.Query = required_params
        task_external_process.validate_parameters(task, {"key": "value"})

        required_params.return_value = ["missing"]
        required_params.name.return_value = ["missing"]
        with self.assertRaises(Exception):
            task_external_process.validate_parameters(task, {"key": "value"})

    def test_validate_parameters_run_loop(self):
        from cs.workflow.tasks import SystemTask
        task = SystemTask.Create(
            cdb_process_id="TEST",
            task_id="TEST",
            task_definition_id="2df381c0-1416-11e9-823e-605718ab0986",
        )

        with self.assertRaises(Exception) as exc:
            task_external_process.validate_parameters(
                task,
                {}
            )

        self.assertEqual(len(exc.exception.args), 3)
        self.assertEqual(
            exc.exception.args[:2],
            (
                "cdbwf_missing_parameters",
                u": ",
            )
        )
        self.assertEqual(
            set(exc.exception.args[2].split(", ")),
            set([u"current_cycle", u"max_cycles"])
            # not success_condition, failure_condition
        )


class TestRun(testcase.RollbackTestCase):
    @patch('cs.workflow.tasks.SystemTask.ByKeys', return_value=None)
    @patch('cs.workflow.wfqueue.getLogger')
    def test_no_task(self, getLogger, _):
        # run system task logic
        task_external_process.run('proc', 'task')

        getLogger.return_value.error.assert_called_with(
            "task %s:%s not found",
            "proc",
            "task"
        )

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    def test_no_task_definition(self, mock_ByKeys):
        task = mock_ByKeys.return_value
        task.Definition = None

        # run system task logic
        task_external_process.run('proc', 'task')

        task.refuse_task.assert_called_once()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_run_sys_task_without_objfilters(self, mock_get_obj, mock_ByKeys):
        # mock return value of getObjectByName as another method
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)
        task.ObjectFilters = None

        # run system task logic
        task_external_process.run('proc', 'task')

        mock_get_obj.return_value.assert_called_with(
            task=task,
            content={'info': 'info', 'edit': 'edit'},
            param='val'
        )

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_run_sys_task_with_objfilters(self, mock_get_obj, mock_ByKeys):
        # mock return value of getObjectByName as another method
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)
        self.set_mock_object_filters(task)
        # run system task logic
        task_external_process.run('proc', 'task')

        mock_get_obj.return_value.assert_called_with(
            task=task,
            content={'info': [], 'edit': []},
            param='val'
        )

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_close_task_async(self, mock_get_obj, mock_ByKeys):
        # mock return value of getObjectByName as another method
        mock_get_obj.return_value = MagicMock()
        mock_get_obj.return_value.side_effect = systemtasks.CloseTaskAsynchronously
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)

        # run system task logic
        task_external_process.run('proc', 'task')

        task.addProtocol.assert_called_once()

        # make sure that the task is untouched
        # in case of CloseTaskAsynchronously exception
        task.close_task.assert_not_called()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_close_task_refused_except(self, mock_get_obj, mock_ByKeys):
        def except_side_effect(task, content, **params):
            raise systemtasks.TaskRefusedException()

        # mock return value of getObjectByName as another method
        mock_get_obj.return_value = MagicMock()
        task_implementation = mock_get_obj.return_value
        task_implementation.side_effect = except_side_effect
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)

        # run system task logic
        task_external_process.run('proc', 'task')

        task.refuse_task.assert_called_once()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_task_canceled_except(self, mock_get_obj, task):
        # mock return value of getObjectByName as another method
        mock_get_obj.return_value.side_effect = systemtasks.TaskCancelledException
        self.set_up_mockup_task(task.return_value)
        task_external_process.run('proc', 'task')
        task.return_value.cancel_task.assert_called_once()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_process_abort_except(self, mock_get_obj, mock_ByKeys):
        # mock return value of getObjectByName as another method
        mock_get_obj.return_value = MagicMock()
        mock_get_obj.return_value.side_effect = systemtasks.ProcessAbortedException
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)

        # run system task logic
        task_external_process.run('proc', 'task')

        task.Process.cancel_process.assert_called_once()

    @patch('cs.workflow.tasks.SystemTask.ByKeys')
    @patch('cdb.tools.getObjectByName')
    def test_simple_exception(self, mock_get_obj, mock_ByKeys):
        # mock return value of getObjectByName as another method
        mock_get_obj.return_value.side_effect = Exception
        task = mock_ByKeys.return_value
        self.set_up_mockup_task(task)

        with self.assertRaises(Exception):
            task_external_process.run('proc', 'task')

    def set_up_mockup_task(self, task):
        def mirror_side_effect(arg):
            return arg
        # mock task properties needed for this code flow
        task.uses_global_maps = False
        task.getContent.side_effect = mirror_side_effect
        task.ObjectFilters = None
        param_obj = Mock(value="val")
        # set name explicitely
        param_obj.name = "param"
        task.Parameters = [param_obj]
        task.Definition.Parameters.Query.return_value = []

    def set_mock_object_filters(self, task):
        mock_id = '91dd3340-ea12-11e2-8ad1-082e5f0d3665'
        task.FilterParams = {}
        task.FilterParams[mock_id] = {"filter_param": "val2"}
        rule_wrapper = Mock(cdb_object_id=mock_id)
        rule_wrapper.Rule = Mock()
        rule_wrapper.Rule.match = MagicMock(return_value=False)
        task.ObjectFilters = [rule_wrapper]
