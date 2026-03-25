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

ASAP, ALAP, MSO, MFO, SNET, SNLT, FNET, FNLT = "01234567"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithoutLinks(ScheduleTestCase):
    """
    - task scheduling depends only on project dates
    - successor is never rescheduled
    """

    def test_a_scheduled_manually(self):
        "schedule manually: no changes"
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 16, 21, 16, 21, 16, 21, 0, 0],
                "B": [5, 8, 13, 16, 21, 8, 13, 8, 8],
            }
        )
        self.assert_dates(
            [
                [self.a, self.original_start_a, self.original_end_a],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_ASAP(self):
        "schedule ASAP: starts with project"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, ASAP)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 8, 13, 0, 5, 8, 8],
                "B": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_ALAP(self):
        "schedule ALAP: ends when last task ends"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, ALAP)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 8, 13, 8, 13, 8, 8],
                "B": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 1), date(2016, 9, 5)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_MSO(self):
        "schedule MSO: starts @ constraint date"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, MSO, date(2016, 9, 8))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 8, 13, 18, 23, 8, 13, 10, 10],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_MFO(self):
        "schedule MFO: ends @ constraint date"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, MFO, date(2016, 9, 12))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 8, 13, 18, 23, 8, 13, 10, 10],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_SNLT(self):
        "schedule SNLT: starts with project"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, SNLT, date(2016, 9, 5))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 8, 13, 0, 5, 8, 8],
                "B": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_SNET(self):
        "schedule SNET"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, SNET, date(2016, 9, 4))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 12, 17, 12, 17, 12, 17, 0, 0],
                "B": [5, 8, 13, 12, 17, 8, 13, 4, 4],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 5), date(2016, 9, 7)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_FNLT(self):
        "schedule FNLT: starts with project"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, FNLT, date(2016, 9, 12))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 8, 13, 0, 5, 8, 8],
                "B": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_a_scheduled_FNET(self):
        "schedule FNET"
        """
        A: automatic
        B: fixed
        """
        self.schedule_automatically(self.a, FNET, date(2016, 9, 12))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 8, 13, 18, 23, 8, 13, 10, 10],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class MoveManualProjectStart(ScheduleTestCase):
    def setUp(self):
        super().setUp()
        self.calculate_manually(self.project)
        self.schedule_manually(self.a)
        self.schedule_manually(self.b)

    def test_move_manual_project_start(self):
        "schedule after moving project start"
        self.move_start(self.project, date(2016, 10, 26))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 16, 21, 38, 43, 16, 21, 22, 22],
                "B": [5, 8, 13, 38, 43, 8, 13, 30, 30],
            }
        )
        self.assert_dates(
            [
                [self.project, date(2016, 10, 26), date(2016, 11, 24)],
                [self.a, date(2016, 11, 7), date(2016, 11, 9)],
                [self.b, date(2016, 11, 1), date(2016, 11, 3)],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithoutLinksManualProject(ScheduleTestCase):
    def setUp(self):
        super().setUp()
        self.calculate_manually(self.project)
        self.schedule_automatically(self.a, ALAP)

    def test_recalculate(self):
        "schedule manual project"
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 38, 43, 38, 43, 38, 38],
                "B": [5, 8, 13, 38, 43, 8, 13, 30, 30],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 22), date(2016, 9, 26)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )
