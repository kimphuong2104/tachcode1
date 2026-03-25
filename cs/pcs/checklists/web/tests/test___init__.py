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

from cs.pcs.checklists import web
from cs.pcs.checklists.web.related import models


@pytest.mark.unit
class UtilityTest(unittest.TestCase):
    @mock.patch.object(web, "get_url_patterns")
    @mock.patch.object(web.ChecklistApp, "get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            web.get_app_url_patterns("request"), get_url_patterns.return_value
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                (
                    "checklist_items",
                    web.ChecklistItemsModel,
                    ["cdb_project_id", "checklist_id"],
                ),
                ("progress", web.ChecklistsProgressModel, []),
                ("ratings", web.RatingsModel, []),
                ("work_objects", web.WorkObjectsModel, []),
                (
                    "related_structure",
                    models.RelatedChecklistsStructureModel,
                    ["cdb_object_id"],
                ),
                ("related_content", models.RelatedChecklistsContentModel, []),
                (
                    "related_refresh",
                    models.RelatedChecklistsRefreshModel,
                    ["cdb_object_id"],
                ),
            ],
        )

    @mock.patch.object(web, "add_stories")
    @mock.patch.object(web.static, "Registry")
    @mock.patch.object(web.static, "Library")
    @mock.patch.object(web.os, "path")
    @mock.patch.object(web, "STORIES", "STORIES")
    @mock.patch.object(web, "APP", "APP")
    @mock.patch.object(web, "VERSION", "VERSION")
    @mock.patch.object(web, "__file__", "__file__")
    def test__register_libraries(self, path, Library, Registry, add_stories):
        self.assertIsNone(web._register_libraries())
        Library.assert_has_calls(
            [
                mock.call("APP", "VERSION", path.join.return_value),
                mock.call().add_file("APP.js"),
                mock.call().add_file("APP.js.map"),
                mock.call("STORIES", "VERSION", path.join.return_value),
                mock.call().add_file("STORIES.js"),
                mock.call().add_file("STORIES.js.map"),
            ]
        )
        self.assertEqual(Library.call_count, 2)
        path.join.assert_has_calls(
            2
            * [
                mock.call(path.dirname.return_value, "js", "build"),
            ]
        )
        self.assertEqual(path.join.call_count, 2)
        path.dirname.assert_has_calls(2 * [mock.call("__file__")])
        self.assertEqual(path.dirname.call_count, 2)
        Registry.assert_has_calls(
            [
                mock.call(),
                mock.call().add(Library.return_value),
                mock.call(),
                mock.call().add(Library.return_value),
            ]
        )
        self.assertEqual(Registry.call_count, 2)

        add_stories.assert_called_once_with(("APP", "VERSION"), ("STORIES", "VERSION"))


@pytest.mark.unit
class ChecklistApp(unittest.TestCase):
    @mock.patch.object(web, "PATH", "PATH")
    @mock.patch.object(web, "get_internal")
    def test_get_app(self, get_internal):
        web.ChecklistApp.get_app("request")
        get_internal.assert_called_once_with("request")
        get_internal.return_value.child.assert_called_once_with("PATH")

    @mock.patch.object(web.ChecklistApp, "__init__", return_value=None)
    def test__mount_app(self, ChecklistApp__init__):
        self.assertIsInstance(
            web._mount_app(),
            web.ChecklistApp,
        )
        ChecklistApp__init__.assert_called_once_with()

    @mock.patch.object(web.RatingsModel, "__init__", return_value=None)
    def test_get_ratings_model(self, RatingsModel__init__):
        self.assertIsInstance(
            web.get_ratings_model("request"),
            web.RatingsModel,
        )
        RatingsModel__init__.assert_called_once_with()

    def test_get_checklist_ratings(self):
        model = mock.MagicMock(spec=web.RatingsModel)
        request = mock.MagicMock()
        self.assertEqual(
            web.get_checklist_ratings(model, request),
            model.get_rating_values.return_value,
        )
        model.get_rating_values.assert_called_once_with()

    @mock.patch.object(web.ChecklistItemsModel, "__init__", return_value=None)
    def test_get_checklist_items_model(self, ChecklistItemsModel__init__):
        self.assertIsInstance(
            web.get_checklist_items_model("request", "PID", "CID"),
            web.ChecklistItemsModel,
        )
        ChecklistItemsModel__init__.assert_called_once_with("PID", "CID")

    def test_get_checklist_items(self):
        model = mock.MagicMock(spec=web.ChecklistItemsModel)
        self.assertEqual(
            web.get_checklist_items(model, "request"),
            model.get_checklist_items.return_value,
        )
        model.get_checklist_items.assert_called_once_with("request")

    @mock.patch.object(web.logging, "error")
    def test_set_checklist_item_positions_no_json(self, error):
        model = mock.MagicMock(spec=web.ChecklistItemsModel)
        request = mock.MagicMock(json=None)
        with self.assertRaises(web.HTTPBadRequest):
            web.set_checklist_item_positions(model, request)

        error.assert_called_once_with("Request Missing payload.")

    def test_set_checklist_item_positions(self):
        model = mock.MagicMock(spec=web.ChecklistItemsModel)
        request = mock.MagicMock()
        self.assertEqual(
            web.set_checklist_item_positions(model, request),
            model.set_checklist_item_positions.return_value,
        )
        model.set_checklist_item_positions.assert_called_once_with(request)

    @mock.patch.object(web.ChecklistsProgressModel, "__init__", return_value=None)
    def test_get_checklists_progress_model(self, ChecklistsProgressModel__init__):
        self.assertIsInstance(
            web.get_checklists_progress_model("request"),
            web.ChecklistsProgressModel,
        )
        ChecklistsProgressModel__init__.assert_called_once_with()

    @mock.patch.object(web.logging, "error")
    def test_get_checklists_progress_no_json(self, error):
        model = mock.MagicMock(spec=web.ChecklistsProgressModel)
        request = mock.MagicMock(json=None)
        with self.assertRaises(web.HTTPBadRequest):
            web.get_checklists_progress(model, request)

        error.assert_called_once_with("Request Missing payload.")

    def test_get_checklists_progress(self):
        model = mock.MagicMock(spec=web.ChecklistsProgressModel)
        request = mock.MagicMock()
        self.assertEqual(
            web.get_checklists_progress(model, request),
            model.get_checklists_progress.return_value,
        )
        model.get_checklists_progress.assert_called_once_with(request)

    @mock.patch.object(web.WorkObjectsModel, "__init__", return_value=None)
    def test_get_work_objects_model(self, WorkObjectsModel__init__):
        request = mock.MagicMock(
            json={"checklist_keys": [{"cdb_project_id": "PID", "checklist_id": "CID"}]}
        )
        self.assertIsInstance(
            web.check_work_objects_model(request),
            web.WorkObjectsModel,
        )
        WorkObjectsModel__init__.assert_called_once_with()

    def test_check_work_objects(self):
        model = mock.MagicMock(spec=web.WorkObjectsModel)
        request = mock.MagicMock(json={"cdb_project_id": "bar", "checklist_id": "baz"})
        self.assertEqual(
            web.check_work_objects(model, request),
            model.check_work_objects.return_value,
        )
        model.check_work_objects.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
