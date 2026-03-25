#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest
from cdb import testcase

from cs.pcs import scheduling


def setup_module():
    testcase.run_level_setup()


@pytest.mark.parametrize(
    "project",
    [
        ({"fixed": 0}),
        ({"fixed": 1, "end_time_fcast": "end"}),
    ],
)
def test_schedule(project):
    "[schedule]"
    with (
        mock.patch.object(scheduling, "persist_changes", return_value=["C1", "C2"]),
        mock.patch.object(scheduling, "calculate_network", return_value="net"),
        mock.patch.object(scheduling.load_relships, "load_relships"),
        mock.patch.object(
            scheduling,
            "get_sorted_task_uuids",
            return_value=[
                {"F1": "f1"},
                {"B1": "b1"},
            ],
        ),
        mock.patch.object(
            scheduling.load_project, "load_project", return_value=[project, "cal"]
        ),
        mock.patch.object(
            scheduling.load_tasks,
            "load_tasks",
            return_value=[
                {
                    "F1": "task_F1",
                    "B1": "task_B1",
                },
                2,
                3,
                4,
                5,
                6,
            ],
        ),
        mock.patch.object(scheduling, "pretty_log"),
    ):
        result = scheduling.schedule("foo")
    assert result == ("C1", "C2", "cal", "net")
