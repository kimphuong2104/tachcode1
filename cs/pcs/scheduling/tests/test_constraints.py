#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest

from cs.pcs.scheduling import constraints
from cs.pcs.scheduling.constants import FNET, FNLT, MFO, MSO, SNET, SNLT


@pytest.mark.unit
@pytest.mark.parametrize(
    "task,task_net,expected_task_net",
    [
        (
            {"constraint_type": MSO, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 5, 7, 5, 7, None, None, None, None],
        ),
        (
            {"constraint_type": MSO, "constraint_date": 5, "position_fix": 1},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 5, 7, 5, 7, None, None, None, None],
        ),
        (
            {"constraint_type": MFO, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 4, 5, 4, 5, None, None, None, None],
        ),
        (
            {"constraint_type": SNET, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 5, 7, 5, 7, None, None, None, None],
        ),
        (
            {"constraint_type": SNLT, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 0, 1, 0, 1, None, None, None, None],
        ),
        (
            {"constraint_type": FNET, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 4, 5, 4, 5, None, None, None, None],
        ),
        (
            {"constraint_type": FNLT, "constraint_date": 5, "position_fix": 0},
            [1, 0, 1, 0, 1, None, None, None, None],
            [1, 0, 1, 0, 1, None, None, None, None],
        ),
    ],
)
def test_handle_fixed_constraints(task, task_net, expected_task_net):
    constraints.handle_fixed_constraints(task, task_net)  # changes task_net in place
    assert task_net == expected_task_net
