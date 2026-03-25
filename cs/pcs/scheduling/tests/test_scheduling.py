#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import sys

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import scheduling


def setup_module():
    testcase.run_level_setup()


@pytest.mark.unit
@pytest.mark.parametrize(
    "network,changed_uuids,expected",
    [
        # case 1: no changed_uuids
        ([None], [], False),
        # case 2: changes match known changes
        ({"A": "old", "C": "whatever"}, {"A"}, False),
        # case 3: new changes
        ({"A": "new", "C": "whatever"}, {"A"}, True),
    ],
)
def test__new_changes(network, changed_uuids, expected):
    known_changes = {"A": "old", "B": "old"}
    result = scheduling._new_changes(known_changes, network, changed_uuids)
    assert result == expected


@pytest.mark.unit
@mock.patch.object(scheduling, "calculate_floats")
@mock.patch.object(scheduling, "finalize")
@mock.patch.object(scheduling, "backward_pass")
@mock.patch.object(scheduling, "get_max_ef", return_value=["f1", "f2"])
@mock.patch.object(scheduling, "forward_pass", return_value=["", "f4"])
@mock.patch.object(scheduling, "init_network")
def test_calculate_network(
    init_network,
    forward_pass,
    get_max_ef,
    backward_pass,
    finalize,
    calculate_floats,
):
    # just test, that the inner methods are called with the correct parameters
    scheduling.calculate_network(
        "task_data",
        "tasks_fwd",
        "tasks_bck",
        ("preds", "succs", "persistent", "p_fwd", "p_bck"),
        "latest_finish",
    )
    init_network.assert_called_once_with("tasks_fwd")
    forward_pass.assert_called_once_with(
        "task_data",
        "tasks_fwd",
        "preds",
        init_network.return_value,
    )
    get_max_ef.assert_called_once_with(
        "tasks_fwd", init_network.return_value, "latest_finish"
    )
    backward_pass.assert_called_once_with(
        "task_data", "tasks_bck", "succs", init_network.return_value, "f1", "f2"
    )
    finalize.assert_called_once_with(
        "tasks_fwd", "preds", "succs", init_network.return_value
    )
    calculate_floats.assert_called_once_with(
        "tasks_bck", "succs", init_network.return_value, "f1"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "tasks,expected_network",
    [
        # case 1: no tasks - empty network
        ([], {}),
        # case 2: fixed task (with days_fcast)
        (
            [
                {
                    "cdb_object_id": "T",
                    "days_fcast": 1,
                    "start_time_fcast": 2,
                    "end_time_fcast": 3,
                    "fixed": True,
                    "milestone": False,
                    "start_is_early": 1,
                    "end_is_early": 0,
                }
            ],
            {"T": [1, 2, 3, 2, 3, 2, 3, 0, 0]},
        ),
        # case 3: not fixed task (without days_fcast)
        (
            [
                {
                    "cdb_object_id": "T",
                    "days_fcast": None,
                    "start_time_fcast": 2,
                    "end_time_fcast": 3,
                    "fixed": False,
                    "milestone": False,
                    "start_is_early": 0,
                    "end_is_early": 1,
                }
            ],
            {
                "T": [
                    0,
                    -sys.maxsize,
                    -sys.maxsize,
                    sys.maxsize,
                    sys.maxsize,
                    None,
                    None,
                    0,
                    0,
                ]
            },
        ),
    ],
)
def test_init_network(tasks, expected_network):
    assert scheduling.init_network(tasks) == expected_network
