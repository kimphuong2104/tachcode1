#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from datetime import date

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import helpers, load_tasks
from cs.pcs.scheduling.calendar import IndexedCalendar

STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"
MSO, MFO, SNET, SNLT, FNET, FNLT = "234567"
FRIDAY = date(2023, 8, 11)
SATURDAY = date(2023, 8, 12)
MONDAY = date(2023, 8, 14)


def setup_module():
    testcase.run_level_setup()


@pytest.mark.parametrize(
    "index,fallback",
    [
        (0, 2),
        (2, 1),
    ],
)
def test_get_value_raises(index, fallback):
    "raises if index does not exist"
    network = [None, 111]
    with pytest.raises(IndexError):
        helpers.get_value(network, index, fallback)


@pytest.mark.parametrize(
    "index,expected",
    [
        (0, 111),
        (1, 222),
        (2, 111),
    ],
)
def test_get_value(index, expected):
    network = [111, 222, None]
    result = helpers.get_value(network, index, 0)
    assert result == expected


@mock.patch.object(helpers, "add_duration")
@mock.patch.object(helpers, "get_duration_as_network")
def test_convert_days2network_default_end_from_dr(
    get_duration_as_network, add_duration
):
    valdict = {
        "end_time_fcast": "",
        "start_time_fcast": "S",
        "days_fcast": "D",
        "position_fix": "PF",
    }

    assert (
        helpers.convert_days2network(
            None,
            valdict,
            [],
            ["end_time_fcast"],
            {},
        )
        is None
    )
    assert valdict == {
        "start_time_fcast": "S",
        "days_fcast": "D",
        "position_fix": "PF",
        "end_time_fcast": add_duration.return_value,
    }
    add_duration.assert_called_once_with(
        "S", get_duration_as_network.return_value, "PF", True
    )
    get_duration_as_network.assert_called_once_with("D", 1, 0)


@mock.patch.object(helpers, "get_duration")
def test_convert_days2network(get_duration):
    "mutates valdict"
    calendar = mock.Mock()
    calendar.day2network.side_effect = lambda x, _, __: x.upper()
    valdict = {
        "s1": "start1",
        "s2": "start2",
        "e1": "end1",
        "e2": "",
        "foo": "bar",
        "start_is_early": "?",
    }

    assert (
        helpers.convert_days2network(
            calendar,
            valdict,
            ["s1", "s2"],
            ["e1", "e2"],
            {"d1": ("s1", "e1"), "d2": ("s2", "e2")},
        )
        is None
    )
    assert valdict == {
        "s1": "START1",
        "s2": "START2",
        "e1": "END1",
        "e2": "",
        "d1": get_duration.return_value,
        "d2": get_duration.return_value,
        "foo": "bar",
        "start_is_early": "?",
    }
    calendar.day2network.assert_has_calls(
        [
            mock.call("start1", True, "?"),
            mock.call("start2", True, "?"),
            mock.call("end1", False, 0),
            mock.call("", False, 0),
        ],
        any_order=True,
    )
    assert calendar.day2network.call_count == 4
    get_duration.assert_has_calls(
        [
            mock.call("START1", "END1"),
            mock.call("START2", ""),
        ]
    )
    assert get_duration.call_count == 2


@pytest.mark.parametrize(
    "constraint_type,expected",
    [
        (MSO, (2, MONDAY)),
        (MFO, (1, FRIDAY)),
        (SNET, (2, MONDAY)),
        (SNLT, (0, FRIDAY)),
        (FNET, (3, MONDAY)),
        (FNLT, (1, FRIDAY)),
    ],
)
def test_convert_days2network_fix_constraint_dates(constraint_type, expected):
    calendar = IndexedCalendar(STANDARD_PROFILE, FRIDAY)
    assert calendar.day2network(FRIDAY, True, True) == 0
    task = {
        "constraint_type": constraint_type,
        "constraint_date": SATURDAY,
    }
    helpers.convert_days2network(calendar, task, [], [], {})
    assert (
        task["constraint_date"],
        calendar.network2day(task["constraint_date"]),
    ) == expected


def test_get_task_date_fields_raises():
    "[_get_task_date_fields] raises if key is missing"
    with pytest.raises(KeyError) as error:
        helpers._get_task_date_fields({})

    assert str(error.value) == "'milestone'"


@pytest.mark.parametrize(
    "milestone,is_early,expected",
    [
        (0, 0, load_tasks.DATES_TASK),
        (0, 1, load_tasks.DATES_TASK),
        (1, 0, load_tasks.DATES_MILESTONE),
        (1, 1, load_tasks.DATES_MILESTONE),
    ],
)
def test_get_task_date_fields(milestone, is_early, expected):
    "[_get_task_date_fields]"
    task = {
        "milestone": milestone,
        "start_is_early": is_early,
    }
    result = helpers._get_task_date_fields(task)
    assert result == expected


@mock.patch.object(helpers, "convert_days2network")
@mock.patch.object(helpers, "_get_task_date_fields", return_value="CDE")
def test_convert_task_dates(_get_task_date_fields, convert_days2network):
    "[convert_task_dates]"
    calendar = mock.Mock()
    assert helpers.convert_task_dates("AB", calendar) is None
    assert [x.call_count for x in (_get_task_date_fields, convert_days2network)] == [
        2,
        2,
    ]
    _get_task_date_fields.assert_has_calls(
        [
            mock.call("A"),
            mock.call("B"),
        ]
    )
    convert_days2network.assert_has_calls(
        [
            mock.call(calendar, "A", "C", "D", "E"),
            mock.call(calendar, "B", "C", "D", "E"),
        ]
    )
