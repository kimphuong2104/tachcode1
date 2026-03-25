#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=inconsistent-return-statements


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.pcs.projects.tasks_efforts.helpers import get_object_with_updated_values

__all__ = [
    "SIGNAL_EMPTY",
    "SIGNAL_GREEN",
    "SIGNAL_YELLOW",
    "SIGNAL_RED",
    "get_changed_status_signals",
]

SIGNAL_EMPTY = 0
SIGNAL_GREEN = 1
SIGNAL_YELLOW = 2
SIGNAL_RED = 3


def _get_status_signal(obj, parent, accessors):
    """
    :param obj: Object representation
    :type obj: dict

    :param parent: Representation of the parent of `obj`
        (may be `None`)
    :type parent: dict

    :param accessors: Ordered functions to be called with `*(obj, parent)`.
        Must return a valid signal (int) and may not raise.
    :type accessors: list of callables

    :returns: The first result of an accessor call
        that is something else than `None`.
        If all accessor calls return `None`,
        the return value is `SIGNAL_GREEN`.
    :rtype: int
    """
    for accessor in accessors:
        result = accessor(obj, parent)
        if result is not None:
            return result

    return SIGNAL_GREEN


def _time_empty(obj, _):
    "time signal is empty if either planned start or end is `None`"
    if not (obj["start_time_fcast"] and obj["end_time_fcast"]):
        return SIGNAL_EMPTY


def _time_red(obj, parent):
    "time signal is red if object violates parent boundaries"
    if (
        parent
        and parent["start_time_plan"]
        and parent["end_time_plan"]
        and (
            obj["start_time_fcast"] < parent["start_time_plan"]
            or obj["end_time_fcast"] > parent["end_time_plan"]
        )
    ):
        return SIGNAL_RED


def _time_yellow(obj, _):
    "time signal is yellow if forecast violates planned boundaries"
    if (
        obj["start_time_plan"]
        and obj["end_time_plan"]
        and (
            obj["start_time_fcast"] > obj["start_time_plan"]
            or obj["end_time_fcast"] < obj["end_time_plan"]
        )
    ):
        return SIGNAL_YELLOW


def _effort_empty(obj, _):
    "effort signal is empty if planned effort is `None`"
    if obj["effort_fcast"] is None:
        return SIGNAL_EMPTY


def _effort_red(obj, parent):
    """
    The effort signal for `obj` is red if

    - work is uncovered,
    - planned efforts exceed those of `parent`,
    - `parent` is overbooked or
    - its assigned less than actual effort.
    """
    work_uncovered = obj.get("work_uncovered", 0)
    planned_exceeds_parent = parent and (obj["effort_fcast"] or 0.0) > (
        parent["effort_fcast"] or 0.0
    )
    parent_overbooked = (
        parent
        and (obj["effort_fcast"] or 0.0) > 0.0
        and (parent["effort_plan"] or 0.0) > (parent["effort_fcast"] or 0.0)
    )
    assigned_less_than_actual = (obj["effort_fcast"] or 0.0) < (
        obj["effort_act"] or 0.0
    ) or (obj["effort_fcast_a"] or 0.0) < (obj["effort_act"] or 0.0)
    if (
        work_uncovered
        or planned_exceeds_parent
        or parent_overbooked
        or assigned_less_than_actual
    ):
        return SIGNAL_RED


def _effort_yellow(obj, _):
    """
    The effort signal for `obj` is yellow if

    - less effort is planned than demanded or
    - less effort is planned than assigned.
    """
    planned_less_than_demand = (obj["effort_fcast"] or 0.0) < (
        obj["effort_plan"] or 0.0
    ) or (obj["effort_fcast"] or 0.0) < (obj["effort_fcast_a"] or 0.0)
    planned_less_than_assigned = (
        0.0 < obj["effort_fcast"] < (obj["effort_fcast_a"] or 0.0)
    )
    if planned_less_than_demand or planned_less_than_assigned:
        return SIGNAL_YELLOW


def get_changed_status_signals(obj, parent=None):
    """
    :param obj: Object representation
    :type obj: dict

    :param parent: Representation of the parent of `obj`
        (defaults to `None`)
    :type parent: dict

    :returns: Updated status signals for `obj`
        (only those that actually have a changed value).
    :rtype: dict
    """
    signals = {
        "status_time_fcast": _get_status_signal(
            obj,
            parent,
            [_time_empty, _time_red, _time_yellow],
        ),
        "status_effort_fcast": _get_status_signal(
            obj,
            parent,
            [_effort_empty, _effort_red, _effort_yellow],
        ),
    }

    changes = {}

    if signals["status_time_fcast"] != obj["status_time_fcast"]:
        changes["status_time_fcast"] = signals["status_time_fcast"]

    if signals["status_effort_fcast"] != obj["status_effort_fcast"]:
        changes["status_effort_fcast"] = signals["status_effort_fcast"]

    return changes


def _update_project_status_signals(prj_with_updated_vals, cdb_project_id, value_dict):
    signals = get_changed_status_signals(prj_with_updated_vals)
    if signals:
        value_dict[cdb_project_id].update(**signals)


def _update_tasks_status_signals(prj_with_updated_vals, tasks_by_id, value_dict):
    for task_id, task in tasks_by_id.items():
        parent = tasks_by_id.get(task["parent_task"], None)
        parent_values = {}
        if parent:
            parent_values.update(parent)
            parent_values.update(**value_dict[task["parent_task"]])
        else:
            parent_values.update(**prj_with_updated_vals)

        status_changes = get_changed_status_signals(task, parent_values)

        if status_changes:
            existing_changes = value_dict.get(task_id, {})
            existing_changes.update(**status_changes)
            value_dict[task_id] = existing_changes


def update_status_signals(project_dict, value_dict, tasks_by_id):
    """
    The status signals (status_effort_fcast, status_time_fcast)
    are updated for the project and tasks.
    """
    cdb_project_id = project_dict["cdb_project_id"]
    project_with_updated_values = get_object_with_updated_values(
        project_dict, value_dict[cdb_project_id]
    )

    _update_project_status_signals(
        project_with_updated_values, cdb_project_id, value_dict
    )

    _update_tasks_status_signals(project_with_updated_values, tasks_by_id, value_dict)
