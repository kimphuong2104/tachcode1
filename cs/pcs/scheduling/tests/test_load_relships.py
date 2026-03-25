#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock

from cs.pcs.scheduling import load_relships


@mock.patch.object(load_relships, "load")
def test_load_relships(load):
    r1 = {
        "minimal_gap": 11,
        "rel_type": "r1",
        "pred_task_oid": "p1",
        "succ_task_oid": "s1",
        "violation": 0,
    }
    r2 = {
        "minimal_gap": 22,
        "rel_type": "r2",
        "pred_task_oid": "p2",
        "succ_task_oid": "s2",
        "violation": 1,
    }
    r3 = {
        "minimal_gap": 33,
        "rel_type": "r3",
        "pred_task_oid": "p3",
        "succ_task_oid": "s1",
        "violation": 0,
    }
    load.return_value = [r1, r2, r3]

    result = load_relships.load_relships({"S3": {("p3", 0)}}, "foo", {"p3", "s2"})
    expected = (
        {
            "p3": [("S3", "p3", "AA", 0, False, True, True)],
            "s1": [
                ("p1", "s1", "r1", 11, False, False, False),
                ("p3", "s1", "r3", 33, True, False, False),
            ],
            "s2": [("p2", "s2", "r2", 22, False, True, False)],
        },
        {
            "p1": [("p1", "s1", "r1", 11, False, False, False)],
            "p2": [("p2", "s2", "r2", 22, False, True, False)],
            "p3": [
                ("p3", "s1", "r3", 33, True, False, False),
                ("p3", "S3", "EE", 0, True, False, True),
            ],
        },
        [
            ("p1", "s1", "r1", 11, False, False, 0),
            ("p2", "s2", "r2", 22, False, True, 1),
            ("p3", "s1", "r3", 33, True, False, 0),
        ],
        {"s1": ["p1", "p3"], "s2": ["p2"], "p3": ["S3"]},
        {"s1": ["p1", "p3"], "s2": ["p2"], "S3": ["p3"]},
    )
    assert result == expected
