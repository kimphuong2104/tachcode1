#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import sys

from cdb import util

from cs.pcs.scheduling.constants import DR
from cs.pcs.scheduling.scheduling_backward import backward_pass
from cs.pcs.scheduling.scheduling_finalize import finalize
from cs.pcs.scheduling.scheduling_floats import calculate_floats
from cs.pcs.scheduling.scheduling_forward import forward_pass, get_max_ef

DEFAULT_MAX_SCHEDULING_RETRIES = 3
DEFAULT_MAX_SCHEDULING_RETRIES_PROP = "pmsr"  # "pcs: max. scheduling retries"


def get_max_scheduling_retries():
    """
    How many time can we repeat the forward pass
    before requiring it to not produce any more changes?
    Because of the two potentially conflicting scheduling dimensions
        1. "direct" (constraints, relships) and
        2. "parent-child" (aggregating/"adopting" child values to task groups)
    conflicts can not be avoided 100%.

    The default value is chosen to be minimal.
    Higher values can be configured as integer values of the property "pmsr".

    WARNING: This is intentionally undocumented. Use at your own risk.
    Exceptions in case scheduling is not stable enough should always be
    reported to find the root cause and remove the source of instability.
    """
    try:
        override = int(util.get_prop(DEFAULT_MAX_SCHEDULING_RETRIES_PROP))
        return max(DEFAULT_MAX_SCHEDULING_RETRIES, override)

    except (TypeError, ValueError):
        return DEFAULT_MAX_SCHEDULING_RETRIES


def _new_changes(known_changes, network, changed_uuids):
    """
    :returns: Whether ``network`` contains any changes related to ``changed_uuids``
        that are not part of ``known_changes``.
    :rtype: bool
    """
    for changed_uuid in changed_uuids:
        if network[changed_uuid] != known_changes.get(changed_uuid, None):
            return True

    return False


def calculate_network(
    task_data, tasks_forward, tasks_backward, relships, latest_finish
):
    """
    Constructs a "task network" (a list of scheduling-related integer values),
    calculates the values and returns the network.

    The network is a dictionary indexed by task UUID and contains entries of exactly
    9 integer values:

    +-----+-------+------------------+------------------------------------------------+
    | Pos | Value | Name             | Description                                    |
    +=====+=======+==================+================================================+
    | 1.  | DR    | duration         | duration in workdays                           |
    |     |       |                  | (mutated for task groups only)                 |
    +-----+-------+------------------+------------------------------------------------+
    | 2.  | ES    | earliest start   | earliest start possible                        |
    +-----+-------+------------------+------------------------------------------------+
    | 3.  | EF    | earliest finish  | earliest end possible                          |
    +-----+-------+------------------+------------------------------------------------+
    | 4.  | LS    | latest start     | latest start possible                          |
    +-----+-------+------------------+------------------------------------------------+
    | 5.  | LF    | latest finish    | latest end possible                            |
    +-----+-------+------------------+------------------------------------------------+
    | 6.  | AA    | scheduled start  | scheduled / resulting start                    |
    +-----+-------+------------------+------------------------------------------------+
    | 7.  | ZZ    | scheduled finish | scheduled / resulting end                      |
    +-----+-------+------------------+------------------------------------------------+
    | 8.  | FF    | free float       | task can be moved this many days without       |
    |     |       | (or "slack")     | affecting any direct successor's earliest end) |
    +-----+-------+------------------+------------------------------------------------+
    | 9.  | TF    | total float      | task can be moved this many days without       |
    |     |       | (or "slack")     | affecting the project's earliest end?)         |
    +-----+-------+------------------+------------------------------------------------+

    The `ES`, `EF`, `LS`, `LF`, `AA` and `ZZ` values represent times,
    e.g. both a day and either the start or end of that day.
    Index 0 maps to the start of the workday the calendar starts on,
    index 1 to its end.
    Index 8 maps to the start of the calendar's 5th workday,
    index 9 to its end.

    The calculation is done in severeal "passes" iterating over all the tasks.
    Arrows pointing to the right indicate a "forward" pass
    (starting with tasks without predecessors),
    arrows pointing to the left a "backward" pass
    (starting with tasks without successors):

    1. -> Calculate ES and EF
    2. <- Calculate LS and LF
    3. <- Calculate task group DR, ES and EF
    4. -> Determine AA and ZZ
    5. <- Calculate FF and TF
    """
    max_retries = get_max_scheduling_retries()
    network = init_network(tasks_forward)
    predecessors, successors = relships[0], relships[1]

    changed_uuids, min_es = forward_pass(
        task_data, tasks_forward, predecessors, network
    )
    all_changes = {}
    retries = 0

    # repeat only if new change came up in last forward_pass call
    while changed_uuids:
        if _new_changes(all_changes, network, changed_uuids):
            # these changes are new, remember them
            for changed_uuid in changed_uuids:
                all_changes[changed_uuid] = list(network[changed_uuid])
        else:
            # we already saw these changes in an earlier run,
            # so we're done now.
            break

        retries += 1
        if retries > max_retries:
            raise RuntimeError("ERROR: unstable scheduling")

        # re-initialize network, but keep DR of last run
        network = init_network(tasks_forward)

        for task_uuid, changed_net in all_changes.items():
            network[task_uuid][DR] = changed_net[DR]

        changed_uuids, min_es = forward_pass(
            task_data, tasks_forward, predecessors, network, min_es
        )

    max_ef, max_ef_discarded = get_max_ef(tasks_forward, network, latest_finish)
    backward_pass(
        task_data, tasks_backward, successors, network, max_ef, max_ef_discarded
    )
    finalize(tasks_forward, predecessors, successors, network)
    calculate_floats(tasks_backward, successors, network, max_ef)

    return network


def init_network(tasks):
    "Initializes task network indexed by UUIDs"
    network = {}

    for task in tasks:
        # initialize task network (see scheduling: DR, ES, EF, LS, LF, AA, ZZ, FF, TF)

        duration = task["days_fcast"] or 0
        start_date = task["start_time_fcast"]
        end_date = task["end_time_fcast"]

        if task["fixed"]:
            task_network = [
                duration,
                # early, late dates
                start_date,
                end_date,
                start_date,
                end_date,
                # final/scheduled dates (won't be overwritten later)
                start_date,
                end_date,
                # floats
                0,
                0,
            ]
        else:
            task_network = [
                duration,
                -sys.maxsize,
                -sys.maxsize,
                sys.maxsize,
                sys.maxsize,
                None,
                None,
                0,
                0,
            ]

        network[task["cdb_object_id"]] = task_network

    return network
