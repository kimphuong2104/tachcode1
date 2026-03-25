#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import unittest

import pytest
from cdb import testcase
from cdb.objects.references import ObjectCollection
from mock import PropertyMock, patch

from cs.pcs.projects import status_updates
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.tests import common


@pytest.mark.integration
class TestTaskIntegration(testcase.RollbackTestCase):
    def test_discard_task(self):
        "E070247: discarding a task may not change target dates"
        pstart = datetime.date(2022, 12, 1)

        project = common.generate_project(
            start_time_fcast=pstart,
            end_time_fcast=pstart,
        )
        task = common.generate_task(
            project,
            "B",
            automatic=1,
            days_fcast=4,
            constraint_type="4",  # start no earlier than
            constraint_date=pstart,
        )

        end = datetime.date(2022, 12, 6)

        def get_task_dates():
            task.Reload()
            return (task.start_time_fcast, task.end_time_fcast)

        self.assertEqual(get_task_dates(), (pstart, end))
        task.ChangeState(Task.DISCARDED.status)
        self.assertEqual(get_task_dates(), (pstart, end))


@pytest.mark.unit
class TestTask(unittest.TestCase):
    @staticmethod
    def get_tasks():
        return ObjectCollection(Task, "cdbpcs_task", "status=0")

    @patch.object(status_updates.Checklist, "Reset")
    def test__reset_checklists(self, Reset):
        "Reset checklists"
        cl1 = status_updates.Checklist()
        cl1.status = 20
        cl2 = status_updates.Checklist()
        cl2.status = 180
        with patch.object(
            Task, "Checklists", new_callable=PropertyMock, return_value=[cl1, cl2]
        ):
            task = Task()
            status_updates.reset_checklists([task])
        Reset.assert_called_once()

    def test__reset_start_time_act(self):
        "Set start_time_act empty"
        tasks = self.get_tasks()
        with patch.object(tasks, "Update"):
            status_updates.reset_start_time_act(tasks)
            tasks.Update.assert_called_once_with(start_time_act="", days_act="")

    @patch.object(status_updates, "datetime")
    def test__set_start_time_act_to_now(self, datetime):
        "Set start_time_act to now"
        tasks = self.get_tasks()

        with patch.object(tasks, "Update"):
            status_updates.set_start_time_act_to_now(tasks)
            tasks.Update.assert_called_once_with(
                start_time_act=datetime.date.today.return_value,
                days_act="",
            )

    def test__reset_end_time_act(self):
        "Set end_time_act empty"
        tasks = self.get_tasks()
        with patch.object(tasks, "Update"):
            status_updates.reset_end_time_act(tasks)
            tasks.Update.assert_called_once_with(end_time_act="", days_act="")

    @patch.object(status_updates, "datetime")
    def test__set_end_time_act_to_now(self, datetime):
        "Set end_time_act to now"
        tasks = self.get_tasks()

        with patch.object(tasks, "Update"):
            status_updates.set_end_time_act_to_now(tasks)
            tasks.Update.assert_called_once_with(
                end_time_act=datetime.date.today.return_value,
            )

    def test__set_percentage_to_0(self):
        "Set percent completion to 0"
        tasks = self.get_tasks()
        with patch.object(tasks, "Update"):
            status_updates.set_percentage_to_0(tasks)
            tasks.Update.assert_called_once_with(percent_complet=0)

    def test__set_percentage_to_1(self):
        "Set percent completion to 1"
        tasks = self.get_tasks()
        with patch.object(tasks, "Update"):
            status_updates.set_percentage_to_1(tasks)
            tasks.Update.assert_called_once_with(percent_complet=1)

    def test__set_percentage_to_100(self):
        "Set percent completion to 100"
        tasks = self.get_tasks()
        with patch.object(tasks, "Update"):
            status_updates.set_percentage_to_100(tasks)
            tasks.Update.assert_called_once_with(percent_complet=100)


if __name__ == "__main__":
    unittest.main()
