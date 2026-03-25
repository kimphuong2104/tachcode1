#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest
from collections import defaultdict

import mock
import pytest

from cs.pcs.projects.tasks_efforts import aggregation
from cs.pcs.projects.tasks_efforts.aggregation import add_efforts


@pytest.mark.unit
class TasksEfforts(unittest.TestCase):
    @mock.patch.object(aggregation, "norm_val", return_value="foo_norm_val")
    def test__aggregate_from_child(self, norm_val):
        """Test _aggregate_child"""

        mock_sub = {
            "task_id": "foo",
            "status": "not 180",  # status not ignored for any attr in ATTRIBUTES
            "percent_complet": 1,
            "effort_fcast": 1,
            "effort_fcast_d": None,
            "effort_fcast_a": None,
            "start_time_fcast": None,
            "end_time_fcast": None,
            "start_time_act": None,
            "end_time_act": None,
            "effort_act": None,
        }

        sub_dict = {
            # end_time_act not present, so fallback to default is used
            "start_time_plan": "sub_start_time_plan",
            "end_time_plan": "sub_end_time_plan",
            "start_time_act": "sub_start_time_act",
            "effort_act": "sub_effort_act",
            "effort_fcast_d": "sub_effort_fcast_d",
            "effort_fcast_a": "sub_effort_fcast_a",
            # effort_fcast and percent_complet, so fallback to sub's values is used
        }

        value_dict = {
            "foo": sub_dict,
            "bar": {  # parent_id
                "start_time_act": "val_start_time_act",
                "end_time_act": "val_end_time_act",
                "effort_plan": "val_effort_plan",
                "effort_fcast": "val_effort_fcast",
                "effort_act": "val_effort_act",
                "effort_fcast_d": "val_effort_fcast_d",
                "effort_fcast_a": "val_effort_fcast_a",
            },
        }

        parent = {
            "is_group": 1,
            "start_time_plan": "parent",
            "end_time_plan": "parent",
            "start_time_act": "parent",
            "end_time_act": "parent",
            "effort_plan": "parent",
            "effort_fcast": "parent",
            "effort_act": "parent",
            "effort_fcast_d": "parent",
            "effort_fcast_a": "parent",
            "auto_update_time": False,  # only case, where parent condition can fail
            "auto_update_effort": False,  # only case, where parent condition can fail
        }
        self.maxDiff = None

        aggregation._aggregate_from_child(value_dict, parent, "bar", mock_sub)

        self.assertDictEqual(
            value_dict,
            {
                # sub_dict unchanged
                "foo": {
                    "effort_act": "sub_effort_act",
                    "effort_fcast_a": "sub_effort_fcast_a",
                    "effort_fcast_d": "sub_effort_fcast_d",
                    "end_time_plan": "sub_end_time_plan",
                    "start_time_act": "sub_start_time_act",
                    "start_time_plan": "sub_start_time_plan",
                },
                "bar": {
                    "effort_act": "foo_norm_valfoo_norm_val",  # result of add
                    "effort_fcast": "foo_norm_val",  # set to parent's value
                    "effort_fcast_a": "foo_norm_valfoo_norm_val",  # result of add
                    "effort_fcast_d": "foo_norm_valfoo_norm_val",  # result of add
                    "effort_plan": "foo_norm_valfoo_norm_val",  # result of add
                    "end_time_act": None,  # fallback to default
                    "end_time_plan": "foo_norm_val",  # result of find_max
                    "start_time_act": "foo_norm_val",  # result of find_min
                    "start_time_plan": "foo_norm_val",  # result of find_min
                },
            },
        )
        # norm_val is called twice per attr in ATTRIBUTES, except for effort_fcast
        norm_val.assert_has_calls(
            [
                mock.call("val_start_time_act", None),
                mock.call("sub_start_time_act", None),
                mock.call("val_end_time_act", None),
                mock.call(
                    None, None
                ),  # using sub.__getitem__'s value as fallback for end_time_act
                mock.call("val_effort_plan", 0.0),
                mock.call(
                    1, 0.0
                ),  # using sub.__getitem__'s value as fallback for effort_fcast
                mock.call("parent", 0.0),
                mock.call("val_effort_act", 0.0),
                mock.call("sub_effort_act", 0.0),
                mock.call("val_effort_fcast_d", 0.0),
                mock.call("sub_effort_fcast_d", 0.0),
                mock.call("val_effort_fcast_a", 0.0),
                mock.call("sub_effort_fcast_a", 0.0),
            ]
        )

    def test__get_percent_complet_effort_plan(self):
        """Test _get_percent_complet: attr 'effort_plan' given"""

        mock_prj = mock.MagicMock(get=mock.MagicMock(return_value=2.0))
        value_dict = {"foo": mock_prj}

        self.assertEqual(
            0,  # effort_dividend / effort_divisor rounded down
            aggregation._get_percent_complet(
                value_dict, 1.0, 1.0, "foo", {}  # sub has len 0
            ),
        )

        mock_prj.get.assert_called_once_with("effort_plan", 0.0)

    def test__get_percent_complet_no_effort_plan(self):
        """Test _get_percent_complet: attr 'effort_plan' not given"""

        mock_prj = mock.MagicMock(get=mock.MagicMock(return_value=0.0))
        value_dict = {"foo": mock_prj}

        self.assertEqual(
            0,  # effortless_dividend / len(subs) rounded down
            aggregation._get_percent_complet(value_dict, 1.0, 1.0, "foo", 2),
        )

        mock_prj.get.assert_called_once_with("effort_plan", 0.0)

    @mock.patch.object(aggregation, "find_max")
    @mock.patch.object(aggregation, "find_min")
    @mock.patch.object(aggregation, "adjust_percentage_complete")
    @mock.patch.object(aggregation, "add_efforts")
    @mock.patch.object(aggregation, "_aggregate_percentage")
    @mock.patch.object(aggregation, "_aggregate_from_child")
    def test_aggregate_sub_tasks(
        self,
        _aggregate_from_child,
        _aggregate_percentage,
        add_efforts,
        adjust_percentage_complete,
        find_min,
        find_max,
    ):
        _aggregate_percentage.return_value = (20, 10)  # (percentage, effort)
        self.counter = [0]

        project = {}
        project_id = "project"
        task1 = {
            "task_id": "task1",
            "start_time_fcast": "foo1",
            "end_time_fcast": "bar1",
        }
        task2 = {
            "task_id": "task2",
            "start_time_fcast": "foo2",
            "end_time_fcast": "bar2",
        }
        project_structure = {"project": [task1, task2], "task1": [], "task2": []}
        leaf_count = {"task1": 1, "task2": 2}

        forecast_dates = [None, None]
        value_dict = {}

        aggregation.aggregate_sub_tasks(
            project,
            project_id,
            project_structure,
            "efforts",
            "demands",
            "assignments",
            leaf_count,
            forecast_dates,
            value_dict,
        )

        _aggregate_from_child.assert_has_calls(
            [
                mock.call(value_dict, project, project_id, task1),
                mock.call(value_dict, project, project_id, task2),
            ]
        )
        _aggregate_percentage.assert_has_calls(
            [mock.call(value_dict, task1, 1), mock.call(value_dict, task2, 2)]
        )

        add_efforts.assert_has_calls(
            [
                mock.call("task1", "efforts", "demands", "assignments", value_dict),
                mock.call("task2", "efforts", "demands", "assignments", value_dict),
                mock.call(project_id, "efforts", "demands", "assignments", value_dict),
            ]
        )

        adjust_percentage_complete.assert_has_calls(
            [mock.call(project, project_id, leaf_count, 40, 20, value_dict, False)]
        )

    @mock.patch.object(aggregation, "adjust_project_prognosis_dates")
    @mock.patch.object(aggregation, "aggregate_sub_tasks")
    @mock.patch.object(aggregation, "count_leaftasks")
    @mock.patch.object(aggregation, "load_project_data")
    def test_aggregate_project_structure(
        self,
        load_project_data,
        count_leaftasks,
        aggregate_sub_tasks,
        adjust_project_prognosis_dates,
    ):
        load_project_data.return_value = (
            "project_structure",
            "tasks_by_id",
            "efforts",
            "demands",
            "assignments",
        )
        count_leaftasks.return_value = "leaf tasks"

        def _aggregate_sub_tasks(*args):
            args[7][0] = "min"
            args[7][1] = "max"

        aggregate_sub_tasks.side_effect = _aggregate_sub_tasks

        project = {"cdb_project_id": "my_project"}
        value_dict = defaultdict(dict)

        self.assertEqual(
            aggregation.aggregate_project_structure(project),
            (value_dict, "tasks_by_id"),
        )
        load_project_data.assert_called_once_with(project)
        count_leaftasks.assert_called_once_with("my_project", "project_structure")
        aggregate_sub_tasks.assert_called_once_with(
            project,
            "my_project",
            "project_structure",
            "efforts",
            "demands",
            "assignments",
            "leaf tasks",
            ["min", "max"],
            value_dict,
            True,
        )

        adjust_project_prognosis_dates.assert_called_once_with(
            project, value_dict, ["min", "max"]
        )

    def test_add_efforts_for_null_values(self):
        # effort_act should not be adoped in the value_dict, since it is 0
        value_dict = defaultdict(dict)
        object_id = "id"
        data = {object_id: 0}

        add_efforts(object_id, data, data, data, value_dict)
        expected_value_dict = {
            object_id: {
                "effort_fcast_d": 0,
                "effort_fcast_a": 0,
            }
        }
        self.assertEqual(value_dict, expected_value_dict)

    def test_add_efforts_for_null_demands_and_assignments(self):
        value_dict = defaultdict(dict)
        object_id = "id"
        data = {object_id: 0}
        data_effort_act = {object_id: 1}

        add_efforts(object_id, data_effort_act, data, data, value_dict)
        expected_value_dict = {
            object_id: {
                "effort_act": 1,
                "effort_fcast_d": 0,
                "effort_fcast_a": 0,
            }
        }
        self.assertEqual(value_dict, expected_value_dict)
