#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from datetime import date, timedelta

from webob.exc import HTTPBadRequest

TIMEFRAME_START_YEAR = "timeFrameStartYear"
TIMEFRAME_START_QUARTER = "timeFrameStartQuarter"
TIMEFRAME_END_YEAR = "timeFrameUntilYear"
TIMEFRAME_END_QUARTER = "timeFrameUntilQuarter"
EXTRA_DATA_PROPS_KEY = "extraDataProps"
TIMEFRAME_KEYS = {TIMEFRAME_START_YEAR, TIMEFRAME_START_QUARTER, TIMEFRAME_END_YEAR, TIMEFRAME_END_QUARTER}


def get_quarter(year, quarter, last_day=False):
    """
    :param year: Year number
    :type year: int [1..9999]

    :param quarter: Number of the year's quarter
    :type quarter: int [1..4]

    :param last_day: Whether the last day of the quarter is to be returned or not.
    :type last_day: bool

    :returns: The first day of the quarter matching the input.
        If ``last_day`` is true, the last day of that quarter is returned instead.
    :rtype: datetime.date

    :raises ValueError: if either of these are true:
        - ``year`` is not an integer between 1 and 9999
        - ``quarter`` is not an integer between 1 and 4
    """
    if last_day:  # add one quarter to include the ending quarter's data
        if quarter == 4:  # -> simply return the known last day of the year
            return date(year, 12, 31)
        else:  # -> next quarter in same year
            return date(year, 1 + 3 * quarter, 1) - timedelta(days=1)

    # simply return the start of the quarter
    return date(year, 1 + 3 * (quarter - 1), 1)


def get_timeframe(request):
    if EXTRA_DATA_PROPS_KEY not in request.json:
        raise HTTPBadRequest
    time_frame_json = request.json[EXTRA_DATA_PROPS_KEY]
    missing_keys = TIMEFRAME_KEYS.difference(time_frame_json.keys())
    if missing_keys:
        logging.error("missing keys: %s", missing_keys)
        raise HTTPBadRequest

    values = {
        key: time_frame_json[key]
        for key in TIMEFRAME_KEYS
    }

    errors = []

    for key in [TIMEFRAME_START_YEAR, TIMEFRAME_END_YEAR]:
        try:
            year = int(values[key])
            if (year < 1) or (year > 10000):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"invalid {key}: '{values[key]}'")

    for key in [TIMEFRAME_START_QUARTER, TIMEFRAME_END_QUARTER]:
        try:
            quarter = int(values[key])
            if quarter not in {1, 2, 3, 4}:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"invalid {key}: '{values[key]}'")

    if errors:
        logging.error(", ".join(errors))
        raise HTTPBadRequest

    start = get_quarter(values[TIMEFRAME_START_YEAR], values[TIMEFRAME_START_QUARTER])
    end = get_quarter(values[TIMEFRAME_END_YEAR], values[TIMEFRAME_END_QUARTER], True)

    if end < start:
        logging.error("requested invalid time frame: %s - %s", start, end)

    return start, end


def raise_bad_request(keys, dictionary):
    logging.error(
        "invalid key '%s' in request dictionary: %s",
        keys,
        dictionary,
    )
    raise HTTPBadRequest


def get_prj_ids(json):
    key = "evaluate_project_ids"
    if key in json.keys() and isinstance(json.get(key), list):
        prj_ids = json.get(key)
        for prj_id in prj_ids:
            if not isinstance(prj_id, str):
                raise_bad_request(key, json)
        return prj_ids
    else:
        return []
