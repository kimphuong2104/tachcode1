#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock, unittest

from cdb import auth
from cdb import testcase

from cs.workflow import briefcases
from cs.workflow import task_external_process
from cs.workflow.processes import Process
from cs.workflow.tasks import ApprovalTask
from cs.workflow.tasks import ExaminationTask
from cs.workflow.tasks import ExecutionTask
from cs.workflow.tasks import FilterParameter
from cs.workflow.tasks import SystemTask
from cs.workflow.systemtasks import InfoMessage
from cs.workflow import tasks_plugin

TARGET_20 = {
    'status': 20,
    'color': u'#ADC902',
    'priority': 10,
    "icon": "/resources/icons/byname/cdbwf_status?status=20",
    'label': u'Abgeschlossen',
    'dialog': {
        u'zielstatus': u'Abgeschlossen',
        u'zielstatus_int': 20,
    },
}
TARGET_30 = {
    'status': 30,
    'color': u'#D00000',
    'priority': 20,
    "icon": "/resources/icons/byname/cdbwf_status?status=30",
    'label': u'Abgelehnt',
    'dialog': {
        u'zielstatus': u'Abgelehnt',
        u'zielstatus_int': 30,
    },
}


def setup_module():
    testcase.run_level_setup()


class WorkflowTaskWithCsTasks(unittest.TestCase):
    def test_delegate_call_to_extension_obj(self):
        ext = mock.Mock()
        obj = mock.Mock(
            spec=tasks_plugin.WorkflowTaskWithCsTasks,
            getExtensionObject=mock.Mock(return_value=ext),
        )

        with mock.patch.object(tasks_plugin.WorkflowBaseWithCsTasks,
                               "csTasksDelegate") as base:
            self.assertEqual(
                tasks_plugin.WorkflowTaskWithCsTasks.csTasksDelegate(
                    obj, "foo"),
                ext.csTasksDelegate.return_value,
            )

        base.assert_not_called()
        ext.csTasksDelegate.assert_called_once_with("foo")

    def test_no_extension_obj(self):
        obj = mock.Mock(
            spec=tasks_plugin.WorkflowTaskWithCsTasks,
            getExtensionObject=mock.Mock(return_value=None),
        )

        with mock.patch.object(tasks_plugin.WorkflowBaseWithCsTasks,
                               "csTasksDelegate") as base:
            tasks_plugin.WorkflowTaskWithCsTasks.csTasksDelegate(obj, "foo")

        base.assert_called_once_with("foo")

    def test_extension_obj_doesnt_implement(self):
        obj = mock.Mock(
            spec=tasks_plugin.WorkflowTaskWithCsTasks,
            getExtensionObject=mock.Mock(return_value="has no methods"),
        )

        with mock.patch.object(tasks_plugin.WorkflowBaseWithCsTasks,
                               "csTasksDelegate") as base:
            tasks_plugin.WorkflowTaskWithCsTasks.csTasksDelegate(obj, "foo")

        base.assert_called_once_with("foo")


class TasksPluginBaseTestCase(testcase.RollbackTestCase):
    __classes__ = None  # to be defined by subclasses

    def _process(self, vals=None):
        pvals = {
            "cdb_process_id": Process.new_process_id(),
            "is_template": 0,
            "status": 10,
            "started_by": auth.persno,
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_objektart": "cdbwf_process",
        }

        if vals:
            pvals.update(vals)

        self.process = Process.Create(**pvals)

    def _tasks(self, vals=None):
        vals = vals or {}
        vals["cdb_process_id"] = self.process.cdb_process_id

        for cls in self.__classes__:
            yield self._task(cls, vals)

    def _task(self, cls, vals):
        raise RuntimeError("to be defined by subclass")

    def _briefcase(self, task_id, mode, vals, content):
        vals = vals or {}
        vals.update({
            "cdb_process_id": self.process.cdb_process_id,
            "briefcase_id": briefcases.Briefcase.new_briefcase_id(),
            "name": "{} {}".format("local" if task_id else "global", mode),
        })
        briefcase = briefcases.Briefcase.Create(**vals)
        briefcases.BriefcaseLink.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=task_id or "",
            briefcase_id=vals["briefcase_id"],
            iotype=briefcases.IOType[mode].value,
            extends_rights=1,
        )

        if content:
            briefcases.FolderContent.Create(
                cdb_folder_id=briefcase.cdb_object_id,
                cdb_content_id=content.cdb_object_id,
            )

        return briefcase

    def _resolve(self, briefcase, info, content=None):
        return {
            "relshipName": ("CsTasksInfoBriefcases" if info
                            else "CsTasksEditBriefcases"),
            "name": briefcase.GetDescription(),
            "mode": "info" if info else "edit",
            "references": [c.cdb_object_id for c in content] if content else[],
        }


class TestInteractiveTasks(TasksPluginBaseTestCase):
    __classes__ = [ApprovalTask, ExaminationTask, ExecutionTask]
    __targets__ = {
        "cdbwf_task_approval": [TARGET_20, TARGET_30],
        "cdbwf_task_examination": [TARGET_20, TARGET_30],
        "cdbwf_task_execution": [TARGET_20],
    }

    def _task(self, cls, vals):
        vals["task_id"] = cls.new_task_id()
        return cls.Create(**vals)

    def test_csTasksDelegate_get_default_ok(self):
        self._process()

        for task in self._tasks():
            self.assertEqual(
                task.csTasksDelegate_get_default(),
                (auth.persno, "Person", auth.name))

    def test_csTasksDelegate_get_default_invalid_user(self):
        self._process({"started_by": "Graf Zahl"})

        for task in self._tasks():
            self.assertEqual(task.csTasksDelegate_get_default(), ("", "", ""))

    def test_csTasksDelegate_get_default_no_user(self):
        self._process({"started_by": None})

        for task in self._tasks():
            self.assertEqual(task.csTasksDelegate_get_default(), ("", "", ""))

    def test_getCsTasksProceedData(self):
        self._process()

        for task in self._tasks({"status": 10}):
            self.assertEqual(
                task.getCsTasksNextStatuses(),
                self.__targets__[task.cdb_classname]
            )


class TestInfoMessage(TasksPluginBaseTestCase):
    __classes__ = [InfoMessage]

    def _task(self, cls, vals):
        vals.update({
            "task_id": SystemTask.new_task_id(),
            "task_definition_id": "7f87cf00-f838-11e2-b1b5-082e5f0d3665",
            "status": 10,
        })
        systask = SystemTask.Create(**vals)
        for n, v in [("subject_id", auth.persno), ("subject_type", "Person")]:
            FilterParameter.Create(
                cdb_process_id=systask.cdb_process_id,
                task_id=systask.task_id,
                rule_name="",
                name=n,
                value=v)

        task_external_process.run(systask.cdb_process_id, systask.task_id)
        return cls.KeywordQuery(
            cdb_process_id=systask.cdb_process_id,
            task_id=systask.task_id)[0]

    def test_csTasksDelegate_get_default_ok(self):
        self._process()

        for task in self._tasks():
            self.assertEqual(
                task.csTasksDelegate_get_default(),
                (auth.persno, "Person", auth.name))

    def test_csTasksDelegate_get_default_invalid_user(self):
        self._process({"started_by": "Graf Zahl"})

        for task in self._tasks():
            self.assertEqual(task.csTasksDelegate_get_default(), ("", "", ""))

    def test_csTasksDelegate_get_default_no_user(self):
        self._process({"started_by": None})

        for task in self._tasks():
            self.assertEqual(task.csTasksDelegate_get_default(), ("", "", ""))
