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

ASAP, ALAP = "01"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ConstrainedChildren(ScheduleTestCase):
    "Summary Task /w Manual Scheduling, Constrained Children"

    def test_constrained_children(self):
        "schedule ASAP tasks: child constraints produces gap"
        """
        Setup:
            - A ASAP
            - B task group, ASAP, children:
                - C duration 2, ASAP
                - D duration 1, manual 02.09.
                - E duration 2, ALAP

            A -FS-> B

        Expected Result:
            . 00  02  04  06  08  10
            A ████████████             A
            B             ████████████ B
            C             ████████     C
            D                     ████ D
            E                 ████████ E
            . 26  29  30  31  01  02   Sep 2016
        """
        d_end = date(2016, 9, 2)
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ASAP)
        self.set_dates(self.b, date(2016, 8, 29), d_end)
        self.link_tasks("EA", self.a, self.b)

        c = self.add_child(
            self.b,
            "C",
            date(2016, 8, 29),
            date(2016, 8, 30),
            2,
        )
        d = self.add_child(self.b, "D", d_end, d_end, 1)
        e = self.add_child(self.b, "E", None, None, 2)
        self.schedule_automatically(c, ASAP)
        self.schedule_manually(d)
        self.schedule_automatically(e, ALAP)
        self.set_task_duration(c, 2)
        self.set_task_duration(d, 1)
        self.set_task_duration(e, 2)

        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 2, 7, 0, 5, 0, 2],
                "B": [5, 6, 11, 8, 11, 6, 11, 2, 2],
                "C": [3, 6, 9, 8, 11, 6, 9, 1, 2],
                "D": [1, 10, 11, 10, 11, 10, 11, 0, 0],
                "E": [3, 6, 9, 8, 11, 8, 11, 0, 2],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 31), d_end],
                [c, date(2016, 8, 31), date(2016, 9, 1)],
                [d, d_end, d_end],
                [e, date(2016, 9, 1), d_end],
            ]
        )
