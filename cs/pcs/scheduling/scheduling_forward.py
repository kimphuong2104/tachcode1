#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-locals

import collections
import sys

from cs.pcs.scheduling.calendar import add_duration
from cs.pcs.scheduling.constants import AA, DR, EF, ES, ZZ
from cs.pcs.scheduling.constraints import handle_fixed_constraints
from cs.pcs.scheduling.helpers import (
    adopt_bottom_up,
    create_dummy_chain_point,
    get_value,
    is_last_child,
)
from cs.pcs.scheduling.relships import apply_relship_forward


def forward_pass(task_data, tasks, predecessors, network, project_start=0):
    """
    Iterate over tasks, starting with those without predecessors
    and ending with those without successors.
        Do note that implicit FF relationships from child to parent are ignored here.

    Updates the network directly with calculated earliest dates ES and EF.
    Latest dates LS and LF are also applied directly for tasks with fixed constraint dates.

    :returns:
        1. Any task group's duration changes due to "adopting" bottom up values
        2. Min. ES of the network (always 0 if 3. is empty)
    :rtype: tuple(int, int, bool)
    """
    # Task data as returned from `cs.pcs.scheduling.tasks.load_sorted_tasks`
    by_uuid, _, __, parents, children, ___ = task_data

    children_done = set()
    changed_uuids = set()

    # unique starting point key to start.uuid start.DR, relship.orig_type, relship.orig_gap, start.EF
    non_discarded_chain_starts = {}
    # task_uuid: set of starting point keys
    non_discarded_preds = collections.defaultdict(set)

    for task in tasks:
        task_uuid = task["cdb_object_id"]
        task_net = network[task_uuid]
        is_discarded = task["discarded"]

        task_predecessors = predecessors.get(task_uuid, [])

        if not task_predecessors:
            # init earliest values (if no predecessors, these are final)
            if task_net[ES] == -sys.maxsize:
                task_net[ES] = project_start
            if task_net[EF] == -sys.maxsize:
                task_net[EF] = add_duration(
                    task_net[ES], task_net[DR], task["position_fix"], True
                )

        if not task_predecessors and is_discarded:  # dummy start for discarded chain
            non_discarded_chain_starts[task_uuid] = create_dummy_chain_point(
                task_uuid,
                task_net[ES],
            )
            non_discarded_preds[task_uuid].add(task_uuid)

        if task_predecessors:
            apply_predecessors(
                network,
                task_predecessors,
                False,
                task_uuid,
                task["position_fix"],
                is_discarded,
                non_discarded_chain_starts,
                non_discarded_preds,
            )

        handle_fixed_constraints(task, task_net)

        # bubble up aggregated values DR, ES, EF to completed parents
        if not task["adopt_bottom_up_target"]:
            children_done.add(task_uuid)

            if is_last_child(parents, children, children_done, task_uuid):
                parent_uuid = parents[task_uuid]
                changed_uuids.update(
                    adopt_bottom_up(
                        by_uuid,
                        parents,
                        children,
                        children_done,
                        network,
                        parent_uuid,
                        [DR, ES, EF],
                    )
                )

    if changed_uuids:
        min_es = min(task_net[ES] for task_net in network.values())
    else:
        min_es = 0

    return changed_uuids, min_es


def apply_predecessors(
    network,
    task_predecessors,
    finalize,
    task_uuid,
    position_fix,
    is_discarded,
    non_discarded_chain_starts,
    non_discarded_preds,
):
    # pylint: disable=too-many-locals
    task_net = network[task_uuid]
    for relship in task_predecessors:
        pred_uuid, _, rel_type, minimal_gap, pred_discarded, __, ___ = relship
        pred_net = network[pred_uuid]

        if pred_discarded and not is_discarded:
            # chain of dicarded tasks ends now
            # construct virtual relship to each starting point of predecessor
            # NOTE: Chains of discarded predecessors beginning at project start
            #       are ignored, since they do not have any starting point
            for starting_point_key in non_discarded_preds[pred_uuid]:
                starting_point = non_discarded_chain_starts[starting_point_key]
                # calculate ES from starting point to current task
                pseudo_pred_net = {
                    DR: starting_point[1],
                    ES: starting_point[4] - starting_point[1],
                    EF: starting_point[4],
                    AA: None,
                    ZZ: None,
                }
                virtual_relship = (
                    starting_point[0],  # predecessor from "ingoing" relship
                    None,
                    starting_point[2][0] + rel_type[1],  # combined rel_type
                    starting_point[3],  # gap from "ingoing" relship
                    None,
                    None,
                    None,
                )

                apply_relship_forward(
                    pseudo_pred_net,
                    task_net,
                    position_fix,
                    virtual_relship,
                    finalize,
                )
        else:
            apply_relship_forward(
                pred_net,
                task_net,
                position_fix,
                relship,
                finalize,
            )
            if is_discarded:
                if pred_discarded:
                    # we're in the middle of a chain of discarded tasks
                    # join starting point of predecessor into own set of predecessors
                    non_discarded_preds[task_uuid].update(
                        non_discarded_preds[pred_uuid]
                    )
                else:
                    # chain of dicarded tasks starts now
                    # remember predecessor as starting point
                    pred_ef = get_value(pred_net, ZZ, EF) if finalize else pred_net[EF]
                    starting_point_key = (pred_uuid, task_uuid)
                    non_discarded_chain_starts[starting_point_key] = [
                        pred_uuid,
                        pred_net[DR],
                        rel_type,
                        minimal_gap,
                        pred_ef,
                    ]
                    non_discarded_preds[task_uuid].add(starting_point_key)


def get_max_ef(tasks, network, latest_finish):
    """
    :param tasks: List of task dictionaries
    :type tasks: list

    :param network: Network; mutated to directly contain aggregated results
    :type network: dict

    :param latest_finish: Project's end index. Only given if project is scheduled manually.
    :type latest_finish: int

    :returns: Maximum date indexes from ``network``'s EF values and ``latest_finish`` (if given)
        1. Ignoring discarded tasks
        2. Including discarded tasks
    :rtype: tuple(int, int)
    """
    max_ef, max_ef_discarded = -sys.maxsize, -sys.maxsize

    for task in tasks:
        task_ef = network[task["cdb_object_id"]][EF]
        max_ef_discarded = max(max_ef_discarded, task_ef)
        if not task["discarded"]:
            max_ef = max(max_ef, task_ef)

    # if project is scheduled manually, latest finish is maximum of project end and max_ef
    if latest_finish:
        max_ef_discarded = max(max_ef_discarded, latest_finish)
        max_ef = max(max_ef, latest_finish)

    return max_ef, max_ef_discarded
