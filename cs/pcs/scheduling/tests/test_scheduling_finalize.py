#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest

from cs.pcs.scheduling import scheduling_finalize
from cs.pcs.scheduling.constants import ALAP, ASAP, EF, RELSHIP_FS, ZZ


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_no_tasks(apply_predecessors, get_value):
    # no tasks - no changes to anything
    network = {}
    expected_network = {}
    scheduling_finalize.finalize([], {}, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_not_called()
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_no_pred_late_milestone(apply_predecessors, get_value):
    # task without predecessors and late position milestone - apply edge case restriction
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": False,
            "is_group": False,
            "parent_uuid": "",
            "fixed": False,
            "milestone": True,
            "start_is_early": 0,
            "end_is_early": 0,
            "constraint_type": ASAP,
            "position_fix": False,
            "adopt_bottom_up_target": False,
        }
    ]
    network = {"T": [0, 0, 0, 0, 0, None, None, 0, 0]}
    expected_network = {"T": [0, 0, 0, 0, 0, 0, 0, 0, 0]}

    scheduling_finalize.finalize(tasks, {}, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_not_called()
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_no_pred_discarded(apply_predecessors, get_value):
    # task without predecessors and is discarded - collect starting point
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": True,
            "is_group": False,
            "parent_uuid": "",
            "fixed": False,
            "milestone": False,
            "start_is_early": False,
            "constraint_type": ASAP,
            "position_fix": True,
            "adopt_bottom_up_target": False,
        }
    ]
    network = {"T": [0, 0, 0, 1, 1, None, None, 0, 0]}
    expected_network = {"T": [0, 0, 0, 1, 1, 0, 0, 0, 0]}

    scheduling_finalize.finalize(tasks, {}, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_not_called()
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_no_pred_alap(apply_predecessors, get_value):
    # task without predecessors and neither milestone nor discarded but ALAP
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": False,
            "is_group": False,
            "parent_uuid": "",
            "fixed": False,
            "milestone": False,
            "start_is_early": False,
            "constraint_type": ALAP,
            "position_fix": True,
            "adopt_bottom_up_target": False,
        }
    ]
    network = {"T": [0, 0, 0, 1, 1, None, None, 0, 0]}
    expected_network = {"T": [0, 0, 0, 1, 1, 1, 1, 0, 0]}

    scheduling_finalize.finalize(tasks, {}, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_not_called()
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_pred_fixed_discarded_pred_discarded(apply_predecessors, get_value):
    # task with predecessors, is fixed, is discarded & pred is discarded - middle of chain
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": True,
            "is_group": False,
            "parent_uuid": "",
            "fixed": True,
            "milestone": False,
            "start_is_early": False,
            "constraint_type": ASAP,
            "position_fix": True,
            "adopt_bottom_up_target": False,
        }
    ]
    network = {
        "T": [0, 0, 0, 1, 1, None, None, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    expected_network = {
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    preds = {"T": [("PRED", "SUCC", RELSHIP_FS, 0, True, True, None)]}

    scheduling_finalize.finalize(tasks, preds, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_called_once_with(network.get("PRED"), ZZ, EF)
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_pred_fixed_discarded_pred_non_discarded(
    apply_predecessors, get_value
):
    # task with predecessors, is fixed, is discarded & pred not discarded - start of chain
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": True,
            "is_group": False,
            "parent_uuid": "",
            "fixed": True,
            "milestone": False,
            "start_is_early": False,
            "constraint_type": ASAP,
            "position_fix": True,
            "adopt_bottom_up_target": False,
        }
    ]
    network = {
        "T": [0, 0, 0, 1, 1, None, None, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    expected_network = {
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    preds = {"T": [("PRED", "SUCC", RELSHIP_FS, 0, False, False, None)]}

    scheduling_finalize.finalize(tasks, preds, {}, network)
    apply_predecessors.assert_not_called()
    get_value.assert_called_once_with(network.get("PRED"), ZZ, EF)
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize.collections, "defaultdict")
@mock.patch.object(scheduling_finalize, "get_value")
@mock.patch.object(scheduling_finalize, "apply_predecessors")
def test_finalize_pred_not_fixed(apply_predecessors, get_value, defaultdict):
    # task with predecessors and is not fixed - apply_predecessors
    tasks = [
        {
            "cdb_object_id": "T",
            "discarded": False,
            "fixed": False,
            "is_group": False,
            "parent_uuid": "",
            "milestone": False,
            "start_is_early": False,
            "constraint_type": ASAP,
            "position_fix": "PF",
            "adopt_bottom_up_target": False,
        }
    ]
    network = {
        "T": [0, 0, 0, 1, 1, None, None, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    expected_network = {
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "PRED": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    preds = {"T": [("PRED", RELSHIP_FS, 0, False, None)]}

    scheduling_finalize.finalize(tasks, preds, {}, network)
    apply_predecessors.assert_called_once_with(
        network,
        preds.get("T"),
        True,
        "T",
        "PF",
        False,  # is_discarded,
        {},  # non_discarded_chain_starts,
        defaultdict.return_value,  # non_discarded_preds,
    )
    get_value.assert_not_called()
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "adjust_task_relship_gap")
def test_calculate_group_tasks_01(adjust_task_relship_gap):
    # with aggregation: parent task and sub task
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "fixed": False,
        "is_group": False,
        "parent_uuid": "P",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF1",
        "adopt_bottom_up_target": False,
    }
    parent = {
        "cdb_object_id": "P",
        "discarded": False,
        "fixed": False,
        "is_group": True,
        "parent_uuid": "",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF2",
        "adopt_bottom_up_target": True,
    }
    task_net = [0, 0, 0, 1, 1, 0, 0, 0, 0]
    parent_task_net = [0, 0, 0, 1, 1, None, None, 0, 0]
    network = {
        "P": parent_task_net,
        "T": task_net,
    }
    expected_network = {
        "P": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
    }
    tasks_by_parents = scheduling_finalize.collections.defaultdict(list)
    tasks_by_parents[parent["parent_uuid"]].append(parent)
    tasks_by_parents[task["parent_uuid"]].append(task)

    scheduling_finalize.calculate_group_tasks(
        tasks_by_parents, network, "preds", "succs"
    )
    adjust_task_relship_gap.assert_called_once_with(
        parent,
        parent_task_net,
        "preds",
        "succs",
    )
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "adjust_task_relship_gap")
def test_calculate_group_tasks_02(adjust_task_relship_gap):
    # with aggregation: top parent task, middle parent task and sub task
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "fixed": False,
        "is_group": False,
        "parent_uuid": "MP",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF1",
        "adopt_bottom_up_target": False,
    }
    middle_parent = {
        "cdb_object_id": "MP",
        "discarded": False,
        "fixed": False,
        "is_group": True,
        "parent_uuid": "TP",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF2",
        "adopt_bottom_up_target": True,
    }
    top_parent = {
        "cdb_object_id": "TP",
        "discarded": False,
        "fixed": False,
        "is_group": True,
        "parent_uuid": "",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF2",
        "adopt_bottom_up_target": True,
    }
    task_net = [0, 0, 0, 1, 1, 0, 0, 0, 0]
    middle_parent_task_net = [0, 0, 0, 1, 1, None, None, 0, 0]
    top_parent_task_net = [0, 0, 0, 1, 1, None, None, 0, 0]
    network = {
        "TP": top_parent_task_net,
        "MP": middle_parent_task_net,
        "T": task_net,
    }
    expected_network = {
        "TP": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "MP": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
    }
    tasks_by_parents = scheduling_finalize.collections.defaultdict(list)
    tasks_by_parents[top_parent["parent_uuid"]].append(top_parent)
    tasks_by_parents[middle_parent["parent_uuid"]].append(middle_parent)
    tasks_by_parents[task["parent_uuid"]].append(task)

    scheduling_finalize.calculate_group_tasks(
        tasks_by_parents, network, "preds", "succs"
    )
    adjust_task_relship_gap.assert_called_with(
        top_parent,
        top_parent_task_net,
        "preds",
        "succs",
    )
    assert network == expected_network


@pytest.mark.unit
@mock.patch.object(scheduling_finalize, "adjust_task_relship_gap")
def test_calculate_group_tasks_03(adjust_task_relship_gap):
    # without aggregation: top parent task, middle parent task and sub task
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "fixed": False,
        "is_group": False,
        "parent_uuid": "P",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF1",
        "adopt_bottom_up_target": False,
    }
    parent = {
        "cdb_object_id": "P",
        "discarded": False,
        "fixed": False,
        "is_group": True,
        "parent_uuid": "",
        "milestone": False,
        "start_is_early": False,
        "constraint_type": ASAP,
        "position_fix": "PF2",
        "adopt_bottom_up_target": False,
    }
    task_net = [0, 0, 0, 1, 1, 0, 0, 0, 0]
    parent_task_net = [0, 0, 0, 1, 1, None, None, 0, 0]
    network = {
        "P": parent_task_net,
        "T": task_net,
    }
    expected_network = {
        "P": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "T": [0, 0, 0, 1, 1, 0, 0, 0, 0],
    }
    tasks_by_parents = scheduling_finalize.collections.defaultdict(list)
    tasks_by_parents[parent["parent_uuid"]].append(parent)
    tasks_by_parents[task["parent_uuid"]].append(task)

    scheduling_finalize.calculate_group_tasks(
        tasks_by_parents, network, "preds", "succs"
    )
    adjust_task_relship_gap.assert_called_once_with(
        parent,
        parent_task_net,
        "preds",
        "succs",
    )
    assert network == expected_network
