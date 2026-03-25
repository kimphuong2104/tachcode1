#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest

from cs.pcs.scheduling import scheduling_forward
from cs.pcs.scheduling.constants import AA, DR, EF, ES, ZZ


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "handle_fixed_constraints")
@mock.patch.object(scheduling_forward, "apply_predecessors")
def test_forward_pass_no_task(apply_predecessors, handle_fixed_constraints):
    task_data = [
        {},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]
    assert scheduling_forward.forward_pass(task_data, [], {}, {}, 1) == (set(), 0)
    apply_predecessors.assert_not_called()
    handle_fixed_constraints.assert_not_called()


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "handle_fixed_constraints")
@mock.patch.object(scheduling_forward, "apply_predecessors")
def test_forward_pass_no_predecessors(apply_predecessors, handle_fixed_constraints):
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "position_fix": "PF",
        "adopt_bottom_up_target": 1,
    }
    task_net = [
        1,
        2,
        -scheduling_forward.sys.maxsize,
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    task_data = [
        {"T": task},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]
    assert scheduling_forward.forward_pass(
        task_data, [task], {}, {"T": task_net}, {}
    ) == (
        set(),
        0,
    )  # DR + ES
    apply_predecessors.assert_not_called()
    handle_fixed_constraints.assert_called_once_with(task, task_net)


@pytest.mark.unit
@mock.patch.object(scheduling_forward.collections, "defaultdict")
@mock.patch.object(scheduling_forward, "handle_fixed_constraints")
@mock.patch.object(scheduling_forward, "apply_predecessors")
def test_forward_pass_predecessors(
    apply_predecessors, handle_fixed_constraints, defaultdict
):
    # task with predecessors - call apply_predecessor
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "position_fix": "PF",
        "adopt_bottom_up_target": 1,
    }
    task_net = [-1, -2, -99, None, None, None, None, None, None]
    task_data = [
        {"T": task},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]
    preds = ["foo"]
    assert scheduling_forward.forward_pass(
        task_data, [task], {"T": preds}, {"T": task_net}, {}
    ) == (
        set(),
        0,
    )
    apply_predecessors.assert_called_once_with(
        {"T": task_net},
        preds,
        False,  # finalize
        "T",
        "PF",
        False,  # is discarded
        {},  # non_discarded_chain_starts
        defaultdict.return_value,  # non_discarded_preds,
    )
    handle_fixed_constraints.assert_called_once_with(task, task_net)


@pytest.mark.unit
def test_apply_predecessors_no_preds():
    network = {"T": None}
    original_network = dict(network)
    assert (
        scheduling_forward.apply_predecessors(
            network,
            [],
            None,
            "T",
            0,
            None,
            None,
            None,
        )
        is None
    )
    assert network == original_network


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "get_value")
@mock.patch.object(scheduling_forward, "apply_relship_forward")
def test_apply_predecessors_discarded_and_pred(apply_relship_forward, get_value):
    # discarded task with one non discarded predecessor - start of chain
    task_discarded = True
    pred_discarded = False
    non_discarded_chain_starts = {}
    non_discarded_preds = {"T": set()}

    task_net = [None, None, 0, None, None, None, None, None, None]
    pred_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "foo", "bar", pred_discarded, "succ_discarded", None)
    assert (
        scheduling_forward.apply_predecessors(
            {"T": task_net, "PRED": pred_net},
            [relship],
            True,  # finalize
            "T",
            0,
            task_discarded,
            non_discarded_chain_starts,
            non_discarded_preds,
        )
        is None
    )

    apply_relship_forward.assert_called_once_with(
        pred_net,
        task_net,
        0,
        relship,
        True,
    )

    get_value.assert_called_once_with(pred_net, ZZ, EF)

    assert non_discarded_chain_starts == {
        ("PRED", "T"): [
            "PRED",
            1,  # pred.DR
            "foo",
            "bar",
            get_value.return_value,
        ]
    }
    assert non_discarded_preds == {"T": set([("PRED", "T")])}


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "get_value")
@mock.patch.object(scheduling_forward, "apply_relship_forward")
def test_apply_predecessors_discarded_and_discarded_pred(
    apply_relship_forward, get_value
):
    # discarded task with one discarded predecessor - middle of chain
    task_discarded = True
    pred_discarded = True
    non_discarded_chain_starts = {}
    non_discarded_preds = {"T": set(["foo"]), "PRED": set(["bar"])}

    task_net = [None, None, 0, None, None, None, None, None, None]
    pred_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "bam", "baz", pred_discarded, "succ_discarded", None)
    assert (
        scheduling_forward.apply_predecessors(
            {"T": task_net, "PRED": pred_net},
            [relship],
            True,  # finalize
            "T",
            0,
            task_discarded,
            non_discarded_chain_starts,
            non_discarded_preds,
        )
        is None
    )

    apply_relship_forward.assert_called_once_with(
        pred_net,
        task_net,
        0,
        relship,
        True,
    )

    get_value.assert_not_called()

    assert not non_discarded_chain_starts  # no changes
    assert non_discarded_preds == {"T": set(["foo", "bar"]), "PRED": set(["bar"])}


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "get_value")
@mock.patch.object(scheduling_forward, "apply_relship_forward")
def test_apply_predecessors_not_discarded_and_not_discarded_pred(
    apply_relship_forward, get_value
):
    # non-discarded task with one non-discarded predecessor - normal case
    task_discarded = False
    pred_discarded = False
    non_discarded_chain_starts = {}
    non_discarded_preds = {}

    task_net = [None, None, 0, None, None, None, None, None, None]
    pred_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "bam", "baz", pred_discarded, "succ_discarded", None)
    assert (
        scheduling_forward.apply_predecessors(
            {"T": task_net, "PRED": pred_net},
            [relship],
            True,  # finalize
            "T",
            0,
            task_discarded,
            non_discarded_chain_starts,
            non_discarded_preds,
        )
        is None
    )

    apply_relship_forward.assert_called_once_with(
        pred_net,
        task_net,
        0,
        relship,
        True,
    )

    get_value.assert_not_called()

    assert not non_discarded_chain_starts  # no changes
    assert not non_discarded_preds  # no changes


@pytest.mark.unit
@mock.patch.object(scheduling_forward, "get_value")
@mock.patch.object(scheduling_forward, "apply_relship_forward")
def test_apply_predecessors_not_discarded_and_discarded_pred(
    apply_relship_forward, get_value
):
    # non-discarded task with one discarded predecessor - end of chain apply virtual relship
    task_discarded = False
    pred_discarded = True
    non_discarded_chain_starts = {"START": ("foo_uuid", 111, "XX", "foo_gap", 333)}
    non_discarded_preds = {"PRED": ["START"]}

    task_net = [None, None, 0, None, None, None, None, None, None]
    pred_net = [1, None, None, None, None, None, 2, None, None]
    assert (
        scheduling_forward.apply_predecessors(
            {"T": task_net, "PRED": pred_net},
            [("PRED", "SUCC", "YY", "baz", pred_discarded, "succ_discarded", None)],
            True,  # finalize
            "T",
            0,
            task_discarded,
            non_discarded_chain_starts,
            non_discarded_preds,
        )
        is None
    )

    apply_relship_forward.assert_called_once_with(
        {
            DR: 111,
            ES: 222,
            EF: 333,
            AA: None,
            ZZ: None,
        },
        task_net,
        0,
        ("foo_uuid", None, "XY", "foo_gap", None, None, None),
        True,  # finalize
    )

    get_value.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    "tasks,network,latest_finish,expected",
    [
        # no tasks, project end not given -> keep defaults
        (
            [],
            {},
            None,
            (-scheduling_forward.sys.maxsize, -scheduling_forward.sys.maxsize),
        ),
        # no tasks, project end given -> use project end
        ([], {}, -1, (-1, -1)),
        (
            [
                {"cdb_object_id": "A", "discarded": 1},
                {"cdb_object_id": "B", "discarded": 0},
            ],
            {"A": {EF: 22}, "B": {EF: 11}},
            None,
            (11, 22),
        ),
        (
            [
                {"cdb_object_id": "A", "discarded": 1},
                {"cdb_object_id": "B", "discarded": 0},
            ],
            {"A": {EF: 22}, "B": {EF: 11}},
            16,
            (16, 22),
        ),
        (
            [
                {"cdb_object_id": "A", "discarded": 1},
                {"cdb_object_id": "B", "discarded": 0},
            ],
            {"A": {EF: 22}, "B": {EF: 11}},
            24,
            (24, 24),
        ),
    ],
)
def test_get_max_ef(tasks, network, latest_finish, expected):
    assert scheduling_forward.get_max_ef(tasks, network, latest_finish) == expected
