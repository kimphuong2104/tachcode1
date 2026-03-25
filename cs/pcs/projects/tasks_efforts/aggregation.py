#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from collections import defaultdict

from cs.pcs.projects.tasks_efforts.helpers import (
    DISCARDED,
    add,
    find_max,
    find_max_all,
    find_min,
    is_discarded,
    norm_val,
)
from cs.pcs.projects.tasks_efforts.load_data import count_leaftasks, load_project_data

AGGREGATION_ATTRIBUTES = [
    # <parent attr>, <method>, <child attr>, <default value>,
    # <parent condition>, <expected condition value>, <all children needed>, <ignore status>
    (
        "start_time_plan",
        find_min,
        "start_time_fcast",
        None,
        "auto_update_time",
        0,
        False,
        DISCARDED,
    ),
    (
        "end_time_plan",
        find_max,
        "end_time_fcast",
        None,
        "auto_update_time",
        0,
        False,
        DISCARDED,
    ),
    ("start_time_act", find_min, "start_time_act", None, None, None, False, DISCARDED),
    ("end_time_act", find_max_all, "end_time_act", None, None, None, True, DISCARDED),
    ("effort_plan", add, "effort_fcast", 0.0, None, None, False, DISCARDED),
    (
        "effort_fcast",
        add,
        "effort_fcast",
        0.0,
        "auto_update_effort",
        1,
        False,
        DISCARDED,
    ),
    ("effort_act", add, "effort_act", 0.0, None, None, False, []),
    ("effort_fcast_d", add, "effort_fcast_d", 0.0, None, None, False, DISCARDED),
    ("effort_fcast_a", add, "effort_fcast_a", 0.0, None, None, False, DISCARDED),
]


def _aggregate_from_child(value_dict, parent, parent_id, sub):
    """
    Side effect that updates `value_dict` in-place
    Will aggregate attributes of subtasks for given parent task.
    """
    if not parent:
        return
    sub_dict = value_dict[sub["task_id"]]
    override = {}

    if parent["is_group"]:
        for (
            attr,
            add_function,
            sub_attr,
            default_value,
            check,
            check_value,
            all_subs,
            ignore,
        ) in AGGREGATION_ATTRIBUTES:
            if sub["status"] not in ignore:
                if check is None or parent[check] == check_value:
                    if add_function.__name__ == "find_max_all":
                        # In case of modifying the 'end_time_act', we want to set the
                        # end_time_act to None if any sub-task has end_time_act equal to None,
                        # so we initially set the active_value to 'start' instead of None
                        # to differentiate between both cases
                        active_value = value_dict[parent_id].get(attr, "start")
                    else:
                        active_value = value_dict[parent_id].get(attr, None)
                    adding_value = sub_dict.get(sub_attr, sub[sub_attr])
                    if all_subs and adding_value is None:
                        override[attr] = default_value
                    value_dict[parent_id][attr] = add_function(
                        norm_val(active_value, default_value),
                        norm_val(adding_value, default_value),
                    )
                else:
                    value_dict[parent_id][attr] = norm_val(parent[attr], default_value)

        for attr, value in override.items():
            value_dict[parent_id][attr] = value


def _aggregate_percentage(value_dict, obj, weight):
    """
    Calculates the percentage of completion value weighted by size of branch
    and  weighted by size of effort.

    :returns: Task weight `by size` and `by effort`
    :rtype: tuple of float
    """
    # sum up dividends for percentage completion
    if is_discarded(obj):
        return 0.0, 0.0
    sub_dict = value_dict[obj["task_id"]]
    percent = sub_dict.get("percent_complet", obj["percent_complet"]) or 0
    effort = sub_dict.get("effort_fcast", obj["effort_fcast"]) or 0.0
    return (float(percent * weight), float(percent * effort))


def _get_percent_complet(
    value_dict, effortless_dividend, effort_dividend, parent_id, leaf_count
):
    """
    Calculate the current completion percentage (`percent_complet`)
    of the task identified by `parent_id`.
    """
    effort_divisor = value_dict[parent_id].get("effort_plan", 0.0)
    if effort_divisor > 0:
        return int(effort_dividend / effort_divisor)
    elif leaf_count:
        return int(effortless_dividend / leaf_count)
    return 0


def adjust_project_prognosis_dates(project, value_dict, forecast_dates):
    min_forecast_date, max_forecast_date = forecast_dates
    project_changes = value_dict[project["cdb_project_id"]]
    do_forecast = project["auto_update_time"] == 0
    if do_forecast:
        project_changes["start_time_plan"] = find_min(
            project_changes.get("start_time_plan"), min_forecast_date
        )
        project_changes["end_time_plan"] = find_max(
            project_changes.get("end_time_plan"), max_forecast_date
        )


def add_efforts(object_id, efforts, demands, assignments, value_dict):
    def add_object_efforts(field_name, data):
        object_efforts = data[object_id]
        if object_efforts or (field_name != "effort_act" and object_efforts == 0):
            current_value = value_dict[object_id].get(field_name, 0.0)
            value_dict[object_id][field_name] = current_value + object_efforts

    add_object_efforts("effort_act", efforts)
    add_object_efforts("effort_fcast_d", demands)
    add_object_efforts("effort_fcast_a", assignments)


def adjust_percentage_complete(
    parent,
    parent_id,
    leaf_count,
    effortless_dividend,
    effort_dividend,
    value_dict,
    is_project,
):
    leafs = leaf_count[parent_id]
    if parent["is_group"] and leafs:
        value_dict[parent_id]["percent_complet"] = _get_percent_complet(
            value_dict, effortless_dividend, effort_dividend, parent_id, leafs
        )
    elif not is_project:
        max_parent_percent_complet = max(
            parent["percent_complet"] if parent["percent_complet"] is not None else 0, 0
        )
        value_dict[parent_id]["percent_complet"] = min(100, max_parent_percent_complet)


# pylint: disable=too-many-arguments
def aggregate_sub_tasks(
    parent,
    parent_id,
    project_structure,
    efforts,
    demands,
    assignments,
    leaf_count,
    forecast_dates,
    value_dict,
    is_project=False,
):
    """
    Recursively aggregates the efforts, demands, assignments
    and percentage completion of the project structure bottom up.
    """
    effortless_dividend = 0.0
    effort_dividend = 0.0
    children = project_structure[parent_id]
    for child in children:
        aggregate_sub_tasks(
            child,
            child["task_id"],
            project_structure,
            efforts,
            demands,
            assignments,
            leaf_count,
            forecast_dates,
            value_dict,
        )
        _aggregate_from_child(value_dict, parent, parent_id, child)
        percentage, effort = _aggregate_percentage(
            value_dict, child, leaf_count[child["task_id"]]
        )
        effortless_dividend += percentage
        effort_dividend += effort

        forecast_dates[0] = find_min(forecast_dates[0], child["start_time_fcast"])
        forecast_dates[1] = find_max(forecast_dates[1], child["end_time_fcast"])

    add_efforts(parent_id, efforts, demands, assignments, value_dict)
    adjust_percentage_complete(
        parent,
        parent_id,
        leaf_count,
        effortless_dividend,
        effort_dividend,
        value_dict,
        is_project,
    )


def aggregate_project_structure(project):
    """
    Loads the project related data and aggregates the
    complete project structure including the project object.
    It also updates the forecast dates of the project.

    :param project: The project dictionary for aggregation
    :type project: dict

    :returns: value_dict (containing updated values)
        and tasks_by_id (dictionary indexed by task_id
        containing tasks without aggregation changes)
    :rtype: tuple
    """
    project_structure, tasks_by_id, efforts, demands, assignments = load_project_data(
        project
    )
    leaf_count = count_leaftasks(project["cdb_project_id"], project_structure)

    value_dict = defaultdict(dict)
    forecast_dates = [None, None]

    aggregate_sub_tasks(
        project,
        project["cdb_project_id"],
        project_structure,
        efforts,
        demands,
        assignments,
        leaf_count,
        forecast_dates,
        value_dict,
        True,
    )
    adjust_project_prognosis_dates(project, value_dict, forecast_dates)

    return value_dict, tasks_by_id
