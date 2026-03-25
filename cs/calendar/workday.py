#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Workdays counter
"""

from __future__ import absolute_import

import datetime
import math
import six

from cdb import holiday
from cdb import util
from cs import calendar as cdbcalendar


# Soll Kalenderlogik (Property: fxcl) verwendet werden?
def _fxcl():
    fxcl = util.get_prop("fxcl")
    if fxcl and fxcl.lower() == "true":
        return True
    return False

WORKDAYS = (
    0,  # Monday
    1,  # Tuesday
    2,  # Wednesday
    3,  # Thursday
    4,  # Friday
)

HOLIDAYS = {
    "de": holiday.GermanHoliday,
}

HOURS = 8.0


def workdays(begin_date, end_date, country=None, region=None):
    """
    :param begin_date: First day of date range to get workdays for
        Note: Time information will be discarded.
    :type begin_date: datetime.date or datetime.datetime

    :param end_date: Last day of date range to get workdays for.
        Note: Time information will be discarded.
    :type end_date: datetime.date or datetime.datetime

    :param country: (Optional) ISO code of a country to respect holidays of.
        By default, only "de" is supported.
    :type country: str

    :param region: (Optional) Region code of given ``country`` to further
        filter holidays.
        If not given, only holidays common to the whole country are returned.
    :type region: str

    returns the date of all workdays (including start and end)

    :returns: List of workdays in range from ``begin_date`` to ``end_date``,
        optionally respecting constraints from ``country`` and ``region``.
    :rtype: list of datetime.date

    :raises ValueError: if either ``begin_date`` or ``end_date`` is no date.
    """
    begin_date = cdbcalendar.lose_time_info(begin_date)
    end_date = cdbcalendar.lose_time_info(end_date)

    diff = end_date - begin_date
    the_workdays = []

    for i in six.moves.range(diff.days + 1):
        actual_day = begin_date + datetime.timedelta(days=i)
        if actual_day.weekday() in WORKDAYS:
            the_workdays.append(actual_day)

    # holidays?
    holidays = []
    hd = HOLIDAYS.get(country, None)
    if hd:
        holidays = hd(begin_date, end_date, region).get()

    the_workdays = [x for x in the_workdays if x not in holidays]

    return the_workdays


def personal_workdays(persno, start_date=None, end_date=None):
    if _fxcl() and persno:
        cal = cdbcalendar.getPersonalWorkdays(list_of_persno=[persno],
                                              start_date=start_date,
                                              end_date=end_date)
        if persno not in cal:
            return []
        return [x[0] for x in cal[persno]]
    return workdays(start_date, end_date)


def is_workday(myDate, country=None, region=None):
    if myDate.weekday() not in WORKDAYS:
        return False
    holidays = []
    hd = HOLIDAYS.get(country, None)
    if hd:
        holidays = hd(myDate, myDate, region).get()
    return myDate not in holidays


def days_to_hours(myDays):
    return int(myDays * HOURS)


def hours_to_days(myHours):
    return int(math.ceil(myHours / HOURS))


def next_day(myDate, span=0):
    return myDate + datetime.timedelta(days=span)


def next_workday(myDate, span=0, country=None, region=None):
    total_workdays = 0
    actual_day = cdbcalendar.lose_time_info(myDate)
    if span > 0:
        while not is_workday(actual_day, country, region):
            actual_day = actual_day + datetime.timedelta(days=1)
            total_workdays += 1
        while span > total_workdays:
            actual_day = actual_day + datetime.timedelta(days=1)
            if is_workday(actual_day, country, region):
                total_workdays += 1
    elif span < 0:
        if is_workday(actual_day, country, region):
            total_workdays -= 1
        while span < total_workdays:
            actual_day = actual_day - datetime.timedelta(days=1)
            if is_workday(actual_day, country, region):
                total_workdays -= 1
    return actual_day


def next_personal_workday(persno, myDate, span=0):
    date = cdbcalendar.lose_time_info(myDate)

    if not _fxcl() or not persno:
        return next_workday(myDate=date, span=span)

    if not span:
        return date

    days = personal_workdays(persno)

    tolerance = span // int(math.fabs(span))
    i = get_index_of_day(date, days, tolerance) + 1

    try:
        result = days[i + int(span) - int(tolerance)]
        return result
    except Exception as e:
        return None


def get_index_of_day(myDay, all_days, next=0):
    """
    The function searches in `all_days` for `myDay`.
    `all_days` has to be sorted ascending and has to
    provide an index operator.

    The function returns the index of `myDay` in the list.
    If `next` is ``0`` and `myDay` is not part of the list,
    the function returns ``-1``.

    If `myDay` is not part of `all_days` and `next` is ``1``
    the function returns the index of the first day of `all_days`
    with a date after `myDay`. If there is no such day the
    function returns the index of the last day in `all_days`.

    If `myDay` is not part of `all_days` and `next` is ``-1``
    the function returns the index of the first day of `all_days`
    with a date before `myDay`. If there is no such day the
    function returns ``0``.
    """
    import bisect
    if not all_days:
        return -1

    if next >= 0:
        result = bisect.bisect_left(all_days, myDay)
        if result == len(all_days):
            result -= 1
        if next > 0 or all_days[result] == myDay:
            return result
        else:
            return -1
    else:
        result = bisect.bisect_right(all_days, myDay)
        if result:
            result -= 1
        return result


def getDays(start_date, end_date):
    return [
        start_date + datetime.timedelta(days=x)
        for x in six.moves.range((end_date - start_date).days + 1)
    ]
