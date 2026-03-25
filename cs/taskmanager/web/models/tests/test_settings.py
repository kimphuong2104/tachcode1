#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.taskmanager.web.models import settings


@pytest.mark.unit
class Settings(unittest.TestCase):
    def test__get_refresh_interval(self):
        model = mock.MagicMock(spec=settings.Settings)
        self.assertEqual(
            settings.Settings._get_refresh_interval(model),
            model._get_setting.return_value,
        )
        model._get_setting.assert_called_once_with("refreshInterval")


@pytest.mark.integration
class SettingsIntegration(unittest.TestCase):
    @mock.patch.object(settings, "get_label")
    @mock.patch.object(settings, "get_cache")
    def test__get_columns(self, get_cache, get_label):
        self.maxDiff = None
        colA = mock.Mock(
            name="cs_tasks_col_read_status",
            plugin_component="cs-tasks-cells-ReadStatus",
            width=38,
            col_position=10,
            visible=True,
        )
        colB = mock.Mock(
            name="cs_tasks_col_classname",
            plugin_component="",
            width=80,
            col_position=25,
            visible=False,
        )
        get_cache.return_value.columns.values.return_value = [colA, colB]

        def _get_label(name):
            if name == colA.name:
                return "Ungelesen?"
            if name == colB.name:
                return "Typname"
            return None

        get_label.side_effect = _get_label
        self.assertEqual(
            settings.Settings()._get_columns(),
            [
                {
                    "contentRenderer": "cs-tasks-cells-ReadStatus",
                    "id": colA.name,
                    "kind": 1,
                    "label": "Ungelesen?",
                    "position": 10,
                    "tooltip": colA.resolve_tooltip.return_value,
                    "visible": True,
                    "width": "38px",
                },
                {
                    "contentRenderer": "",
                    "id": colB.name,
                    "kind": 1,
                    "label": "Typname",
                    "position": 25,
                    "tooltip": colB.resolve_tooltip.return_value,
                    "visible": False,
                    "width": "80px",
                },
            ],
        )

    def test__get_task_classes_data(self):
        self.maxDiff = None
        self.assertEqual(
            settings.Settings()._get_task_classes_data(),
            {
                "detailOutletNames": {
                    "Test Task (Custom Status Op)": "selected_object",
                    "Test Tasks (OLC)": "selected_object",
                },
                "statusChange": {
                    "Test Task (Custom Status Op)": "tasks_test_status_change",
                    "Test Tasks (OLC)": "CDB_Workflow",
                },
            },
        )

    @mock.patch.object(settings.ViewBaseModel, "get_all_views")
    @mock.patch.object(settings.Settings, "_get_columns")
    def test_get_tasks_settings(self, _get_columns, get_all_views):
        self.maxDiff = None
        request = mock.MagicMock(application_url="base")
        self.assertEqual(
            settings.Settings().get_tasks_settings(request),
            {
                "settings": {
                    "columns": _get_columns.return_value,
                    "contexts": ["cs_tasks_test_olc"],
                    "detailOutletNames": {
                        "Test Task (Custom Status Op)": "selected_object",
                        "Test Tasks (OLC)": "selected_object",
                    },
                    "mapping": {
                        "cs_tasks_test_custom": {
                            "cs_tasks_col_deadline": {
                                "is_async": False,
                                "propname": "",
                            },
                            "cs_tasks_col_name": {
                                "is_async": 0,
                                "propname": "name",
                            },
                            "cs_tasks_col_status": {
                                "is_async": 1,
                                "propname": "getCsTasksStatusData",
                            },
                        },
                        "cs_tasks_test_olc": {
                            "cs_tasks_col_deadline": {
                                "is_async": False,
                                "propname": "deadline",
                            },
                            "cs_tasks_col_effort": {
                                "is_async": 1,
                                "propname": "getCsTasksEffort",
                            },
                            "cs_tasks_col_status": {
                                "is_async": 1,
                                "propname": "getCsTasksStatusData",
                            },
                            "cs_tasks_col_priority": {
                                "is_async": 1,
                                "propname": "getCsTasksPriority",
                            },
                            "cs_tasks_col_name": {"is_async": 0, "propname": "name"},
                            "cs_tasks_col_responsible": {
                                "is_async": 1,
                                "propname": "getCsTasksResponsible",
                            },
                        },
                    },
                    "offerAdminUI": True,
                    "refreshInterval": None,
                    "statusChange": {
                        "Test Task (Custom Status Op)": "tasks_test_status_change",
                        "Test Tasks (OLC)": "CDB_Workflow",
                    },
                    "types": [
                        "base/api/v1/class/cs_tasks_test_custom",
                        "base/api/v1/class/cs_tasks_test_olc",
                    ],
                },
                "views": get_all_views.return_value,
            },
        )


if __name__ == "__main__":
    unittest.main()
