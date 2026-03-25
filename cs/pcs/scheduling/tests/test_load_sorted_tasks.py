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

from cs.pcs.scheduling import load_sorted_tasks


def setup_module():
    testcase.run_level_setup()


@mock.patch.object(load_sorted_tasks, "_toposort")
def test_get_sorted_task_uuids(_toposort):
    "[get_sorted_task_uuids]"
    by_uuid = {
        "dos": {"discarded": 1},
        "uno": {"discarded": 0},
    }
    sorted_uuids = ["uno", "dos"]
    result = load_sorted_tasks.get_sorted_task_uuids(by_uuid, "p_fwd", "p_bck")
    assert result == (_toposort.return_value, _toposort.return_value)
    assert _toposort.call_count == 2
    _toposort.assert_has_calls(
        [
            mock.call(sorted_uuids, "p_fwd"),
            mock.call(sorted_uuids, "p_bck"),
        ]
    )


def test_toposort_raises():
    "[_toposort] raises if task graph is cyclic"
    with pytest.raises(load_sorted_tasks.util.ErrorMessage) as error:
        load_sorted_tasks._toposort(
            ["A", "B"],
            {
                "A": ["B"],
                "B": ["A"],
            },
        )

    assert str(error.value) == (
        "Die Aufgaben enthalten eine zirkuläre Abhängigkeit. Bitte informieren Sie Ihren Administrator."
    )


def test_toposort():
    "[_toposort]"
    result = load_sorted_tasks._toposort(
        ["ROOT", "LEAF", "A", "B"],
        {
            "LEAF": ["A", "B"],
            "A": ["ROOT"],
            "B": ["ROOT"],
        },
    )
    # we do not care about the order of A and B
    x = (result[0], set(result[1:-1]), result[-1])
    assert x == ("ROOT", {"A", "B"}, "LEAF")
