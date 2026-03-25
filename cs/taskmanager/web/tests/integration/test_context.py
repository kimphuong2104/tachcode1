#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import testcase
from cs.taskmanager.web.tests.integration import load_json, make_request
from cs.taskmanagertest import TestTaskOLC as TaskOLC

TEST_TASK_NAME = "context_integration_task"
PARENT_OBJECT_ID = "46b8ae61-9ee5-11ec-93ff-334b6053520d"  # Leaf (武士)


def setUpModule():
    testcase.run_level_setup()


class TasksContext(testcase.RollbackTestCase):
    """
    Tests the backend response for resolving the context.
    """

    def test_resolve_context(self):
        task = TaskOLC.Create(
            name=TEST_TASK_NAME,
            cdb_object_id=TEST_TASK_NAME,
            parent_object_id=PARENT_OBJECT_ID,
        )
        response = make_request(
            "/internal/tasks/context/cs_tasks_test_olc/{}".format(task.cdb_object_id),
            {},
        )
        self.maxDiff = None
        self.assertDictEqual(load_json("context_response"), response.json)
