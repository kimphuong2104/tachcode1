#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import testcase
from cdb.objects.operations import operation
from cs.actions import Action

from cs.pcs.projects.tests import common

TASK_ID = "TEST_ACTION_TASK"
PID_A = "TEST_PROJECT_A"
PID_B = "TEST_PROJECT_B"


@pytest.mark.integration
class ProjectTaskActionsInteractionIntegrationTestCase(testcase.RollbackTestCase):
    """
    Test Interactions between Actions and Projects and/or Tasks.
    """

    def test_create_action_on_project(self):
        # create project with baseline
        project = common.generate_project()
        # create action on project
        action = common.generate_action(project)
        # check if only one action exists
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 1

    def test_create_action_on_project_task(self):
        # create project
        project = common.generate_project()
        # create task on project
        task = common.generate_task(project, TASK_ID)
        # create action on project task
        action = common.generate_action(task)
        # create baseline of project
        common.generate_baseline_of_project(project)
        # check if only one action exists
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 1

    def test_move_action_on_project(self):
        # create project A with baseline
        pA = common.generate_project(cdb_project_id=PID_A)
        # create action on project A
        action = common.generate_action(pA)
        # create project B
        pB = common.generate_project(cdb_project_id=PID_B)
        # modify action to be part of B
        kwargs = {"cdb_project_id": pB.cdb_project_id}
        mod_action = operation("CDB_Modify", action, **kwargs)
        # check if only one action exists
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 1
        # check if action now is part of project B
        assert mod_action.cdb_project_id == pB.cdb_project_id

    def test_move_action_on_project_task(self):
        # create project A with baseline
        pA = common.generate_project(cdb_project_id=PID_A)
        # create action on project A
        action = common.generate_action(pA)
        # create project B
        pB = common.generate_project(cdb_project_id=PID_B)
        # create task on project B
        taskB = common.generate_task(pB, TASK_ID)
        # create baseline of project B
        common.generate_baseline_of_project(pB)
        # modify action to be part of task of project B
        kwargs = {
            "cdb_project_id": taskB.cdb_project_id,
            "task_id": taskB.task_id,
        }
        mod_action = operation("CDB_Modify", action, **kwargs)
        # check if only one action exists
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 1
        # check if action now is part of project B
        assert (
            mod_action.cdb_project_id == taskB.cdb_project_id
            and mod_action.task_id == taskB.task_id
        )

    def test_delete_project_with_action(self):
        # create project with baseline
        project = common.generate_project()
        # create action on project
        action = common.generate_action(project)
        # delete project
        operation("CDB_Delete", project)
        # check if action does not exist
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 0

    def test_delete_project_task_with_action(self):
        # create project A
        pA = common.generate_project(cdb_project_id=PID_A)
        # create action on project A
        action = common.generate_action(pA)
        # create project B
        pB = common.generate_project(cdb_project_id=PID_B)
        # create task on project B
        taskB = common.generate_task(pA, TASK_ID)
        # create baseline of project B
        common.generate_baseline_of_project(pB)
        # modify action to be part of project B
        kwargs = {
            "cdb_project_id": taskB.cdb_project_id,
            "task_id": taskB.task_id,
        }
        operation("CDB_Modify", action, **kwargs)
        # delete task of project B
        operation("CDB_Delete", taskB)
        # check if action does not exist
        assert len(Action.KeywordQuery(cdb_object_id=action.cdb_object_id)) == 0


if __name__ == "__main__":
    unittest.main()
