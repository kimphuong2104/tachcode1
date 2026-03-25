#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-locals

import collections

from cs.pcs.scheduling.calendar import add_duration, add_gap
from cs.pcs.scheduling.constants import AA, ALAP, DR, EF, ES, LF, LS, ZZ
from cs.pcs.scheduling.helpers import create_dummy_chain_point, get_value
from cs.pcs.scheduling.scheduling_forward import apply_predecessors


def finalize(tasks, predecessors, successors, network):
    """
    Iterate over tasks, starting with those without predecessors
    and ending with those without successors.

    Updates the network directly with scheduled dates AA and ZZ.
    """
    # pylint: disable=too-many-nested-blocks
    # unique starting point key to start.uuid start.EF, start.DR, relship.orig_type, relship.orig_gap
    non_discarded_chain_starts = {}
    # task_uuid: set of starting point keys
    non_discarded_preds = collections.defaultdict(set)
    # subtasks by task_id of parent task
    tasks_by_parents = collections.defaultdict(list)

    for task in tasks:
        task_uuid = task["cdb_object_id"]
        task_net = network[task_uuid]
        position_fix = task["position_fix"]
        task_predecessors = predecessors.get(task_uuid, [])
        is_discarded = task["discarded"]
        tasks_by_parents[task["parent_uuid"]].append(task)

        # make sure latest dates are not earlier than earliest
        # (might happen for task groups with position_fix children)
        task_es = task_net[ES]
        if task_es > task_net[LS]:
            task_net[LS] = add_gap(task_es, 0, position_fix, True, True)
            task_net[LF] = add_duration(task_net[LS], task_net[DR], position_fix, True)

        if task_predecessors:
            if task["fixed"]:
                # task is fixed - so do not change itself, but still gather its starting points
                if is_discarded:
                    for (
                        pred_uuid,
                        _,
                        rel_type,
                        minimal_gap,
                        pred_discarded,
                        _,
                        _,
                    ) in task_predecessors:
                        pred_net = network[pred_uuid]
                        pred_ef = get_value(pred_net, ZZ, EF)  # finalize == True
                        if pred_discarded:
                            # we're in the middle of a chain of discarded tasks
                            # join starting point of predecessor into own set of predecessors
                            non_discarded_preds[task_uuid].update(
                                non_discarded_preds[pred_uuid]
                            )
                        else:
                            # chain of dicarded tasks starts now
                            # remember predecessor as starting point
                            starting_point_key = (pred_uuid, task_uuid)
                            non_discarded_chain_starts[starting_point_key] = [
                                pred_uuid,
                                pred_net[DR],
                                rel_type,
                                minimal_gap,
                                pred_ef,
                            ]
                            non_discarded_preds[task_uuid].add(starting_point_key)
            else:  # predecessors are now finalized, so apply again
                apply_predecessors(
                    network,
                    task_predecessors,
                    True,
                    task_uuid,
                    task["position_fix"],
                    is_discarded,
                    non_discarded_chain_starts,
                    non_discarded_preds,
                )
        elif is_discarded:
            non_discarded_chain_starts[task_uuid] = create_dummy_chain_point(
                task_uuid, task_net[ES]
            )
            non_discarded_preds[task_uuid].add(task_uuid)

        # this is _finally_ the real scheduling (only for non group tasks)
        if task["is_group"] == 0:
            is_late = task["constraint_type"] == ALAP
            if task_net[AA] is None:
                task_net[AA] = task_net[LS if is_late else ES]

            if task_net[ZZ] is None:
                task_net[ZZ] = task_net[LF if is_late else EF]

            adjust_task_relship_gap(task, task_net, predecessors, successors)

    # finally adjust all group tasks by the start/end values of their children
    calculate_group_tasks(tasks_by_parents, network, predecessors, successors)


def calculate_group_tasks(
    tasks_by_parents, network, predecessors, successors, task=None
):
    sub_tasks = []
    if task:
        sub_tasks = tasks_by_parents[task["cdb_object_id"]]
    else:
        sub_tasks = tasks_by_parents[""]

    if not sub_tasks:
        if task:
            # single task --> return finalized start and end
            task_uuid = task["cdb_object_id"]
            task_net = network[task_uuid]
            return task_net[AA], task_net[ZZ]
        # project contains no tasks at all
        return None, None

    start = None
    end = None

    # subtasks have been found: use them to determine start/end of group task
    number_of_used_subtasks = 0
    # count number of subtasks, that are used for aggregation of group task values
    #   - if complete task structure is discarded (summary task and subtasks),
    #     then aggregate task structure as normal
    #   - if group task has at least one non-discarded subtask,
    #     then aggregate task structure, but skip discarded subtasks
    #   - if for group task bottom-up aggregation is not activated,
    #     then ignore all subtask, so no aggregation will be done
    parent_adopt_bottom_up_target = task and task["adopt_bottom_up_target"]
    parent_discarded = parent_adopt_bottom_up_target and task["discarded"]
    for subtask in sub_tasks:
        a_start, a_end = calculate_group_tasks(
            tasks_by_parents, network, predecessors, successors, task=subtask
        )
        if parent_adopt_bottom_up_target:
            if parent_discarded or not subtask["discarded"]:
                number_of_used_subtasks += 1
                start = min(start, a_start) if start is not None else a_start
                end = max(end, a_end) if end is not None else a_end

    if task:
        # set start/end of group task
        task_uuid = task["cdb_object_id"]
        task_net = network[task_uuid]
        if not number_of_used_subtasks:
            start = task_net[ES]
            end = task_net[EF]
        task_net[AA] = start
        task_net[ZZ] = end
        adjust_task_relship_gap(task, task_net, predecessors, successors)

    return start, end


def adjust_task_relship_gap(task, task_net, predecessors, successors):
    """
    Since the group tasks can change their duration during
    their scheduling (due to auto updating dates from children),
    their relationship gaps have to be adjusted.

    :param task: the group task for which we need to adjust the relship gaps
    :type task: dict

    :param task_net: group task's calculated network values
    :type task_net: list

    :param predecessors: predecessors of tasks indexed by task uuid
    :type predecessors: dict

    :param successors: successors of tasks indexed by task uuid
    :type successors: dict

    :returns: Nothing, changes the predecessors and successors in place.
    :rtype: None
    """

    if not task["adopt_bottom_up_target"]:
        return

    task_uuid = task["cdb_object_id"]
    succ = successors.get(task_uuid, [])

    for i, relship in enumerate(succ):
        (
            _,
            succ_uuid,
            rel_type,
            minimal_gap,
            __,
            succ_discarded,
            is_parent_child,
        ) = relship

        if is_parent_child:
            # skip implicit parent-child relships
            continue

        original_duration = task["days_fcast"]
        new_duration = task_net[ZZ] - task_net[AA]
        if new_duration != original_duration:
            diff = new_duration - original_duration
            new_gap = minimal_gap - diff
            succ[i] = (
                _,
                succ_uuid,
                rel_type,
                new_gap,
                __,
                succ_discarded,
                is_parent_child,
            )

            preds = predecessors.get(succ_uuid, [])

            for j, pred_info in enumerate(preds):
                (
                    pred_uuid,
                    _,
                    rel_type,
                    _,  # gap
                    pred_discarded,
                    _,
                    is_parent_child,
                ) = pred_info
                if pred_uuid == task_uuid:  # predecessor is the current task
                    preds[j] = (
                        pred_uuid,
                        _,
                        rel_type,
                        new_gap,
                        pred_discarded,
                        _,
                        is_parent_child,
                    )
