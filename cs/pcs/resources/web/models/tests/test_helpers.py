#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest
from webob.exc import HTTPBadRequest

from cs.pcs.resources.web.models import helpers


@pytest.mark.parametrize("year,quarter,last_day,expected", [
    (2023, 1, False, helpers.date(2023, 1, 1)),
    (2023, 2, False, helpers.date(2023, 4, 1)),
    (2023, 3, False, helpers.date(2023, 7, 1)),
    (2023, 4, False, helpers.date(2023, 10, 1)),
    (2023, 1, True, helpers.date(2023, 3, 31)),
    (2023, 2, True, helpers.date(2023, 6, 30)),
    (2023, 3, True, helpers.date(2023, 9, 30)),
    (2023, 4, True, helpers.date(2023, 12, 31)),
])
def test_get_quarter(year, quarter, last_day, expected):
    assert helpers.get_quarter(year, quarter, last_day) == expected


def test_get_timeframe():
    request = mock.Mock(json={
        "extraDataProps": {
            "timeFrameStartYear": 2023,
            "timeFrameStartQuarter": 1,
            "timeFrameUntilYear": 2024,
            "timeFrameUntilQuarter": 3,
        }
    })
    expected = (helpers.date(2023, 1, 1), helpers.date(2024, 9, 30))
    assert helpers.get_timeframe(request) == expected


def test_get_timeframe_missing_key():
    request = mock.Mock(json={})

    with pytest.raises(helpers.HTTPBadRequest):
        helpers.get_timeframe(request)


@mock.patch.object(helpers.logging, "error")
def test_get_timeframe_missing_sub_keys(log_error):
    request = mock.Mock(json={
        "extraDataProps": {
            "timeFrameStartQuarter": "Q",
        }
    })

    with pytest.raises(helpers.HTTPBadRequest):
        helpers.get_timeframe(request)

    log_error.assert_called_once_with(
        "missing keys: %s",
        {"timeFrameUntilQuarter", "timeFrameUntilYear", "timeFrameStartYear"},
    )


@mock.patch.object(helpers.logging, "error")
def test_get_timeframe_invalid_values(log_error):
    request = mock.Mock(json={
        "extraDataProps": {
            "timeFrameStartYear": 2023,
            "timeFrameStartQuarter": 1,
            "timeFrameUntilYear": "Y",
            "timeFrameUntilQuarter": "q",
        }
    })

    with pytest.raises(helpers.HTTPBadRequest):
        helpers.get_timeframe(request)

    log_error.assert_called_once_with(
        "invalid timeFrameUntilYear: 'Y', invalid timeFrameUntilQuarter: 'q'"
    )


@pytest.mark.parametrize("json,expected", [
    ({"k1": "foo"}, []),
    ({"evaluate_project_ids": "foo"}, []),
    ({"evaluate_project_ids": ["id0", "id1", "id3"]}, ["id0", "id1", "id3"]),
])
def test_get_prj_ids(json, expected):
    assert helpers.get_prj_ids(json) == expected


def test_get_prj_ids_raises():
    "exception is raises for non-string project IDs"
    with pytest.raises(HTTPBadRequest):
        helpers.get_prj_ids({"evaluate_project_ids": ["id0", "id1", 2]})
