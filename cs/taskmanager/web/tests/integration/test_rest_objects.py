#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest

from cs.taskmanager.web.tests.integration.rest_helpers import RESTSmokeTestBase
from cs.taskmanager.web.tests.integration.util import (
    create_read_status,
    create_task_tag,
)

PERSNO = "caddok"


@pytest.mark.dependency(name="integration", depends=["cs.taskmanager"])
class TaskmanagerRestObjects(RESTSmokeTestBase):
    # All methods forbidden
    def test_tasks_column(self):
        self.rest_all_forbidden("tasks_column", "01e638a1-3dec-11e6-b6df-00aa004d0001")

    # All methods forbidden
    def test_tasks_context(self):
        self.rest_all_forbidden("tasks_context", "cs_tasks_test_olc")

    # All methods forbidden
    def test_cs_tasks_user_view(self):
        self.rest_all_forbidden(
            "cs_tasks_user_view", "8468ff8f-95d0-11e8-960a-68f7284ff046"
        )

    # Only GET
    def test_tasks_attribute(self):
        self.rest_get_only(
            "tasks_attribute",
            "7b2aae40-9880-11e7-aec5-5cc5d4123f3b",
            "cs_tasks_attribute",
        )

    # Only GET
    def test_tasks_class(self):
        self.rest_get_only(
            "tasks_class", "Test~20Task~20~28Custom~20Status~20Op~29", "cs_tasks_class"
        )

    # Only GET
    def test_cs_tasks_context_tree(self):
        self.rest_get_only(
            "cs_tasks_context_tree", "Task~20OLC~20Context", "cs_tasks_context_tree"
        )

    # Only GET
    def test_cs_tasks_context_tree_relships(self):
        self.rest_get_only(
            "cs_tasks_context_tree_relships",
            "f3aecd54-9620-11ec-b2b5-4146bd21e48d",
            "cs_tasks_context_tree_relships",
        )

    # Only GET
    def test_tasks_read_status(self):
        create_read_status(PERSNO)
        self.rest_get_only(
            "tasks_read_status",
            "caddok@bf529417-9ee6-11ec-93ed-334b6053520d",
            "cs_tasks_read_status",
        )

    # Only GET
    def test_tasks_tag(self):
        create_task_tag(PERSNO)
        self.rest_get_only(
            "tasks_tag",
            "caddok@bf529417-9ee6-11ec-93ed-334b6053520d@foo_tag",
            "cs_tasks_tag",
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
