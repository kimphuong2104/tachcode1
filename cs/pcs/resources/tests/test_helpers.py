#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date, datetime

import pytest

from cs.pcs.resources import helpers


@pytest.mark.parametrize("date_str,expected", [
    ("01.08.2022", date(2022, 8, 1)),
    ("01.08.2022 10:11:12", date(2022, 8, 1)),
    ("", None),
    (None, None),
    (0, None),
])
def test_date_from_legacy_str(date_str, expected):
    assert helpers.date_from_legacy_str(date_str) == expected


@pytest.mark.parametrize("date_str,expected", [
    ("2022-08-01", ValueError),
    ("x", ValueError),
    (1, TypeError),
    (date(2022, 8, 1), TypeError),
])
def test_date_from_legacy_str_fails(date_str, expected):
    with pytest.raises(expected):
        helpers.date_from_legacy_str(date_str)


@pytest.mark.parametrize("date_value,expected", [
    (date(2022, 8, 1), "01.08.2022"),
    (datetime(2022, 8, 1, 10, 11, 12), "01.08.2022"),
])
def test_to_legacy_str(date_value, expected):
    assert helpers.to_legacy_str(date_value) == expected


@pytest.mark.parametrize("date_value,expected", [
    ("01.08.2022", AttributeError),
    (None, AttributeError),
    (1, AttributeError),
])
def test_to_legacy_str_fails(date_value, expected):
    with pytest.raises(expected):
        helpers.to_legacy_str(date_value)


@pytest.mark.parametrize("date_value,expected", [
    (date(2022, 8, 1), "2022-08-01"),
    (datetime(2022, 8, 1, 10, 11, 12), "2022-08-01"),
])
def test_to_iso_date(date_value, expected):
    assert helpers.to_iso_date(date_value) == expected


@pytest.mark.parametrize("date_value,expected", [
    ("x", AttributeError),
    (None, AttributeError),
    (1, AttributeError),
])
def test_to_iso_date_fails(date_value, expected):
    with pytest.raises(expected):
        helpers.to_iso_date(date_value)
