#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase, util

from cs.pcs.projects import Role, kProjectManagerRole, kProjectMemberRole


@pytest.mark.unit
class TestRole(testcase.RollbackTestCase):
    def test_remove_prj_role_project_manager(self):

        role = mock.MagicMock(spec=Role)
        role.role_id = kProjectManagerRole
        role.mapped_name = "Project Manager"

        ctx = mock.MagicMock(action="delete")

        with self.assertRaises(util.ErrorMessage):
            Role.remove_prj_role(role, ctx)

    def test_remove_prj_role_project_member(self):

        role = mock.MagicMock(spec=Role)
        role.role_id = kProjectMemberRole
        role.mapped_name = "Project Member"

        ctx = mock.MagicMock(action="delete")

        Role.remove_prj_role(role, ctx)
        self.assert_(True)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
