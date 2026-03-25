#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,no-value-for-parameter


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import testcase

from cs.pcs.projects import tasks_resources


@pytest.mark.integration
class Task(testcase.RollbackTestCase):
    def test_updateResourceStatusSignals(self):
        t1 = tasks_resources.Task.Create(
            cdb_project_id="Ptest.msp.export",
            task_id="set to 3",
            ce_baseline_id="",
            work_uncovered=1,
            status=180,
        )
        t2 = tasks_resources.Task.Create(
            cdb_project_id="Ptest.msp.export",
            task_id="non-final status",
            ce_baseline_id="",
            work_uncovered=1,
            status=0,
        )
        t3 = tasks_resources.Task.Create(
            cdb_project_id="Ptest.msp.export",
            task_id="work is covered",
            ce_baseline_id="",
            work_uncovered=0,
            status=180,
        )
        self.assertIsNone(
            tasks_resources.Task.updateResourceStatusSignals([t1, t2, t3])
        )
        t1.Reload()
        t2.Reload()
        t3.Reload()
        self.assertEqual(t1.status_effort_fcast, 3)
        self.assertEqual(t2.status_effort_fcast, None)
        self.assertEqual(t3.status_effort_fcast, None)


if __name__ == "__main__":
    unittest.main()
