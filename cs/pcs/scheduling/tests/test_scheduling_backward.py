#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest

from cs.pcs.scheduling import scheduling_backward
from cs.pcs.scheduling.constants import DR, LF, LS


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "handle_fixed_constraints")
@mock.patch.object(scheduling_backward, "apply_successors")
def test_backward_pass_no_successors(apply_successors, handle_fixed_constraints):
    # task without successors - LS = max_ef - DR; LF = max_ef
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "position_fix": "PF",
        "adopt_bottom_up_target": 1,
    }
    task_net = [1, None, None, None, None, None, None, None, None]
    task_data = [
        {"T": task},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]

    scheduling_backward.backward_pass(task_data, [task], {}, {"T": task_net}, 1, 1)
    assert task_net == [1, None, None, 0, 1, None, None, None, None]
    apply_successors.assert_not_called()
    handle_fixed_constraints.assert_called_once_with(task, task_net)


@pytest.mark.unit
@mock.patch.object(scheduling_backward.collections, "defaultdict")
@mock.patch.object(scheduling_backward, "handle_fixed_constraints")
@mock.patch.object(scheduling_backward, "apply_successors")
def test_backward_pass_successors(
    apply_successors, handle_fixed_constraints, defaultdict
):
    # task with successors - call apply_succecessor
    task = {
        "cdb_object_id": "T",
        "discarded": False,
        "position_fix": "PF",
        "adopt_bottom_up_target": 1,
    }
    task_net = [1, None, None, None, None, None, None, None, None]
    succs = ["foo"]
    task_data = [
        {"T": task},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]
    scheduling_backward.backward_pass(
        task_data, [task], {"T": succs}, {"T": task_net}, 1, 1
    )

    assert task_net == [1, None, None, 0, 1, None, None, None, None]
    apply_successors.assert_called_once_with(
        {"T": task_net},
        "T",
        "PF",
        False,  # is discarded
        succs,
        defaultdict.return_value,  # non_discarded_succs,
        {},  # non_discarded_chain_ends
        1,  # max_ef
    )
    handle_fixed_constraints.assert_called_once_with(task, task_net)


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "handle_fixed_constraints")
@mock.patch.object(scheduling_backward, "apply_successors")
def test_backward_pass_no_successors_discarded(
    apply_successors, handle_fixed_constraints
):
    # discarded task without successors - construct dummy endpoint
    task = {
        "cdb_object_id": "T",
        "discarded": True,
        "position_fix": "PF",
        "adopt_bottom_up_target": 1,
    }
    task_net = [1, None, None, None, None, None, None, None, None]
    task_data = [
        {"T": task},
        "unused",
        "unused",
        "P",
        "C",
        "AC",
    ]
    scheduling_backward.backward_pass(task_data, [task], {}, {"T": task_net}, 1, 1)

    assert task_net == [1, None, None, 0, 1, None, None, None, None]
    apply_successors.assert_not_called()
    handle_fixed_constraints.assert_called_once_with(task, task_net)


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "apply_relship_backward")
def test_apply_successors_discarded_and_succ(apply_relship_backward):
    # discarded task with one non discarded successor - end of chain
    task_discarded = True
    succ_discarded = False
    non_discarded_chain_ends = {}
    non_discarded_succs = {"T": set()}

    task_net = [None, None, 0, None, None, None, None, None, None]
    succ_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "foo", "bar", "pred_discarded", succ_discarded, None)

    scheduling_backward.apply_successors(
        {"T": task_net, "SUCC": succ_net},
        "T",
        "PF",
        task_discarded,
        [relship],
        non_discarded_succs,
        non_discarded_chain_ends,
        1,
    )

    apply_relship_backward.assert_called_once_with(
        task_net,
        succ_net,
        "PF",
        relship,
        True,
    )

    assert non_discarded_chain_ends == {
        ("T", "SUCC"): ["SUCC", 1, "foo", "bar", None]  # succ.DR
    }
    assert non_discarded_succs == {"T": set([("T", "SUCC")])}


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "apply_relship_backward")
def test_apply_successors_discarded_and_discarded_succ(apply_relship_backward):
    # discarded task with one discarded succecessor - middle of chain
    task_discarded = True
    succ_discarded = True
    non_discarded_chain_ends = {}
    non_discarded_succs = {"T": set(["foo"]), "SUCC": set(["bar"])}

    task_net = [None, None, 0, None, None, None, None, None, None]
    succ_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "bam", "baz", "pred_discarded", succ_discarded, None)

    scheduling_backward.apply_successors(
        {"T": task_net, "SUCC": succ_net},
        "T",
        "PF",
        task_discarded,
        [relship],
        non_discarded_succs,
        non_discarded_chain_ends,
        1,
    )

    apply_relship_backward.assert_called_once_with(
        task_net,
        succ_net,
        "PF",
        relship,
        True,
    )

    assert not non_discarded_chain_ends  # no changes
    assert non_discarded_succs == {"T": set(["foo", "bar"]), "SUCC": set(["bar"])}


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "apply_relship_backward")
def test_apply_successors_not_discarded_and_not_discarded_succ(apply_relship_backward):
    # non-discarded task with one non-discarded succecessor - normal case
    task_discarded = False
    succ_discarded = False
    non_discarded_chain_ends = {}
    non_discarded_succs = {}

    task_net = [None, None, 0, None, None, None, None, None, None]
    succ_net = [1, None, None, None, None, None, 2, None, None]
    relship = ("PRED", "SUCC", "bam", "baz", "pred_discarded", succ_discarded, None)

    scheduling_backward.apply_successors(
        {"T": task_net, "SUCC": succ_net},
        "T",
        "PF",
        task_discarded,
        [relship],
        non_discarded_succs,
        non_discarded_chain_ends,
        1,
    )

    apply_relship_backward.assert_called_once_with(
        task_net,
        succ_net,
        "PF",
        relship,
        False,
    )

    assert not non_discarded_chain_ends  # no changes
    assert not non_discarded_succs  # no changes


@pytest.mark.unit
@mock.patch.object(scheduling_backward, "apply_relship_backward")
def test_apply_successors_not_discarded_and_discarded_succ(apply_relship_backward):
    # non-discarded task with one discarded succecessor - end of chain apply virtual relship
    task_discarded = False
    succ_discarded = True
    non_discarded_chain_ends = {"END": ("foo_uuid", 111, "YY", "foo_gap", 222)}
    non_discarded_succs = {"SUCC": ["END"]}

    task_net = [None, None, None, 0, None, None, None, None, None]
    succ_net = [1, None, None, None, None, None, 2, None, None]

    scheduling_backward.apply_successors(
        {"T": task_net, "SUCC": succ_net},
        "T",
        "PF",
        task_discarded,
        [("PRED", "SUCC", "XX", "baz", "pred_discarded", succ_discarded, None)],
        non_discarded_succs,
        non_discarded_chain_ends,
        1,
    )

    apply_relship_backward.assert_called_once_with(
        task_net,
        {
            DR: 111,
            LS: 222,
            LF: 333,
        },
        "PF",
        ("foo_uuid", None, "XY", "baz", None, None, None),
        task_discarded,
    )
