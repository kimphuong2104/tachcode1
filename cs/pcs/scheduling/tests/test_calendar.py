#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

"""
Calendar tests

Test fixtures look at this week in February, 2023:

day        15  16  17  18  19  20  21  22
------------------------------------------
workday?   X   X   X   -   X   -   X   X
exception?                 X   X
weekday    Wed Thu Fri Sat Sun Mon Tue Wed

leading to these workday indexes:

index  -3  -2  -1   0   1   2   3   4   5
Feb23  10  13  14  15  16  17  19  21  22
"""

from contextlib import contextmanager

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import calendar


def setup_module():
    testcase.run_level_setup()


def feb23(day):
    return calendar.date(2023, 2, day)


DAY_EXC_FREE = feb23(20)  # monday
DAY_EXC_WORK = feb23(19)  # sunday
UUID = "fixture"


@contextmanager
def mocked_calendar_fixtures(bitmask=None):
    "fixture variant 1: simply mock access and replace return values"
    with (
        mock.patch.object(
            calendar,
            "get_calendar_workday_bitmask",
            return_value=bitmask or (1, 1, 1, 1, 1, 0, 0),
        ),
        mock.patch.object(
            calendar,
            "get_calendar_exceptions",
            return_value={
                DAY_EXC_FREE: 0,
                DAY_EXC_WORK: 1,
            },
        ),
    ):
        yield


def persistent_calendar_fixtures():
    """
    fixture variant 2: actually create fixtures in database
    (MUST be used in test decorated with testcase.rollback)
    """
    calendar.CalendarProfile.CreateNoResult(
        cdb_object_id=UUID,
        name="Test Profile",
        description="-",
        mo_type_id=1,
        tu_type_id=1,
        we_type_id=1,
        th_type_id=1,
        fr_type_id=1,
        sa_type_id=2,
        su_type_id=2,
    )
    calendar.CalendarException.CreateNoResult(
        calendar_profile_id=UUID,
        day=DAY_EXC_FREE,
        day_type_id=3,
        description="this is not a workday, normally it would be",
        cdb_object_id="fixture exc free",
    )
    calendar.CalendarException.CreateNoResult(
        calendar_profile_id=UUID,
        day=DAY_EXC_WORK,
        day_type_id=1,
        description="this is a workday, normally it wouldn't be",
        cdb_object_id="fixture exc work",
    )
    calendar.get_calendar_workday_bitmask.cache_clear()
    calendar.get_calendar_exceptions.cache_clear()


@mock.patch.object(calendar.sqlapi, "RecordSet2", return_value=[])
def test_get_calendar_workday_bitmask_unknown(RecordSet2):
    "get_calendar_workday_bitmask fails for unknown profiles"
    calendar.get_calendar_workday_bitmask.cache_clear()
    for _ in range(2):
        with pytest.raises(ValueError) as error:
            calendar.get_calendar_workday_bitmask(None)

        assert str(error.value) == "unknown calendar profile: 'None'"

    assert RecordSet2.call_count == 2  # exception prevents caching


@mock.patch.object(calendar.sqlapi, "RecordSet2", return_value=[])
def test_get_calendar_exceptions_unknown(RecordSet2):
    "get_calendar_exceptions empty for unknown profiles"
    calendar.get_calendar_exceptions.cache_clear()
    for _ in range(2):
        assert calendar.get_calendar_exceptions(None) == {}

    RecordSet2.assert_called_once()  # no second call due to cache hit


@testcase.rollback
@pytest.mark.parametrize(
    "func,expected",
    [
        (calendar.get_calendar_workday_bitmask, (1, 1, 1, 1, 1, 0, 0)),
        (calendar.get_calendar_exceptions, {DAY_EXC_WORK: 1, DAY_EXC_FREE: 0}),
    ],
)
def test_get_calendar_workday_bitmask(func, expected):
    "get_calendar_workday_bitmask and get_calendar_exceptions work and are cached"
    persistent_calendar_fixtures()
    with mock.patch.object(
        calendar.sqlapi, "RecordSet2", side_effect=calendar.sqlapi.RecordSet2
    ) as RecordSet2:
        assert func(UUID) == expected

    RecordSet2.assert_called_once()  # no second call due to cache hit


@pytest.mark.parametrize(
    "handler,cls,action,mode",
    [
        ("clear_profile_cache", calendar.CalendarProfile, "modify", "post"),
        ("clear_profile_cache", calendar.CalendarProfile, "delete", "post"),
        ("clear_exception_cache", calendar.CalendarException, "create", "post"),
        ("clear_exception_cache", calendar.CalendarException, "copy", "post"),
        ("clear_exception_cache", calendar.CalendarException, "modify", "post"),
        ("clear_exception_cache", calendar.CalendarException, "delete", "post"),
    ],
)
def test_signal_connected(handler, cls, action, mode):
    "UE handlers are connected to their slots"
    slot_names = [
        (x.__module__, x.__name__) for x in calendar.sig.find_slots(cls, action, mode)
    ]
    assert ("cs.pcs.scheduling.calendar", handler) in slot_names


@pytest.mark.parametrize(
    "call_func,cached_func",
    [
        (calendar.clear_profile_cache, calendar.get_calendar_workday_bitmask),
        (calendar.clear_exception_cache, calendar.get_calendar_exceptions),
    ],
)
def test_clear_cache(call_func, cached_func):
    "UE handlers clear caches if not ctx.error"
    with mock.patch.object(cached_func, "cache_clear") as clear:
        call_func(None, mock.Mock(error=False))
    clear.assert_called_once_with()


@pytest.mark.parametrize(
    "call_func,cached_func",
    [
        (calendar.clear_profile_cache, calendar.get_calendar_workday_bitmask),
        (calendar.clear_exception_cache, calendar.get_calendar_exceptions),
    ],
)
def test_clear_cache_error(call_func, cached_func):
    "UE handlers do not clear caches if ctx.error"
    with mock.patch.object(cached_func, "cache_clear") as clear:
        call_func(None, mock.Mock(error=True))
    clear.assert_not_called()


def test_get_indexed_calendar_later():
    "loads later dates (start = saturday)"
    with mocked_calendar_fixtures():
        # feb23(18) is a saturday
        result = calendar.get_indexed_calendar(
            "foo",
            feb23(18),
            6,
            -2,
        )

    assert result == (
        {
            feb23(19): -2,
            feb23(21): -1,
            feb23(22): 0,
            feb23(23): 1,
            feb23(24): 2,
            feb23(27): 3,
        },
        {
            -2: feb23(19),
            -1: feb23(21),
            0: feb23(22),
            1: feb23(23),
            2: feb23(24),
            3: feb23(27),
        },
    )


def test_get_indexed_calendar_earlier():
    "loads earlier dates"
    with mocked_calendar_fixtures():
        # feb23(22) is a wednesday
        result = calendar.get_indexed_calendar(
            "foo",
            feb23(22),
            -6,
            4,
        )

    assert result == (
        {
            feb23(22): 4,
            feb23(21): 3,
            feb23(19): 2,
            feb23(17): 1,
            feb23(16): 0,
            feb23(15): -1,
        },
        {
            4: feb23(22),
            3: feb23(21),
            2: feb23(19),
            1: feb23(17),
            0: feb23(16),
            -1: feb23(15),
        },
    )


def test_IndexedCalendar_init_no_workdays():
    "fails if profile has not workdays"
    with mocked_calendar_fixtures((0, 0, 0, 0, 0, 0, 0)):
        with pytest.raises(ValueError) as error:
            calendar.IndexedCalendar("foo", feb23(15), 5)

    assert str(error.value) == "calendar profile without workdays"


def test_IndexedCalendar_init_no_next_workday():
    "fails if profile has no next workday"
    start = feb23(20)
    with (
        mock.patch.object(
            calendar,
            "get_calendar_workday_bitmask",
            return_value=(1, 0, 0, 0, 0, 0, 0),
        ),
        mock.patch.object(
            calendar,
            "get_calendar_exceptions",
            return_value={
                (start + calendar.timedelta(days=index)): 0 for index in range(0, 92, 7)
            },
        ),
    ):
        cal = calendar.IndexedCalendar("foo", start, 1)
        with pytest.raises(ValueError) as error:
            cal.day2network(start, True, True)

    assert str(error.value) == "no next workday found"


def test_IndexedCalendar_init_datetime():
    "time info of start is cut"
    start = calendar.datetime(2023, 2, 15, 11, 12, 13)

    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", start, 5)

    assert cal.start_date == feb23(15)


def test_IndexedCalendar_init():
    start = feb23(15)

    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", start, 5)

    assert (
        cal.calendar_profile_id,
        cal.start_date,
        cal.pagesize,
    ) == ("foo", start, 5)
    assert (cal._workday_bitmask, cal._exceptions, cal._by_offset,) == (
        (1, 1, 1, 1, 1, 0, 0),
        {
            feb23(19): 1,
            feb23(20): 0,
        },
        {
            0: feb23(15),
            1: feb23(16),
            2: feb23(17),
            3: feb23(19),
            4: feb23(21),
        },
    )


@mock.patch.object(calendar, "date")
@mock.patch.object(calendar.IndexedCalendar, "_load_page")
def test_IndexedCalendar_init_defaults(_load_page, date):
    with mocked_calendar_fixtures():
        indexed = calendar.IndexedCalendar("foo", None)

    assert (indexed.calendar_profile_id, indexed.start_date, indexed.pagesize,) == (
        "foo",
        date.today.return_value,
        265,
    )
    _load_page.assert_called_once_with(date.today.return_value, 0)


def test_IndexedCalendar_get_pagesize():
    cal = mock.Mock(
        spec=calendar.IndexedCalendar,
        pagesize=5,
    )
    assert [
        calendar.IndexedCalendar._get_pagesize(cal, min_pagesize)
        for min_pagesize in [-3, -7, 0, 3, 7]
    ] == [-5, -8, 5, 5, 8]


@mock.patch.object(
    calendar,
    "get_indexed_calendar",
    return_value=({"DATE": "OFFSET"}, {"offset": "date"}),
)
def test_IndexedCalendar_load_page(_):
    cal = mock.Mock(
        spec=calendar.IndexedCalendar,
        calendar_profile_id="foo",
        _by_day={"D": "O"},
        _by_offset={"o": "d"},
    )
    start = feb23(8)
    assert calendar.IndexedCalendar._load_page(cal, start, -2) is None
    assert cal._by_day == {"D": "O", "DATE": "OFFSET"}
    assert cal._by_offset == {"o": "d", "offset": "date"}


def test_IndexedCalendar_load_next_page():
    cal = mock.Mock(
        spec=calendar.IndexedCalendar,
        _by_offset={5: "five", 7: "seven"},
    )
    assert calendar.IndexedCalendar._load_next_page(cal, -2) is None
    assert calendar.IndexedCalendar._load_next_page(cal, 3) is None

    cal._load_page.assert_has_calls(
        [
            mock.call("five", 5, -2),
            mock.call("seven", 7, 3),
        ]
    )
    assert cal._load_page.call_count == 2


@pytest.mark.parametrize(
    "offset,loads,expected",
    [
        (0, [], feb23(15)),  # one already loaded
        (4, [2], feb23(17)),  # load later
        (-4, [-2], feb23(13)),  # load earlier
        (8, [4], feb23(21)),  # load exceptions
    ],
)
def test_IndexedCalendar_network2day(offset, loads, expected):
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(15), 1)
        with mock.patch.object(
            cal, "_load_next_page", side_effect=cal._load_next_page
        ) as load:
            result = cal.network2day(offset)

    assert result == expected
    load.assert_has_calls([mock.call(x) for x in loads])
    assert load.call_count == len(loads)


@pytest.mark.parametrize(
    "day,expected",
    [
        (feb23(17), 1),  # regular workday
        (feb23(18), 0),  # regular day off
        (feb23(19), 1),  # exceptional workday
        (feb23(20), 0),  # exceptional day off
    ],
)
def test_IndexedCalendar_is_workday(day, expected):
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(15), 1)
        assert cal._is_workday(day) == expected


@pytest.mark.parametrize(
    "day,is_start,expected",
    [
        (feb23(17), True, feb23(17)),
        (feb23(18), True, feb23(19)),
        (feb23(19), True, feb23(19)),
        (feb23(20), True, feb23(21)),
        (feb23(17), False, feb23(17)),
        (feb23(18), False, feb23(17)),
        (feb23(19), False, feb23(19)),
        (feb23(20), False, feb23(19)),
    ],
)
def test_IndexedCalendar_get_next_workday(day, is_start, expected):
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(15), 1)
        assert cal._get_next_workday(day, is_start) == expected


@pytest.mark.parametrize(
    "day,start,early,loads,expected",
    [
        (None, 0, 0, None, 3),  # default offsets
        (None, 0, 1, None, 2),
        (None, 1, 0, None, 1),
        (None, 1, 1, None, 0),
        (feb23(15), 0, 0, None, 1),  # day 1 already loaded
        (feb23(15), 0, 1, None, 0),
        (feb23(15), 1, 0, None, 1),
        (feb23(15), 1, 1, None, 0),
        (feb23(21), 0, 0, feb23(21), 9),  # load day after loaded days
        (feb23(21), 0, 1, feb23(21), 8),
        (feb23(21), 1, 0, feb23(21), 9),
        (feb23(21), 1, 1, feb23(21), 8),
        (feb23(18), 0, 0, feb23(17), 5),  # load non-working day after loaded days
        (feb23(18), 0, 1, feb23(17), 4),
        (feb23(18), 1, 0, feb23(19), 7),
        (feb23(18), 1, 1, feb23(19), 6),
        (feb23(13), 0, 0, feb23(13), -3),  # load day before loaded days
        (feb23(13), 0, 1, feb23(13), -4),
        (feb23(13), 1, 0, feb23(13), -3),
        (feb23(13), 1, 1, feb23(13), -4),
        (feb23(12), 0, 0, feb23(10), -5),  # load non-working day before loaded days
        (feb23(12), 0, 1, feb23(10), -6),
        (feb23(12), 1, 0, feb23(13), -3),
        (feb23(12), 1, 1, feb23(13), -4),
    ],
)
def test_IndexedCalendar_day2network(day, start, early, loads, expected):
    "IndexedCalendar.day2network"
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(15), 1)
        with mock.patch.object(
            cal, "_load_until_day", side_effect=cal._load_until_day
        ) as load:
            result = cal.day2network(day, start, early)

    assert result == expected
    if loads:
        load.assert_called_once_with(loads)
    else:
        load.assert_not_called()


@pytest.mark.parametrize(
    "day,expected",
    [
        (
            calendar.date.min,
            [-1055093, -1055094, -1055093, -1055094],
        ),  # 01.01.0001, a monday
        # skip date.max as it's just not worth the runtime
        # (calendar.date.max, [4162135, 4162134, 4162135, 4162134]),  # 31.12.9999, a friday
    ],
)
def test_IndexedCalendar_day2network_extremes(day, expected):
    "IndexedCalendar.day2network works close to min and max dates"
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(15), 1)
        assert [
            cal.day2network(day, a, b) for a, b in ((0, 0), (0, 1), (1, 0), (1, 1))
        ] == expected


def test_IndexedCalendar_str():
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(9), 3)
        cal._load_next_page(-2)

    assert str(cal) == "IndexedCalendar [-2: 2023-02-07] - [2: 2023-02-13] (5 workdays)"


def test_IndexedCalendar_str_not_loaded():
    with mocked_calendar_fixtures():
        cal = calendar.IndexedCalendar("foo", feb23(9), 3)
        cal._by_offset.clear()

    assert str(cal) == "IndexedCalendar (not loaded)"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0),
        (-2, -1),
        (-1, -1),
        (0, 0),
        (1, 0),
        (2, 1),
        (3, 1),
    ],
)
def test_network2index(value, expected):
    assert calendar.network2index(value) == expected


@pytest.mark.parametrize(
    "value,is_early,expected",
    [
        (-1, True, -2),
        (-1, False, -1),
        (None, True, 0),
        (None, False, 1),
        (0, True, 0),
        (0, False, 1),
        (1, True, 2),
        (1, False, 3),
    ],
)
def test_index2network(value, is_early, expected):
    assert calendar.index2network(value, is_early) == expected


@pytest.mark.parametrize(
    "dr,eas,eaf,expected",
    [
        (3, 0, 0, 6),
        (3, 0, 1, 7),
        (3, 1, 0, 5),
        (3, 1, 1, 6),
    ],
)
def test_get_duration_as_network(dr, eas, eaf, expected):
    """
    eas/eaf -> scheduling if duration 3 and no dates are given
    .  00  02  04  06  08
    00   ██████████████
    01   ████████████████
    10 ████████████
    11 ██████████████
    """
    assert calendar.get_duration_as_network(dr, eas, eaf) == expected


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (1, 0, -1),
        (None, None, 0),
        (0, 0, 0),
        (0, 1, 1),
        (0, 2, 1),
        (0, 3, 2),
        (1, 1, 0),
        (1, 2, 0),
        (1, 3, 1),
        (1, 4, 1),
    ],
)
def test_get_duration_in_days(start, end, expected):
    duration = calendar.get_duration_in_days(start, end)
    assert duration == expected


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (1, 0, -1),
        (None, None, 0),
        (0, 0, 0),
        (0, 1, 1),
        (0, 2, 2),
        (0, 3, 3),
        (1, 1, 0),
        (1, 2, 1),
        (1, 3, 2),
    ],
)
def test_get_duration(start, end, expected):
    duration = calendar.get_duration(start, end)
    assert duration == expected


@pytest.mark.parametrize(
    "a,duration,position_fix,is_start,expected",
    [
        # cases 1: position fix
        (0, 0, True, 0, 0),
        (0, 0, True, 1, 1),
        (1, 0, True, 0, 0),
        (1, 0, True, 1, 1),
        (0, -1, True, 0, -2),
        (0, 1, True, 1, 1),
        (1, -1, True, 0, 0),
        (1, 1, True, 1, 3),
        # cases 2: position not fix
        (0, 0, False, 0, 0),
        (0, 0, False, 1, 0),
        (0, -1, False, 0, -2),
        (0, 1, False, 1, 1),
        (0, -2, False, 0, -2),
        (0, 2, False, 1, 2),
        (0, -3, False, 0, -4),
        (0, 3, False, 1, 3),
        (1, 0, False, 0, 1),
        (1, 0, False, 1, 1),
        (1, -1, False, 0, 0),
        (1, 1, False, 1, 3),
        (1, -2, False, 0, -1),
        (1, 2, False, 1, 3),
        (1, -3, False, 0, -2),
        (1, 3, False, 1, 5),
    ],
)
def test_add_duration(a, duration, position_fix, is_start, expected):
    b = calendar.add_duration(a, duration, position_fix, is_start)
    assert b == expected


@pytest.mark.parametrize(
    "a,gap,position_fix,get_start,is_forward,expected",
    [
        # cases 1: position fix
        (0, 0, True, 0, 0, -1),
        (0, 0, True, 0, 1, 1),
        (0, 0, True, 1, 0, 0),
        (0, 0, True, 1, 1, 0),
        (0, 1, True, 0, 0, 1),
        (0, 1, True, 0, 1, 1),
        (0, 1, True, 1, 0, 2),
        (0, 1, True, 1, 1, 2),
        (0, -1, True, 0, 0, -3),
        (0, -1, True, 0, 1, -3),
        (0, -1, True, 1, 0, -2),
        (0, -1, True, 1, 1, -2),
        (1, 0, True, 0, 0, 1),
        (1, 0, True, 0, 1, 1),
        (1, 0, True, 1, 0, 0),
        (1, 0, True, 1, 1, 2),
        (1, 1, True, 0, 0, 3),
        (1, 1, True, 0, 1, 3),
        (1, 1, True, 1, 0, 4),
        (1, 1, True, 1, 1, 4),
        (1, -1, True, 0, 0, -1),
        (1, -1, True, 0, 1, -1),
        (1, -1, True, 1, 0, 0),
        (1, -1, True, 1, 1, 0),
        # cases 2: position not fix
        (0, 0, False, 0, 0, 0),
        (0, 0, False, 0, 1, 0),
        (0, 0, False, 1, 0, 0),
        (0, 0, False, 1, 1, 0),
        (0, 1, False, 0, 0, 1),
        (0, 1, False, 0, 1, 1),
        (0, 1, False, 1, 0, 1),
        (0, 1, False, 1, 1, 1),
        (0, -1, False, 0, 0, -2),
        (0, -1, False, 0, 1, -2),
        (0, -1, False, 1, 0, -2),
        (0, -1, False, 1, 1, -2),
        (1, 0, False, 0, 0, 1),
        (1, 0, False, 0, 1, 1),
        (1, 0, False, 1, 0, 1),
        (1, 0, False, 1, 1, 1),
        (1, 1, False, 0, 0, 3),
        (1, 1, False, 0, 1, 3),
        (1, 1, False, 1, 0, 3),
        (1, 1, False, 1, 1, 3),
        (1, -1, False, 0, 0, 0),
        (1, -1, False, 0, 1, 0),
        (1, -1, False, 1, 0, 0),
        (1, -1, False, 1, 1, 0),
    ],
)
def test_add_gap(a, gap, position_fix, get_start, is_forward, expected):
    b = calendar.add_gap(a, gap, position_fix, get_start, is_forward)
    assert b == expected
