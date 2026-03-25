#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=pointless-string-statement

from datetime import date

import pytest
from cdb import testcase

from cs.pcs.scheduling.tests.integration import ScheduleTestCase

ASAP, ALAP, SNET = "014"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class CriticalPath(ScheduleTestCase):
    __default_constraint__ = (ASAP, None)

    def setUp(self):
        super().setUp()
        self.c = self.a.Copy(task_id="C", task_name="Task C", cdb_object_id="C")

    def _setup(self, relships, constr_a=None, constr_b=None, constr_c=None):
        """
        (the year is 2016)

        Project X (starts on 08/26)
        └ Task A (duration: 3)
        └ Task B (duration: 3)
        └ Task C (duration: 3)
        """
        for pred, rs_type, succ in relships:
            self.link_tasks(rs_type, pred, succ)

        for task, constraint in zip(
            [self.a, self.b, self.c], [constr_a, constr_b, constr_c]
        ):
            if constraint is None:
                constraint = self.__default_constraint__

            ctype, cdate = constraint

            if ctype == "manual":
                start, end, _ = task.calculateTimeFrame(
                    start=cdate, days=task.days_fcast
                )
                task.Update(start_time_fcast=start, end_time_fcast=end)
                self.schedule_manually(task)
            else:
                self.schedule_automatically(task, ctype, cdate)

        self.schedule_project()

    def assertTotalFloat(self, *expected):
        tasks = [self.a, self.b, self.c]
        for task in tasks:
            task.Reload()
        floats = tuple(task.total_float for task in tasks)
        self.assertEqual(floats, expected)

    def test_c_offset(self):
        "C has constraints-based offset"
        self._setup(
            (
                (self.a, "EA", self.b),
                (self.b, "EA", self.c),
            ),
            constr_c=(SNET, date(2016, 9, 12)),
        )
        self.assertTotalFloat(5, 5, 0)

    def test_c_offset_b_manual(self):
        "C has constraints-based offset, B scheduled manually without gap"
        """
        Setup:
            - A -FS-> B -FS-> C
            - B scheduled manually, 31.08. - 02.09.
            - C SNET 12.09.

        Expected Result:
            . 00 01 02 03 04 05 06 07 08 09 10 11 12 13
            A █████████                                  A
            B          █████████                         B
            C                                  █████████ C
            . 26 29 30 31 01 02 05 06 07 08 09 12 13 14  Sep 2016
        """
        self._setup(
            (
                (self.a, "EA", self.b),
                (self.b, "EA", self.c),
            ),
            constr_b=("manual", date(2016, 8, 31)),
            constr_c=(SNET, date(2016, 9, 12)),
        )
        self.assertTotalFloat(5, 5, 0)


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class CriticalPathTotalFloat(ScheduleTestCase):
    def setUp(self):
        """
        Initial default values:

        Project X (starts on 08/26/2016)
        └ Task A
        └ Task B
        └ Task C
        └ Task D

        Each task takes 3 days.
        No task dependencies.
        """
        super().setUp()
        self.c = ScheduleTestCase.create_task(
            self.project.cdb_project_id,
            self.project.ce_baseline_id,
            "C",
            date(2016, 9, 12),
            date(2016, 9, 13),
            3,
        )
        self.d = ScheduleTestCase.create_task(
            self.project.cdb_project_id,
            self.project.ce_baseline_id,
            "D",
            date(2016, 9, 12),
            date(2016, 9, 13),
            3,
        )

    def test_check_total_float(self):
        "test_check_total_float"
        """
        Setup:
            - Task A with duration of 3 is scheduled manually to start on Sep 7th
            - Other tasks are related: B -FS-> C -SF-> D
            - Task B with duration of 3 is scheduled ALAP
            - Task C with duration of 2 is scheduled ASAP
            - Task D with duration of 3 is scheduled SNLT (Sep 12th)

        Expected Result:
            - D determines the latest possible dates (must start by Sep 12th)
            - ALAP-scheduled predecessor B pushes C and D to latest possible dates
            - Neither B, nor C, nor D should float
            - Project dates are adjusted (Sep 7th - 14th)

            . 16  18  20  22  24  26
            A ████████████             A
            B     ████████████         B
            C                 ████████ C
            D             ████████████ D
            . 07  08  09  12  13  14   Sep 2016
        """
        self.a.Update(automatic=0)
        self.b.Update(automatic=1, constraint_type=ALAP)
        self.c.Update(automatic=1, constraint_type=ASAP)
        self.d.Update(
            automatic=1,
            constraint_type=SNET,
            constraint_date=date(2016, 9, 12),
        )
        self.set_task_duration(self.c, 2)
        self.set_task_duration(self.d, 3)
        self.link_tasks("EA", self.b, self.c, 0)
        self.link_tasks("AE", self.c, self.d, 0)
        self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [5, 16, 21, 22, 27, 16, 21, 6, 6],
                "B": [5, 0, 5, 18, 23, 18, 23, 0, 18],
                "C": [3, 24, 27, 24, 27, 24, 27, 0, 0],
                "D": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 7), date(2016, 9, 9)],
                [self.b, date(2016, 9, 8), date(2016, 9, 12)],
                [self.c, date(2016, 9, 13), date(2016, 9, 14)],
                [self.d, date(2016, 9, 12), date(2016, 9, 14)],
                [self.project, date(2016, 9, 7), date(2016, 9, 14)],
            ]
        )
        self.assertEqual(
            [x.total_float for x in [self.a, self.b, self.c, self.d]],
            [3, 9, 0, 0],  # for A: not changed, not updated
        )
