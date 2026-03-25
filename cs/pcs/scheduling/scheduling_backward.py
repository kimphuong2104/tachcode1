#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-locals

import collections

from cs.pcs.scheduling.calendar import add_duration
from cs.pcs.scheduling.constants import DR, LF, LS
from cs.pcs.scheduling.constraints import handle_fixed_constraints
from cs.pcs.scheduling.helpers import adopt_bottom_up, is_last_child
from cs.pcs.scheduling.relships import apply_relship_backward


def backward_pass(task_data, tasks, successors, network, max_ef, max_ef_with_discarded):
    """
    Iterate over tasks, starting with those without successors
    and ending with those without predecessors.
    Do note that implicit SS relationships from parent to child are ignored here.

    Updates the network directly with calculated latest dates LS and LF.
    """
    # Task data as returned from `cs.pcs.scheduling.tasks.load_sorted_tasks`
    by_uuid, _, __, parents, children, ___ = task_data

    children_done = set()
    # unique ending point key to end.uuid, end.DR, relship.orig_type, relship.orig_gap, end.LS
    non_discarded_chain_ends = {}
    # task_uuid: set of ending point keys
    non_discarded_succs = collections.defaultdict(set)

    for task in reversed(tasks):
        task_uuid = task["cdb_object_id"]
        task_net = network[task_uuid]
        duration = task_net[DR]
        is_discarded = task["discarded"]

        # init lates values (if no successors, these are final)
        if is_discarded:
            task_net[LS] = add_duration(
                max_ef_with_discarded, -duration, task["position_fix"], False
            )
            task_net[LF] = max_ef_with_discarded
        else:
            task_net[LS] = add_duration(max_ef, -duration, task["position_fix"], False)
            task_net[LF] = max_ef

        task_successors = successors.get(task_uuid, [])

        if task_successors:
            apply_successors(
                network,
                task_uuid,
                task["position_fix"],
                is_discarded,
                task_successors,
                non_discarded_succs,
                non_discarded_chain_ends,
                max_ef,
            )

        handle_fixed_constraints(task, task_net)

        # bubble up aggregated values LS, LF to completed parents
        if not task["adopt_bottom_up_target"]:
            children_done.add(task_uuid)

            if is_last_child(parents, children, children_done, task_uuid):
                parent_uuid = parents[task_uuid]
                adopt_bottom_up(
                    by_uuid,
                    parents,
                    children,
                    children_done,
                    network,
                    parent_uuid,
                    [LS, LF],
                )


def apply_successors(
    network,
    task_uuid,
    position_fix,
    is_discarded,
    task_successors,
    non_discarded_succs,
    non_discarded_chain_ends,
    max_ef,
):
    task_net = network[task_uuid]
    for relship in task_successors:
        _, succ_uuid, rel_type, minimal_gap, __, succ_discarded, ___ = relship
        succ_net = network[succ_uuid]

        if succ_discarded and not is_discarded:
            # chain of dicarded tasks starts now

            # Does the successor have any end point?
            # - Task on a discarded chain to the end do not have one
            # NOTE: Tasks on a discarded chain TO the end have no end point;
            #       only tasks on discarded chains FROM the start have.
            #       That's why dummy chain points are created during forward pass and finalize.
            if non_discarded_succs[succ_uuid]:
                # construct virtual relship to each ending point of successor
                for ending_point_key in non_discarded_succs[succ_uuid]:
                    ending_point = non_discarded_chain_ends[ending_point_key]
                    # Calculate LF from ending point to current task
                    pseudo_succ_net = {
                        DR: ending_point[1],
                        LS: ending_point[4],
                        LF: ending_point[4] + ending_point[1],
                    }
                    virtual_relship = (
                        ending_point[0],  # successor from last relship
                        None,
                        rel_type[0] + ending_point[2][1],  # combined rel_type
                        minimal_gap,  # gap from "ingoing" relship
                        None,
                        None,
                        None,
                    )
                    apply_relship_backward(
                        task_net,
                        pseudo_succ_net,
                        position_fix,
                        virtual_relship,
                        is_discarded,
                    )

            else:
                # Successor Chain is completely discarded
                task_net[LS] = max_ef - task_net[DR]
                task_net[LF] = max_ef

        else:
            apply_relship_backward(
                task_net,
                succ_net,
                position_fix,
                relship,
                is_discarded,
            )

            if is_discarded:
                if succ_discarded:
                    # we're in the middle of a chain of discarded tasks
                    # join ending point of successor into own set of ending points
                    non_discarded_succs[task_uuid].update(
                        non_discarded_succs[succ_uuid]
                    )
                else:
                    # chain of discarded tasks ends now
                    # remember successor as ending point
                    ending_point_key = (task_uuid, succ_uuid)
                    non_discarded_chain_ends[ending_point_key] = [
                        succ_uuid,
                        succ_net[DR],
                        rel_type,
                        minimal_gap,  # unused
                        succ_net[LS],
                    ]
                    non_discarded_succs[task_uuid].add(ending_point_key)
