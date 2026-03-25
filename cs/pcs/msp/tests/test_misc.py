#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest

from cs.pcs.msp import misc


@pytest.mark.parametrize(
    "date_value,hours,expected",
    [
        (date(2024, 2, 29), None, "2024-02-29T00:00:00"),
        (date(2023, 8, 19), "08:15", "2023-08-19T08:15:00"),
        (date(2023, 8, 18), "17:1", "2023-08-18T17:01:00"),
    ],
)
def test_date2xml_date(date_value, hours, expected):
    assert misc.date2xml_date(date_value, hours) == expected


@pytest.mark.parametrize(
    "isodate_value,ignore_time,expected",
    [
        ("", False, (None, None)),
        ("", True, (None, None)),
        ("2024-02-29T00:00:00", True, (date(2024, 2, 29), None)),
        ("2024-02-29T07:01:02", False, (date(2024, 2, 29), None)),
        ("2024-02-29T08:01:02", False, (date(2024, 2, 29), None)),
        ("2024-02-29T08:00:02", False, (date(2024, 2, 29), 1)),
        ("2024-02-29T17:00:02", False, (date(2024, 2, 29), 0)),
    ],
)
def test_xml_date2date(isodate_value, ignore_time, expected):
    assert misc.xml_date2date(isodate_value, ignore_time) == expected
