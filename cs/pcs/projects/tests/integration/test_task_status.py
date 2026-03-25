#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest
from cdb import ElementsError, testcase

from cs.pcs.projects.tests import common


@pytest.mark.integration
class TaskStatusIntegrationTestCase(testcase.RollbackTestCase):
    def test_avoid_discarded_msp_standard(self):
        project = common.generate_project()
        t1 = common.generate_task(project, "top_task1")
        project.msp_active = 2  # MSP Standard edition
        project.ChangeState(50)
        with self.assertRaises(ElementsError):
            t1.ChangeState(t1.DISCARDED.status)

    def test_avoid_discarded_msp_professional(self):
        project = common.generate_project()
        t1 = common.generate_task(project, "top_task1")
        project.msp_active = 1  # MSP Professional edition
        project.ChangeState(50)
        t1.ChangeState(t1.DISCARDED.status)
        self.assertEquals(t1.status, t1.DISCARDED.status)
