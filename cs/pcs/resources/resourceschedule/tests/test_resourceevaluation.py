#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest

from cs.pcs.resources.resourceschedule import resourceevaluation


@pytest.mark.parametrize("weekday,expected", [
    (-2, 0),
    (-1, 0),
    (0, 0),
    (1, 6),
    (2, 5),
    (3, 4),
    (4, 3),
    (5, 2),
    (6, 1),
    (7, 0),
    (8, -1),
])
def test_next_monday(weekday, expected):
    assert resourceevaluation.next_monday(weekday) == expected


def test_next_monday_raises():
    with pytest.raises(TypeError):
        resourceevaluation.next_monday(None)


@pytest.mark.parametrize("weekday,expected", [
    (-2, 1),
    (-1, 0),
    (0, -1),
    (1, -2),
    (2, -3),
    (3, -4),
    (4, -5),
    (5, -6),
    (6, 0),
    (7, 0),
    (8, 0),
])
def test_last_sunday(weekday, expected):
    assert resourceevaluation.last_sunday(weekday) == expected


def test_last_sunday_raises():
    with pytest.raises(TypeError):
        resourceevaluation.last_sunday(None)


@pytest.mark.parametrize("interval,start,end,expected", [
    ("foo", "bar", "baz", ("bar", "baz")),
    ("day", "s", "e", ("s", "e")),
    ("week", date(2023, 9, 20), date(2023, 10, 3), (date(2023, 9, 25), date(2023, 10, 1))),
    ("month", date(2023, 9, 20), date(2023, 10, 3), (date(2023, 9, 1), date(2023, 10, 31))),
    ("quarter", date(2023, 9, 20), date(2023, 10, 3), (date(2023, 7, 1), date(2023, 12, 31))),
    ("half-year", date(2023, 9, 20), date(2023, 10, 3), (date(2023, 7, 1), date(2023, 12, 31))),
])
def test_sanitize_interval(interval, start, end, expected):
    assert resourceevaluation.sanitize_interval(interval, start, end) == expected
