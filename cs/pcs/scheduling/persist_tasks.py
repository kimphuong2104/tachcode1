#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import collections
import logging

from cdb import sqlapi

from cs.pcs.projects.common import partition
from cs.pcs.scheduling.calendar import network2duration
from cs.pcs.scheduling.constants import AA, DR, EF, ES, FF, LF, LS, TF, ZZ
from cs.pcs.scheduling.persist_tasks_sql import write_task_changes_to_db

TASK_FIELDS = set(
    [
        # map network value indexes to DB field names
        # network index, field name, is offset (requires conversion to date)
        # WARNING: TASK_FIELDS length / field names must match tasks.TASK_COLUMNS
        (DR, "days_fcast", False),
        (ES, "early_start", True),
        (EF, "early_finish", True),
        (LS, "late_start", True),
        (LF, "late_finish", True),
        (AA, "start_time_fcast", True),
        (ZZ, "end_time_fcast", True),
        (FF, "free_float", False),
        (TF, "total_float", False),
    ]
)
FIXED_FIELDS = set(
    [
        # these fields are never overwritten for fixed tasks
        "start_time_fcast",
        "end_time_fcast",
    ]
)
START_OFFSETS = set([ES, LS, AA])
POST_PROCESS = set(
    [
        # if any of these fields are changed,
        # the task ID is post-processed (for ex. in cs.resources)
        "start_time_fcast",
        "end_time_fcast",
    ]
)


def persist_tasks(tasks, network, project, calendar, original_data):
    """
    Calculate changes between ``tasks`` and ``network`` and update the database.

    Writes all changes encoded in ``network`` back into the database.
    Updates are applied inside a single transaction and issue less than one
    SQL update statement per changed row.

    :param tasks: Task metadata as dicts sorted in topological order
    :type tasks: list

    :param network: Network per task indexed by UUID
    :type network: dict

    :param project: Project metadata
    :type project: dict

    :param calendar: Calendar instance for converting dates and date offsets
    :type calendar: cs.pcs.scheduling.calendar.IndexedCalendar

    :param original_dates: Partial task metadata (all date fields) indexed by UUID
    :type original_dates: dict

    :returns: 1. Set of ``task_id`` values that were actually changed,
        2. Set of ``task_id`` values where at least one target date was,
        3. The new mininmum start offset and
        4. The new maximum end offset
    :rtype: tuple
    """
    # pylint: disable=too-many-locals
    from cs.pcs.helpers import get_dbms_split_count

    project_start_offset = project["start_time_fcast"]

    def network2day(offset):
        return calendar.network2day(project_start_offset + offset)

    starts, ends = set(), set()

    task_change_pages = []
    changed_ids = set()
    changed_res_ids = set()

    for task_page in partition(tasks, get_dbms_split_count()):
        changed_task_ids = set()
        all_changes = collections.defaultdict(dict)

        for task in task_page:
            task_changes, changed_target_dates = _get_task_changes(
                network, original_data, network2day, task
            )
            task_id = task["task_id"]

            if task_changes:
                changed_task_ids.add(task_id)
                for field_name, new_value in task_changes.items():
                    all_changes[field_name][task_id] = new_value

            if changed_target_dates:
                changed_res_ids.add(task_id)

            if not task["discarded"]:  # ignore discarded tasks for project duration
                task_uuid = task["cdb_object_id"]
                starts.add(network[task_uuid][AA])
                ends.add(network[task_uuid][ZZ])

        if all_changes:
            logging.debug(
                "persist_tasks: apply page of %s changes", len(changed_task_ids)
            )
            task_change_pages.append((changed_task_ids, all_changes))
            changed_ids.update(changed_task_ids)

    min_start = min(starts) if starts else 0
    max_end = max(ends) if ends else 0

    write_task_changes_to_db(project["cdb_project_id"], task_change_pages)
    return changed_ids, changed_res_ids, min_start, max_end


def _get_task_changes(network, original_data, network2day, task):
    task_changes = {}
    changed_target_dates = False
    task_uuid = task["cdb_object_id"]

    for network_index, field_name, is_offset in TASK_FIELDS:
        if task["fixed"] and field_name in FIXED_FIELDS:
            continue

        raw_value = network[task_uuid][network_index]

        if is_offset:
            if raw_value is None:
                # should never happen (scheduling's goal is to set AA and ZZ, especially)
                logging.exception(
                    "empty offset value in network [%s]:\n\t%s = %s",
                    network_index,
                    task_uuid,
                    network[task_uuid],
                )
                raise TypeError("empty offset value in network")

            # compare date from new offset to original date
            # (dates may differ even though offsets are the same)
            new_date_value = network2day(raw_value)
            new_value = sqlapi.SQLdate_literal(new_date_value)
            field_changed = new_date_value != original_data[task_uuid][field_name]
        else:
            new_value = network2duration(raw_value)
            field_changed = new_value != original_data[task_uuid][field_name]

        if field_changed:
            task_changes[field_name] = new_value
            if field_name in POST_PROCESS:
                changed_target_dates = True

    if not task["fixed"]:
        # Adjust early/late flags
        new_start_is_early = int(network[task_uuid][AA] % 2 == 0)
        new_end_is_early = int(network[task_uuid][ZZ] % 2 == 0)

        if original_data[task_uuid]["start_is_early"] != new_start_is_early:
            task_changes["start_is_early"] = new_start_is_early

        if original_data[task_uuid]["end_is_early"] != new_end_is_early:
            task_changes["end_is_early"] = new_end_is_early

    return task_changes, changed_target_dates
