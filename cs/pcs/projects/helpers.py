#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import collections
import datetime

import isodate
from cdb import misc
from cdb.typeconversion import from_legacy_date_format


def is_cdbpc():
    # kAppl_IIOPServer and cdbpc URLs will be removed in CE 16
    return hasattr(misc, "kAppl_IIOPServer") and misc.CDBApplicationInfo().rootIsa(
        misc.kAppl_IIOPServer
    )


def _filter_hook_vals(vals, class_prefix):
    """
    :param vals: values of dialog hook
    :type vals: dictionary

    :returns: all vals entries, which keys started with class_prefix,
        but now without this prefix.
        class_prefix is e.g. for projects 'cdbpcs_project.'
    :rtype: dict
    """
    processed_vals = {}
    for val in vals:
        if val.startswith(class_prefix):
            new_val = val.split(".")[1]
            processed_vals.update({new_val: vals[val]})
    return processed_vals


def ensure_date(value):
    """
    :param value: Date representation, either
        - "legacy" Elements format (from User Exits),
        - ISO 8601 (from frontend hooks) or
        - an object (from ORM access)
    :type value: str, datetime.datetime or datetime.date

    :rtype: datetime.date
    """
    if not value:
        return None

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    try:
        parsed = from_legacy_date_format(value)
        return parsed.date()
    except (ValueError, TypeError):
        try:
            return isodate.parse_date(value)
        except (isodate.ISO8601Error, ValueError):
            return None


def _get_act_dates(obj):
    start_time_act = obj.start_time_act
    end_time_act = obj.end_time_act
    return start_time_act, end_time_act


def index_tasks_by_parent_and_id(tasks):
    """
    :param tasks: Task objects of a single project.
        May break if used with tasks from multiple projects,
        because task IDs are only unique in the context of their project.
    :type tasks: list

    :returns: Two mappings of ``tasks``:
        1. Their adjacency list (children task IDs indexed by parent task ID)
           Used in ``sort_tasks_bottom_up`` to traverse through the tasks
           and sort them in level-order.
        2. Their full metadata as the task itself, indexed by task ID
           Used in ``sort_tasks_bottom_up`` to retrieve the sorted task,
           since the sorting is done by ``task_id``.
    :rtype: tuple(dict, dict)
    """
    children_by_parent = collections.defaultdict(list)
    tasks_by_id = {}

    for t in tasks:
        task_id, parent_task = t["task_id"], t["parent_task"]
        children_by_parent[parent_task].append(task_id)
        tasks_by_id[task_id] = t

    return children_by_parent, tasks_by_id


def sort_tasks_bottom_up(tasks):
    """
    :param tasks: Task objects of a single project.
        May break if used with tasks from multiple projects,
        because task IDs are only unique in the context of their project.
    :type tasks: list

    :returns: ``tasks`` sorted so that no parent appears before any of its children, meaning
        reversed level-order sorting. Sorting is implemented using a breadth-first-search approach.
    :rtype: sorted list of Task objects
    """
    children_by_parent, tasks_by_id = index_tasks_by_parent_and_id(tasks)
    result = []
    queue = [""]

    while queue:
        node = queue.pop(0)
        if node:
            result.append(tasks_by_id[node])
        for child in children_by_parent.get(node, []):
            queue.append(child)

    return result[::-1]
