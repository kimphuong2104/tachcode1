#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=pointless-string-statement,too-many-lines

from datetime import date

import pytest
from cdb import testcase

from cs.pcs.scheduling.tests.integration import ScheduleTestCase

ASAP, ALAP, SNET, SNLT = "0145"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class TestFreeFloatCalculation(ScheduleTestCase):
    def test_FF_equals_TF(self):
        """
        FF = TF (no successors)
        A,B both scheduled as soon as possible in a project of length 22
        Both A and B have FF == TF of 38
        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, "ASAP")
        self.schedule_automatically(self.b, "ASAP")
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 38, 43, 0, 5, 38, 38],
                "B": [5, 0, 5, 38, 43, 0, 5, 38, 38],
            },
        )

    def test_no_FF(self):
        """
        No FF (at least one successor follows directly after relship arrow from predecessor)
        A-FS+1->B
        A-FS+5->C

        A has no free float
        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ASAP)
        self.c = self.create_task(
            self.project.cdb_project_id,
            self.project.ce_baseline_id,
            "C",
            self.original_start_b,
            self.original_end_b,
            3,
            1,  # automatically scheduled
        )
        self.link_tasks("EA", self.a, self.c, 5)
        self.link_tasks("EA", self.a, self.b, 1)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 22, 27, 0, 5, 0, 22],
                "B": [5, 8, 13, 38, 43, 8, 13, 30, 30],
                "C": [5, 16, 21, 38, 43, 16, 21, 22, 22],
            },
        )

    def test_negative_FF(self):
        """
        Negative free float (violated relships)

        A -FS+5-> B
        A and B constrained to start on day 0

        => Relship is violated
        => A's latest dates are before its earliest
        => A's free float is negative
        => But is fixed in "finalize" because latest dates cannot be before earliest
        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, SNLT, self.project.start_time_fcast)
        self.link_tasks("EA", self.a, self.b, 5)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "B": [5, 0, 5, 0, 5, 0, 5, 0, 0],
            },
        )

    def test_FF_due_to_later_predecessor(self):
        """
        FF due to successor having another, later predecessor
        A-FS+1->B, C-FS+1->B
        A, B and C start as soon as possible
        C has a higher duration (10) than A (3)

        A has free float of 15

          00 02 04 06 08 10 12 14 16 18 20 22 24 26
        A █████████
        B                                  ████████
        C ██████████████████████████████
        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ASAP)
        self.c = self.create_task(
            self.project.cdb_project_id,
            self.project.ce_baseline_id,
            "C",
            self.original_start_b,
            self.original_end_b,
            10,
            1,  # automatically scheduled
        )
        self.set_task_duration(self.c, 10)
        self.link_tasks("EA", self.a, self.b, 1)
        self.link_tasks("EA", self.c, self.b, 1)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 30, 35, 0, 5, 14, 30],
                "B": [5, 22, 27, 38, 43, 22, 27, 16, 16],
                "C": [19, 0, 19, 16, 35, 0, 19, 0, 16],
            },
        )

    def test_FF_due_to_fixed_constraint(self):
        """
        FF due to fixed constraint (successor is constrained)

        A-FS+2->B
        A as soon as possible; B start no earlier than index 22
        A has free float of 6 workdays

          00 02 04 06 08 10 12 14 16 18 20 22 24 26
        A █████████
        B                                  █████████

        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, SNET, date(2016, 9, 12))  # index 22
        self.link_tasks("EA", self.a, self.b, 2)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 28, 33, 0, 5, 12, 28],
                "B": [5, 22, 27, 38, 43, 22, 27, 16, 16],
            },
        )

    def test_FF_due_to_ALAP(self):
        """
        FF due to ALAP constraint (successor scheduled ALAP)

        Project from 2016-08-26 until 2016-09-26
        A-FS+2->B
        A as soon as possible (index 0); B as late as possible (index 42)
        Expect Free Float for A

          00 02 04 06 08 10 12 14 16 18 20 22 24 26 28 30 32 34 36 38 40 42
        A █████████
        B                                                          █████████
        """
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ALAP)
        self.link_tasks("EA", self.a, self.b, 2)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 28, 33, 0, 5, 28, 28],
                "B": [5, 10, 15, 38, 43, 38, 43, 28, 28],
            },
        )
