#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb.lru_cache import lru_cache

from cs.pcs.scheduling.calendar import (
    add_duration,
    get_duration,
    get_duration_as_network,
)
from cs.pcs.scheduling.constants import (
    AA,
    DR,
    EF,
    ES,
    FIXED_CONSTRAINT_FIX_FORWARD,
    FIXED_CONSTRAINT_TYPES_EARLY,
    FIXED_CONSTRAINT_TYPES_LATE,
    LF,
    LS,
    RELSHIP_FS,
    ZZ,
)
from cs.pcs.scheduling.constraints import handle_fixed_constraints


@lru_cache(maxsize=5)
def log_level_is_enabled(level=logging.INFO):
    logger = logging.getLogger()
    return logger.isEnabledFor(level)


def get_value(task_net, index, fallback):
    """
    :param task_net: A single task's network
    :type task_net: list

    :param index: Index of network value to get
    :type index: int

    :param fallback: Index of network value to fall back to
    :type fallback: int

    :returns: The network's value at ``index``
        (or ``fallback`` if the former is ``None``).
    :rtype: int
    """
    scheduled = task_net[index]
    if scheduled is None:
        return task_net[fallback]
    return scheduled


def convert_days2network(calendar, valdict, start_dates, end_dates, durations):
    """
    :param calendar: Project's calendar dates indexed by offsets
    :type calendar: dict

    :param valdict: Metadata to mutate;
        all ``start_dates`` and ``end_dates`` are replaced with the converted values
    :type valdict: dict

    :param start_dates: Field names of start dates
    :type start_dates: set

    :param end_dates: Field names of end dates
    :type end_dates: set

    :param durations: Start and end date field names indexed by duration field names
    :type durations: dict

    :raises KeyError: if any key in ``start_dates`` and ``end_dates``
        is missing in ``valdict``.
    """
    eas = valdict.get("start_is_early", 1)
    eaf = valdict.get("end_is_early", 0)

    for field_name in start_dates:
        valdict[field_name] = calendar.day2network(valdict[field_name], True, eas)
    for field_name in end_dates:
        end = valdict[field_name]
        if not end and field_name == "end_time_fcast":
            # hard-coded: if planned end is not set, add duration to start
            # (may happen for tasks that were just created)
            task_dr = get_duration_as_network(valdict["days_fcast"], eas, eaf)
            valdict[field_name] = add_duration(
                valdict["start_time_fcast"],
                task_dr,
                valdict["position_fix"],
                True,
            )
        else:
            valdict[field_name] = calendar.day2network(end, False, eaf)
    for duration_field, (start_field, end_field) in durations.items():
        valdict[duration_field] = get_duration(valdict[start_field], valdict[end_field])

    # hard-code constraint date conversion because it relies on the exact constraint type
    # (because this is called for a single project only,
    # we don't bother with an early return in case the value is None)
    constraint_type = valdict.get("constraint_type", None)

    if constraint_type in FIXED_CONSTRAINT_TYPES_EARLY:
        valdict["constraint_date"] = calendar.day2network(
            valdict["constraint_date"],
            True,
            True,
            FIXED_CONSTRAINT_FIX_FORWARD[constraint_type],
        )
    elif constraint_type in FIXED_CONSTRAINT_TYPES_LATE:
        valdict["constraint_date"] = calendar.day2network(
            valdict["constraint_date"],
            False,
            False,
            FIXED_CONSTRAINT_FIX_FORWARD[constraint_type],
        )


def _get_task_date_fields(task):
    """
    :param task: Task metadata
    :type task: dict

    :returns: Set of start date field names, set of end date field names and
        dict of duration fields
    :rtype: tuple

    :raises KeyError: if ``task`` is missing key "milestone"
    """
    from cs.pcs.scheduling.load_tasks import DATES_MILESTONE, DATES_TASK

    return DATES_MILESTONE if task["milestone"] else DATES_TASK


def convert_task_dates(tasks, calendar):
    """
    :param tasks: List of task dictionaries to mutate;
        all ``start_dates`` and ``end_dates`` are replaced with the converted values
    :type tasks: list

    :param calendar: Project's calendar dates indexed by offsets
    :type calendar: dict
    """
    for task in tasks:
        start_dates, end_dates, durations = _get_task_date_fields(task)
        convert_days2network(calendar, task, start_dates, end_dates, durations)


def create_dummy_chain_point(task_uuid, value):
    # create dummy starting/ending point of chain
    # note: use duration of 1 to avoid being handled like a milestone
    # (UUID, DR, rel_type, gap, target_date)
    return (task_uuid, 1, RELSHIP_FS, 0, value)


def is_last_child(parents, children, children_done, task_uuid):
    """
    :param parents: Parent UUID indexed by child UUID
    :type parents: dict

    :param children: Set of child UUIDs indexed by parent UUID
    :type children: dict

    :param children_done: Task UUIDs that have been marked as done
    :type children_done: set

    :param task_uuid: UUID of the task to check for
    :type task_uuid: str

    :returns: Whether the task identified by ``task_uuid``
        and all of its siblings are marked as done.
    :rtype: bool
    """
    parent = parents.get(task_uuid, None)

    if not parent:
        return False

    current_children = children.get(parent, set())

    if not current_children:
        # parent without children; this should never happen,
        # but it is possible to have broken data
        # where a non-discarded parent only has discarded children
        return False

    if not current_children - children_done:
        return True

    return False


def aggregate_children(network, children, indexes):
    """
    Aggregate child values identified by ``indexes`` in the network.
    ``children`` is not expected to contain discarded tasks.

    :returns: Values to change in the parent's network,
        indexed by their network index.
    :rtype: dict
    """
    min_es, max_ef, min_ls, max_lf = None, None, None, None

    for child in children:  # non-discarded children only
        child_net = network[child]

        # ignore earliest/latest dates of already scheduled (e.g. fixed) tasks
        child_es = get_value(child_net, AA, ES)
        child_ef = get_value(child_net, ZZ, EF)
        child_ls = get_value(child_net, AA, LS)
        child_lf = get_value(child_net, ZZ, LF)

        if min_es is None or child_es < min_es:
            min_es = child_es

        if max_ef is None or child_ef > max_ef:
            max_ef = child_ef

        if min_ls is None or child_ls < min_ls:
            min_ls = child_ls

        if max_lf is None or child_lf > max_lf:
            max_lf = child_lf

    result = {
        DR: max_ef - min_es,
        ES: min_es,
        EF: max_ef,
        LS: min_ls,
        LF: max_lf,
    }
    return {index: result[index] for index in indexes}


def get_task_net_updates(task, task_net, kwargs):
    """
    :param task: Task metadata (used to re-apply fixed constraints)
    :type task: dict

    :param task_net: Task network before updating
    :type task_net: list

    :param kwargs: Updated values indexed by network index
    :type kwargs: dict

    :returns: Updated task network or ``None`` in case of no updates.
    :rtype: dict
    """
    updated_task_net = list(task_net)
    for index, new_value in kwargs.items():
        updated_task_net[index] = new_value

    # make sure fixed constraints are never overwritten
    handle_fixed_constraints(task, updated_task_net)

    if updated_task_net != task_net:
        return updated_task_net

    return None


def adopt_bottom_up(
    tasks_by_id, parents, children, children_done, network, parent_uuid, indexes
):
    """
    Aggregates child values to given parent,
    then recursively up the tree branches that are already marked done.
    Aggregated values are written into the network directly.

    :param tasks_by_id: Full task metadata indexed by UUID
    :type tasks_by_id: dict

    :param parents: Parent UUID indexed by child UUID
    :type parents: dict

    :param children: Set of child UUIDs indexed by parent UUID
    :type children: dict

    :param children_done: Task UUIDs that have been marked as done
    :type children_done: set

    :param network: Network; mutated to directly contain aggregated results
    :type network: dict

    :param parent_uuid: UUID of the parent to aggregate child values for
    :type parent_uuid: str

    :param indexes: Network indexes of values to aggregate
    :type indexes: list

    :returns: UUIDs of changed task groups.
    :rtype: set
    """
    changed_uuids = set()

    # do not bother with updating discarded parents;
    # we would need a second set of children including all discarded children
    parent = tasks_by_id[parent_uuid]
    if parent["discarded"]:
        return changed_uuids

    aggregated_values = aggregate_children(network, children[parent_uuid], indexes)
    updates = get_task_net_updates(
        tasks_by_id[parent_uuid], network[parent_uuid], aggregated_values
    )

    if updates:
        network[parent_uuid] = updates
        changed_uuids.add(parent_uuid)

    children_done.add(parent_uuid)

    if is_last_child(parents, children, children_done, parent_uuid):
        # parents only includes non-fixed parents with "adopt_bottom_up_target"
        # if the parent's parent is a task group without this flag, grandparent will be None
        grandparent_uuid = parents[parent_uuid]
        changed_uuids.update(
            adopt_bottom_up(
                tasks_by_id,
                parents,
                children,
                children_done,
                network,
                grandparent_uuid,
                indexes,
            )
        )

    return changed_uuids
