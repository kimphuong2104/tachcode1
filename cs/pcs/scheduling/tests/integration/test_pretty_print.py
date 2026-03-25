#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# flake8: noqa

import unittest
from datetime import date

import pytest
from cdb import testcase

from cs.pcs.scheduling.calendar import IndexedCalendar
from cs.pcs.scheduling.pretty_print import pretty_print

STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.integration
class PrettyPrintBase(unittest.TestCase):
    maxDiff = None
    max_line_length = 100

    @classmethod
    def setUpClass(cls):
        cls.calendar = IndexedCalendar(STANDARD_PROFILE, date(2023, 3, 17))

    def pp(self, network, diff):
        return pretty_print(self.calendar, network, diff, self.max_line_length)


@pytest.mark.integration
class PrettyPrint(PrettyPrintBase):
    maxDiff = None
    network = {
        "A": [11, 22, 33, 44, 55, 2, 10, 66, 77],
        "B": [77, 66, 55, 44, 33, 4, 8, 22, 11],
    }
    diff = {
        "A": [11, 22, 33, 44, 55, 4, 6, 66, 77],
        "B": [77, 66, 55, 44, 33, 4, 8, 22, 11],
    }

    def test_no_diff(self):
        self.assertEqual(
            self.pp(self.network, None),
            """
Result                                 02  04  06  08  10
[11, 22, 33, 44, 55, 02, 10, 66, 77] A ██████████████████ A [OK]
[77, 66, 55, 44, 33, 04, 08, 22, 11] B     ██████████     B [OK]
                            Mar 2023   20  21  22  23  24   Mar 2023""",
        )

    def test_diff(self):
        self.assertEqual(
            self.pp(self.network, self.diff),
            """
Result                                 02  04  06  08  10   Expected
[11, 22, 33, 44, 55, 02, 10, 66, 77] A ▀▀▀▀██████▀▀▀▀▀▀▀▀ A [11, 22, 33, 44, 55, 04, 06, 66, 77]
[77, 66, 55, 44, 33, 04, 08, 22, 11] B     ▒▒▒▒▒▒▒▒▒▒     B [OK]
                            Mar 2023   20  21  22  23  24   Mar 2023""",
        )


@pytest.mark.integration
class PrettyPrintTruncated(PrettyPrintBase):
    network = {
        "A": [77, 66, 55, 44, 33, -400, 0, 22, 11],
        "B": [11, 22, 33, 44, 55, 0, 6, 66, 77],
    }
    diff = {
        "A": [77, 66, 55, 44, 33, -20, 4, 22, 11],
        "B": [11, 22, 33, 44, 55, 0, 6, 66, 77],
    }

    def test_truncated_no_diff(self):
        self.assertEqual(
            self.pp(self.network, None),
            """
Result                                   00  98 ...2  10  -8  -6  -4  -2  00  02  04  06
[77, 66, 55, 44, 33, -400, 00, 22, 11] A ███████...█████████████████████████             A [OK]
[11, 22, 33, 44, 55, 00, 06, 66, 77]   B        ...                       ██████████████ B [OK]
                              Jun 2022   10  13 ...9  10  13  14  15  16  17  20  21  22   Mar 2023""",
        )

    def test_truncated_diff(self):
        self.assertEqual(
            self.pp(self.network, self.diff),
            """
Result                                   00  98 ...  04  06   Expected
[77, 66, 55, 44, 33, -400, 00, 22, 11] A ▀▀▀▀▀▀▀...▄▄▄▄     A [77, 66, 55, 44, 33, -20, 04, 22, 11]
[11, 22, 33, 44, 55, 00, 06, 66, 77]   B        ...▒▒▒▒▒▒▒▒ B [OK]
                              Jun 2022   10  13 ...  21  22   Mar 2023""",
        )
