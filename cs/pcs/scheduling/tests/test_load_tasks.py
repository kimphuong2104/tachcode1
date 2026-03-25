#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
from cdb import testcase

from cs.pcs.scheduling import load_tasks


def setup_module():
    testcase.run_level_setup()


@mock.patch.object(load_tasks, "convert_task_dates")
@mock.patch.object(load_tasks, "DATES_TASK", ({"start_time_fcast"}, {"milestone"}))
@mock.patch.object(load_tasks, "FLOATS", [])
@mock.patch.object(load_tasks, "load")
def test_load_tasks(load, convert_task_dates):
    "[load_tasks]"
    normal = {
        "cdb_object_id": "normal",
        "status": "not discarded",
        "start_time_fcast": 100,
        "constraint_date": None,
        "milestone": None,
        "start_is_early": "is_early",
        "end_is_early": None,
        "parent_uuid": None,
        "is_group": 0,
        "days_fcast": 10,
        "adopt_bottom_up_target": 0,
    }
    constrained = {
        "cdb_object_id": "constrained",
        "status": "not discarded",
        "start_time_fcast": None,
        "constraint_date": 200,
        "milestone": None,
        "start_is_early": "is_early",
        "end_is_early": None,
        "parent_uuid": "normal",
        "is_group": 0,
        "days_fcast": 5,
        "adopt_bottom_up_target": 0,
    }
    milestone = {
        "cdb_object_id": "milestone",
        "status": "not discarded",
        "start_time_fcast": 300,
        "constraint_date": None,
        "milestone": 1,
        "start_is_early": "is_early",
        "end_is_early": None,
        "parent_uuid": "normal",
        "is_group": 0,
        "days_fcast": 1,
        "adopt_bottom_up_target": 0,
    }
    discarded = {
        "cdb_object_id": "discarded",
        "status": 180,
        "start_time_fcast": -4,
        "constraint_date": None,
        "milestone": None,
        "start_is_early": "is_early",
        "end_is_early": None,
        "parent_uuid": "normal",
        "is_group": 0,
        "days_fcast": 4,
        "adopt_bottom_up_target": 0,
    }
    fixed_group = {
        "cdb_object_id": "fixed_group",
        "status": 123,
        "start_time_fcast": 111,
        "constraint_date": None,
        "milestone": None,
        "start_is_early": "eas",
        "end_is_early": "eaf",
        "parent_uuid": "normal",
        "fixed": 1,
        "days_fcast": 333,
        "adopt_bottom_up_target": 1,
    }
    group = {
        "cdb_object_id": "group",
        "status": 123,
        "start_time_fcast": 222,
        "constraint_date": None,
        "milestone": None,
        "start_is_early": "eas",
        "end_is_early": "eaf",
        "parent_uuid": "normal",
        "fixed": 0,
        "days_fcast": 444,
        "adopt_bottom_up_target": 1,
    }
    load.return_value = [normal, constrained, milestone, discarded, fixed_group, group]
    result = load_tasks.load_tasks("foo", "bar")
    assert result == (
        {x["cdb_object_id"]: x for x in load.return_value},
        {"discarded"},
        {
            "milestone": {
                "constraint_date": None,
                "days_fcast": 1,
                "end_is_early": None,
                "milestone": 1,
                "start_is_early": "is_early",
                "start_time_fcast": 300,
            },
            "normal": {
                "constraint_date": None,
                "days_fcast": 10,
                "end_is_early": None,
                "milestone": None,
                "start_is_early": "is_early",
                "start_time_fcast": 100,
            },
            "discarded": {
                "constraint_date": None,
                "days_fcast": 4,
                "end_is_early": None,
                "milestone": None,
                "start_is_early": "is_early",
                "start_time_fcast": -4,
            },
            "constrained": {
                "constraint_date": 200,
                "days_fcast": 5,
                "end_is_early": None,
                "milestone": None,
                "start_is_early": "is_early",
                "start_time_fcast": None,
            },
            "fixed_group": {
                "constraint_date": None,
                "days_fcast": 333,
                "end_is_early": "eaf",
                "milestone": None,
                "start_is_early": "eas",
                "start_time_fcast": 111,
            },
            "group": {
                "constraint_date": None,
                "days_fcast": 444,
                "end_is_early": "eaf",
                "milestone": None,
                "start_is_early": "eas",
                "start_time_fcast": 222,
            },
        },
        {},
        {
            "normal": {"constrained", "milestone", "fixed_group", "group"},
        },
        {
            "": {("normal", 0)},
            "normal": {
                ("constrained", 0),
                ("milestone", 0),
                ("fixed_group", 1),
                ("group", 1),
                ("discarded", 0),
            },
        },
    )
    convert_task_dates.assert_called_once_with(load.return_value, "bar")
