#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import mock
import pytest

from cs.pcs.projects.tasks_efforts import status_signals


@pytest.mark.unit
class TestStatusSignal(unittest.TestCase):
    @mock.patch.object(
        status_signals, "get_changed_status_signals", return_value={"bam": "boo"}
    )
    def test__update_status_signals_project(
        self,
        get_changed_status_signals,
    ):
        """Test _update_status_signals"""

        prj = {"bar": "baz"}
        value_dict = {"foo": {"bar": "baz"}}

        status_signals._update_project_status_signals(prj, "foo", value_dict)

        get_changed_status_signals.assert_called_once_with({"bar": "baz"})
        self.assertDictEqual(value_dict, {"foo": {"bar": "baz", "bam": "boo"}})

    @mock.patch.object(
        status_signals, "get_changed_status_signals", return_value={"bam": "boo"}
    )
    def test__update_status_signals_tasks(
        self,
        get_changed_status_signals,
    ):
        prj = {"proj": "test_project"}

        task1 = {"task1": "test_task1", "parent_task": ""}
        task2 = {"task2": "test_task2", "parent_task": "task1"}

        tasks_by_id = {"task1": task1, "task2": task2}
        value_dict = {"task1": {"some_attr": "some_value"}}

        status_signals._update_tasks_status_signals(prj, tasks_by_id, value_dict)

        get_changed_status_signals.assert_has_calls(
            [
                mock.call(task1, {"proj": "test_project"}),
                mock.call(
                    task2,
                    {
                        "task1": "test_task1",
                        "some_attr": "some_value",
                        "bam": "boo",  # parent contains get status updates as its already processed
                        "parent_task": "",
                    },
                ),
            ]
        )

        self.assertDictEqual(
            value_dict["task1"], {"some_attr": "some_value", "bam": "boo"}
        )

        self.assertDictEqual(value_dict["task2"], {"bam": "boo"})

    @mock.patch.object(status_signals, "_update_project_status_signals")
    @mock.patch.object(status_signals, "_update_tasks_status_signals")
    @mock.patch.object(
        status_signals,
        "get_object_with_updated_values",
        return_value="project_with_vals",
    )
    def test_update_status_signals(
        self, _, _update_tasks_status_signals, _update_project_status_signals
    ):
        project = {"cdb_project_id": "my_project"}
        value_dict = {"my_project": "proj"}
        tasks_by_id = {"foo": "bar"}
        status_signals.update_status_signals(project, value_dict, tasks_by_id)
        _update_project_status_signals.assert_called_once_with(
            "project_with_vals", "my_project", value_dict
        )

        _update_tasks_status_signals.assert_called_once_with(
            "project_with_vals", tasks_by_id, value_dict
        )
