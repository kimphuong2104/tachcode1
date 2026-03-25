# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import unittest

import mock
import pytest

from cdb import testcase
from cs.pcs.costs import tasks


@pytest.mark.unit
class TestTasksSignals(testcase.RollbackTestCase):
    def test_checkAllParentTasksOfNewTaskForCostAllocation_empty_args(self):
        "Return remove_cost_allocation=False if no sig_args are given"
        self.assertDictEqual(
            {"remove_cost_allocation": False},
            tasks.checkAllParentTasksOfNewTaskForCostAllocation({}),
        )

    def test_checkAllParentTasksOfNewTaskForCostAllocation_no_parent(self):
        "Return remove_cost_allocation=False if param target_parent not a Task"
        sig_args = {"target_parent": "foo"}
        self.assertDictEqual(
            {"remove_cost_allocation": False},
            tasks.checkAllParentTasksOfNewTaskForCostAllocation(sig_args),
        )

    def test_checkAllParentTasksOfNewTaskForCostAllocation(self):
        """
        Return remove_cost_allocation=True if target_parent or any of its
        parents have allocated costs
        """
        # mock a task and one of its parent tasks with allocated costs
        mock_task = mock.MagicMock(spec=tasks.Task)
        mock_task.costsAreAllocated.return_value = False
        mock_parent_task = mock.MagicMock(spec=tasks.Task)
        mock_parent_task.costsAreAllocated.return_value = True
        mock_task.AllParentTasks = [mock_parent_task]
        sig_args = {"target_parent": mock_task}
        self.assertDictEqual(
            {"remove_cost_allocation": True},
            tasks.checkAllParentTasksOfNewTaskForCostAllocation(sig_args),
        )

    def test_determineChangesForNewTaskFromTemplate_empty_args(self):
        "Return empty dict of changes if no sig_args are given"
        self.assertDictEqual({}, tasks.determineChangesForNewTaskFromTemplate({}))

    def test_determineChangesForNewTaskFromTemplate_no_remove(self):
        "Return empty dict of changes if param remove_cost_allocation not given"
        sig_args = {
            "params": {},
            "new_task": "foo",
        }
        self.assertDictEqual({}, tasks.determineChangesForNewTaskFromTemplate(sig_args))

    def test_determineChangesForNewTaskFromTemplate_no_new_task(self):
        "Return empty dict of changes if given new_task is not a Task"
        sig_args = {
            "params": {"remove_cost_allocation": True},
            "new_task": "not_a_task",
        }
        self.assertDictEqual({}, tasks.determineChangesForNewTaskFromTemplate(sig_args))

    def test_determineChangesForNewTaskFromTemplate_new_task_not_allocated(self):
        "Return empty dict of changes if given new_task has no cost allocation"
        mock_task = mock.MagicMock(spec=tasks.Task)
        mock_task.costsAreAllocated.return_value = False
        sig_args = {
            "params": {"remove_cost_allocation": True},
            "new_task": mock_task,
        }
        self.assertDictEqual({}, tasks.determineChangesForNewTaskFromTemplate(sig_args))

    def test_determineChangesForNewTaskFromTemplate(self):
        "Return dict of changes if given new_task has cost allocation"
        mock_task = mock.MagicMock(spec=tasks.Task)
        mock_task.costsAreAllocated.return_value = True
        sig_args = {
            "params": {"remove_cost_allocation": True},
            "new_task": mock_task,
        }
        self.assertDictEqual(
            {
                "costs_allocated": False,
                "hourly_rate": None,
                "currency_object_id": None,
                "costtype_object_id": None,
                "costcenter_object_id": None,
                "currency_name": None,
            },
            tasks.determineChangesForNewTaskFromTemplate(sig_args),
        )


if __name__ == "__main__":
    unittest.main()
