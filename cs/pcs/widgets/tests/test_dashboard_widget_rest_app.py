#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
from cdb import testcase
from cs.web.components.base.main import SettingDict

from cs.pcs.widgets import widget_rest_app


class WidgetRestAppTest(testcase.RollbackTestCase):
    @mock.patch.object(widget_rest_app.static, "Library")
    @mock.patch.object(widget_rest_app.static, "Registry")
    @mock.patch.object(widget_rest_app.os.path, "join", return_value="/js/build")
    @mock.patch.object(widget_rest_app, "VERSION", "VERSION")
    @mock.patch.object(widget_rest_app, "APP", "APP")
    def test_register_libraries(self, join, Registry, Library):
        self.assertIsNone(widget_rest_app.register_libraries())
        Library.assert_called_once_with("APP", "VERSION", "/js/build")
        Library.return_value.add_file.assert_has_calls(
            [
                mock.call("APP.js"),
                mock.call("APP.js.map"),
            ]
        )
        Registry.assert_called_once_with()
        Registry.return_value.add.assert_called_once_with(Library.return_value)

    @mock.patch.object(widget_rest_app, "get_url_patterns")
    @mock.patch.object(widget_rest_app.widget_rest_models.InternalWidgetApp, "get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            widget_rest_app.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        models = widget_rest_app.widget_rest_models
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("in_budget", models.InBudgetModel, ["rest_key"]),
                (
                    "project_notes",
                    models.ProjectNotesModel,
                    ["rest_key", "cdb_object_id"],
                ),
                ("rating", models.RatingModel, ["rest_key"]),
                ("remaining_time", models.RemainingTimeModel, ["rest_key"]),
                ("in_time", models.InTimeModel, ["rest_key"]),
                ("unassigned_roles", models.UnassignedRolesModel, ["rest_key"]),
                ("list_widget", models.ListModel, ["rest_key", "list_config_name"]),
            ],
        )
        get_app.assert_called_once_with("request")

    def test_extend_app_setup(self):
        app_setup = SettingDict()
        request = mock.MagicMock()
        request.class_link.return_value = "class_link"
        widget_rest_app.extend_app_setup(app_setup, request)
        self.maxDiff = None
        self.assertEqual(
            app_setup,
            {
                "cs-objectdashboard-widgets": {
                    "widgets": {
                        "in_budget": {"url": "class_link"},
                        "project_notes": {"url": "class_link"},
                        "rating": {"url": "class_link"},
                        "remaining_time": {"url": "class_link"},
                        "in_time": {"url": "class_link"},
                        "unassigned_roles": {"url": "class_link"},
                        "list_widget": {"url": "class_link"},
                    },
                },
            },
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
