#!/usr/bin/env powerscript
# coding: utf-8
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import testcase

from cs.pcs import helpers
from cs.pcs.projects import Project
from cs.pcs.projects.tests import common


@pytest.mark.integration
class HelpersIntegrationTestCase(testcase.RollbackTestCase):
    def test_get_and_check_object_key_with_special_char(self):
        """Assert no error, when pid contains special char"""
        # generate test project with special char in pid
        common.generate_project(cdb_project_id="pid_with_&")
        # get and check project
        self.assertIsNotNone(
            helpers.get_and_check_object(Project, "read", cdb_project_id="pid_with_&")
        )

    @pytest.mark.dependency(depends=["cs.pcs.checklist"])
    def test_get_and_check_object_key_is_integer(self):
        from cs.pcs.checklists import Checklist

        # generate test project with special char in pid
        p = common.generate_project(cdb_project_id="pid_with_&")
        # generate checklist with integer primary key
        cl = common.generate_checklist(p)
        # get and check checklist
        self.assertIsNotNone(
            helpers.get_and_check_object(
                Checklist,
                "read",
                cdb_project_id="pid_with_&",
                checklist_id=cl.checklist_id,
            )
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
