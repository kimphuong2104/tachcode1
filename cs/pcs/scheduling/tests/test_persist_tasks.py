#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import persist_tasks


def setup_module():
    testcase.run_level_setup()


@mock.patch.object(persist_tasks, "write_task_changes_to_db")
def test_persist_tasks(write):
    "[persist_tasks] makes write calls"

    def _get_changes(_, __, ___, task):
        return {
            "target": (
                {"f1": 1, "f2": 1},
                True,
            ),
            "non-target": (
                {"n1": 2, "f2": 2},
                False,
            ),
            "none": ({}, False),
        }[task["cdb_object_id"]]

    tasks = [
        {
            "cdb_object_id": "target",
            "task_id": "Ttarget",
            "discarded": 1,
        },
        {
            "cdb_object_id": "non-target",
            "task_id": "Tnon-target",
            "discarded": 0,
        },
        {
            "cdb_object_id": "none",
            "task_id": "Tnone",
            "discarded": 0,
        },
    ]
    network = {
        # target is discarded, project ignores its AA and ZZ dates
        "target": ["DR", "ES", "EF", "LS", "LF", 1, 6, "FF", "TF"],
        "non-target": ["DR", "ES", "EF", "LS", "LF", 2, 4, "FF", "TF"],
        "none": ["DR", "ES", "EF", "LS", "LF", 3, 5, "FF", "TF"],
    }
    project = {
        "cdb_project_id": "Pfoo",
        "start_time_fcast": 5,
    }
    with mock.patch.object(persist_tasks, "_get_task_changes") as _get_task_changes:
        _get_task_changes.side_effect = _get_changes
        result = persist_tasks.persist_tasks(tasks, network, project, "C", "O")

    assert result == ({"Ttarget", "Tnon-target"}, {"Ttarget"}, 2, 5)
    assert _get_task_changes.call_count == len(tasks)
    write.assert_called_once_with(
        "Pfoo",
        [
            (
                {"Ttarget", "Tnon-target"},
                {
                    "f1": {"Ttarget": 1},
                    "f2": {"Ttarget": 1, "Tnon-target": 2},
                    "n1": {"Tnon-target": 2},
                },
            )
        ],
    )


@mock.patch.object(
    persist_tasks,
    "TASK_FIELDS",
    [
        (0, "unchanged", False),
        (1, "unchanged offset", True),
    ],
)
@mock.patch.object(persist_tasks.logging, "exception")
def test_get_task_changes_raises(log_exc):
    "[_get_task_changes] network offset value None -> TypeError"
    network = {"uuid": [0, None]}
    original_dates = {"uuid": {"unchanged": 0, "unchanged offset": 3}}
    task = {
        "cdb_object_id": "uuid",
        "milestone": 0,
        "start_is_early": 0,
        "fixed": 0,
        "unchanged": 0,
    }
    with pytest.raises(TypeError) as error:
        persist_tasks._get_task_changes(network, original_dates, None, task)

    assert str(error.value) == "empty offset value in network"
    log_exc.assert_called_once_with(
        "empty offset value in network [%s]:\n\t%s = %s",
        1,
        "uuid",
        [0, None],
    )


@pytest.mark.parametrize(
    "fixed,milestone,is_early,expected,conversions",
    [
        (
            0,
            0,
            0,
            {
                "changed": 11,
                "changed but fixed": 22,
                "changed offset": "'44'",
                "changed but fixed offset": "'55'",
                "start_is_early": 0,
            },
            [
                3,
                44,
                55,
            ],
        ),
        (
            0,
            1,
            0,
            {
                "changed": 11,
                "changed but fixed": 22,
                "changed offset": "'44'",
                "changed but fixed offset": "'55'",
                "start_is_early": 0,
            },
            [
                3,
                44,
                55,
            ],
        ),
        (
            0,
            1,
            1,
            {
                "changed": 11,
                "changed but fixed": 22,
                "changed offset": "'44'",
                "changed but fixed offset": "'55'",
                "start_is_early": 0,
            },
            [
                3,
                44,
                55,
            ],
        ),
        (
            1,
            0,
            0,
            {
                "changed": 11,
                "changed offset": "'44'",
            },
            [
                3,
                44,
            ],
        ),
    ],
)
def test_get_task_changes(fixed, milestone, is_early, expected, conversions):
    "[_get_task_changes] calculates diff"
    network = {
        "uuid": [0, 11, 22, 3, 44, 55, 1, 0],
    }
    original_data = {
        "uuid": {
            "unchanged offset": 3,
            "changed offset": 4,
            "changed but fixed offset": 5,
            "unchanged": 0,
            "changed": 1,
            "changed but fixed": 2,
            "start_is_early": 1,
            "end_is_early": 0,
        }
    }
    network2day = mock.Mock(side_effect=lambda a: a)
    network2duration = mock.Mock(side_effect=lambda a: a)

    task = {
        "cdb_object_id": "uuid",
        "milestone": milestone,
        "start_is_early": is_early,
        "end_is_early": is_early,
        "fixed": fixed,
        "unchanged": 0,
        "changed": 1,
        "changed but fixed": 2,
    }
    with (
        mock.patch.object(
            persist_tasks,
            "TASK_FIELDS",
            [
                (0, "unchanged", False),
                (1, "changed", False),
                (2, "changed but fixed", False),
                (3, "unchanged offset", True),
                (4, "changed offset", True),
                (5, "changed but fixed offset", True),
            ],
        ),
        mock.patch.object(
            persist_tasks,
            "FIXED_FIELDS",
            ["changed but fixed", "changed but fixed offset"],
        ),
        mock.patch.object(persist_tasks, "START_OFFSETS", [4]),
        mock.patch.object(persist_tasks, "POST_PROCESS", ["changed"]),
        mock.patch.object(
            persist_tasks.sqlapi, "SQLdate_literal", side_effect=lambda x: f"'{x}'"
        ),
        mock.patch.object(persist_tasks, "network2duration", network2duration),
    ):
        result = persist_tasks._get_task_changes(
            network, original_data, network2day, task
        )
    assert result == (expected, True)

    assert network2day.call_count == len(conversions)
    network2day.assert_has_calls([mock.call(conversion) for conversion in conversions])
