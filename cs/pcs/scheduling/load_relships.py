#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import collections
import itertools

from cdb import sqlapi

from cs.pcs.scheduling.constants import RELSHIP_FF, RELSHIP_SS
from cs.pcs.scheduling.load import load

SELECT_RELSHIPS = """
    -- SELECT
        pred_task_oid,
        succ_task_oid,
        rel_type,
        minimal_gap,
        violation
    FROM cdbpcs_taskrel
    WHERE cdb_project_id = '{project_id}'
        AND cdb_project_id2 = '{project_id}'
"""
COLUMNS_RELSHIPS = [
    ("pred_task_oid", sqlapi.SQLstring),
    ("succ_task_oid", sqlapi.SQLstring),
    ("rel_type", sqlapi.SQLstring),
    ("minimal_gap", sqlapi.SQLinteger),
    ("violation", sqlapi.SQLinteger),
]


def _get_descendants(children_by_uuid, parent_uuid):
    children = children_by_uuid.get(parent_uuid, set())

    if not children:
        return {}

    if parent_uuid == "":
        descendants = {}
    else:
        descendants = {parent_uuid: set(child_uuid for child_uuid, _ in children)}

    for child_uuid, adopt_bottom_up in children:
        if adopt_bottom_up:
            for uuid, next_level in _get_descendants(
                children_by_uuid, child_uuid
            ).items():
                descendants[uuid] = next_level
                if parent_uuid != "":
                    descendants[parent_uuid].update(next_level)

    return descendants


def add_relships(all_children, discarded, relships):
    """
    1. "flatten" relships:
        if either pred or succ is a parent,
        add the relship with one copy for each descendant of the parent

    2. add implicit relships:
        parent -SS-> child (for forward passes only)
        child -FF-> parent (for backward passes only)
    """
    descendants_by_uuid = _get_descendants(all_children, "")
    originals = [tuple(list(original[:-1]) + [False]) for original in relships]
    flattened = []

    for original in relships:
        pred_original = original[0]
        succ_original = original[1]
        rel_type = original[2]
        gap = original[3]
        pred_descendants = descendants_by_uuid.get(pred_original, None)
        succ_descendants = descendants_by_uuid.get(succ_original, None)

        if pred_descendants or succ_descendants:
            pred_descendants = pred_descendants or [pred_original]
            succ_descendants = succ_descendants or [succ_original]

            flattened += [
                (
                    pred_new,
                    succ_new,
                    rel_type,
                    gap,
                    pred_new in discarded,
                    succ_new in discarded,
                    False,
                )
                for pred_new, succ_new in itertools.product(
                    pred_descendants, succ_descendants
                )
            ]

    parents_forward, parents_backward = [], []
    for parent, children in all_children.items():
        if parent == "":
            continue
        for child, _ in children:
            parents_forward.append(
                (
                    parent,
                    child,
                    RELSHIP_SS,
                    0,
                    parent in discarded,
                    child in discarded,
                    True,
                )
            )
            parents_backward.append(
                (
                    child,
                    parent,
                    RELSHIP_FF,
                    0,
                    child in discarded,
                    parent in discarded,
                    True,
                )
            )

    return originals, flattened, parents_forward, parents_backward


def load_relships(all_children, project_id, discarded):
    """
    :param all_children: UUIDs of children indexed by parent UUID
    :type all_children: dict

    :param project_id: Project ID to load tasks for
    :type project_id: str

    :param discarded: UUIDs of discarded tasks
    :type discarded: set

    :returns:
        1. Predecessor data by successor UUID (not including implicit FF relships)
        2. Successor data by predecessor UUID (not including implicit SS relships)
        3. List of persistent relationship data
           (does not include implicit parent-child relships, unlike 1. and 2.)
        4. Copy of 1., but only containing predecessor UUIDs
        5. Copy of 2., but reversed, indexing predecessors (UUIDs only) by successor UUID

        3. is a list of relship tuples,
        all others are dicts indexing lists of relship tuples by UUID.

        Relship tuples consist of these values:
            1. The predecessor UUID
            2. The successor UUID
            3. The relationship type
            4. The relationship (minimal) gap
            5. If the predecessor is discarded
            6. If the successor is discarded
            7. If this is an implicit parent-child relationship

        Usage:

        - 1. and 2. are used in the forward and backward pass, respectively
        - 3. is used for diffing during the persist step
        - 4. and 5. are used for topologically sorting the tasks
    :rtype: tuple
    """
    condition = SELECT_RELSHIPS.format(project_id=sqlapi.quote(project_id))
    persistent = load(condition, COLUMNS_RELSHIPS)
    persistent = [
        (
            x["pred_task_oid"],
            x["succ_task_oid"],
            x["rel_type"],
            x["minimal_gap"],
            x["pred_task_oid"] in discarded,
            x["succ_task_oid"] in discarded,
            x["violation"],
        )
        for x in persistent
    ]
    originals, flattened, parents_forward, parents_backward = add_relships(
        all_children, discarded, persistent
    )

    preds, succs = collections.defaultdict(list), collections.defaultdict(list)
    pred_uuids_forward = collections.defaultdict(list)
    pred_uuids_backward = collections.defaultdict(list)

    for relship in originals:
        pred = relship[0]
        succ = relship[1]
        preds[succ].append(relship)
        succs[pred].append(relship)
        pred_uuids_forward[succ].append(pred)
        pred_uuids_backward[succ].append(pred)

    for relship in flattened:
        pred = relship[0]
        succ = relship[1]
        pred_uuids_forward[succ].append(pred)
        pred_uuids_backward[succ].append(pred)

    for relship in parents_forward:
        pred = relship[0]
        succ = relship[1]
        preds[succ].append(relship)
        pred_uuids_forward[succ].append(pred)

    for relship in parents_backward:
        pred = relship[0]
        succ = relship[1]
        succs[pred].append(relship)
        pred_uuids_backward[succ].append(pred)

    # preds, succs: used in forward_pass, backward_pass
    # persistent: for diffing in persist step
    # pred_uuids_forward, pred_uuids_backward: used in toposort
    return preds, succs, persistent, pred_uuids_forward, pred_uuids_backward
