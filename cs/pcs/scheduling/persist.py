#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi, transactions, util

from cs.pcs.projects import Project
from cs.pcs.projects.common import partition
from cs.pcs.scheduling.calendar import network2duration
from cs.pcs.scheduling.persist_tasks import persist_tasks
from cs.pcs.scheduling.relships import relship_gap_from_network
from cs.pcs.helpers import get_dbms_split_count


def _get_split_count():
    return get_dbms_split_count()


def persist_changes(
    tasks, discarded, original_dates, network, project, calendar, persistent_relships
):
    """
    Writes all changes encoded in ``network`` back into the database.
    Updates are applied inside a single transaction and issue less than one
    SQL update statement per changed row.

    :param tasks: Sorted task metadata for use in forward passes
    :type tasks: list

    :param discarded: UUIDs of discarded tasks
    :type discarded: set

    :param original_dates: Original task date values by UUID
    :type original_dates: dict

    :param network: Network per task by UUID
    :type network: dict

    :param project: Project metadata
    :type project: dict

    :param calendar: Calendar instance for converting dates and date offsets
    :type calendar: cs.pcs.scheduling.calendar.IndexedCalendar

    :param persistent_relships: Persistent relationship data
    :type persistent_relships: list

    :returns: 1. Set of ``task_id`` values that were actually changed and
        2. Set of ``task_id`` values where at least one target date was changed.
    :rtype: tuple
    """
    with transactions.Transaction():
        changed_ids, changed_res_ids, min_start, max_end = persist_tasks(
            tasks, network, project, calendar, original_dates
        )
        persist_relships(persistent_relships, discarded, network)
        persist_project(project, calendar, min_start, max_end)

    # IDs of all changed tasks, IDs of changed tasks to post-process (target dates only)
    return changed_ids, changed_res_ids


def persist_relships(persistent_relships, discarded, network):
    """
    Calculate task relationship violations and updates the database.

    :param persistent_relships: Persistent relationship data
    :type persistent_relships: list

    :param discarded: UUIDs of discarded tasks
    :type discarded: set

    :param network: Network per task indexed by UUID
    :type network: dict
    """
    changes = {0: [], 1: []}

    for (
        pred_uuid,
        succ_uuid,
        rel_type,
        minimal_gap,
        _,
        __,
        violation,
    ) in persistent_relships:
        if pred_uuid in discarded or succ_uuid in discarded:
            continue

        gap = relship_gap_from_network(network[pred_uuid], network[succ_uuid], rel_type)
        new_violation = int(gap < minimal_gap)

        if new_violation != violation:
            changes[new_violation].append((pred_uuid, succ_uuid))

    for new_violation, v_changes in changes.items():
        for page in partition(v_changes, _get_split_count()):
            condition = [
                f"(pred_task_oid = '{pred_uuid}' AND succ_task_oid = '{succ_uuid}')"
                for pred_uuid, succ_uuid in page
            ]
            if condition:
                sql_where = " OR ".join(condition)
                sqlapi.SQLupdate(
                    f"cdbpcs_taskrel"
                    f" SET violation = {new_violation}"
                    f" WHERE {sql_where}"
                )


def persist_project(project, calendar, min_start, max_end):
    """
    Calculate project metadata changes and updates the database.

    :param project: Project metadata
    :type project: dict

    :param calendar: Calendar instance for converting dates and date offsets
    :type calendar: cs.pcs.scheduling.calendar.IndexedCalendar

    :param min_start: Offset of new minimum start date
    :type min_start: int

    :param max_end: Offset of new maximum end date
    :type max_end: int

    :raises KeyError: if ``project`` is missing any of these keys:
        - ``cdb_project_id``
        - ``fixed``
        - ``start_time_plan``
        - ``end_time_plan``
        - ``days``
        - ``start_time_fcast``
        - ``end_time_fcast``
        - ``days_fcast``
        - ``force_set_start``
    """
    max_end = max(min_start + 1, max_end)  # projects must be at least 1 day long
    days = max_end - min_start

    if project["fixed"]:
        values = [
            (min_start, "start_time_plan", True),
            (max_end, "end_time_plan", True),
            (days, "days", False),
        ]
    else:
        values = [
            (min_start, "start_time_fcast", True),
            (max_end, "end_time_fcast", True),
            (days, "days_fcast", False),
        ]
        # Reset to None to force DB update of uninitialised project
        if project["force_set_start"]:
            project["start_time_fcast"] = None
            project["end_time_fcast"] = None

    project_changes = {
        field_name: (
            calendar.network2day(new_value) if is_date else network2duration(new_value)
        )
        for new_value, field_name, is_date in values
        if new_value != project[field_name]
    }

    if project_changes:
        table_info = util.tables["cdbpcs_project"]
        cca = Project.MakeChangeControlAttributes()
        project_changes["cdb_adate"] = cca["cdb_mdate"]
        project_changes["cdb_apersno"] = cca["cdb_mpersno"]

        changes = [
            f"{key} = {sqlapi.make_literal(table_info, key, project_changes[key])}"
            for key in project_changes
        ]
        sql_set = ", ".join(changes)
        sqlapi.SQLupdate(
            f"cdbpcs_project SET {sql_set} WHERE cdb_project_id = '{project['cdb_project_id']}'"
        )
