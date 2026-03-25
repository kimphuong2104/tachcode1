#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest
from cdb import testcase

from cs.pcs.scheduling.tests.integration import ScheduleTestCase

ASAP, FNET = "06"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class TaskGroupConstraintInChild(ScheduleTestCase):
    def test_constraint_in_child(self):
        """Schedule constraint in subtask

        Project
        └ A (ASAP)
        └ B (ASAP)
        └ C (FNET 09/05)

        A -FS-> B

        C (child of B) pushes B back to create a 1-day gap between A and B

        . 00  02  04  06  08  10  12
        A ████████████                 A
        B                 ████████████ B
        C                 ████████████ C
        . 26  29  30  31  01  02  05     Sep 2016
        """
        self.c = self.add_child(
            self.b,
            "C",
            date(2016, 9, 7),
            date(2016, 9, 9),
            3,
        )
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ASAP)
        self.schedule_automatically(self.c, FNET, date(2016, 9, 5))
        self.link_tasks("EA", self.a, self.b)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 2, 7, 0, 5, 2, 2],
                "B": [5, 8, 13, 8, 13, 8, 13, 0, 0],
                "C": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 9, 1), date(2016, 9, 5)],
                [self.c, date(2016, 9, 1), date(2016, 9, 5)],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class TaskGroupDiscardedChild(ScheduleTestCase):
    def test_discarded_child(self):
        """Task group ignores discarded end dates

        Project
        └ A (ASAP)
        └ B (ASAP)
        └ C (ASAP)
        └ D (discarded)

        C -FS-> D

        Because D is discarded, B shares C's end date

        . 00  02  04  06  08  10
        A ████████████             A
        B ████████████             B
        C ████████████             C
        D             ████████████ D
        . 26  29  30  31  01  02     Aug 2016
        """
        self.c = self.add_child(
            self.b,
            "C",
            date(2016, 9, 7),
            date(2016, 9, 9),
            3,
        )
        self.d = self.add_child(
            self.b,
            "D",
            date(2016, 9, 7),
            date(2016, 9, 9),
            3,
        )
        self.d.Update(status=self.d.DISCARDED.status)

        for task in [self.a, self.b, self.c, self.d]:
            self.schedule_automatically(task, ASAP)

        self.link_tasks("EA", self.c, self.d)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "B": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "C": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "D": [5, 6, 11, 6, 11, 6, 11, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 26), date(2016, 8, 30)],
                [self.c, date(2016, 8, 26), date(2016, 8, 30)],
                [self.d, date(2016, 8, 31), date(2016, 9, 2)],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class TaskGroupManualChild(ScheduleTestCase):
    def test_manual_child(self):
        """Task group with manual child

        Project
        └ A (ASAP)
        └ B (ASAP)
            └ C (manual)
            └ D (ASAP)

        A -FS-> B
        C -FS-> D

        Because C is scheduled manually, B starts earlier.
        This in turn violated the relationship between A and B.

        . 00  02  04  06  08  10
        A ████████████             A (predecessor)
        B       ██████████████████ B (task group)
        C       ██                 C (manual child)
        D             ████████████ D (automatic child)
        . 26  29  30  31  01  02     Aug 2016
        """
        self.c = self.add_child(
            self.b,
            "C",
            date(2016, 8, 29),
            date(2016, 8, 29),
            0,
        )
        self.is_milestone(self.c, False)
        self.d = self.add_child(
            self.b,
            "D",
            date(2016, 9, 7),
            date(2016, 9, 9),
            2,
        )

        for task in [self.a, self.b, self.d]:
            self.schedule_automatically(task, ASAP)

        self.link_tasks("EA", self.a, self.b)
        self.link_tasks("EA", self.c, self.d)

        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "B": [8, 3, 11, 3, 11, 3, 11, 0, 0],
                "C": [0, 5, 5, 6, 6, 3, 3, 1, 1],
                "D": [5, 6, 11, 6, 11, 6, 11, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 29), date(2016, 9, 2)],
                [self.c, date(2016, 8, 29), date(2016, 8, 29)],
                [self.d, date(2016, 8, 31), date(2016, 9, 2)],
            ]
        )

        self.a.Reload()
        self.assertEqual(self.a.SuccessorTaskRelations.violation, [1])
