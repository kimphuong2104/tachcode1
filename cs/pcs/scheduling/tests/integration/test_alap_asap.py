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

ASAP, ALAP, SNET, SNLT = "0145"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class ALAP_ASAP(ScheduleTestCase):
    """
    ASAP-Scheduled Tasks Following ALAP-Scheduled Task

    Setup:

    Project
    └ A duration 3, ASAP
    └ B duration 3, ALAP
    └ C duration 1, various (depends on test case)
    └ D duration 1, SNET 15.09. (pushes back project end for ALAP)

    A -FS-> B -FS-> C
    """

    def _alap_asap(self, b_start, b_end, c_end, c_constr, c_constr_date, network):
        self.schedule_automatically(self.a, ASAP)
        self.schedule_automatically(self.b, ALAP)
        c = ScheduleTestCase.create_task(
            self.a.cdb_project_id,
            self.a.ce_baseline_id,
            "C",
            date(2016, 9, 9),
            date(2016, 9, 9),
            1,
        )
        if c_constr is None:
            self.schedule_manually(c)
        else:
            self.schedule_automatically(c, c_constr, c_constr_date)
        d = ScheduleTestCase.create_task(
            self.a.cdb_project_id, self.a.ce_baseline_id, "D", None, None, 1
        )
        self.schedule_automatically(d, SNET, date(2016, 9, 15))
        self.link_tasks("EA", self.a, self.b)
        self.link_tasks("EA", self.b, c)
        self.schedule_project()
        self.assertNetworkEqual(network)
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, b_start, b_end],
                [c, c_end, c_end],
                [d, date(2016, 9, 15), date(2016, 9, 15)],
            ]
        )

    def test_c_ASAP(self):
        "schedule ALAP-ASAP chain with third successor ASAP"
        """
        Setup:
            - A duration 3, ASAP
            - B duration 3, ALAP
            - C duration 1, ASAP
            - D duration 1, SNET 15.09. (pushes back project end for ALAP)
            - A -FS-> B -FS-> C

        Expected Result:
            . 00  02  04  06  08  10  12  14  16  18  20  22  24  26  28
            A ████████████                                                 A
            B                                             ████████████     B
            C                                                         ████ C
            D                                                         ████ D
            . 26  29  30  31  01  02  05  06  07  08  09  12  13  14  15  Sep 2016
        """
        self._alap_asap(
            date(2016, 9, 12),
            date(2016, 9, 14),
            date(2016, 9, 15),
            ASAP,
            None,
            {
                "A": [5, 0, 5, 16, 21, 0, 5, 16, 16],
                "B": [5, 6, 11, 22, 27, 22, 27, 0, 16],
                "C": [1, 28, 29, 28, 29, 28, 29, 0, 0],
                "D": [1, 28, 29, 28, 29, 28, 29, 0, 0],
            },
        )

    def test_c_SNLT(self):
        "schedule ALAP-ASAP chain with third successor SNLT"
        """
        Setup:
            - A duration 3, ASAP
            - B duration 3, ALAP
            - C duration 1, SNLT 13.09.
            - D duration 1, SNET 15.09. (pushes back project end for ALAP)
            - A -FS-> B -FS-> C

        Expected Result:
            . 00  02  04  06  08  10  12  14  16  18  20  22  24  26  28
            A ████████████                                                 A
            B                                     ████████████             B
            C                                                 ████         C
            D                                                         ████ D
            . 26  29  30  31  01  02  05  06  07  08  09  12  13  14  15   Sep 2016
        """
        self._alap_asap(
            date(2016, 9, 8),
            date(2016, 9, 12),
            date(2016, 9, 13),
            SNLT,
            date(2016, 9, 13),
            {
                "A": [5, 0, 5, 12, 17, 0, 5, 12, 12],
                "B": [5, 6, 11, 18, 23, 18, 23, 0, 12],
                "C": [1, 24, 25, 24, 25, 24, 25, 0, 0],
                "D": [1, 28, 29, 28, 29, 28, 29, 0, 0],
            },
        )

    def test_c_manually(self):
        "schedule ALAP-ASAP chain with third manual successor"
        """
        Setup:
            - A duration 3, ASAP
            - B duration 3, ALAP
            - C duration 1, manually 09.09.
            - D duration 1, SNET 15.09. (pushes back project end for ALAP)
            - A -FS-> B -FS-> C

        Expected Result:
            . 00  02  04  06  08  10  12  14  16  18  20  22  24  26  28
            A ████████████                                                 A
            B                                             ████████████     B
            C                                         ████                 C
            D                                                         ████ D
            . 26  29  30  31  01  02  05  06  07  08  09  12  13  14  15   Sep 2016
        """
        self._alap_asap(
            date(2016, 9, 12),
            date(2016, 9, 14),
            date(2016, 9, 9),
            None,
            None,
            {
                "A": [5, 0, 5, 16, 21, 0, 5, 16, 16],
                "B": [5, 6, 11, 22, 27, 22, 27, 0, 16],
                "C": [1, 20, 21, 28, 29, 20, 21, 8, 8],
                "D": [1, 28, 29, 28, 29, 28, 29, 0, 0],
            },
        )
