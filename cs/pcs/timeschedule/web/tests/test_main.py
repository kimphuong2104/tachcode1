#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from mock import MagicMock, call, patch

from cs.pcs.timeschedule.web import main


@pytest.mark.unit
class Utility(unittest.TestCase):
    @patch("cs.pcs.timeschedule.web.rest_app.RestApp.get_app")
    @patch.object(main, "get_url_patterns")
    def test_get_app_url_patterns(self, get_url_patterns, get_app):
        self.assertEqual(
            main.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("appData", main.AppModel, ["context_object_id"]),
                ("tableData", main.DataModel, ["context_object_id"]),
                ("elementsData", main.ElementsModel, ["context_object_id"]),
                ("readOnlyData", main.ReadOnlyModel, ["context_object_id"]),
                ("updateData", main.UpdateModel, ["context_object_id"]),
                (
                    "setDates",
                    main.SetDatesModel,
                    ["context_object_id", "content_object_id"],
                ),
                (
                    "setRelships",
                    main.SetRelshipsModel,
                    ["context_object_id", "task_object_id", "relship_name"],
                ),
                (
                    "setAttribute",
                    main.SetAttributeModel,
                    ["context_object_id", "cdb_object_id"],
                ),
                ("getBaselines", main.BaselineModel, ["project_oid"]),
                ("getBaselineData", main.BaselineDataModel, ["context_object_id"]),
            ],
        )
        get_app.assert_called_once_with("request")

    @patch.object(
        main.Label,
        "KeywordQuery",
        return_value=[
            {"d": "eins", "uk": "one"},
            {"d": "zwei", "uk": "two"},
        ],
    )
    def test_get_reltypes(self, KeywordQuery):
        "returns reltype mapping of labels to IDs"
        self.assertEqual(
            main.get_reltypes(),
            {
                "eins": "eins",
                "zwei": "zwei",
                "one": "eins",
                "two": "zwei",
            },
        )
        KeywordQuery.assert_called_once_with(
            ausgabe_label=[
                "web.timeschedule.taskrel-AA",
                "web.timeschedule.taskrel-AE",
                "web.timeschedule.taskrel-EA",
                "web.timeschedule.taskrel-EE",
            ]
        )

    @patch.object(main, "get_reltypes", autospec=True)
    @patch.object(main, "APP", "APP")
    @patch.object(main.ColumnDefinition, "ByGroup")
    def test_update_app_setup(self, ByGroup, get_reltypes):
        model = MagicMock()
        app_setup = MagicMock()
        main.update_app_setup(model, "request", app_setup)
        app_setup.merge_in.assert_called_once_with(
            ["APP"],
            {
                "reltype_labels": get_reltypes.return_value,
            },
        )
        ByGroup.cache_clear.assert_called_once_with()

    @patch.object(main.static, "Registry")
    @patch.object(main.static, "Library")
    @patch.object(main.os, "path")
    @patch.object(main, "APP", "APP")
    @patch.object(main, "VERSION", "VERSION")
    @patch.object(main, "__file__", "__file__")
    def test__register_libraries(self, path, Library, Registry):
        # pylint: disable=protected-access
        self.assertIsNone(main._register_libraries())
        Library.assert_called_once_with(
            "APP",
            "VERSION",
            path.join.return_value,
        )
        path.join.assert_called_once_with(
            path.dirname.return_value,
            "js",
            "build",
        )
        path.dirname.assert_called_once_with("__file__")
        Library.return_value.add_file.assert_has_calls(
            [
                call("APP.js"),
                call("APP.js.map"),
            ]
        )
        self.assertEqual(Library.return_value.add_file.call_count, 2)
        Registry.assert_called_once_with()
        Registry.return_value.add.assert_called_once_with(
            Library.return_value,
        )


if __name__ == "__main__":
    unittest.main()
