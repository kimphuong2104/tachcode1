#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import defaultdict

from cdb import sqlapi

from cs.pcs.projects.tasks import Task
from cs.pcs.scheduling.helpers import convert_task_dates
from cs.pcs.scheduling.load import SQLdate, load

SELECT_TASKS = """
    -- SELECT
        task.cdb_object_id,
        parent.cdb_object_id AS parent_uuid,
        task.task_name,  -- just for pretty-printing results
        task.task_id,  -- just for legacy persist, could also be rewritten to use UUIDs

        -- target dates, network values
        task.start_time_fcast,
        task.end_time_fcast,
        COALESCE(task.days_fcast, 0) AS days_fcast,

        task.early_start,
        task.late_start,
        task.early_finish,
        task.late_finish,
        task.free_float,
        task.total_float,

        -- scheduling input
        task.milestone,
        task.start_is_early,
        task.end_is_early,
        task.status,
        CASE
            WHEN task.automatic = 1 AND COALESCE(task.percent_complet, 0) = 0
                THEN 0
            ELSE 1 END fixed,
        task.is_group,
        CASE
            WHEN task.auto_update_time = 1
            AND task.automatic = 1 AND task.is_group = 1
                THEN 1
            ELSE 0 END adopt_bottom_up_target,
        task.constraint_type,
        task.constraint_date
    FROM cdbpcs_task task
    LEFT JOIN cdbpcs_task parent
        ON parent.cdb_project_id = task.cdb_project_id
        AND parent.ce_baseline_id = task.ce_baseline_id
        AND parent.task_id = task.parent_task
    WHERE task.cdb_project_id = '{0}'
        AND task.ce_baseline_id = ''
"""


def _SQLinteger(table, col, row):
    """
    Variant of ``cdb.sqlapi.SQLinteger``
    that returns ``None`` for ``NULL`` values instead of ``0``.

    Required for fields we want to change, e.g. to overwrite
    NULL values with zeroes.
    """
    if sqlapi.SQLnull(table, col, row):
        return None
    return sqlapi.SQLinteger(table, col, row)


COLUMNS_TASKS = [
    ("cdb_object_id", sqlapi.SQLstring),
    ("parent_uuid", sqlapi.SQLstring),
    ("task_name", sqlapi.SQLstring),
    ("task_id", sqlapi.SQLstring),
    ("start_time_fcast", SQLdate),
    ("end_time_fcast", SQLdate),
    ("days_fcast", _SQLinteger),
    ("early_start", SQLdate),
    ("late_start", SQLdate),
    ("early_finish", SQLdate),
    ("late_finish", SQLdate),
    ("free_float", _SQLinteger),
    ("total_float", _SQLinteger),
    ("milestone", sqlapi.SQLinteger),
    ("start_is_early", _SQLinteger),
    ("end_is_early", _SQLinteger),
    ("status", sqlapi.SQLinteger),
    ("fixed", sqlapi.SQLinteger),
    ("is_group", sqlapi.SQLinteger),
    ("adopt_bottom_up_target", sqlapi.SQLinteger),
    ("constraint_type", sqlapi.SQLstring),
    ("constraint_date", SQLdate),
]
START_DATES = {
    "early_start",
    "late_start",
    "early_finish",
    "late_finish",
}
DURATIONS = {
    "days_fcast": ("start_time_fcast", "end_time_fcast"),
}
FLOATS = {"free_float", "total_float"}

DATES_TASK = (
    START_DATES.union(["start_time_fcast"]),
    set(["end_time_fcast"]),
    DURATIONS,
)
DATES_MILESTONE = (
    START_DATES.union(["start_time_fcast", "end_time_fcast"]),
    set(),
    DURATIONS,
)
BOOLEANS = {"start_is_early", "end_is_early"}

CONSTRAINTS = {"constraint_date"}


def load_tasks(project_id, calendar):
    """
    :param project_id: Project ID to load tasks for
    :type project_id: str

    :param calendar: Calendar instance for converting dates and date offsets
    :type calendar: cs.pcs.scheduling.calendar.IndexedCalendar

    :returns:
        1. Original task metadata indexed by UUID
        2. discarded tasks,
        3. original date values by UUID
        4. parent UUID by child UUID
            (only includes non-fixed parents with "adopt_bottom_up_target")
        5. child UUIDs by parent UUID
            (only includes non-discarded children)
        6. *all* child UUIDs by parent UUID
            (values are tuples (child_uuid, adopt_bottom_up))
    :rtype: tuple(dict, set, dict, dict, dict, dict)

    :raises cdb.util.ErrorMessage: if a cycle is found
    """
    # pylint: disable=too-many-locals
    all_task_fields = (
        DATES_TASK[0]
        .union(DATES_TASK[1])
        .union(DURATIONS)
        .union(FLOATS)
        .union(BOOLEANS)
        .union(CONSTRAINTS)
    )
    status_discarded = Task.DISCARDED.status
    project_id = sqlapi.quote(project_id)
    condition = SELECT_TASKS.format(project_id)

    tasks = load(condition, COLUMNS_TASKS)

    by_uuid, original_data = {}, {}
    task_uuids, discarded = [], set()
    children, all_children = defaultdict(set), defaultdict(set)
    parents = {}

    filtered_parents = {
        task["cdb_object_id"]
        for task in tasks
        if task["adopt_bottom_up_target"] and not task["fixed"]
    }

    for task in tasks:
        uuid = task["cdb_object_id"]

        # first keep unmodified values for diffing in persist step
        original_data[uuid] = {
            field_name: task[field_name] for field_name in all_task_fields
        }

        task_discarded = task["status"] == status_discarded
        task["discarded"] = task_discarded
        adopt_bottom_up = task["adopt_bottom_up_target"]

        if task["milestone"] or adopt_bottom_up:
            task["position_fix"] = 0
        else:
            task["position_fix"] = 1

        # make eventual fixes to early flags
        if task["position_fix"]:
            task["start_is_early"] = 1
            task["end_is_early"] = 0
        elif task["milestone"]:
            task["end_is_early"] = task["start_is_early"]

        parent_uuid = task["parent_uuid"]
        if parent_uuid:
            all_children[parent_uuid].add((uuid, adopt_bottom_up))
        else:
            all_children[""].add((uuid, adopt_bottom_up))

        if task_discarded:
            discarded.add(uuid)
        elif parent_uuid:
            children[parent_uuid].add(uuid)

        if parent_uuid in filtered_parents:
            parents[uuid] = parent_uuid

        by_uuid[uuid] = task
        task_uuids.append(uuid)

    convert_task_dates(tasks, calendar)
    return (
        by_uuid,
        discarded,
        original_data,
        parents,
        children,
        all_children,
    )
