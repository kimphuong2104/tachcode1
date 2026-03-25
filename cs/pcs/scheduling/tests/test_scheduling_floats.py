#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest

from cs.pcs.scheduling import scheduling_floats


@pytest.mark.unit
@mock.patch.object(scheduling_floats, "calc_max_end", return_value=2)
@mock.patch.object(scheduling_floats.collections, "defaultdict")
def test_calculate_floats_with_successor(defaultdict, calc_max_end):
    # one non-discarded task with one successor
    task = {"cdb_object_id": "T", "discarded": False, "position_fix": True}
    task_net = [None, 0, None, 2, None, None, 1, None, None]
    network = {"T": task_net}
    scheduling_floats.calculate_floats([task], {"T": "foo"}, network, "bar")

    calc_max_end.assert_called_once_with(
        network,
        "T",
        True,
        "foo",  # successor
        False,  # is_discarded
        "bar",  # max_ef
        defaultdict.return_value,
        {},
    )
    assert task_net == [None, 0, None, 2, None, None, 1, 1, 2]
    defaultdict.assert_called_once_with(set)


@pytest.mark.unit
@mock.patch.object(scheduling_floats, "calc_max_end")
@mock.patch.object(scheduling_floats.collections, "defaultdict")
def test_calculate_floats_without_successor(defaultdict, calc_max_end):
    # one discarded task without successor
    task = {"cdb_object_id": "T", "discarded": True}
    task_net = [None, 0, None, 2, None, None, 1, None, None]
    network = {"T": task_net}
    scheduling_floats.calculate_floats([task], {}, network, "foo")

    assert task_net == [None, 0, None, 2, None, None, 1, 2, 2]
    defaultdict.assert_called_once_with(set)
    calc_max_end.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    "rel_type,gap,pred_DR,pos_fix,succ_ES,succ_EF,expected",
    [
        ("EA", 0, 1, True, 3, 9, 3),
        ("AA", 0, 1, True, 3, 9, 3),
        ("EE", 0, 1, True, 3, 9, 8),
        ("AE", 0, 1, True, 3, 9, 11),
    ],
)
def test__calc_max_end(rel_type, gap, pred_DR, pos_fix, succ_ES, succ_EF, expected):
    assert (
        scheduling_floats._calc_max_end(
            rel_type,
            gap,
            pred_DR,
            pos_fix,
            succ_ES,
            succ_EF,
        )
        == expected
    )


@pytest.mark.unit
def test_calc_max_end_no_succ():
    # no succesors - return max_ef
    assert (
        scheduling_floats.calc_max_end({"T": None}, "T", True, [], False, "foo", {}, {})
        == "foo"
    )


@pytest.mark.unit
@mock.patch.object(scheduling_floats, "_calc_max_end", return_value=0)
def test_calc_max_end_not_discarded_succ_not_discarded(_calc_max_end):
    # non-discrded task with non discarded successor - end of chain
    non_discarded_chain_ends = {}
    non_discarded_succs = {}
    assert (
        scheduling_floats.calc_max_end(
            {
                "T": [1, None, None, None, None, 111, 222, None, None],
                "SUCC": [1, None, None, None, None, 333, 444, None, None],
            },
            "T",
            True,
            [("PRED", "SUCC", "foo_rel_type", "foo_gap", False, False, None)],
            False,
            1,
            non_discarded_succs,
            non_discarded_chain_ends,
        )
        == 0
    )

    _calc_max_end.assert_called_once_with("foo_rel_type", "foo_gap", 1, True, 333, 444)
    # unchanged
    assert not non_discarded_chain_ends
    assert not non_discarded_succs


@pytest.mark.unit
@mock.patch.object(scheduling_floats, "_calc_max_end", return_value=0)
def test_calc_max_end_discarded_succ_not_discarded(_calc_max_end):
    # discarded task with non discarded successor - end of chain
    non_discarded_chain_ends = {}
    non_discarded_succs = {"T": set([])}
    assert (
        scheduling_floats.calc_max_end(
            {
                "T": [1, None, None, None, None, 111, 222, None, None],
                "SUCC": [1, None, None, None, None, 333, 444, None, None],
            },
            "T",
            True,
            [("PRED", "SUCC", "foo_rel_type", "foo_gap", False, False, None)],
            True,
            1,
            non_discarded_succs,
            non_discarded_chain_ends,
        )
        == 0
    )

    _calc_max_end.assert_called_once_with("foo_rel_type", "foo_gap", 1, True, 333, 444)
    # addd one ending point
    assert non_discarded_chain_ends == {("T", "SUCC"): (333, 444)}
    assert non_discarded_succs == {"T": set([("T", "SUCC")])}


@pytest.mark.unit
@mock.patch.object(scheduling_floats, "_calc_max_end", return_value=0)
def test_calc_max_end_discarded_succ_discarded(_calc_max_end):
    # discarded task with discarded successor - middle of chain
    non_discarded_chain_ends = {}
    non_discarded_succs = {"T": set([]), "SUCC": set(["bar"])}
    assert (
        scheduling_floats.calc_max_end(
            {
                "T": [1, None, None, None, None, 111, 222, None, None],
                "SUCC": [1, None, None, None, None, 333, 444, None, None],
            },
            "T",
            True,
            [("PRED", "SUCC", "foo_rel_type", "foo_gap", True, True, None)],
            True,
            1,
            non_discarded_succs,
            non_discarded_chain_ends,
        )
        == 0
    )

    _calc_max_end.assert_called_once_with("foo_rel_type", "foo_gap", 1, True, 333, 444)
    # added successors ending point
    assert not non_discarded_chain_ends
    assert non_discarded_succs == {"T": set(["bar"]), "SUCC": set(["bar"])}
