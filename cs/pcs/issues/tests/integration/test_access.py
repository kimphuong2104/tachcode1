#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import pytest
from cdb import auth, testcase
from cdb.validationkit.SwitchRoles import run_with_project_roles, run_with_roles

from cs.pcs.issues.tests.common import generate_issue
from cs.pcs.projects.tests import common


@pytest.mark.integration
class IssuesAccessTestCase(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.project = common.generate_project()
        self.issue = generate_issue(self.project, "ISS-0000001")

    def test_access_as_projektmitglied(self):
        @run_with_roles(["public"])
        @run_with_project_roles(self.project, ["Projektmitglied"])
        def check_access():
            self.assertTrue(self.issue.CheckAccess("read", auth.persno))
            self.assertTrue(self.issue.CheckAccess("create", auth.persno))
            self.assertTrue(self.issue.CheckAccess("save", auth.persno))
            self.assertTrue(self.issue.CheckAccess("accept", auth.persno))
            self.assertTrue(self.issue.CheckAccess("delete", auth.persno))

        check_access()
