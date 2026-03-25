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

ASAP, ALAP, MSO = "012"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class TaskGroupRelships(ScheduleTestCase):
    def _setup_task_groups(self):
        """
        A is a task group with only child B (duration 1)
        C is a task group with only child D (duration 1)
        E is a task group with only child F (duration 1)

        no relships yet:

        . 00
        A ████ A (task group with child B)
        B ████ B
        C ████ C (task group with child D)
        D ████ D
        E ████ E (task group with child F)
        F ████ F
        . 26  29   Aug 2016
        """
        self.b.Update(parent_task=self.a.task_id)
        self.a.Update(is_group=1)
        self.c = self.create_task(
            self.a.cdb_project_id, "", "C", date(2016, 9, 1), date(2016, 9, 1), 1
        )
        self.d = self.add_child(self.c, "D", date(2016, 9, 1), date(2016, 9, 1), 1)
        self.e = self.create_task(
            self.a.cdb_project_id, "", "E", date(2016, 9, 1), date(2016, 9, 1), 1
        )
        self.f = self.add_child(self.e, "F", date(2016, 9, 1), date(2016, 9, 1), 1)

        for task in [self.a, self.b, self.c, self.d, self.e, self.f]:
            self.set_task_duration(task, 1)
            self.schedule_automatically(task, ASAP)

    def _setup_linked_groups(self):
        """
        A -FS-> C
        C -FS-> E

        Expected:

        . 00  02  04
        A ████         A (task group with child B)
        B ████         B
        C     ████     C (task group with child D)
        D     ████     D
        E         ████ E (task group with child F)
        F         ████ F
        . 26  29  30   Aug 2016

        Task groups would like to schedule starting late so there are no gaps in between.
        But children have "position_fix" (they can only start early),
        pushing back task group start dates to the start of the next day.
        """
        self._setup_task_groups()
        self.link_tasks("EA", self.a, self.c)
        self.link_tasks("EA", self.c, self.e)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "E": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "F": [1, 4, 5, 4, 5, 4, 5, 0, 0],
            }
        )

    def test_linked_groups_tasks_alap(self):
        """
        Regular tasks (B, D, F) are scheduled ALAP.

        . 00  02  04
        A ████         A (task group with child B)
        B ████         B
        C     ████     C (task group with child D)
        D     ████     D
        E         ████ E (task group with child F)
        F         ████ F
        . 26  29  30   Aug 2016
        """
        self._setup_linked_groups()
        for task in [self.b, self.d, self.f]:
            self.schedule_automatically(task, ALAP)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "E": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "F": [1, 4, 5, 4, 5, 4, 5, 0, 0],
            }
        )

    def test_linked_groups_move_later(self):
        """
        linked groups are moved to a later schedule because B MSO 02

        . 00  02  04
        A ████         A (task group with child B)
        B ████         B
        C     ████     C (task group with child D)
        D     ████     D
        E         ████ E (task group with child F)
        F         ████ F
        . 26  29  30   Aug 2016

        Expected:

        . 00  02  04  06
        A     ████         A (task group with child B)
        B     ████         B
        C         ████     C (task group with child D)
        D         ████     D
        E             ████ E (task group with child F)
        F             ████ F
        . 26  29  30   Aug 2016
        """
        self._setup_linked_groups()
        self.schedule_automatically(self.b, MSO, date(2016, 8, 28))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "E": [1, 6, 7, 6, 7, 6, 7, 0, 0],
                "F": [1, 6, 7, 6, 7, 6, 7, 0, 0],
            }
        )

    def test_linked_groups_move_earlier(self):
        """linked groups are moved to an earlier schedule because B MSO -02

        this test case is tricky because

        1. the first scheduling run changes the task group's earliest dates
           to fit the fixed position of their children
        2. the repeated scheduling run then has to overrule these earliest dates
           with even earlier ones (which is usually not allowed for good reason)
        """
        self._setup_linked_groups()
        self.schedule_automatically(self.b, MSO, date(2016, 8, 25))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, -2, -1, -2, -1, -2, -1, 0, 0],
                "B": [1, -2, -1, -2, -1, -2, -1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "E": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "F": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            }
        )

    def _setup_linked_children(self):
        """
        just like linked groups above, but relships are defined between children instead:
        B -FS-> D
        D -FS-> F

        Expected:

        . 00  02  04
        A ████         A (task group with child B)
        B ████         B
        C     ████     C (task group with child D)
        D     ████     D
        E         ████ E (task group with child F)
        F         ████ F
        . 26  29  30   Aug 2016
        """
        self._setup_task_groups()
        self.link_tasks("EA", self.b, self.d)
        self.link_tasks("EA", self.d, self.f)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "E": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "F": [1, 4, 5, 4, 5, 4, 5, 0, 0],
            }
        )

    def test_linked_children_move_later(self):
        "linked children are moved to a later schedule because A MSO 02"
        self._setup_linked_children()
        self.schedule_automatically(self.a, MSO, date(2016, 8, 28))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "E": [1, 6, 7, 6, 7, 6, 7, 0, 0],
                "F": [1, 6, 7, 6, 7, 6, 7, 0, 0],
            }
        )

    def test_linked_children_move_earlier(self):
        "linked children are moved to an earlier schedule because A MSO -02"
        self._setup_linked_children()
        self.schedule_automatically(self.a, MSO, date(2016, 8, 25))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [1, -2, -1, -2, -1, -2, -1, 0, 0],
                "B": [1, -2, -1, -2, -1, -2, -1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "E": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "F": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            }
        )
