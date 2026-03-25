#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,abstract-method

import unittest

import mock
import pytest

from cs.pcs.projects import project_structure


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(project_structure.ProjectStructureViews, "GetViewClass")
    def test__get_view_class(self, GetViewClass):
        self.assertEqual(
            project_structure.get_view_class("view"), GetViewClass.return_value
        )
        GetViewClass.assert_called_once_with("view")

    @mock.patch.object(project_structure, "_get_dummy_request")
    def test__ensure_request_dummy(self, _get_dummy_request):
        self.assertEqual(
            project_structure._ensure_request(None),
            _get_dummy_request.return_value,
        )
        _get_dummy_request.assert_called_once_with()

    @mock.patch.object(project_structure, "_get_dummy_request")
    def test__ensure_request(self, _get_dummy_request):
        self.assertEqual(
            project_structure._ensure_request("foo"),
            "foo",
        )
        _get_dummy_request.assert_not_called()

    @mock.patch.object(project_structure, "get_view_class")
    @mock.patch.object(project_structure, "_ensure_request")
    def test_resolve(self, _ensure_request, get_view_class):
        "resolves structure"
        self.assertEqual(
            project_structure.resolve("root", "view", "req", "first"),
            get_view_class.return_value.return_value.resolve.return_value,
        )
        _ensure_request.assert_called_once_with("req")
        get_view_class.assert_called_once_with("view")
        get_view_class.return_value.assert_called_once_with(
            "root", _ensure_request.return_value
        )
        get_view_class.return_value.return_value.resolve.assert_called_once_with(
            "first"
        )

    @mock.patch.object(project_structure, "get_view_class")
    @mock.patch.object(project_structure, "_ensure_request")
    def test_get_full_data(self, _ensure_request, get_view_class):
        "resolves structure"
        self.assertEqual(
            project_structure.get_full_data("oids", "view", "req"),
            get_view_class.return_value.get_full_data_of.return_value,
        )
        _ensure_request.assert_called_once_with("req")
        get_view_class.assert_called_once_with("view")
        get_view_class.return_value.get_full_data_of.assert_called_once_with(
            "oids", _ensure_request.return_value
        )

    @mock.patch.object(project_structure, "get_view_class")
    def test_persist_drop_move(self, get_view_class):
        "persists dopped node (move)"
        self.assertEqual(
            project_structure.persist_drop(
                "target", "parent", "children", "pred", "view"
            ),
            get_view_class.return_value.persist_drop.return_value,
        )
        get_view_class.assert_called_once_with("view")
        get_view_class.return_value.persist_drop.assert_called_once_with(
            "target", "parent", "children", "pred", True
        )

    @mock.patch.object(project_structure, "get_view_class")
    def test_persist_drop_copy(self, get_view_class):
        "persists dopped node (move)"
        self.assertEqual(
            project_structure.persist_drop(
                "target", "parent", "children", "pred", "view", False
            ),
            get_view_class.return_value.persist_drop.return_value,
        )
        get_view_class.assert_called_once_with("view")
        get_view_class.return_value.persist_drop.assert_called_once_with(
            "target", "parent", "children", "pred", False
        )


@pytest.mark.unit
class ProjectStructureViews(unittest.TestCase):
    def test___init__(self):
        x = mock.MagicMock(spec=project_structure.ProjectStructureViews)
        self.assertIsNone(project_structure.ProjectStructureViews.__init__(x))
        x.collect.assert_called_once_with()

    def test_GetViewClass(self):
        self.assertEqual(
            project_structure.ProjectStructureViews.GetViewClass("project_structure"),
            project_structure.TreeView,
        )

    def test__register_view_fail(self):
        "fails if view has no view_name"
        x = mock.MagicMock(spec=project_structure.ProjectStructureViews)
        with self.assertRaises(AttributeError) as error:
            project_structure.ProjectStructureViews._register_view(x, "view")

        self.assertEqual(
            str(error.exception),
            "'str' object has no attribute 'view_name'",
        )

    def test__register_view_not_a_view(self):
        "fails if view is not a View instance"

        class MyView:
            view_name = "foo"

        x = mock.MagicMock(spec=project_structure.ProjectStructureViews)
        with self.assertRaises(TypeError) as error:
            project_structure.ProjectStructureViews._register_view(x, MyView)

        self.assertEqual(str(error.exception), f"not a view: {MyView}")

    @mock.patch.object(project_structure.logging, "error")
    def test__register_view_already_registered(self, error):
        "ignored already-registered view"

        class MyView(project_structure.View):
            view_name = "foo"

        x = mock.MagicMock(
            spec=project_structure.ProjectStructureViews,
            views={"foo": "X"},
        )
        self.assertIsNone(
            project_structure.ProjectStructureViews._register_view(x, MyView)
        )
        self.assertEqual(x.views, {"foo": "X"})
        error.assert_called_once_with("ignoring duplicate view '%s': %s", "foo", MyView)

    def test__register_view(self):
        "registers view"

        class MyView(project_structure.View):
            view_name = "foo"

        x = mock.MagicMock(
            spec=project_structure.ProjectStructureViews,
            views={},
        )
        self.assertIsNone(
            project_structure.ProjectStructureViews._register_view(x, MyView)
        )
        self.assertEqual(x.views, {"foo": MyView})

    @mock.patch.object(project_structure.sig, "emit")
    @mock.patch.object(project_structure, "GET_VIEWS", "GET_VIEWS")
    def test_collect(self, emit):
        x = mock.MagicMock(spec=project_structure.ProjectStructureViews)
        self.assertIsNone(project_structure.ProjectStructureViews.collect(x))
        self.assertEqual(x.views, {"project_structure": project_structure.TreeView})
        emit.assert_called_once_with("GET_VIEWS")
        emit.return_value.assert_called_once_with(x._register_view)


if __name__ == "__main__":
    unittest.main()
