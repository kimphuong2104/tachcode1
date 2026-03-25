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

from cs.pcs.projects.web.rest_app.project_structure import models


@pytest.mark.unit
class StructureModel(unittest.TestCase):
    @mock.patch.object(models.logging, "error")
    @mock.patch.object(models, "resolve_root_object", return_value=None)
    def test___init___read_denied(self, resolve_root_object, log_error):
        "raises on denied read access"
        model = mock.MagicMock(
            spec=models.StructureModel,
            project="?",
        )
        with self.assertRaises(models.HTTPNotFound):
            models.StructureModel.__init__(model, None, "project_structure", "ID")

        log_error.assert_called_once_with("object not found or not readable: %s", "ID")
        resolve_root_object.assert_called_once_with(None, "project_structure", "ID")

    @mock.patch.object(models, "resolve_root_object")
    def test___init__(self, resolve_root_object):
        "checks read access"
        model = mock.MagicMock(spec=models.StructureModel)
        self.assertIsNone(
            models.StructureModel.__init__(model, None, "project_structure", "ID")
        )

        self.assertEqual(model.object, resolve_root_object.return_value)
        resolve_root_object.assert_called_once_with(None, "project_structure", "ID")

    @mock.patch.object(models, "resolve")
    def test_resolve(self, resolve):
        "load flat structure's metadata"
        model = mock.MagicMock(
            spec=models.StructureModel, object=mock.MagicMock(), view="view"
        )
        self.assertEqual(
            models.StructureModel.resolve(model, "req"),
            resolve.return_value,
        )
        resolve.assert_called_once_with(
            model.object.cdb_object_id, "view", "req", model.__first_page_size__
        )

    @mock.patch.object(models, "get_full_data")
    def test_get_full_data(self, get_full_data):
        model = mock.MagicMock(spec=models.StructureModel, view="view")
        self.assertEqual(
            models.StructureModel.get_full_data(model, "oids", "req"),
            get_full_data.return_value,
        )
        get_full_data.assert_called_once_with("oids", "view", "req")

    @mock.patch.object(models, "persist_drop")
    def test_persist_drop(self, persist_drop):
        model = mock.MagicMock(spec=models.StructureModel, view="view")
        self.assertIsNotNone(
            models.StructureModel.persist_drop(
                model, "target", "parent", "children", "pred", "is_move"
            )
        )
        persist_drop.assert_called_once_with(
            "target", "parent", "children", "pred", "view", "is_move"
        )

    @mock.patch.object(models.Task, "generate_project_structure_URL")
    def test_generate_URL(self, generate_project_structure_URL):
        "generate project structure URL of a task"
        model = mock.MagicMock(
            spec=models.StructureURLModel,
            task=mock.MagicMock(),
            rest_key=mock.MagicMock(),
        )
        self.assertEqual(
            models.StructureURLModel.generate_URL(model, "req"),
            generate_project_structure_URL.return_value,
        )
        generate_project_structure_URL.assert_called_once_with(
            model.task, "req", model.rest_key
        )


if __name__ == "__main__":
    unittest.main()
