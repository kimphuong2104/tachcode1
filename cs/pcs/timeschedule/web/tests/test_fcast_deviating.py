# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import datetime
import unittest

import pytest
from cdb import testcase

from cs.pcs.projects.tests import common as ProjectsCommon


@pytest.mark.integration
class FcastDeviatingAttribute(testcase.RollbackTestCase):
    def test_fcast_deviating_field_01(self):
        p = ProjectsCommon.generate_project()
        task = ProjectsCommon.generate_task(p, "taskFoo")
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_02(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_act = datetime.date(2020, 5, 15)
        kwargs = {
            "milestone": 1,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_act": end_time_act,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_03(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_act = datetime.date(2020, 6, 15)
        kwargs = {
            "milestone": 1,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_act": end_time_act,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 1)

    def test_fcast_deviating_field_03(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_plan = datetime.date(2020, 5, 15)
        kwargs = {
            "milestone": 1,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_04(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_plan = datetime.date(2020, 6, 15)
        kwargs = {
            "milestone": 1,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 1)

    def test_fcast_deviating_field_05(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_plan = datetime.date(2020, 6, 15)
        kwargs = {
            "milestone": 1,
            "status": 180,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_06(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        end_time_plan = datetime.date(2020, 6, 15)
        kwargs = {
            "milestone": 1,
            "percent_complet": 100,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_07(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        start_time_plan = datetime.date(2020, 1, 15)
        end_time_plan = datetime.date(2020, 5, 15)
        kwargs = {
            "milestone": 0,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "start_time_plan": start_time_plan,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 0)

    def test_fcast_deviating_field_08(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        start_time_plan = datetime.date(2020, 2, 15)
        end_time_plan = datetime.date(2020, 5, 15)
        kwargs = {
            "milestone": 0,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "start_time_plan": start_time_plan,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 1)

    def test_fcast_deviating_field_09(self):
        p = ProjectsCommon.generate_project()
        start_time_fcast = datetime.date(2020, 1, 15)
        end_time_fcast = datetime.date(2020, 5, 15)
        start_time_plan = datetime.date(2020, 1, 15)
        end_time_plan = datetime.date(2020, 4, 15)
        kwargs = {
            "milestone": 0,
            "start_time_fcast": start_time_fcast,
            "end_time_fcast": end_time_fcast,
            "start_time_plan": start_time_plan,
            "end_time_plan": end_time_plan,
            "daytime": 1,
            "automatic": 0,
        }
        task = ProjectsCommon.generate_task(p, "taskFoo", **kwargs)
        self.assertEqual(task.fcast_deviating, 1)


if __name__ == "__main__":
    unittest.main()
