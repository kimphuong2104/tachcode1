#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi

from cs.pcs.scheduling.calendar import IndexedCalendar
from cs.pcs.scheduling.helpers import convert_days2network
from cs.pcs.scheduling.load import SQLdate, load

SELECT_PROJECT = """
    -- SELECT
        cdb_project_id,
        calendar_profile_id,
        -- dates to update for auto-scheduled projects
        start_time_fcast,
        end_time_fcast,
        -- dates to update for manually-scheduled projects
        start_time_plan,
        end_time_plan,
        -- auto_update_time 0, 2 are not fixed
        CASE WHEN auto_update_time = 1 THEN 0 ELSE 1 END fixed,
        days_fcast,
        days
    FROM cdbpcs_project
    WHERE cdb_project_id = '{}'
        AND ce_baseline_id = ''
"""
COLUMNS_PROJECT = [
    ("cdb_project_id", sqlapi.SQLstring),
    ("calendar_profile_id", sqlapi.SQLstring),
    ("start_time_fcast", SQLdate),
    ("end_time_fcast", SQLdate),
    ("start_time_plan", SQLdate),
    ("end_time_plan", SQLdate),
    ("fixed", sqlapi.SQLinteger),
    ("days_fcast", sqlapi.SQLinteger),
    ("days", sqlapi.SQLinteger),
]

START_DATES = {"start_time_fcast", "start_time_plan"}
END_DATES = {"end_time_fcast", "end_time_plan"}
DURATIONS = {
    "days_fcast": ("start_time_fcast", "end_time_fcast"),
    "days": ("start_time_plan", "end_time_plan"),
}


def load_project(project_id):
    """
    :param project_id: ID of the project to load
    :type project_id: str

    :returns: Dict with project metadata and IndexedCalendar instance
    :rtype: tuple
    """
    condition = SELECT_PROJECT.format(sqlapi.quote(project_id))
    for project in load(condition, COLUMNS_PROJECT):
        calendar = IndexedCalendar(
            project["calendar_profile_id"],
            project["start_time_fcast"],
            project["days_fcast"],
        )
        project["position_fix"] = 1
        # If start_time_fcast is None, we've to set it during persisting
        project["force_set_start"] = not project["start_time_fcast"]
        convert_days2network(calendar, project, START_DATES, END_DATES, DURATIONS)
        return project, calendar
