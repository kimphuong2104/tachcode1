#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Resolves calendar profiles including global exceptions
without using ``cdb_calendar_entry``.
Does NOT respect personal exceptions.
"""

import logging
from datetime import date, datetime, timedelta
from math import ceil

from cdb import sig, sqlapi
from cdb.lru_cache import lru_cache
from cs.calendar import CalendarException, CalendarProfile

CALENDAR_WORKDAY_BITMASK = """
WITH workdays AS (
    SELECT day_type_id
    FROM cdb_day_type
    WHERE is_day_off_type = 0
)
SELECT
    CASE WHEN mo_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday0,
    CASE WHEN tu_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday1,
    CASE WHEN we_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday2,
    CASE WHEN th_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday3,
    CASE WHEN fr_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday4,
    CASE WHEN sa_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday5,
    CASE WHEN su_type_id IN (SELECT day_type_id FROM workdays) THEN 1 ELSE 0 END AS workday6
FROM (
    SELECT mo_type_id, tu_type_id, we_type_id, th_type_id, fr_type_id, sa_type_id, su_type_id
    FROM cdb_calendar_profile
    WHERE cdb_object_id = '{}'
) cal_prof
"""
CALENDAR_EXCEPTIONS = """
SELECT
    cdb_cal_prof_exc.day,
    cdb_day_type.is_day_off_type
FROM cdb_cal_prof_exc
JOIN cdb_day_type
    ON cdb_cal_prof_exc.day_type_id = cdb_day_type.day_type_id
WHERE calendar_profile_id = '{}'
"""


@lru_cache(maxsize=10)
def get_calendar_workday_bitmask(calendar_profile_id):
    """
    :param calendar_profile_id: ID of calendar profile
    :type calendar_profile_id: str

    :returns: A bitmask of seven bits where each bit represents if the weekday
        (starting with monday) is a workday in this calendar profile or not.
    :rtype: tuple
    """
    query = CALENDAR_WORKDAY_BITMASK.format(sqlapi.quote(calendar_profile_id))
    for record in sqlapi.RecordSet2(sql=query):
        return tuple(
            int(x)
            for x in [record[f"workday{weekday_index}"] for weekday_index in range(7)]
        )
    raise ValueError(f"unknown calendar profile: '{calendar_profile_id}'")


@lru_cache(maxsize=10)
def get_calendar_exceptions(calendar_profile_id):
    """
    :param calendar_profile_id: ID of calendar profile
    :type calendar_profile_id: str

    :returns: Mapping of exceptional days (``datetime.date``)
        to ``int`` values indicating whether
        this day is a workday or not.
    :rtype: dict
    """
    query = CALENDAR_EXCEPTIONS.format(sqlapi.quote(calendar_profile_id))
    exceptions = {
        record.day.date(): int(not record.is_day_off_type)
        for record in sqlapi.RecordSet2(sql=query)
    }
    return exceptions


@sig.connect(CalendarProfile, "modify", "post")
@sig.connect(CalendarProfile, "delete", "post")
def clear_profile_cache(_, ctx):
    """
    Clear cached results of `get_calendar_workday_bitmask`
    after successfully changing or deleting calendar profiles.
    """
    if not ctx.error:
        get_calendar_workday_bitmask.cache_clear()


@sig.connect(CalendarException, "create", "post")
@sig.connect(CalendarException, "copy", "post")
@sig.connect(CalendarException, "modify", "post")
@sig.connect(CalendarException, "delete", "post")
def clear_exception_cache(_, ctx):
    """
    Clear cached results of `get_calendar_exceptions`
    after successful CRUD operations on calendar profile exceptions.
    """
    # clear cache after successful operations on existing calendar profile exceptions
    if not ctx.error:
        get_calendar_exceptions.cache_clear()


def get_indexed_calendar(
    calendar_profile_id, start_date, next_page, start_offset=0, target_date=None
):
    """
    :param calendar_profile_id: ID of calendar profile
    :type calendar_profile_id: str

    :param start_date: Date to represent ``start_offset``
    :type start_date: datetime.date

    :param next_page: Amount of calendar entries later than ``start_date`` to get.
        If negative, that many dates earlier than ``start_date`` are fetched.
    :type next_page: int

    :param start_offset: The index ``start_date`` represents
        in the return value (defaults to 0)
    :type start_offset: int

    :param target_date: (optional) Date to load. This overrides ``next_page`` if given.
    :type target_date: datetime.date

    :returns: Offsets indexed by dates and dates indexed by offsets
        for converting between both.
    :rtype: tuple of dict
    """
    workday_bitmask = get_calendar_workday_bitmask(calendar_profile_id)
    exceptions = get_calendar_exceptions(calendar_profile_id)

    if target_date:
        direction = 1 if target_date > start_date else -1
    else:
        direction = 1 if next_page > 0 else -1
        pagesize = abs(next_page)

    offset = start_offset
    by_day, by_offset = {}, {}
    day = date(start_date.year, start_date.month, start_date.day)

    def stop(day):
        if target_date:
            if direction > 0:
                return day >= target_date
            return day <= target_date
        else:
            return len(by_offset) >= pagesize

    while True:
        exception = exceptions.get(day, None)
        if exception is None:
            is_workday = workday_bitmask[day.weekday()]
        else:
            is_workday = exception

        if is_workday:
            by_day[day] = offset
            by_offset[offset] = day
            offset += direction

        if stop(day):
            break

        try:
            day = day + timedelta(days=direction)
        except OverflowError:
            logging.exception(
                "requested day: %s (min: %s, max: %s)", day, date.min, date.max
            )
            break

    return by_day, by_offset


class IndexedCalendar:
    """
    Provides conversions between dates and values of the scheduling network
    relative to a given start date.

    Internally, dates are represented as offsets
    relative to a given absolute start date.

    Scheduling network values are integers,
    representing the start and end of each workday.
    So the workday at calendar offset 5 is represented by the network values
    10 (the start of workday 5) and 11 (the end of workday 5).
    Use the provided conversion methods ``network2day`` and ``day2network``
    to convert between these.

    During initialization and when converting values not seen before,
    the "rules" of a calendar profile are loaded
    (which weekdays are workdays, which specific days are exceptions?).
    These rules for the 10 least recently used profiles are cached.

    .. note ::

        This class does NOT use the single days persisted in the DB table
        `cdb_calendar_entry` for better (and more predictable) performance.
    """

    def __init__(self, calendar_profile_id, start_date, pagesize=None):
        """
        :param calendar_profile_id: ID of calendar profile
        :type calendar_profile_id: str

        :param start_date: Date to represent offset 0.
            If a `datetime.datetime` is given, it is converted to `date`.
            Defaults to today's date.
        :type start_date: datetime.date

        :param pagesize: Minimal amount of calendar entries to load on cache misses.
            If negative, the absolute value is used.
            Defaults to 265 (approx. one year with an average of 5 workdays per week).
        :type pagesize: int

        :raises ValueError: if the calendar profile does not exist
            or has no regular workdays.
        """
        self.calendar_profile_id = calendar_profile_id

        if not start_date:
            self.start_date = date.today()
        elif isinstance(start_date, datetime):
            self.start_date = start_date.date()
        else:
            self.start_date = start_date

        self._by_day = {}
        self._by_offset = {}
        self.pagesize = abs(pagesize) if pagesize else 265
        self._workday_bitmask = get_calendar_workday_bitmask(self.calendar_profile_id)
        if not sum(self._workday_bitmask):
            raise ValueError("calendar profile without workdays")
        self._exceptions = get_calendar_exceptions(self.calendar_profile_id)
        self._load_page(self.start_date, 0)

    def _get_pagesize(self, min_pagesize=0):
        if min_pagesize < 0:
            return min(min_pagesize - 1, -self.pagesize, -1)

        return max(min_pagesize + 1, self.pagesize, 1)

    def _load_page(self, start_date, start_offset, min_pagesize=0):
        pagesize = self._get_pagesize(min_pagesize)
        by_day, by_offset = get_indexed_calendar(
            self.calendar_profile_id, start_date, pagesize, start_offset
        )
        self._by_day.update(by_day)
        self._by_offset.update(by_offset)

    def _load_next_page(self, min_pagesize):
        # may not be called before initializing _by_offset

        if min_pagesize > 0:
            # load page after max offset
            start_offset = max(self._by_offset)
        else:
            # load page before min offset
            start_offset = min(self._by_offset)

        start_date = self._by_offset[start_offset]
        self._load_page(start_date, start_offset, min_pagesize)

    def _load_until_day(self, target_date):
        if self._by_offset:
            max_offset = max(self._by_offset)
            min_offset = min(self._by_offset)

            if target_date > self._by_offset[max_offset]:
                # load page after max offset
                start_date = self._by_offset[max_offset]
                start_offset = max_offset
            elif target_date < self._by_offset[min_offset]:
                # load page before min offset
                start_date = self._by_offset[min_offset]
                start_offset = min_offset
            else:
                raise KeyError(target_date)
        else:
            start_offset = 0

        by_day, by_offset = get_indexed_calendar(
            self.calendar_profile_id,
            start_date,
            None,
            start_offset,
            target_date=target_date,
        )
        self._by_day.update(by_day)
        self._by_offset.update(by_offset)

    def network2day(self, network_value):
        """
        :param network_value: Scheduling network value to convert to date.
        :type network_value: int

        :returns: Date representing ``network_value`` in this calendar.
        :rtype: datetime.date
        """
        _offset = network2index(network_value)
        result = self._by_offset.get(_offset, None)

        if result is None:
            if _offset > 0:
                closest_offset = max(self._by_offset)
            else:
                closest_offset = min(self._by_offset)

            self._load_next_page(_offset - closest_offset)
            return self._by_offset[_offset]

        return result

    def _is_workday(self, day):
        exception = self._exceptions.get(day, None)
        if exception is None:
            return self._workday_bitmask[day.weekday()]
        return exception

    def _get_next_workday(self, day, fix_forward):
        if self._is_workday(day):
            return day

        # get next-later workday if fix_forward, else next-earlier one
        next_day = timedelta(days=(1 if fix_forward else -1))
        workday = day + next_day
        counter = 0

        while not self._is_workday(workday):
            workday += next_day
            counter += 1
            if counter > 90:  # prevent infinite loop
                raise ValueError("no next workday found")

        return workday

    def day2network(self, day, is_start, is_early, fix_forward=None):
        """
        :param day: Day to convert to scheduling network value.
            If ``day`` is not a workday, the next workday is used instead
            (or the previous workday, if ``is_start`` is falsy).
        :type day: datetime.date

        :param is_start: If ``True``, ``day`` represents
            a start / minimum date, else an end / maximum date.
            Only relevant if ``day`` is not a workday in this calendar.
        :type is_start: bool

        :param is_early: If ``True``, the return value represents
            the start of ``day``, else its end.
        :type is_early: bool

        :param fix_forward: Specifies how to handle non-workdays:
            - If ``None`` (default), the value of ``is_start`` is used instead.
            - If ``True``, the next workday following ``day`` is used.
            - If ``False``, the previous workday before ``day`` is used.
        :type fix_forward: bool

        :returns: Scheduling network value representing ``day``
            and ``is_early`` in this calendar.
        :rtype: int

        :raises TypeError: if ``day`` is not a ``datetime.date``
        """
        if not day:
            return index2network(int(not is_start), is_early)

        workday = self._get_next_workday(
            day, is_start if fix_forward is None else fix_forward
        )

        try:
            offset = self._by_day[workday]
        except KeyError:
            # missing, so load difference
            self._load_until_day(workday)
            offset = self._by_day[workday]

        return index2network(offset, is_early)

    def __str__(self):
        if self._by_offset:
            max_days = max(self._by_offset)
            min_days = min(self._by_offset)
            return (
                f"IndexedCalendar [{min_days}: {self._by_offset[min_days]}]"
                f" - [{max_days}: {self._by_offset[max_days]}]"
                f" ({len(self._by_offset)} workdays)"
            )

        return "IndexedCalendar (not loaded)"


def network2index(network_value):
    """
    :param network_value: Scheduling network value to convert to calendar index.
    :type network_value: int

    :returns: Calendar index representing the same day as ``network_value``
    :rtype: int
    """
    if not network_value:
        return 0

    return network_value // 2


def index2network(index, is_early):
    """
    :param index: Calendar index to convert to scheduling network value.
    :type index: int

    :param is_early: If true, the result is to represent the start of the workday.
        Else, it'll represent the end of the workday.
    :type is_early: bool

    :returns: Scheduling network value index representing the same day as ``index``
    :rtype: int
    """
    return 2 * (index or 0) + (0 if is_early else 1)


def get_duration_as_network(duration, eas, eaf):
    """
    :param duration: Duration in days ("days_fcast")
    :type duration: int

    :param eas: "start_is_early"; 0 or 1
    :type eas: int

    :param eaf: "end_is_early"; 0 or 1
    :type eaf: int
    """
    if eas == eaf:
        modifier = 0
    elif eas:
        modifier = -1
    elif eaf:
        modifier = 1
    return 2 * duration + modifier


def get_duration_in_days(start, end):
    """
    :param start: Scheduling network value of the workday the tasks starts on
    :type start: int

    :param end: Scheduling network value of the workday the tasks ends on
    :type end: int

    :returns: the duration in workdays (not calendar days!)
    :rtype: int

    .. warning ::

        Invalid inputs (e.g. the task ends before it starts)
        will result in a negative duration.

        This is the case for the following inputs

        1. ``start`` is greater than ``end``
        2. ``start`` and ``end`` are equal,
        but the task starts late and ends early
    """
    start_index = network2index(start)
    end_index = network2index(end)
    return (
        1
        + end_index
        - start_index  # workday distance (but assume default of 1)
        - ((start or 0) % 2)  # late start -> 1 day shorter
        - (1 - ((end or 0) % 2))  # early end -> 1 day shorter
    )


def network2duration(offset):
    """
    :param offset: Scheduling network value representing the duration in days.
    :type offset: int

    :returns: Duration in days.
    :rtype: int
    """
    return ceil(offset / 2)


def get_duration(start, end):
    """
    :param start: Scheduling network value of the workday the tasks starts on
    :type start: int

    :param end: Scheduling network value of the workday the tasks ends on
    :type end: int

    :returns: the duration as scheduling network value
    :rtype: int

    .. warning ::

        Invalid inputs (e.g. the task ends before it starts)
        will result in a negative duration.

        This is the case for the following inputs

        1. ``start`` is greater than ``end``
        2. ``start`` and ``end`` are equal,
        but the task starts late and ends early
    """
    return (end or 0) - (start or 0)


def add_duration(origin, duration, position_fix, is_start):
    """
    Calculates a task start or end date based on the other date and a duration.
    Because durations as network values are ambigous,
    we cannot simply add them to a start index.

    :param origin: Scheduling network value of a workday.
        ``is_start`` determines if this represents a start or end date.
    :type origin: int

    :param duration: Duration as scheduling network value to add to ``origin``
    :type duration: int

    :param position_fix: If true, the result will map to default times
        (ending late or starting early).
    :type position_fix: bool

    :param is_start: Whether ``origin`` represents a start or end date.
    :type is_start: bool

    :returns: the scheduling network value that is ``origin`` plus ``duration``
        considering the ``position_fix`` constraint and making sure
        the duration in workdays does not change.
    :rtype: int
    """
    a = origin or 0
    b = a + duration

    # position fix: make sure b starts early or ends late
    if position_fix:
        if is_start and b % 2 == 0:
            b += 1
        elif not is_start and b % 2 == 1:
            b -= 1

    # position not fix: make sure duration does not change
    elif duration % 2 == 1:
        if is_start and a % 2 == 1:
            b += 1
        elif not is_start and a % 2 == 0:
            b -= 1

    return b


def add_gap(origin, gap, position_fix, get_start, is_forward):
    """
    Calculates a task start or end date based on a predecessor's or successor's date and a gap.
    Because durations as network values are ambigous,
    we cannot simply add them to a start index.

    :param origin: Scheduling network value of a workday
    :type origin: int

    :param gap: Gap as minimal number of workdays to add to ``origin``
    :type gap: int

    :param position_fix: If true, the result will map to default times
        (ending late or starting early).
    :type position_fix: bool

    :param get_start: Whether the result is to represent a start or end date.
    :type get_start: bool

    :param is_forward: Whether the gap is applied "forward" (predecessor to successor)
        or the other way round.
        The predecessor is the constraint the return value has to respect.
    :type is_forward: bool

    :returns: the scheduling network value that is ``origin`` plus ``gap``
        considering the ``position_fix`` constraint and making sure
        the gap in workdays does not change.
    :rtype: int
    """
    a = origin or 0
    b = a + (2 * gap)

    # position fix: make sure b starts early or ends late
    # while keeping it >= than the no. of workdays in gap parameter
    if position_fix:
        if get_start and b % 2 == 1:
            # we're looking for a start date, but naive calculation is late
            # -> apply fix to move b to early position
            if not is_forward and gap == 0:
                b -= 1
            else:
                b += 1
        elif not get_start and b % 2 == 0:
            # we're looking for an end date, but naive calculation is early
            # -> apply fix to move b to late position
            if is_forward and gap == 0:
                b += 1
            else:
                b -= 1

    # position not fix: minimize resulting gap
    # while keeping it >= than the no. of workdays in gap parameter
    elif gap > 0 and a % 2 == 0:
        # a and b are both early, b is later
        # -> b can be late while keeping the workday gap constant
        b -= 1
    elif gap < 0 and a % 2 == 1:
        # a and b are both late, b is earlier
        # -> b can be early while keeping the workday gap constant
        b += 1

    return b
