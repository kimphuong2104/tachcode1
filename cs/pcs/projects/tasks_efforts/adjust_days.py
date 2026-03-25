#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import defaultdict

from cs.pcs.projects.common import partition
from cs.pcs.projects.tasks_efforts.helpers import get_object_with_updated_values

PLANNED = ("start_time_plan", "end_time_plan", "days")
ACTUAL = ("start_time_act", "end_time_act", "days_act")


def adjust_task_dates(
    project_id, calendar_profile_id, start_date, tasks_by_id, planned, actual
):
    """
    Update the amount of workdays for each task of ``project_id`` contained in ``tasks_by_id``.

    If ``planned`` is truthy, the amount of planned days are set from planned dates.
    If ``actual`` is truthy, the amount of actual days are set from actual dates.

    Only changed values are included in the SQL statement.

    The calendar indexed by ``calendar_profile_id`` and ``start_date`` defines workdays.
    """
    from cs.pcs.scheduling.calendar import IndexedCalendar
    from cs.pcs.scheduling.helpers import get_duration
    from cs.pcs.helpers import get_dbms_split_count
    from cs.pcs.scheduling.persist_tasks_sql import write_task_changes_to_db

    calendar = IndexedCalendar(calendar_profile_id, start_date)

    def get_change(changed_task_ids, task_changes, task_id, task, fields):
        field_start, field_end, field_days = fields
        end = task[field_end]
        start = task[field_start]

        if start and end:
            # ISS-0065788@P014273
            # use early/late flags of target dates even though we're
            # reading forecast and actual dates here
            # the short reason is: we don't want to see different durations for matching dates
            offset_start = calendar.day2network(start, True, task["start_is_early"])
            offset_end = calendar.day2network(end, False, task["end_is_early"])
            days_new = get_duration(offset_start, offset_end)
        else:
            days_new = 0

        if days_new != task[field_days]:
            task_changes[field_days][task_id] = days_new
            changed_task_ids.add(task_id)

    task_change_pages = []

    for task_page in partition(tasks_by_id.keys(), get_dbms_split_count()):
        changed_task_ids = set()
        task_changes = defaultdict(dict)

        for task_id in task_page:
            task = tasks_by_id[task_id]

            if planned:
                get_change(changed_task_ids, task_changes, task_id, task, PLANNED)

            if actual:
                get_change(changed_task_ids, task_changes, task_id, task, ACTUAL)

        if changed_task_ids:
            task_change_pages.append((changed_task_ids, task_changes))

    if task_change_pages:
        write_task_changes_to_db(project_id, task_change_pages)


def adjust_project_and_task_days(project, project_dict, tasks_by_id, value_dict):
    project_id = project_dict["cdb_project_id"]
    project_aggregation_changes = value_dict[project_id]
    project_with_updated_values = get_object_with_updated_values(
        project_dict, value_dict[project_id]
    )

    adjust_task_dates(
        project_id,
        project_dict["calendar_profile_id"],
        project_dict["start_time_plan"],
        tasks_by_id,
        planned=project_dict["msp_active"],
        actual=True,
    )

    # adjust days_act of the project
    days_act = project.get_days_actual(
        project_with_updated_values["start_time_act"],
        project_with_updated_values["end_time_act"],
    )
    if days_act != project_with_updated_values["days_act"]:
        project_aggregation_changes["days_act"] = days_act

    value_dict[project_id] = project_aggregation_changes
