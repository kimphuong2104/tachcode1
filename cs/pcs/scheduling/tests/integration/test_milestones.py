#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=pointless-string-statement, too-many-lines

from datetime import date, timedelta

import pytest
from cdb import testcase

from cs.pcs.scheduling.tests.integration import ScheduleTestCase

ASAP, ALAP, MSO, MFO, SNET, SNLT, FNET, FNLT = "01234567"


def setup_module():
    testcase.run_level_setup()


class MilestoneSetup(ScheduleTestCase):
    def assertDaytime(self, expected, *milestones):
        for x in milestones:
            x.Reload()

        result = {
            x["task_id"]: (x["start_is_early"], x["end_is_early"], x["daytime"])
            for x in milestones
        }
        self.assertEqual(result, expected)

    def test_initial_daytime(self):
        """
        Create project with milestones and make sure initial scheduling consistently sets
        start_is_early, end_is_early and daytime:

        a) automatic milestone ASAP
        b) automatic milestone FNET day 1
        c) manual milestone "Morning"
        d) manual milestone "Evening"

        . 00  02
        A ▒▒       A
        B       ▒▒ B
        C ▒▒       C
        D   ▒▒     D
        """
        self.a.Delete()
        self.b.Delete()

        pid = self.project.cdb_project_id
        day = self.project.start_time_fcast
        a = self.create_task(pid, "", "A", day, day, 0)
        b = self.create_task(pid, "", "B", day, day, 0)
        c = self.create_task(pid, "", "C", day, day, 0)
        d = self.create_task(pid, "", "D", day, day, 0)
        self.is_milestone(a)
        self.is_milestone(b)
        self.is_milestone(c)
        self.is_milestone(d)
        self.schedule_automatically(a, ASAP)
        self.schedule_automatically(b, FNET, day + timedelta(days=1))
        self.schedule_manually(c)
        self.schedule_manually(d)
        c.Update(start_is_early=1)
        d.Update(start_is_early=0)

        self.assertDaytime(
            {
                "A": (None, None, None),
                "B": (None, None, None),
                "C": (1, None, None),
                "D": (0, None, None),
            },
            a,
            b,
            c,
            d,
        )

        self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [0, 0, 0, 3, 3, 0, 0, 3, 3],
                "B": [0, 3, 3, 3, 3, 3, 3, 0, 0],
                "C": [0, 0, 0, 3, 3, 0, 0, 3, 3],
                "D": [0, 1, 1, 3, 3, 1, 1, 2, 2],
            }
        )
        # Note: values for C and D should be
        # (1, 1, 0) and (0, 0, 1), respectively,
        # but fixed tasks are not updated by the scheduling
        # It the milestones were created via operation CDB_Create,
        # user exits would ensure this kind of consistency
        self.assertDaytime(
            {
                "A": (1, 1, None),
                "B": (0, 0, None),
                "C": (
                    1,
                    None,
                    None,
                ),
                "D": (
                    0,
                    None,
                    None,
                ),
            },
            a,
            b,
            c,
            d,
        )


class PredecessorIsMilestoneBase(ScheduleTestCase):
    def _pred_is_milestone(self, link_type, gap, b_start, b_end, network):
        """
        Project
        └ A milestone, manually scheduled 07.09.
        └ B various constraints

        A -link-> B

        Milestone can be early or late, depending on
        ``__early_position__`` subclass constant.
        """
        milestone_end = date(2016, 9, 7)
        self.is_milestone(self.a, self.__early_position__)
        self.set_dates(self.a, milestone_end, milestone_end)
        self.schedule_automatically(self.b, ASAP)
        self.link_tasks(link_type, self.a, self.b, gap)
        self.schedule_project()
        self.assertNetworkEqual(network)
        self.assert_dates(
            [
                [self.a, milestone_end, milestone_end],
                [self.b, b_start, b_end],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class PredecessorIsMilestoneEarly(PredecessorIsMilestoneBase):
    """
    Project
    └ A early milestone 07.09.
    └ B various constraints

    A -link-> B
    """

    __early_position__ = 1

    def test_SS(self):
        "schedule early milestone -SS-> task"
        """
        Setup:
            - A early milestone 07.09
            - B ASAP
            - A -SS-> B

        . 16  18  20
        A ██▒▒         A
        B ████████████ B
        . 07  08  09   Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            0,
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )

    def test_SS_minus2(self):
        "schedule milestone -SS-2-> task"
        """
        . 12  14  16
        A         ██▒▒ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            -2,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_SS_plus2(self):
        "schedule milestone -SS+2-> task"
        """
        . 16  18  20  22  24
        A ██▒▒                 A
        B         ████████████ B
        . 07  08  09  12  13   Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            2,
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_FS(self):
        "schedule milestone -FS-> task"
        """
        . 16  18  20
        A ██▒▒         A
        B ████████████ B
        . 07  08  09   Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            0,
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )

    def test_FS_minus2(self):
        "schedule milestone -FS-2-> task"
        """
        . 12  14  16
        A         ██▒▒ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            -2,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_FS_plus2(self):
        "schedule milestone -FS+2-> task"
        """
        . 16  18  20  22  24
        A ██▒▒                 A
        B         ████████████ B
        . 07  08  09  12  13   Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            2,
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_SF(self):
        "schedule milestone -SF-> task"
        """
        . 12  14  16
        A         ██▒▒ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            0,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 16, 16, 17, 17, 16, 16, 1, 1],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_SF_minus2(self):
        "schedule milestone -SF-2-> task"
        """
        . 06  08  10  12  14  16
        A                     ██ A
        B ████████████           B
        . 31  01  02  05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            -2,
            date(2016, 8, 31),
            date(2016, 9, 2),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 6, 11, 10, 16, 6, 11, 4, 4],
            },
        )

    def test_SF_plus2(self):
        "schedule milestone -SF+2-> task"
        """
        . 14  16  18
        A     ██       A
        B ████████████ B
        . 06  07  08   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            2,
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 14, 19, 14, 19, 14, 19, 0, 0],
            },
        )

    def test_FF(self):
        "schedule milestone -FF-> task"
        """
        . 12  14  16
        A         ██▒▒ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            0,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 16, 16, 17, 17, 16, 16, 1, 1],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_FF_minus2(self):
        "schedule milestone -FF-2-> task"
        """
        . 06  08  10  12  14  16
        A                     ██  A
        B ████████████            B
        . 31  01  02  05  06  07  Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            -2,
            date(2016, 8, 31),
            date(2016, 9, 2),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 6, 11, 10, 16, 6, 11, 4, 4],
            },
        )

    def test_FF_plus2(self):
        "schedule milestone -FF+2-> task"
        """
        . 14  16  18
        A     ██       A
        B ████████████ B
        . 06  07  08   Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            2,
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [0, 16, 16, 16, 16, 16, 16, 0, 0],
                "B": [5, 14, 19, 14, 19, 14, 19, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class PredecessorIsMilestoneLate(PredecessorIsMilestoneBase):
    """
    Project
    └ A late milestone 07.09.
    └ B various constraints

    A -link-> B
    """

    __early_position__ = 0

    def test_SS(self):
        "schedule milestone -SS-> task"
        """
        Setup:
            - A milestone 07.09
            - B ASAP
            - A -SS-> B

        . 16  18  20  22
        A ▒▒██             A
        B     ████████████ B
        . 07 08 09 12  Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            0,
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_FS(self):
        "schedule milestone -FS-> task"
        """
        . 16  18  20  22
        A ▒▒██             A
        B     ████████████ B
        . 07 08 09 12  Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            0,
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_SS_minus2(self):
        "schedule milestone -SS-2-> task"
        """
        . 14  16  18
        A       ██     A
        B ████████████ B
        . 06  07  08   Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            -2,
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 14, 19, 14, 19, 14, 19, 0, 0],
            },
        )

    def test_FS_minus2(self):
        "schedule milestone -FS-2-> task"
        """
        . 14  16  18
        A       ██     A
        B ████████████ B
        . 06  07  08   Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            -2,
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 14, 19, 14, 19, 14, 19, 0, 0],
            },
        )

    def test_SS_plus2(self):
        "schedule milestone -SS+2-> task"
        """
        . 16  18  20  22  24  26
        A ▒▒██                     A
        B             ████████████ B
        . 07  08  09  12  13  14   Sep 2016
        """
        self._pred_is_milestone(
            "AA",
            2,
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_FS_plus2(self):
        "schedule milestone -FS+2-> task"
        """
        . 16  18  20  22  24  26
        A ▒▒██                     A
        B             ████████████ B
        . 07  08  09  12  13  14   Sep 2016
        """
        self._pred_is_milestone(
            "EA",
            2,
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_SF(self):
        "schedule milestone -SF-> task"
        """
        . 12  14  16
        A         ▒▒██ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            0,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_SF_minus2(self):
        "schedule milestone -SF-2-> task"
        """
        . 08  10  12  14  16
        A                 ▒▒██ A
        B ████████████         B
        . 01  02  05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            -2,
            date(2016, 9, 1),
            date(2016, 9, 5),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 8, 13, 12, 17, 8, 13, 4, 4],
            },
        )

    def test_SF_plus2(self):
        "schedule milestone -SF+2-> task"
        """
        . 16  18  20
        A   ██         A
        B ████████████ B
        . 07  08  09   Sep 2016
        """
        self._pred_is_milestone(
            "AE",
            2,
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )

    def test_FF(self):
        "schedule milestone -FF-> task"
        """
        . 12  14  16
        A         ▒▒██ A
        B ████████████ B
        . 05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            0,
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_FF_minus2(self):
        "schedule milestone -FF-2-> task"
        """
        . 08  10  12  14  16
        A                 ▒▒██ A
        B ████████████         B
        . 01  02  05  06  07   Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            -2,
            date(2016, 9, 1),
            date(2016, 9, 5),
            {
                "A": [0, 17, 17, 17, 17, 17, 17, 0, 0],
                "B": [5, 8, 13, 12, 17, 8, 13, 4, 4],
            },
        )

    def test_FF_plus2(self):
        "schedule milestone -FF+2-> task"
        """
        . 16  18  20
        A   ██         A
        B ████████████ B
        . 07  08  09   Sep 2016
        """
        self._pred_is_milestone(
            "EE",
            2,
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [0, 17, 17, 18, 18, 17, 17, 1, 1],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class SuccessorIsMilestone(ScheduleTestCase):
    """
    Project
    └ A 07.09. - 09.09.
    └ B automatic milestone

    A -link-> B
    """

    def _succ_is_milestone(
        self, link_type, gap, b_end, network, constraint_type=None, constraint_date=None
    ):
        """
        Project
        └ A 07.09. - 09.09.
        └ B automatic milestone

        A -link-> B
        """
        self.is_milestone(self.b)
        if constraint_type is None:
            self.schedule_automatically(self.b, ASAP)
        else:
            self.schedule_automatically(self.b, constraint_type, constraint_date)
        self.link_tasks(link_type, self.a, self.b, gap)
        self.schedule_project()
        self.assertNetworkEqual(network)
        self.assert_dates(
            [
                [self.a, self.original_start_a, self.original_end_a],
                [self.b, b_end, b_end],
            ]
        )

    def test_SS(self):
        "schedule task -SS-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B ██▒▒         B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AA",
            0,
            date(2016, 9, 7),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 16, 16, 21, 21, 16, 16, 5, 5],
            },
        )

    def test_SF(self):
        "schedule task -SF-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B ██▒▒         B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AE",
            0,
            date(2016, 9, 7),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 16, 16, 21, 21, 16, 16, 5, 5],
            },
        )

    def test_FS_minus2(self):
        "schedule task -FS-2-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B     ██       B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            -2,
            date(2016, 9, 8),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 18, 18, 21, 21, 18, 18, 3, 3],
            },
        )

    def test_FF_minus2(self):
        "schedule task -FF-2-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B     ██       B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EE",
            -2,
            date(2016, 9, 8),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 18, 18, 21, 21, 18, 18, 3, 3],
            },
        )

    def test_SS_plus2(self):
        "schedule task -SS+2-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B       ██     B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AA",
            2,
            date(2016, 9, 8),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 19, 19, 21, 21, 19, 19, 2, 2],
            },
        )

    def test_SF_plus2(self):
        "schedule task -SF+2-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B       ██     B
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AE",
            2,
            date(2016, 9, 8),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 19, 19, 21, 21, 19, 19, 2, 2],
            },
        )

    def test_FS(self):
        "schedule task -FS-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B         ▒▒██ B early MS scheduled optimally / late
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            0,
            date(2016, 9, 9),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 21, 21, 21, 21, 21, 21, 0, 0],
            },
        )

    def test_FF(self):
        "schedule task -FF-> milestone"
        """
        . 16  18  20
        A ████████████ A
        B         ▒▒██ B early MS scheduled optimally / late
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EE",
            0,
            date(2016, 9, 9),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 21, 21, 21, 21, 21, 21, 0, 0],
            },
        )

    def test_SS_minus2(self):
        "schedule task -SS-2-> milestone"
        """
        . 12  14  16  18  20
        A         ████████████ A
        B ██▒▒                 B
        . 05  06  07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AA",
            -2,
            date(2016, 9, 5),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 12, 12, 21, 21, 12, 12, 9, 9],
            },
        )

    def test_SF_minus2(self):
        "schedule task -SF-2-> milestone"
        """
        . 12  14  16  18  20
        A         ████████████ A
        B ██▒▒                 B
        . 05  06  07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "AE",
            -2,
            date(2016, 9, 5),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 12, 12, 21, 21, 12, 12, 9, 9],
            },
        )

    def test_FS_plus2(self):
        "schedule task -FS+2-> milestone"
        """
        . 16  18  20  22  24
        A ████████████         A
        B                 ▒▒██ B early MS scheduled optimally / late
        . 07  08  09  12  13   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            2,
            date(2016, 9, 13),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 25, 25, 25, 25, 25, 25, 0, 0],
            },
        )

    def test_FF_plus2(self):
        "schedule task -FF+2-> milestone"
        """
        . 16  18  20  22  24
        A ████████████         A
        B                 ▒▒██ B early MS scheduled optimally / late
        . 07  08  09  12  13   Sep 2016
        """
        self._succ_is_milestone(
            "EE",
            2,
            date(2016, 9, 13),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 25, 25, 25, 25, 25, 25, 0, 0],
            },
        )

    def test_FS_SNET_1(self):
        "schedule task -FS-> milestone (SNET +1)"
        """
        . 16  18  20  22
        A ████████████     A
        B             ██▒▒ B milestone SNET 22
        . 07  08  09  12   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            0,
            date(2016, 9, 12),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 22, 22, 22, 22, 22, 22, 0, 0],
            },
            SNET,
            date(2016, 9, 12),
        )

    def test_FS_SNET_minus1(self):
        "schedule task -FS-> milestone (SNET -1)"
        """
        . 16  18  20
        A ████████████ A
        B         ▒▒██ B milestone SNET 21
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            0,
            date(2016, 9, 9),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 21, 21, 21, 21, 21, 21, 0, 0],
            },
            SNET,
            date(2016, 9, 9),
        )

    def test_FS_SNET_minus2(self):
        "schedule task -FS-> milestone (SNET -2)"
        """
        . 16  18  20
        A ████████████ A
        B         ▒▒██ B milestone SNET 20
        . 07  08  09   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            0,
            date(2016, 9, 9),
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [0, 21, 21, 21, 21, 21, 21, 0, 0],
            },
            SNET,
            date(2016, 9, 8),
        )

    def test_FS_FNET_1(self):
        "schedule task -FS-> milestone (FNET +1)"
        """
        . 16  18  20  22
        A ████████████     A
        B             ▒▒██ B milestone FNET 22
        . 07  08  09  12   Sep 2016
        """
        self._succ_is_milestone(
            "EA",
            0,
            date(2016, 9, 12),
            {
                "A": [5, 16, 21, 18, 23, 16, 21, 2, 2],
                "B": [0, 23, 23, 23, 23, 23, 23, 0, 0],
            },
            FNET,
            date(2016, 9, 12),
        )
