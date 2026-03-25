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

from cs.pcs.projects import tasks
from cs.pcs.projects.tests import common_data
from cs.pcs.scheduling.tests.integration import ScheduleTestCase

MSO = "2"


def setup_module():
    testcase.run_level_setup()


class DiscardedTaskBase(ScheduleTestCase):
    def create_simple_task(self, task_id):
        return super().create_task(
            self.project.cdb_project_id,
            "",
            task_id,
            self.project.start_time_fcast,
            self.project.start_time_fcast,
            1,
            automatic=1,
        )

    def create_data(self):
        """
        Setup:
            The year is 2021

            Project X (08/02-08/02)

        Initial schedule:
            . 00
            A ███ A
            B ███ B
            C ███ C
            . 02  Aug 2016
        """
        pid = "INT_TEST_DISCARDED"
        self.project, _ = common_data.create_project(
            pid,
            start_date=date(2021, 8, 2),
        )
        self.a = self.create_simple_task("A")
        self.b = self.create_simple_task("B")
        self.c = self.create_simple_task("C")

    def _discard_and_schedule(self, to_discard, network, dates):
        for x in to_discard:
            x.Update(status=tasks.Task.DISCARDED.status)
        self.schedule_project()
        self.assertNetworkEqual(network)
        self.assert_dates(dates)


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class DiscardedTaskTest(DiscardedTaskBase):
    def test_multiple_predecessors_all_discarded(self):
        """
        Task with multiple predecessors - discard all predecessors

        1) Setup
        A ███
        B ███
        C    ███
        A -FS-> C
        B -FS-> C

        2) Discard A and B

        3) Expected Result:
        A XXX
        B XXX
        C ███
        """
        self.link_tasks("EA", self.a, self.c)
        self.link_tasks("EA", self.b, self.c)
        self._discard_and_schedule(
            [self.a, self.b],
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_multiple_predecessors_some_discarded(self):
        """
        Task with multiple predecessors - discard some

        1) Setup
        A ███
        B ███
        C         ███
        A -FS+5-> C
        B -FS+2-> C (dominated by A -> C, therefore actual gap is 5)

        2) Discard A

        3) Expected Result
        A XXX
        B ███
        C      ███
        Fallback to what B -> C allows (actual gap between B and C is now 2)
        """
        self.link_tasks("EA", self.a, self.c, 5)
        self.link_tasks("EA", self.b, self.c, 1)
        self._discard_and_schedule(
            [self.a],
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 4), date(2021, 8, 4)),
            ],
        )

    def test_free_float_due_to_discarded_successor(self):
        """
        Free Float calculation due to discarded successor
        A ███
        B       XXX
        C ███

        A-FS->B, B-SF->C
        B discarded, but starts due to constraint date 1 day after A ends
        A should not have FF of 1, but 0 due to virtual FF relship to C.
        """
        self.link_tasks("EA", self.a, self.b)
        self.link_tasks("AE", self.b, self.c)
        self.schedule_automatically(self.b, MSO, constraint_date=date(2021, 8, 4))
        self._discard_and_schedule(
            [self.b],
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 4), date(2021, 8, 4)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_chain_of_discarded_predecessor_does_not_yield_max_ef(self):
        """
        Maximal EF value comes from non-disc. pred and not from disc. pred chain
        A ███
        B ███
        C    XXX
        D            ███

        A-FS+4->D, B-FS+0->C, C-FS+0->D
        virtual Relship B-FS+0->D is overshadowed by real relship A-FS+4->D
        max_ef is determined via A->D
        """
        self.d = self.create_simple_task("D")
        self.link_tasks("EA", self.a, self.d, 4)
        self.link_tasks("EA", self.b, self.c)
        self.link_tasks("EA", self.c, self.d)
        self._discard_and_schedule(
            [self.c],
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 8, 9, 0, 1, 8, 8],
                "C": [1, 2, 3, 8, 9, 2, 3, 6, 6],
                "D": [1, 10, 11, 10, 11, 10, 11, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 9), date(2021, 8, 9)),
            ],
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class DiscardSingleTaskTest(DiscardedTaskBase):
    def _discard_b_and_schedule(self, reltype1, reltype2, network, dates):
        self.link_tasks(reltype1, self.a, self.b)
        self.link_tasks(reltype2, self.b, self.c)
        self._discard_and_schedule([self.b], network, dates)

    def test_discarded_task_between_SS_SS(self):
        """
        A -SS-> B, B -SS-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AA",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SS_SF(self):
        """
        A -SS-> B, B -SF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AA",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SS_FS(self):
        """
        A -SS-> B, B -FS-> C; discard B; C does move back
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C    ███                  C ███
        """
        self._discard_b_and_schedule(
            "AA",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SS_FF(self):
        """
        A -SS-> B, B -FF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AA",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SF_SS(self):
        """
        A -SF-> B, B -SS-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AE",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SF_SF(self):
        """
        A -SF-> B, B -SF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AE",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SF_FS(self):
        """
        A -SF-> B, B -FS-> C; discard B; C does move back
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C    ███                  C ███
        """
        self._discard_b_and_schedule(
            "AE",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_SF_FF(self):
        """
        A -SF-> B, B -FF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "AE",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_FS_SS(self):
        """
        A -FS-> B, B -SS-> C; discard B; C does not move
        A ███                        A ███
        B    ███     -Discard B- >   B    XXX
        C    ███                     C    ███
        """
        self._discard_b_and_schedule(
            "EA",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_task_between_FS_SF(self):
        """
        A -FS-> B, B -SF-> C; discard B; C does not move
        A ███                   A ███
        B    ███  -Discard B->  B    XXX
        C ███                   C ███
        """
        self._discard_b_and_schedule(
            "EA",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_FS_FS(self):
        """
        A -FS-> B, B -FS-> C; discard B; C does move back
        A ███                   A ███
        B    ███  -Discard B->  B    XXX
        C       ███             C    ███
        """
        self._discard_b_and_schedule(
            "EA",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_task_between_FS_FF(self):
        """
        A -FS-> B, B -FF-> C; discard B; C aligns with A
        A ███                   A ███
        B    ███  -Discard B->  B    XXX
        C    ███                C ███
        """
        self._discard_b_and_schedule(
            "EA",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_FF_SS(self):
        """
        A -FF-> B, B -SS-> C; discard B; C moves after A
        A ███                A ███
        B ███  -Discard B->  B XXX
        C ███                C    ███
        """
        self._discard_b_and_schedule(
            "EE",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 2, 3, 0, 1, 2, 2],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_task_between_FF_SF(self):
        """
        A -FF-> B, B -SF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "EE",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_task_between_FF_FS(self):
        """
        A -FF-> B, B -FS-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C    ███                  C    ███
        """
        self._discard_b_and_schedule(
            "EE",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_task_between_FF_FF(self):
        """
        A -FF-> B, B -FF-> C; discard B; C does not move
        A ███                     A ███
        B ███     -Discard B- >   B XXX
        C ███                     C ███
        """
        self._discard_b_and_schedule(
            "EE",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class DiscardTaskBlockTest(DiscardedTaskBase):
    def create_data(self):
        """
        Setup:
            The year is 2021
            Project X (08/02-08/06)
        """
        super().create_data()
        self.d = self.create_simple_task("D")

    def _discard_block_and_schedule(self, reltype1, reltype2, network, dates):
        self.link_tasks(reltype1, self.a, self.b)
        self.link_tasks(reltype2, self.c, self.d)
        # reltype between discarded tasks does not matter for test cases
        self.link_tasks("EA", self.b, self.c)

        self._discard_and_schedule([self.b, self.c], network, dates)

    def test_discarded_block_between_SS_SS(self):
        """
        A -SS-> B, B -> C, C -SS-> D; discard B and C; D aligns with A
        A ███                        A ███
        B ███      -Discard B,C- >   B XXX
        C    ███                     C    XXX
        D    ███                     D ███
        """
        self._discard_block_and_schedule(
            "AA",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SS_SF(self):
        """
        A -SS-> B, B -> C, D -SF-> C; discard B and C; D aligns with A
        A ███                          A ███
        B ███      -Discard B,C- >     B XXX
        C    ███                       C    XXX
        D    ███                       D ███
        """
        self._discard_block_and_schedule(
            "AA",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SS_FS(self):
        """
        A -SS-> B, B -> C, D -FS-> C; discard B and C; D alings with A
        A ███                       A ███
        B ███     -Discard B,C- >   B XXX
        C    ███                    C    XXX
        D       ███                 D ███
        """
        self._discard_block_and_schedule(
            "AA",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SS_FF(self):
        """
        A -SS-> B, B -> C, D -FF-> C; discard B and C; D alings with A
        A ███                       A ███
        B ███     -Discard B, C- >  B XXX
        C    ███                    C    XXX
        D    ███                    D ███
        """
        self._discard_block_and_schedule(
            "AA",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SF_SS(self):
        """
        A -SF-> B, B -> C, D -SS-> C; discard B and C; D aligns with A
        A ███                       A ███
        B ███     -Discard B,C- >   B XXX
        C    ███                    C    XXX
        D    ███                    D ███
        """
        self._discard_block_and_schedule(
            "AE",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SF_SF(self):
        """
        A -SF-> B, B -> C, D -SF-> C; discard B and C; D aligns with A
        A ███                       A ███
        B ███     -Discard B,C- >   B XXX
        C    ███                    C    XXX
        D    ███                    D ███
        """
        self._discard_block_and_schedule(
            "AE",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SF_FS(self):
        """
        A -SF-> B, B -> C, D -FS-> C; discard B and C; D aligns with A
        A ███                      A ███
        B ███     -Discard B,C->   B XXX
        C    ███                   C    XXX
        D       ███                D ███
        """
        self._discard_block_and_schedule(
            "AE",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_SF_FF(self):
        """
        A -SF-> B, B -> C, D -FF-> C; discard B and C; D aligns with A
        A ███                      A ███
        B ███     -Discard B,C->   B XXX
        C    ███                   C    XXX
        D    ███                   D ███
        """
        self._discard_block_and_schedule(
            "AE",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_FS_SS(self):
        """
        A -FS-> B, B -> C, D -SS-> C; discard B and C; D comes after A
        A ███                         A ███
        B    ███     -Discard B,C->   B    XXX
        C       ███                   C       XXX
        D       ███                   D    ███
        """
        self._discard_block_and_schedule(
            "EA",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 4), date(2021, 8, 4)),
                (self.d, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_block_between_FS_SF(self):
        """
        A -FS-> B, B -> C, D -SF-> C; discard B and C; D aligns with A
        A ███                        A ███
        B    ███    -Discard B,C->   B    XXX
        C       ███                  C       XXX
        D ███                        D ███
        """
        self._discard_block_and_schedule(
            "EA",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 4), date(2021, 8, 4)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_FS_FS(self):
        """
        A -FS-> B, B -> C, D -FS-> C; discard B and C; D comes after A
        A ███                           A ███
        B    ███        -Discard B,C->  B    XXX
        C       ███                     C       XXX
        D          ███                  D    ███
        """
        self._discard_block_and_schedule(
            "EA",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 4), date(2021, 8, 4)),
                (self.d, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_block_between_FS_FF(self):
        """
        A -FS-> B, B -> C, D -FF-> C; discard B and C; D aligns with A
        A ███                        A ███
        B    ███     -Discard B,C->  B    XXX
        C       ███                  C       XXX
        D       ███                  D ███
        """
        self._discard_block_and_schedule(
            "EA",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "C": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 3), date(2021, 8, 3)),
                (self.c, date(2021, 8, 4), date(2021, 8, 4)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_FF_SS(self):
        """
        A -FF-> B, B -> C, D -SS-> C; discard B and C; D comes after A
        A ███                     A ███
        B ███     -Discard B,C->  B XXX
        C    ███                  C    XXX
        D    ███                  D    ███
        """
        self._discard_block_and_schedule(
            "EE",
            "AA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_block_between_FF_SF(self):
        """
        A -FF-> B, B -> C, D -SF-> C; discard B and C; D aligns with A
        A ███                      A ███
        B ███     -Discard B,C->   B XXX
        C    ███                   C    XXX
        D    ███                   D ███
        """
        self._discard_block_and_schedule(
            "EE",
            "AE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )

    def test_discarded_block_between_FF_FS(self):
        """
        A -FF-> B, B -> C, D -FS-> C; discard B and C; D comes after A
        A ███                       A ███
        B ███     -Discard B,C- >   B XXX
        C    ███                    C    XXX
        D       ███                 D    ███
        """
        self._discard_block_and_schedule(
            "EE",
            "EA",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 2, 3, 2, 3, 2, 3, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 3), date(2021, 8, 3)),
            ],
        )

    def test_discarded_block_between_FF_FF(self):
        """
        A -FF-> B, B -> C, D -FF-> C; discard B and C; D aligns with A
        A ███                      A ███
        B ███     -Discard B,C->   B XXX
        C    ███                   C    XXX
        D    ███                   D ███
        """
        self._discard_block_and_schedule(
            "EE",
            "EE",
            {
                "A": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "B": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "C": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "D": [1, 0, 1, 0, 1, 0, 1, 0, 0],
            },
            [
                (self.a, date(2021, 8, 2), date(2021, 8, 2)),
                (self.b, date(2021, 8, 2), date(2021, 8, 2)),
                (self.c, date(2021, 8, 3), date(2021, 8, 3)),
                (self.d, date(2021, 8, 2), date(2021, 8, 2)),
            ],
        )
