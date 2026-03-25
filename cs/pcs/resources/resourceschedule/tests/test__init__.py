#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import datetime

import mock
import pytest

from cs.pcs.resources import resourceschedule
from cs.pcs.resources.resourceschedule import (
    _get_current_quarter,
    _get_end_date,
    _get_start_date,
    _get_valid_pools,
    _remove_duplicates_in_hierarchy,
)

resource_schedules = {
    'a' : mock.MagicMock(parent_oid=''),
    'b' : mock.MagicMock(parent_oid='a'),
    'c' : mock.MagicMock(parent_oid='b'),
    'x' : mock.MagicMock(parent_oid=''),
}


def KeywordQuery(cdb_object_id):
    return [resource_schedules[cdb_object_id]]


@pytest.mark.parametrize("pools_input,pools_expected", [
    (['a','b','c','x'], ['a','x']),
    (['x','c','b','a'], ['x','a']),
    (['c'], ['c']),
])
@mock.patch("cs.pcs.resources.pools.ResourcePool.KeywordQuery", side_effect=KeywordQuery)
def test_remove_duplicates_in_hierarchy(mock_kwq, pools_input, pools_expected):
    # use sorted because the set(...) cast does not guarantee order
    assert sorted(_remove_duplicates_in_hierarchy(pools_input)) == sorted(pools_expected)


def test_get_current_quarter():
    expected = {1:1,2:1,3:1,
                4:2,5:2,6:2,
                7:3,8:3,9:3,
                10:4,11:4,12:4}
    result = {}
    for k in expected.keys():
        date = datetime.date(2023,k,1)
        result[k] = _get_current_quarter(date)
    assert expected == result


def test_get_start_date():
    testdata = [
        [2023, 1, [2022, 10, 1]],
        [2023, 2, [2022, 10, 1]],
        [2023, 3, [2022, 10, 1]],
        [2023, 4, [2023, 1, 1]],
        [2023, 5, [2023, 1, 1]],
        [2023, 6, [2023, 1, 1]],
        [2023, 7, [2023, 4, 1]],
        [2023, 8, [2023, 4, 1]],
        [2023, 9, [2023, 4, 1]],
        [2023, 10, [2023, 7, 1]],
        [2023, 11, [2023, 7, 1]],
        [2023, 12, [2023, 7, 1]]
    ]
    result = []
    for data in testdata:
        date = datetime.date(data[0],data[1],1)
        result.append(_get_start_date(date))
    assert result == [datetime.date(d[2][0],d[2][1],d[2][2]) for d in testdata]


def test_get_end_date():
    testdata = [
        [2023, 1, [2023, 7, 31]],
        [2023, 2, [2023, 7, 31]],
        [2023, 3, [2023, 7, 31]],
        [2023, 4, [2023, 10, 31]],
        [2023, 5, [2023, 10, 31]],
        [2023, 6, [2023, 10, 31]],
        [2023, 7, [2024, 1, 31]],
        [2023, 8, [2024, 1, 31]],
        [2023, 9, [2024, 1, 31]],
        [2023, 10, [2024, 4, 30]],
        [2023, 11, [2024, 4, 30]],
        [2023, 12, [2024, 4, 30]]
    ]
    result = []
    for data in testdata:
        date = datetime.date(data[0],data[1],1)
        result.append(_get_end_date(date))
    assert result == [datetime.date(d[2][0],d[2][1],d[2][2]) for d in testdata]


@pytest.mark.parametrize("start_date,end_date,memberships,expected_pool_ids", [
    (datetime.date(2022,10,1), datetime.date(2023,2,1), [[datetime.date(2023,1,1), None]], [0]),
    (datetime.date(2022,10,1), datetime.date(2023,2,1), [[datetime.date(2022,1,1), datetime.date(2022,9,1)]], []),
    (datetime.date(2022,10,1), datetime.date(2023,2,1), [[datetime.date(2022,1,1), datetime.date(2022,11,15)]], [0]),
    (datetime.date(2022,10,1), datetime.date(2023,2,1),
        [[datetime.date(2025,1,1), None], [datetime.date(2029,1,1), None]], []),
    (datetime.date(2022,10,1), datetime.date(2023,2,1),
        [[datetime.date(2021,1,1), None], [datetime.date(2023,1,1), None]], [0,1])
])
def test_get_valid_pools(start_date, end_date, memberships, expected_pool_ids):
    ms = []
    # pylint: disable-next=consider-using-enumerate
    for i in range(len(memberships)):
        m = mock.MagicMock(start_date=memberships[i][0], end_date=memberships[i][1], pool_oid=i)
        ms.append(m)
    with mock.patch.object(resourceschedule, "_get_start_date", return_value=start_date):
        with mock.patch.object(resourceschedule, "_get_end_date", return_value=end_date):
            assert _get_valid_pools(ms) == expected_pool_ids
