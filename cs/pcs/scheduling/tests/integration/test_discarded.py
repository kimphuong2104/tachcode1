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
class DiscardedTasksInTaskGroup(ScheduleTestCase):
    def test_running_successor_is_fixed(self):
        "task group ignores first and last discarded tasks"
        """
        (see E072231)
        Setup:
            - A is scheduled ALAP
            - B is a task group with subtasks C, D, E
            - A -FS-> B
            - C, D and E are scheduled manually on 06., 08. and 12.09., respectively
            - C and E are discarded
            - B is expected to be shortened

        Before Discarding / Scheduling:
            . 08  10  12  14  16  18  20  22     | Constr | Pred | Parent | Discarded? |
            A ████████████                     A | ALAP   |      |        |            |
            B             ████████████████████ B | ASAP   | A    |        |            |
            C             ████                 C | fixed  |      | B      |            |
            D                     ████         D | fixed  |      | B      |            |
            E                             ████ E | fixed  |      | B      |            |
            . 01  02  05  06  07  08  09  12   Sep 2016

        Expected Result:
            . 08  10  12  14  16  18  20  22     | Constr | Pred | Parent | Discarded? |
            A         ████████████             A | ALAP   |      |        |            |
            B                     ████         B | ASAP   | A    |        |            |
            C             ████                 C | fixed  |      | B      | X          |
            D                     ████         D | fixed  |      | B      |            |
            E                             ████ E | fixed  |      | B      | X          |
            . 01  02  05  06  07  08  09  12   Sep 2016
        """
        self.schedule_automatically(self.a, ALAP)
        self.schedule_automatically(self.b, ASAP)
        self.c = self.add_child(self.b, "C", date(2016, 9, 6), date(2016, 9, 6), 1)
        self.schedule_manually(self.c)
        self.d = self.add_child(self.b, "D", date(2016, 9, 8), date(2016, 9, 8), 1)
        self.schedule_manually(self.d)
        self.e = self.add_child(self.b, "E", date(2016, 9, 12), date(2016, 9, 12), 1)
        self.schedule_manually(self.e)
        self.link_tasks("EA", self.a, self.b)
        self.c.Update(status=self.c.DISCARDED.status)
        self.e.Update(status=self.e.DISCARDED.status)

        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 12, 17, 12, 17, 0, 12],
                "B": [1, 18, 19, 18, 19, 18, 19, 0, 0],
                "C": [1, 18, 19, 18, 19, 14, 15, 0, 0],
                "D": [1, 18, 19, 18, 19, 18, 19, 0, 0],
                "E": [1, 22, 23, 22, 23, 22, 23, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 5), date(2016, 9, 7)],
                [self.b, date(2016, 9, 8), date(2016, 9, 8)],
                [self.c, date(2016, 9, 6), date(2016, 9, 6)],
                [self.d, date(2016, 9, 8), date(2016, 9, 8)],
                [self.e, date(2016, 9, 12), date(2016, 9, 12)],
            ]
        )
