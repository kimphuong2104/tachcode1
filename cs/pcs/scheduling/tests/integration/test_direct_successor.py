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

ALAP, SNET = "14"


def setup_module():
    testcase.run_level_setup()


class ScheduleWithDirectSuccessorBase(ScheduleTestCase):
    def _set_up(self, mode, link_type):
        self.schedule_automatically(self.a, ALAP)
        self.schedule_automatically(self.b, mode, date(2016, 9, 12))
        self.link_tasks(link_type, self.a, self.b, 0)
        self.schedule_project()

    def _assert_dates(self, a_start, a_end, network):
        self.assertNetworkEqual(network)
        self.assert_dates(
            [
                [self.a, a_start, a_end],
                [self.b, date(2016, 9, 12), date(2016, 9, 14)],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectSuccessorALAP(ScheduleWithDirectSuccessorBase):
    def _alap(self, a_duration, link_type, a_start, a_end, network):
        self.set_task_duration(self.a, a_duration)
        self._set_up(SNET, link_type)
        self._assert_dates(a_start, a_end, network)

    def test_SS_2_days(self):
        "schedule ALAP task (duration 2) -SS-> task"
        """
        Expected Result:
            . 22  24  26
            A ████████     A
            B ████████████ B
            . 12  13  14   Sep 2016
        """
        self._alap(
            2,
            "AA",
            date(2016, 9, 12),
            date(2016, 9, 13),
            {
                "A": [3, 0, 3, 22, 25, 22, 25, 0, 22],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_SS_4_days(self):
        "schedule ALAP task (duration 4) -SS-> task"
        """
        Expected Result:
            . 20  22  24  26
            A ████████████     A
            B     ████████████ B
            . 09  12  13  14   Sep 2016
        """
        self._alap(
            4,
            "AA",
            date(2016, 9, 9),
            date(2016, 9, 14),
            {
                "A": [7, 0, 7, 20, 27, 20, 27, 0, 20],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_SF_3_days(self):
        "schedule ALAP task (duration 3) -SF-> task"
        """
        Expected Result:
            . 22  24  26
            A ████████████ A
            B ████████████ B
            . 12  13  14   Sep 2016
        """
        self._alap(
            3,
            "AE",
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 0, 5, 22, 27, 22, 27, 0, 22],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_FS_3_days(self):
        "schedule ALAP task (duration 3) -FS-> task"
        """
        Expected Result:
            . 16  18  20  22  24  26
            A ████████████             A
            B             ████████████ B
            . 07  08  09  12  13  14   Sep 2016
        """
        self._alap(
            3,
            "EA",
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [5, 0, 5, 16, 21, 16, 21, 0, 16],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_FF_2_days(self):
        "schedule ALAP task (duration 2) -FF-> task"
        """
        Expected Result:
            . 22  24  26
            A     ████████ A
            B ████████████ B
            . 12  13  14   Sep 2016
        """
        self._alap(
            2,
            "EE",
            date(2016, 9, 13),
            date(2016, 9, 14),
            {
                "A": [3, 0, 3, 24, 27, 24, 27, 0, 24],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_FF_4_days(self):
        "schedule ALAP task (duration 4) -FF-> task"
        """
        Expected Result:
            . 20  22  24  26
            A ████████████████ A
            B     ████████████ B
            . 09  12  13  14   Sep 2016
        """
        self._alap(
            4,
            "EE",
            date(2016, 9, 9),
            date(2016, 9, 14),
            {
                "A": [7, 0, 7, 20, 27, 20, 27, 0, 20],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )
