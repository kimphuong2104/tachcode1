#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import util


def get_sorted_task_uuids(by_uuid, pred_uuids_forward, pred_uuids_backward):
    """
    :param by_uuid: Task metadata by UUID
    :type by_uuid: dict

    :param pred_uuids_forward: Predecessor UUIDs indexed by successor UUID
    :type pred_uuids_forward: dict

    :param pred_uuids_backward: Successor UUIDs indexed by predecessor UUID
    :type pred_uuids_backward: dict

    :returns: Topologically-sorted values of ``task_uuids``,
        e.g. no predecessor is sorted after its successor.
        The first copy is for use in forward passes,
        the second one for use in backward passes.
    :rtype: tuple(list, list)
    """
    uuids_discarded_last = sorted(
        by_uuid.keys(), key=lambda uuid: by_uuid[uuid]["discarded"]
    )
    sorted_uuids_forward = _toposort(uuids_discarded_last, pred_uuids_forward)
    sorted_uuids_backward = _toposort(uuids_discarded_last, pred_uuids_backward)
    return sorted_uuids_forward, sorted_uuids_backward


def _toposort(task_uuids, predecessors):
    """
    :param task_uuids: Task UUIDs to sort (sorting is preserved in leaves)
    :type task_uuids: list

    :param predecessors: Task UUIDs indexed by their successors's UUID
    :type predecessors: dict

    :returns: Topologically-sorted values of ``task_uuids``,
        e.g. no predecessor is sorted after its successor
    :rtype: list
    """
    counts = {uuid: 0 for uuid in task_uuids}

    # "counts" keeps track of the number of successors per task
    for preds in predecessors.values():
        for predecessor in preds:
            counts[predecessor] += 1

    sorted_uuids = []
    # nodes without successors
    # (using a list so the order of leaf IDs is stable)
    independent = [uuid for uuid in task_uuids if counts[uuid] == 0]
    # unhandled parts of the graph
    remaining_graph = dict(predecessors)

    while independent:
        # visit any node without predecessors
        node_without_preds = independent.pop()
        sorted_uuids.insert(0, node_without_preds)

        # remove visited node from all of its successor counts
        for succ_node in remaining_graph.pop(node_without_preds, ()):
            counts[succ_node] -= 1
            # successors that have no other predecessors left are now independent
            if counts[succ_node] == 0:
                independent.append(succ_node)

    # we expect to have handled each node now
    if remaining_graph:
        raise util.ErrorMessage("cdbpcs_taskrel_cycle_found")

    return sorted_uuids
