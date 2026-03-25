#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id: utils.py 201443 2019-09-16 09:02:53Z sko $"

import datetime

from cdb import sqlapi, ue

from cs.pcs.projects.common import partition
from cs.pcs.helpers import get_dbms_split_count

TOLERANCE = 1
INTERACTIVE_CALLS = set()
OBJECTS_CHANGING = set()
OBJECTS_CHANGED = {}


def within_one_second(timestamp):
    now = datetime.datetime.now()
    return now < timestamp + datetime.timedelta(seconds=TOLERANCE)


def add_interactive_call(obj):
    if not OBJECTS_CHANGING:
        INTERACTIVE_CALLS.clear()
        INTERACTIVE_CALLS.add((obj.cdb_object_id, datetime.datetime.now()))


def evaluate_interactive_call(obj):
    try:
        if INTERACTIVE_CALLS:
            object_id, timestamp = INTERACTIVE_CALLS.pop()
            if within_one_second(timestamp) or (obj and obj.cdb_object_id == object_id):
                OBJECTS_CHANGING.add(object_id)
    finally:
        INTERACTIVE_CALLS.clear()


def add_to_change_stack(obj, ctx=None):
    # if context is called directly by user always reset stack
    # because it must to be the first one to stack
    # (and the last to remove)
    evaluate_interactive_call(obj)
    if ctx and (
        hasattr(ctx, "batch")
        and not ctx.batch
        or hasattr(ctx, "interactive")
        and ctx.interactive
    ):
        clear_update_stack()
    # add object to stack of objects, that are still changing
    OBJECTS_CHANGING.add(obj.cdb_object_id)


def unregister_from_change_stack(obj):
    oid = obj.cdb_object_id
    if oid in OBJECTS_CHANGING:
        OBJECTS_CHANGING.remove(oid)


def _get_obj_status(obj):
    return getattr(obj, "status", None)


def _add_to_objects_changed(obj, ctx):
    str_from_status = _get_obj_status(ctx.old) if ctx else ""
    from_status = int(str_from_status) if str_from_status else None
    to_status = _get_obj_status(obj)
    OBJECTS_CHANGED[obj.cdb_object_id] = (from_status, to_status)


def remove_from_change_stack(obj, ctx=None):
    evaluate_interactive_call(obj)

    oid = obj.cdb_object_id
    changed = set()

    # add object to stack of objects, that have been changed
    _add_to_objects_changed(obj, ctx)

    # remove object from stack of still changing objects
    if oid in OBJECTS_CHANGING:
        OBJECTS_CHANGING.remove(oid)

    # if stack of changed objects gets empty, all changes are made
    # now all effected objects will be returned
    if (
        not OBJECTS_CHANGING
        or ctx
        and (
            hasattr(ctx, "batch")
            and not ctx.batch
            or hasattr(ctx, "interactive")
            and ctx.interactive
        )
    ):
        changed = OBJECTS_CHANGED.copy()
        clear_update_stack()
    return changed


def clear_update_stack(*args, **kwargs):
    OBJECTS_CHANGING.clear()
    OBJECTS_CHANGED.clear()


def get_calendar_index_for_dates(calendar_profile_id, dates_and_is_start):
    """
    Returns late/early calendar indices for given dates in given
    calendar profile, depending if the dates are start or end dates

    :param calendar_profile_id: Id of calendar profile.
    :type calendar_profile_id: string

    :param dates_and_is_start: List of tuples
                                1st entry is the date to get the calendar index for.
                                2nd entry is wether the date is considered
                                a starting date.
    :type dates_and_is_start: list of tuples (date, bool)

    :returns: Determined late/ealry calendar indices in the same order
                as given dates. Late indices are returned for Start Dates
                and early indices are returned for End Dates.
    :rtype: list of integers

    :raises ue.Exception: If any date in dates_and_is_start is not in
                        given calendar_profile
    """

    dict_date_to_idx = {}

    _stmt_template_ = """
        SELECT day,
        early_work_idx,
        late_work_idx
        FROM cdb_calendar_entry_v
        WHERE day IN ({days})
        AND personalnummer IS NULL
        AND calendar_profile_id='{cpid}'
    """

    dates = [t[0] for t in dates_and_is_start]

    for part_dates in partition(dates, get_dbms_split_count()):
        sql = _stmt_template_.format(
            days=", ".join(
                [sqlapi.SQLdbms_date(part_date) for part_date in part_dates]
            ),
            cpid=sqlapi.quote(calendar_profile_id),
        )
        records = sqlapi.RecordSet2(sql=sql)
        for record in records:
            dict_date_to_idx[record.day.date()] = {
                "early": record.early_work_idx,
                "late": record.late_work_idx,
            }

    return_list_of_idx = []
    try:
        for date, is_start in dates_and_is_start:
            if is_start:
                idx = dict_date_to_idx[date]["late"]
            else:
                idx = dict_date_to_idx[date]["early"]
            return_list_of_idx.append(idx)
    except KeyError as exc:
        # Given Date not in Calendar Profile
        raise ue.Exception("cdbpcs_calendar_outdated") from exc
    return return_list_of_idx
