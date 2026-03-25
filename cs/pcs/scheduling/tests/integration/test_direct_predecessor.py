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

ASAP, ALAP, MSO, MFO, SNET, SNLT, FNET, FNLT = "01234567"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class DoNotReschedule(ScheduleTestCase):
    def test_running_successor_is_fixed(self):
        "do not reschedule an already-running task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP, already started 01.09 - 05.09.
            - A -FS-> B

        Expected Result:
            . 08  10  12  14  16  18  20
            A                 ████████████ A
            B ████████████                 B (already started, so FS link is ignored)
            . 01  02  05  06  07  08  09   Sep 2016
        """
        self.schedule_automatically(self.b, ASAP)
        self.link_tasks("EA", self.a, self.b)
        self.b.Update(percent_complet=1)  # already running
        self.set_dates(self.a, date(2016, 9, 8), date(2016, 9, 12))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )

    def test_manual_task_is_fixed(self):
        "do not reschedule a manual task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B scheduled manually 01.09. - 05.09.
            - A -FS-> B

        Expected Result:
            . 08  10  12  14  16  18  20
            A                 ████████████ A
            B ████████████                 B
            . 01  02  05  06  07  08  09   Sep 2016
        """
        self.schedule_manually(self.b)
        self.link_tasks("EA", self.a, self.b)
        self.set_dates(self.a, date(2016, 9, 8), date(2016, 9, 12))
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, self.original_start_b, self.original_end_b],
            ]
        )


class ScheduleWithDirectPredecessorBase(ScheduleTestCase):
    def _set_up(self, mode, link_type, constraint_date=None, gap=0):
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B dynamic constraint
            - A -> B (dynamic link)
        """
        self.set_dates(self.a, date(2016, 9, 8), date(2016, 9, 12))
        self.schedule_automatically(self.b, mode, constraint_date)
        self.link_tasks(link_type, self.a, self.b, gap)
        self.schedule_project()

    def _assert_dates(self, b_start, b_end, network):
        self.assertNetworkEqual(network)
        self.assert_dates(
            [
                [self.a, date(2016, 9, 8), date(2016, 9, 12)],
                [self.b, b_start, b_end],
            ]
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorASAP(ScheduleWithDirectPredecessorBase):
    def test_ASAP_SS(self):
        "schedule ASAP task -SS-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B
            . 08  09  12   Sep 2016
        """
        self._set_up(ASAP, "AA")
        self._assert_dates(
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_ASAP_SS_plus2(self):
        "schedule ASAP task -SS+2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SS+2-> B

        Expected Result:
            . 18  20  22  24  26
            A ████████████         A
            B         ████████████ B
            . 08  09  12  13  14   Sep 2016
        """
        self._set_up(ASAP, "AA", gap=2)
        self._assert_dates(
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_ASAP_SS_minus2(self):
        "schedule ASAP task -SS-2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SS-2-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B
            . 06  07  08  09  12   Sep 2016
        """
        self._set_up(ASAP, "AA", gap=-2)
        self._assert_dates(
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )

    def test_ASAP_SF(self):
        "schedule ASAP task -SF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SF-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B
            . 06  07  08  09  12   Sep 2016
        """
        self._set_up(ASAP, "AE")
        self._assert_dates(
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )

    def test_ASAP_SF_plus2(self):
        "schedule ASAP task -SF+2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SF+2-> B

        Expected Result:
            . 16  18  20  22
            A     ████████████ A
            B ████████████     B
            . 07  08  09  12   Sep 2016
        """
        self._set_up(ASAP, "AE", gap=2)
        self._assert_dates(
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 16, 21, 18, 23, 16, 21, 2, 2],
            },
        )

    def test_ASAP_SF_minus2(self):
        "schedule ASAP task -SF-2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -SF-2-> B

        Expected Result:
            . 08  10  12  14  16  18  20  22
            A                     ████████████ A
            B ████████████                     B
            . 01  02  05  06  07  08  09  12   Sep 2016
        """
        self._set_up(ASAP, "AE", gap=-2)
        self._assert_dates(
            date(2016, 9, 1),
            date(2016, 9, 5),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 8, 13, 18, 23, 8, 13, 10, 10],
            },
        )

    def test_ASAP_FS(self):
        "schedule ASAP task -FS-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B
            . 08  09  12  13  14  15   Sep 2016
        """
        self._set_up(ASAP, "EA")
        self._assert_dates(
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_ASAP_FS_plus2(self):
        "schedule ASAP task -FS+2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FS+2-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32
            A ████████████                     A
            B                     ████████████ B
            . 08  09  12  13  14  15  16  19   Sep 2016
        """
        self._set_up(ASAP, "EA", gap=2)
        self._assert_dates(
            date(2016, 9, 15),
            date(2016, 9, 19),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_ASAP_FS_minus2(self):
        "schedule ASAP task -FS-2> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FS-2-> B

        Expected Result:
            . 18  20  22  24
            A ████████████     A
            B     ████████████ B
            . 08  09  12  13   Sep 2016
        """
        self._set_up(ASAP, "EA", gap=-2)
        self._assert_dates(
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_ASAP_FF(self):
        "schedule ASAP task -FF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B
            . 08  09  12   Sep 2016
        """
        self._set_up(ASAP, "EE")
        self._assert_dates(
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_ASAP_FF_plus2(self):
        "schedule ASAP task -FF+2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FF+2-> B

        Expected Result:
            . 18  20  22  24  26
            A ████████████         A
            B         ████████████ B
            . 08  09  12  13  14   Sep 2016
        """
        self._set_up(ASAP, "EE", gap=2)
        self._assert_dates(
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_ASAP_FF_minus2(self):
        "schedule ASAP task -FF-2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ASAP
            - A -FF-2-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B
            . 06  07  08  09  12   Sep 2016
        """
        self._set_up(ASAP, "EE", gap=-2)
        self._assert_dates(
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorMSO(ScheduleWithDirectPredecessorBase):
    def _mso1(self, mode, network):
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B MSO 15.09.
            - A -> B (link type is ``mode``, see caller)

        Expected Result:
            . 18  20  22  24  26  28  30  32
            A ████████████                     A
            B                     ████████████ B
            . 08  09  12  13  14  15  16  19   Sep 2016
        """
        self._set_up(MSO, mode, constraint_date=date(2016, 9, 15))
        self._assert_dates(date(2016, 9, 15), date(2016, 9, 19), network)

    def _mso2(self, mode, network):
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B MSO 02.09.
            - A -> B (link type is ``mode``, see caller)

        Expected Result:
            . 10  12  14  16  18  20  22
            A                 ████████████ A
            B ████████████                 B
            . 02  05  06  07  08  09  12   Sep 2016
        """
        self._set_up(MSO, mode, constraint_date=date(2016, 9, 2))
        self._assert_dates(date(2016, 9, 2), date(2016, 9, 6), network)

    def test_MSO_SS_later(self):
        "schedule MSO task -SS-> task (later)"
        self._mso1(
            "AA",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 10, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MSO_SS_earlier(self):
        "schedule MSO task -SS-> task (earlier)"
        self._mso2(
            "AA",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MSO_SF_later(self):
        "schedule MSO task -SF-> task (later)"
        self._mso1(
            "AE",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 10, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MSO_SF_earlier(self):
        "schedule MSO task -SF-> task (earlier)"
        self._mso2(
            "AE",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MSO_FS_later(self):
        "schedule MSO task -FS-> task (later)"
        self._mso1(
            "EA",
            {
                "A": [5, 18, 23, 22, 27, 18, 23, 4, 4],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MSO_FS_earlier(self):
        "schedule MSO task -FS-> task (earlier)"
        self._mso2(
            "EA",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MSO_FF_later(self):
        "schedule MSO task -FF-> task (later)"
        self._mso1(
            "EE",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 9, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MSO_FF_earlier(self):
        "schedule MSO task -FF-> task (earlier)"
        self._mso2(
            "EE",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorMFO(ScheduleWithDirectPredecessorBase):
    def _mfo1(self, mode, network):
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B MFO 19.09.
            - A -> B (link type is ``mode``, see caller)

        Expected Result:
            . 18  20  22  24  26  28  30  32
            A ████████████                     A
            B                     ████████████ B
            . 08  09  12  13  14  15  16  19   Sep 2016
        """
        self._set_up(MFO, mode, constraint_date=date(2016, 9, 19))
        self._assert_dates(date(2016, 9, 15), date(2016, 9, 19), network)

    def _mfo2(self, mode, network):
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B MFO 06.09.
            - A -> B (link type is ``mode``, see caller)

        Expected Result:
            . 10  12  14  16  18  20  22
            A                 ████████████ A
            B ████████████                 B
            . 02  05  06  07  08  09  12   Sep 2016
        """
        self._set_up(MFO, mode, constraint_date=date(2016, 9, 6))
        self._assert_dates(date(2016, 9, 2), date(2016, 9, 6), network)

    def test_MFO_SS_later(self):
        "schedule MFO task -SS-> task (later)"
        self._mfo1(
            "AA",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 10, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MFO_SS_earlier(self):
        "schedule MFO task -SS-> task (earlier)"
        self._mfo2(
            "AA",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MFO_SF_later(self):
        "schedule MFO task -SF-> task (later)"
        self._mfo1(
            "AE",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 10, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MFO_SF_earlier(self):
        "schedule MFO task -SF-> task (earlier)"
        self._mfo2(
            "AE",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MFO_FS_later(self):
        "schedule MFO task -FS-> task (later)"
        self._mfo1(
            "EA",
            {
                "A": [5, 18, 23, 22, 27, 18, 23, 4, 4],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MFO_FS_earlier(self):
        "schedule MFO task -FS-> task (earlier)"
        self._mfo2(
            "EA",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_MFO_FF_later(self):
        "schedule MFO task -FF-> task (later)"
        self._mfo1(
            "EE",
            {
                "A": [5, 18, 23, 28, 33, 18, 23, 9, 10],
                "B": [5, 28, 33, 28, 33, 28, 33, 0, 0],
            },
        )

    def test_MFO_FF_earlier(self):
        "schedule MFO task -FF-> task (earlier)"
        self._mfo2(
            "EE",
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorSNET(ScheduleWithDirectPredecessorBase):
    def _snet(self, mode, constr_date, b_start, b_end, network):
        self._set_up(SNET, mode, constraint_date=constr_date)
        self._assert_dates(b_start, b_end, network)

    def test_SNET_SS_constraint_wins(self):
        "schedule SNET task -SS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 09.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22  24
            A ████████████     A
            B     ████████████ B (constraint wins)
            . 08  09  12  13   Sep 2016
        """
        self._snet(
            "AA",
            date(2016, 9, 9),
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 2, 2],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_SNET_SS_link_wins(self):
        "schedule SNET task -SS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 07.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._snet(
            "AA",
            date(2016, 9, 7),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_SNET_SF_constraint_wins(self):
        "schedule SNET task -SF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 07.09.
            - A -SF-> B

        Expected Result:
            . 16  18  20  22
            A     ████████████ A
            B ████████████     B (constraint wins)
            . 07  08  09  12   Sep 2016
        """
        self._snet(
            "AE",
            date(2016, 9, 7),
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 16, 21, 18, 23, 16, 21, 2, 2],
            },
        )

    def test_SNET_SF_link_wins(self):
        "schedule SNET task -SF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 01.09.
            - A -SF-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B (link wins)
            . 06  07  08  09  12   Sep 2016
        """
        self._snet(
            "AE",
            date(2016, 9, 1),
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )

    def test_SNET_FS_constraint_wins(self):
        "schedule SNET task -FS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 14.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28  30
            A ████████████                 A
            B                 ████████████ B (constraint wins)
            . 08  09  12  13  14  15  16   Sep 2016
        """
        self._snet(
            "EA",
            date(2016, 9, 14),
            date(2016, 9, 14),
            date(2016, 9, 16),
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 2, 2],
                "B": [5, 26, 31, 26, 31, 26, 31, 0, 0],
            },
        )

    def test_SNET_FS_link_wins(self):
        "schedule SNET task -FS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 09.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B (link wins)
            . 08  09  12  13  14  15   Sep 2016
        """
        self._snet(
            "EA",
            date(2016, 9, 9),
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_SNET_FF_constraint_wins(self):
        "schedule SNET task -FF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 09.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22  24
            A ████████████     A
            B     ████████████ B (constraint wins)
            . 08  09  12  13   Sep 2016
        """
        self._snet(
            "EE",
            date(2016, 9, 9),
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 1, 2],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_SNET_FF_link_wins(self):
        "schedule SNET task -FF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNET 07.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._snet(
            "EE",
            date(2016, 9, 7),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorSNLT(ScheduleWithDirectPredecessorBase):
    def _snlt(self, mode, constr_date, b_start, b_end, network):
        self._set_up(SNLT, mode, constraint_date=constr_date)
        self._assert_dates(b_start, b_end, network)

    def test_SNLT_SS_constraint_wins(self):
        "schedule SNLT task -SS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNLT 02.09.
            - A -SS-> B

        Expected Result:
            . 10  12  14  16  18  20  22
            A                 ████████████ A
            B ████████████                 B (constraint wins)
            . 02  05  06  07  08  09  12   Sep 2016
        """
        self._snlt(
            "AA",
            date(2016, 9, 2),
            date(2016, 9, 2),
            date(2016, 9, 6),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_SNLT_SS_link_wins(self):
        "schedule SNLT task -SS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNLT 09.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._snlt(
            "AA",
            date(2016, 9, 9),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_SNLT_SF(self):
        "schedule SNLT task -SF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNLT 02.09.
            - A -SF-> B

        Expected Result:
            . 10  12  14  16  18  20  22
            A                 ████████████ A
            B ████████████                 B (constraint wins)
            . 02  05  06  07  08  09  12   Sep 2016
        """
        self._snlt(
            "AE",
            date(2016, 9, 2),
            date(2016, 9, 2),
            date(2016, 9, 6),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 10, 15, 10, 15, 10, 15, 0, 0],
            },
        )

    def test_SNLT_FS_link_wins(self):
        "schedule SNLT task -FS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNLT 15.09.
            - A -SF-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B (link wins)
            . 08  09  12  13  14  15   Sep 2016
        """
        self._snlt(
            "EA",
            date(2016, 9, 15),
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_SNLT_FS_violation(self):
        "schedule SNLT task -FS-> task (constraint violates link)"
        """
        Setup:
            - A scheduled manually 08.09 - 12.09.
            - B SNLT 12.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26
            A ████████████         A
            B         ████████████ B (constraint wins, violating link)
            . 08  09  12  13  14   Sep 2016
        """
        self._snlt(
            "EA",
            date(2016, 9, 12),
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_SNLT_FF(self):
        "schedule SNLT task -FF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B SNLT 08.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._snlt(
            "EE",
            date(2016, 9, 8),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorFNET(ScheduleWithDirectPredecessorBase):
    def _fnet(self, mode, constr_date, b_start, b_end, network):
        self._set_up(FNET, mode, constraint_date=constr_date)
        self._assert_dates(b_start, b_end, network)

    def test_FNET_SS_constraint_wins(self):
        "schedule FNET task -SS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 13.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22  24
            A ████████████     A
            B     ████████████ B (constraint wins)
            . 08  09  12  13   Sep 2016
        """
        self._fnet(
            "AA",
            date(2016, 9, 13),
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 2, 2],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_FNET_SS_link_wins(self):
        "schedule FNET task -SS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 09.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._fnet(
            "AA",
            date(2016, 9, 9),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_FNET_SF_constraint_wins(self):
        "schedule FNET task -SF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 13.09.
            - A -SF-> B

        Expected Result:
            . 12  14  18  20  22  24
            A         ████████████     A
            B             ████████████ B (constraint wins)
            . 06  07  08  09  12  13   Sep 2016
        """
        self._fnet(
            "AE",
            date(2016, 9, 13),
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 2, 2],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_FNET_SF_link_wins(self):
        "schedule FNET task -SF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 07.09.
            - A -SF-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B (link wins)
            . 06  07  08  09  12   Sep 2016
        """
        self._fnet(
            "AE",
            date(2016, 9, 7),
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )

    def test_FNET_FS_constraint_wins(self):
        "schedule FNET task -FS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 20.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34
            A ████████████                         A
            B                         ████████████ B (constraint wins)
            . 08  09  12  13  14  15  16  19  20   Sep 2016
        """
        self._fnet(
            "EA",
            date(2016, 9, 20),
            date(2016, 9, 16),
            date(2016, 9, 20),
            {
                "A": [5, 18, 23, 24, 29, 18, 23, 6, 6],
                "B": [5, 30, 35, 30, 35, 30, 35, 0, 0],
            },
        )

    def test_FNET_FS_link_wins(self):
        "schedule FNET task -FS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 12.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B (link wins)
            . 08  09  12  13  14  15   Sep 2016
        """
        self._fnet(
            "EA",
            date(2016, 9, 12),
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_FNET_FF_constraint_wins(self):
        "schedule FNET task -FF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 20.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34
            A ████████████                         A
            B                         ████████████ B (constraint wins)
            . 08  09  12  13  14  15  16  19  20   Sep 2016
        """
        self._fnet(
            "EE",
            date(2016, 9, 20),
            date(2016, 9, 16),
            date(2016, 9, 20),
            {
                "A": [5, 18, 23, 30, 35, 18, 23, 11, 12],
                "B": [5, 30, 35, 30, 35, 30, 35, 0, 0],
            },
        )

    def test_FNET_FF_link_wins(self):
        "schedule FNET task -FF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNET 09.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._fnet(
            "EE",
            date(2016, 9, 9),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorFNLT(ScheduleWithDirectPredecessorBase):
    def _fnlt(self, mode, constr_date, b_start, b_end, network):
        self._set_up(FNLT, mode, constraint_date=constr_date)
        self._assert_dates(b_start, b_end, network)

    def test_FNLT_SS_link_wins(self):
        "schedule FNLT task -SS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 14.09.
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._fnlt(
            "AA",
            date(2016, 9, 14),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_FNLT_SS_constraint_wins(self):
        "schedule FNLT task -SS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 09.09.
            - A -SS-> B

        Expected Result:
            . 16  18  20  22
            A     ████████████ A
            B ████████████     B (constraint wins)
            . 07  08  09  12   Sep 2016
        """
        self._fnlt(
            "AA",
            date(2016, 9, 9),
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )

    def test_FNLT_SF_link_wins(self):
        "schedule FNLT task -SF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 14.09.
            - A -SF-> B

        Expected Result:
            . 14  16  18  20  22
            A         ████████████ A
            B ████████████         B (link wins)
            . 06  07  08  09  12   Sep 2016
        """
        self._fnlt(
            "AE",
            date(2016, 9, 14),
            date(2016, 9, 6),
            date(2016, 9, 8),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 14, 19, 4, 4],
            },
        )

    def test_FNLT_SF_constraint_wins(self):
        "schedule FNLT task -SF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 07.09.
            - A -SF-> B

        Expected Result:
            . 12  14  16  18  20  22
            A             ████████████ A
            B ████████████             B (constraint wins)
            . 05  06  07  08  09  12   Sep 2016
        """
        self._fnlt(
            "AE",
            date(2016, 9, 7),
            date(2016, 9, 5),
            date(2016, 9, 7),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 12, 17, 12, 17, 12, 17, 0, 0],
            },
        )

    def test_FNLT_FS_link_wins(self):
        "schedule FNLT task -FS-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 20.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B (link wins)
            . 08  09  12  13  14  15   Sep 2016
        """
        self._fnlt(
            "EA",
            date(2016, 9, 20),
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_FNLT_FS_constraint_wins(self):
        "schedule FNLT task -FS-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 14.09.
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26
            A ████████████         A
            B         ████████████ B (constraint wins)
            . 08  09  12  13  14   Sep 2016
        """
        self._fnlt(
            "EA",
            date(2016, 9, 14),
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_FNLT_FF_link_wins(self):
        "schedule FNLT task -FF-> task (link wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 20.09.
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (link wins)
            . 08  09  12   Sep 2016
        """
        self._fnlt(
            "EE",
            date(2016, 9, 20),
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_FNLT_FF_constraint_wins(self):
        "schedule FNLT task -FF-> task (constraint wins)"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B FNLT 09.09.
            - A -FF-> B

        Expected Result:
            . 16  18  20  22
            A     ████████████ A
            B ████████████     B (constraint wins)
            . 07  08  09  12   Sep 2016
        """
        self._fnlt(
            "EE",
            date(2016, 9, 9),
            date(2016, 9, 7),
            date(2016, 9, 9),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 16, 21, 16, 21, 16, 21, 0, 0],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorALAPAuto(ScheduleWithDirectPredecessorBase):
    def _alap(self, mode, gap, b_start, b_end, network):
        self._set_up(ALAP, mode, gap=gap)
        self._assert_dates(b_start, b_end, network)

    def test_auto_SS_plus9(self):
        "schedule ALAP auto task -SS+9-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SS+9-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40
            A ████████████                                     A
            B                                     ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23   Sep 2016
        """
        self._alap(
            "AA",
            9,
            date(2016, 9, 21),
            date(2016, 9, 23),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 36, 41, 36, 41, 36, 41, 0, 0],
            },
        )

    def test_auto_SF(self):
        "schedule ALAP auto task -SF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B (ALAP pushes link-based end of 18 back as far as possible)
            . 08  09  12   Sep 2016
        """
        self._alap(
            "AE",
            0,
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 18, 23, 4, 4],
            },
        )

    def test_auto_SF_plus4(self):
        "schedule ALAP auto task -SF+4-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SF+4-> B

        Expected Result:
            . 18  20  22  24
            A ████████████     A
            B     ████████████ B
            . 08  09  12  13  14   Sep 2016
        """
        self._alap(
            "AE",
            4,
            date(2016, 9, 9),
            date(2016, 9, 13),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 20, 25, 20, 25, 20, 25, 0, 0],
            },
        )

    def test_auto_FS(self):
        "schedule ALAP auto task -FS-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28
            A ████████████             A
            B             ████████████ B
            . 08  09  12  13  14  15   Sep 2016
        """
        self._alap(
            "EA",
            0,
            date(2016, 9, 13),
            date(2016, 9, 15),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 24, 29, 24, 29, 24, 29, 0, 0],
            },
        )

    def test_auto_FF(self):
        "schedule ALAP auto task -FF-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B
            . 08  09  12   Sep 2016
        """
        self._alap(
            "EE",
            0,
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 18, 23, 18, 23, 18, 23, 0, 0],
            },
        )

    def test_auto_FF_plus2(self):
        "schedule ALAP auto task -FF+2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF+2-> B

        Expected Result:
            . 18  20  22  24  26
            A ████████████         A
            B         ████████████ B
            . 08  09  12  13  14   Sep 2016
        """
        self._alap(
            "EE",
            2,
            date(2016, 9, 12),
            date(2016, 9, 14),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 22, 27, 22, 27, 22, 27, 0, 0],
            },
        )

    def test_auto_FF_minus2(self):
        "schedule ALAP auto task -FF-2-> task"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF-2-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B ████████████ B
            . 08  09  12   Sep 2016
        """
        self._alap(
            "EE",
            -2,
            date(2016, 9, 8),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [5, 14, 19, 18, 23, 18, 23, 4, 4],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorALAPManual(ScheduleWithDirectPredecessorBase):
    def _alap(self, mode, gap, network):
        self.calculate_manually(self.project)
        self._set_up(ALAP, mode, gap=gap)
        self._assert_dates(date(2016, 9, 22), date(2016, 9, 26), network)

    def test_manual_SS_plus9(self):
        "schedule ALAP manual task -SS+9> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SS+9-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "AA",
            9,
            {
                "A": [5, 18, 23, 20, 25, 18, 23, 2, 2],
                "B": [5, 36, 41, 38, 43, 38, 43, 2, 2],
            },
        )

    def test_manual_SF(self):
        "schedule ALAP manual task -SF-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SF-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "AE",
            0,
            {
                "A": [5, 18, 23, 38, 43, 18, 23, 20, 20],
                "B": [5, 14, 19, 38, 43, 38, 43, 24, 24],
            },
        )

    def test_manual_SF_plus4(self):
        "schedule ALAP manual task -SF+4-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -SF+4-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "AE",
            4,
            {
                "A": [5, 18, 23, 36, 41, 18, 23, 18, 18],
                "B": [5, 20, 25, 38, 43, 38, 43, 18, 18],
            },
        )

    def test_manual_FS(self):
        "schedule ALAP manual task -FS-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FS-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "EA",
            0,
            {
                "A": [5, 18, 23, 32, 37, 18, 23, 14, 14],
                "B": [5, 24, 29, 38, 43, 38, 43, 14, 14],
            },
        )

    def test_manual_FF(self):
        "schedule ALAP manual task -FF-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "EE",
            0,
            {
                "A": [5, 18, 23, 38, 43, 18, 23, 19, 20],
                "B": [5, 18, 23, 38, 43, 38, 43, 20, 20],
            },
        )

    def test_manual_FF_plus2(self):
        "schedule ALAP manual task -FF+2-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF+2-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "EE",
            2,
            {
                "A": [5, 18, 23, 34, 39, 18, 23, 16, 16],
                "B": [5, 22, 27, 38, 43, 38, 43, 16, 16],
            },
        )

    def test_manual_FF_minus2(self):
        "schedule ALAP manual task -FF-2-> task"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FF-2-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                         ████████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self._alap(
            "EE",
            -2,
            {
                "A": [5, 18, 23, 38, 43, 18, 23, 20, 20],
                "B": [5, 14, 19, 38, 43, 38, 43, 24, 24],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorALAPShort(ScheduleWithDirectPredecessorBase):
    """
    edge case: successor duration is shorter
    """

    def _alap(self, b_start, b_end, network):
        self.set_task_duration(self.b, 2)
        self._set_up(ALAP, "AA")
        self._assert_dates(b_start, b_end, network)

    def test_auto(self):
        "schedule ALAP auto successor duration is shorter"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B (duration 2) ALAP
            - A -SS-> B

        Expected Result:
            . 18  20  22
            A ████████████ A
            B     ████████ B
            . 08  09  12   Sep 2016
        """
        self._alap(
            date(2016, 9, 9),
            date(2016, 9, 12),
            {
                "A": [5, 18, 23, 18, 23, 18, 23, 0, 0],
                "B": [3, 18, 21, 20, 23, 20, 23, 2, 2],
            },
        )

    def test_manual(self):
        "schedule ALAP manual successor duration is shorter"
        """
        Setup:
            - Project calculated manually
            - A scheduled manually 08.09. - 12.09.
            - B (duration 2) ALAP
            - A -SS-> B

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                             ████████ B
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self.calculate_manually(self.project)
        self._alap(
            date(2016, 9, 23),
            date(2016, 9, 26),
            {
                "A": [5, 18, 23, 38, 43, 18, 23, 20, 20],
                "B": [3, 18, 21, 40, 43, 40, 43, 22, 22],
            },
        )


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ScheduleWithDirectPredecessorALAPUnrelated(ScheduleWithDirectPredecessorBase):
    """
    edge case: last task is unrelated to others,
    but postpones the project end
    """

    def _alap(self, b_start, b_end, network):
        self.set_task_duration(self.b, 2)
        self.c = ScheduleTestCase.create_task(
            self.b.cdb_project_id,
            self.b.ce_baseline_id,
            "C",
            date(2016, 9, 16),
            date(2016, 9, 16),
            1,
        )
        self._set_up(ALAP, "EA")
        self._assert_dates(b_start, b_end, network)

    def test_auto(self):
        "schedule ALAP auto unlinked tasks"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B duration 2, ALAP
            - A -FS-> B
            - C scheduled manually 16.09. - 16.09.

        Expected Result:
            . 18  20  22  24  26  28  30
            A ████████████                 A
            B                     ████████ B
            C                         ████ C
            . 08  09  12  13  14  15  16   Sep 2016
        """
        self._alap(
            date(2016, 9, 15),
            date(2016, 9, 16),
            {
                "A": [5, 18, 23, 22, 27, 18, 23, 4, 4],
                "B": [3, 24, 27, 28, 31, 28, 31, 4, 4],
                "C": [1, 30, 31, 30, 31, 30, 31, 0, 0],
            },
        )

    def test_manual(self):
        "schedule ALAP manual unlinked tasks"
        """
        Setup:
            - A scheduled manually 08.09. - 12.09.
            - B ALAP
            - A -FS-> B
            - C scheduled manually 16.09. - 16.09.
            - project end is not calculated automatically

        Expected Result:
            . 18  20  22  24  26  28  30  32  34  36  38  40  42
            A ████████████                                         A
            B                                             ████████ B
            C                         ████                         C
            . 08  09  12  13  14  15  16  19  20  21  22  23  26   Sep 2016
        """
        self.calculate_manually(self.project)
        self._alap(
            date(2016, 9, 23),
            date(2016, 9, 26),
            {
                "A": [5, 18, 23, 34, 39, 18, 23, 16, 16],
                "B": [3, 24, 27, 40, 43, 40, 43, 16, 16],
                "C": [1, 30, 31, 42, 43, 30, 31, 12, 12],
            },
        )
