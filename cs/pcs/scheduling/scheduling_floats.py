#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import collections

from cs.pcs.scheduling.calendar import add_duration, add_gap, get_duration
from cs.pcs.scheduling.constants import (
    AA,
    DR,
    ES,
    FF,
    LS,
    RELSHIP_FF,
    RELSHIP_FS,
    RELSHIP_SF,
    RELSHIP_SS,
    TF,
    ZZ,
)

RELTYPE_START = RELSHIP_FS[1]


def calculate_floats(tasks, successors, network, project_end):
    """
    Iterate over tasks, starting with those without successors
    and ending with those without predecessors.

    Updates the network directly with calculated free and total float values.
    """
    # unique end point key (task UUID) to end.DR, original relship type, end.AA
    non_discarded_chain_ends = {}
    # task_uuid: set of ending point keys
    non_discarded_succs = collections.defaultdict(set)

    for task in reversed(tasks):
        task_uuid = task["cdb_object_id"]
        task_net = network[task_uuid]
        is_discarded = task["discarded"]
        task_successors = successors.get(task_uuid, [])
        if task_successors:
            max_end = calc_max_end(
                network,
                task_uuid,
                task["position_fix"],
                task_successors,
                is_discarded,
                project_end,
                non_discarded_succs,
                non_discarded_chain_ends,
            )
            # free float until earliest successor start
            # Note: We take scheduled dates AA and ZZ - they already include ASAP/ALAP constraints
            free_float = get_duration(task_net[ZZ], max_end)
            task_net[FF] = max(0, free_float)
        else:
            task_net[FF] = task_net[LS] - task_net[ES]
            if is_discarded:
                # construct dummy endpoint
                non_discarded_chain_ends[task_uuid] = (task_net[AA], task_net[ZZ])
                non_discarded_succs[task_uuid].add(task_uuid)

        task_net[TF] = get_duration(task_net[ES], task_net[LS])
        task_net[FF] = min(task_net[FF], task_net[TF])  # FF cannot exceed TF


def _calc_max_end(rel_type, gap, pred_DR, pred_position_fix, succ_ES, succ_EF):
    if rel_type == RELSHIP_FS:
        return add_gap(succ_ES, -gap, pred_position_fix, False, False)

    elif rel_type == RELSHIP_SS:
        max_pred_es = add_gap(succ_ES, -gap, pred_position_fix, True, False)
        return add_duration(max_pred_es, pred_DR, pred_position_fix, True)

    elif rel_type == RELSHIP_FF:
        return add_gap(succ_EF, -gap, pred_position_fix, True, False)

    elif rel_type == RELSHIP_SF:
        max_pred_es = add_gap(succ_EF, -gap, pred_position_fix, False, False)
        return add_duration(max_pred_es, pred_DR, pred_position_fix, True)


def calc_max_end(
    network,
    task_uuid,
    position_fix,
    task_successors,
    is_discarded,
    project_end,
    non_discarded_succs,
    non_discarded_chain_ends,
):
    """
    Calculates the theoretical latest end of a task
    if we assume relship minimal gaps and successor earliest starts
    to be unchangeable.

    The distance from the task's scheduled end to this value
    will be the task's free float.
    """
    max_ef = project_end

    for relship in task_successors:
        _, succ_uuid, rel_type, gap, __, succ_discarded, ___ = relship
        succ_net = network[succ_uuid]
        if not is_discarded and succ_discarded:
            # start of chain - create virtual relship to each ending point
            for ending_point_key in non_discarded_succs[succ_uuid]:
                # construct virtual relship
                end_point_aa, end_point_zz = non_discarded_chain_ends[ending_point_key]
                max_ef = min(
                    max_ef,
                    _calc_max_end(
                        rel_type[0] + RELTYPE_START,  # virtual rel_type
                        gap,
                        network[task_uuid][DR],
                        position_fix,
                        end_point_aa,
                        end_point_zz,
                    ),
                )
        else:
            max_ef = min(
                max_ef,
                _calc_max_end(
                    rel_type,
                    gap,
                    network[task_uuid][DR],
                    position_fix,
                    succ_net[AA],
                    succ_net[ZZ],
                ),
            )
            if is_discarded:
                if succ_discarded:
                    # inside chain - join ending points
                    non_discarded_succs[task_uuid].update(
                        non_discarded_succs[succ_uuid]
                    )
                else:
                    # end of chain - remember successor as ending point
                    ending_point_key = (task_uuid, succ_uuid)
                    non_discarded_chain_ends[ending_point_key] = (
                        succ_net[AA],
                        succ_net[ZZ],
                    )
                    non_discarded_succs[task_uuid].add(ending_point_key)

    return max_ef
