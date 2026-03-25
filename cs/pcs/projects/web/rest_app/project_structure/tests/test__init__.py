#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.pcs.projects.web.rest_app import project_structure


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(project_structure, "get_url_patterns")
    @mock.patch.object(project_structure.StructureApp, "get_app")
    @mock.patch.object(project_structure, "APP", "APP")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            project_structure.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("APP", project_structure.StructureModel, ["view", "root_rest_key"]),
            ],
        )


@pytest.mark.unit
class StructureApp(unittest.TestCase):
    @mock.patch.object(project_structure, "get_internal", autospec=True)
    @mock.patch.object(project_structure, "APP", "APP")
    def test_get_app(self, get_internal):
        "returns app URL"
        self.assertEqual(
            project_structure.StructureApp.get_app("request"),
            get_internal.return_value.child.return_value,
        )
        get_internal.assert_called_once_with("request")
        get_internal.return_value.child.assert_called_once_with("APP")

    @mock.patch.object(project_structure, "StructureApp")
    def test__mount_app(self, StructureApp):
        "returns initialized app"
        # pylint: disable=protected-access
        self.assertEqual(project_structure._mount_app(), StructureApp.return_value)
        StructureApp.assert_called_once_with()

    @mock.patch.object(project_structure, "StructureURLModel", autospec=True)
    def test_get_structure_URL_model(self, URLModel):
        "returns initialized model"
        self.assertEqual(
            project_structure.get_structure_URL_model("request", "project_id@task_id"),
            URLModel.return_value,
        )
        URLModel.assert_called_once_with("request", "project_id@task_id")

    def test_get_generated_URL(self):
        "returns generated URL"
        model = mock.MagicMock(spec=project_structure.StructureURLModel)
        request = mock.MagicMock()
        self.assertEqual(
            project_structure.get_generated_URL(model, request),
            model.generate_URL.return_value,
        )
        model.generate_URL.assert_called_once_with(request)

    @mock.patch.object(project_structure, "StructureModel", autospec=True)
    def test_get_structure_model(self, PSModel):
        "returns initialized model"
        self.assertEqual(
            project_structure.get_structure_model(
                "request", "project_structure", "cdb_project_id"
            ),
            PSModel.return_value,
        )
        PSModel.assert_called_once_with(
            "request", "project_structure", "cdb_project_id"
        )

    def test_resolve_structure_no_params(self):
        "returns project structure for default"
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(params={})
        self.assertEqual(
            project_structure.resolve_structure(model, request),
            model.resolve.return_value,
        )
        model.resolve.assert_called_once_with(request)

    def test_resolve_structure_tree_table(self):
        "returns project structure for tree table"
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(
            params={
                "subprojects": "1",
                "view": "tree",
            }
        )
        self.assertEqual(
            project_structure.resolve_structure(model, request),
            model.resolve.return_value,
        )
        model.resolve.assert_called_once_with(request)

    def test_resolve_structure_foo(self):
        "returns project structure for another view"
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(
            params={
                "subprojects": "0",
                "view": "foo",
            }
        )
        self.assertEqual(
            project_structure.resolve_structure(model, request),
            model.resolve.return_value,
        )
        model.resolve.assert_called_once_with(request)

    @mock.patch.object(project_structure.util, "get_oids_from_json")
    def test_get_full_data(self, get_oids_from_json):
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(json={"view": "foo"})
        self.assertEqual(
            project_structure.get_full_data(model, request),
            model.get_full_data.return_value,
        )
        model.get_full_data.assert_called_once_with(
            get_oids_from_json.return_value,
            request,
        )
        get_oids_from_json.assert_called_once_with(request)

    @mock.patch.object(
        project_structure,
        "parse_persist_drop_payload",
        return_value=("T", "P", "C", "PR", "I"),
    )
    def test_save_dropped_node(self, parse_persist_drop_payload):
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(json={"view": "foo"})
        self.assertEqual(
            project_structure.save_dropped_node(model, request),
            model.persist_drop.return_value,
        )
        model.persist_drop.assert_called_once_with(
            *parse_persist_drop_payload.return_value
        )
        parse_persist_drop_payload.assert_called_once_with({"view": "foo"})

    @mock.patch.object(project_structure, "parse_revert_drop_payload")
    def test_delete_copied_node(self, parse_revert_drop_payload):
        model = mock.MagicMock(spec=project_structure.StructureModel)
        request = mock.MagicMock(json={"view": "foo"})
        self.assertIsNone(project_structure.delete_copied_node(model, request))

        model.delete_copy.assert_called_once_with(
            parse_revert_drop_payload.return_value
        )
        parse_revert_drop_payload.assert_called_once_with({"view": "foo"})


if __name__ == "__main__":
    unittest.main()
