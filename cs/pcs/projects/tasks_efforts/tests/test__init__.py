#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
import pytest

from cs.pcs.projects import tasks_efforts


@pytest.mark.unit
class TestInit(unittest.TestCase):
    @mock.patch.object(tasks_efforts.tasks_changes, "add_indirect_changes")
    def test_add_changes(self, mock_add_indirect_changes):
        """Test add_changes"""

        # mock values for half the attributes and
        # test fallback to default for other half
        task_dict_1 = {
            "effort_act": "act",
            "effort_fcast": "forecast",
            "effort_fcast_a": "forecast_a",
            "effort_fcast_d": "forecast_d",
            "effort_plan": "plan",
            "end_time_act": "end_act",
            "percent_complet": "percent",
            "start_time_act": "start_act",
        }

        task_dict_2 = {
            "effort_act": "act",
            "effort_fcast": "forecast",
            "effort_fcast_a": "forecast_a",
            "effort_fcast_d": "forecast_d",
            "effort_plan": "plan",
            "end_time_act": "end_act",
            "percent_complet": "percent",
            "start_time_act": "start_act",
        }

        mock_value_dict = {
            "foo_1": task_dict_1,
            "foo_2": task_dict_2,
        }

        mock_task_1 = mock.MagicMock(is_group=True)
        mock_task_2 = mock.MagicMock(is_group=False)

        task_1_attr_dict = {
            "effort_act": None,
            "effort_fcast": None,
            "effort_fcast_a": None,
            "effort_fcast_d": None,
            "effort_plan": None,
            "end_time_act": None,
            "percent_complet": None,
            "start_time_act": None,
        }

        def getitem(key):
            return task_1_attr_dict[key]

        mock_task_1.return_value.__getitem__.side_effect = getitem
        mock_task_2.return_value.__getitem__.side_effect = getitem

        mock_task_by_id = {"foo_1": mock_task_1, "foo_2": mock_task_2}

        tasks_efforts.add_task_changes(mock_task_by_id, mock_value_dict)

        mock_add_indirect_changes.assert_has_calls(
            [
                mock.call(
                    "foo_1",
                    **{
                        "effort_act": "act",
                        "effort_fcast": "forecast",
                        "effort_fcast_a": "forecast_a",
                        "effort_fcast_d": "forecast_d",
                        "effort_plan": "plan",
                        "end_time_act": "end_act",
                        "percent_complet": "percent",
                        "start_time_act": "start_act",
                    }
                ),
                mock.call(
                    "foo_2",
                    **{
                        "effort_act": "act",
                        "effort_fcast": "forecast",
                        "effort_fcast_a": "forecast_a",
                        "effort_fcast_d": "forecast_d",
                        "effort_plan": "plan",
                        "end_time_act": "end_act",
                        "percent_complet": "percent",
                        "start_time_act": "start_act",
                    }
                ),
            ]
        )
