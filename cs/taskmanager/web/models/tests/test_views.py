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

from cdb import testcase
from cs.taskmanager.web.models import views

MOCK_ERROR = views.ElementsError("foo")


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(views, "operation")
    def test_run_operation(self, operation):
        self.assertEqual(
            views.run_operation("foo", 1, 2, c=3),
            operation.return_value,
        )
        operation.assert_called_once_with("foo", 1, 2, c=3)

    @mock.patch.object(views.logging, "exception")
    @mock.patch.object(views, "operation", side_effect=MOCK_ERROR)
    def test_run_operation_fail(self, operation, exception):
        with self.assertRaises(views.HTTPInternalServerError):
            views.run_operation("foo", 1, 2, c=3)
        operation.assert_called_once_with("foo", 1, 2, c=3)
        exception.assert_called_once_with(
            "view operation '%s' failed; args: >%s< (UUID '%s'); kwargs: >%s<",
            "foo",
            (1, 2),
            "?",
            {"c": 3},
        )

    @mock.patch.object(views, "get_classname_from_rest_id")
    @mock.patch.object(views, "get_uuid_from_rest_id")
    @mock.patch.object(views, "get_pkeys_from_rest_id")
    def test_get_backend_condition(
        self, get_pkeys_from_rest_id, get_uuid_from_rest_id, get_classname_from_rest_id
    ):
        self.assertEqual(
            views.get_backend_condition(
                (
                    ("types", "T"),
                    ("contexts", "C"),
                    ("users", "U"),
                )
            ),
            {
                "types": [get_classname_from_rest_id.return_value],
                "contexts": [get_uuid_from_rest_id.return_value],
                "users": [get_pkeys_from_rest_id.return_value],
            },
        )
        get_pkeys_from_rest_id.assert_called_once_with("U")
        get_uuid_from_rest_id.assert_called_once_with("C")
        get_classname_from_rest_id.assert_called_once_with("T")

    @mock.patch.object(views, "get_backend_condition", return_value={"foo": "bar"})
    def test_get_view_condition_json(self, get_backend_condition):
        self.assertEqual(
            views.get_view_condition_json("foo"),
            '{"foo": "bar"}',
        )
        get_backend_condition.assert_called_once_with("foo")


@pytest.mark.unit
class ViewBaseModel(unittest.TestCase):
    def test___init__(self):
        with testcase.min_licfeatures(["TASKMANAGER_050"]):
            views.ViewBaseModel()

    def test__get_selected_view_id(self):
        model = mock.MagicMock(spec=views.ViewBaseModel)
        model._get_setting.return_value = "foo"
        self.assertEqual(
            views.ViewBaseModel._get_selected_view_id(model),
            "foo",
        )
        model._get_setting.assert_called_once_with("selectedView")

    @mock.patch.object(views, "offer_admin_ui", return_value=False)
    @mock.patch.object(views.UserView, "ForUser")
    @mock.patch.object(views.UserView, "GetDefaultView")
    def test_get_all_views(self, GetDefaultView, ForUser, _):
        default_view = mock.MagicMock(cdb_object_id="D")
        custom_view = mock.MagicMock(cdb_object_id="C")
        default_view.toJSON.return_value = {"@id": "DEFAULT"}
        custom_view.toJSON.return_value = {"@id": "CUSTOM"}
        GetDefaultView.return_value = default_view
        ForUser.return_value = [custom_view]
        request = mock.MagicMock(application_url="base")
        model = mock.MagicMock(spec=views.ViewBaseModel)
        self.assertEqual(
            views.ViewBaseModel.get_all_views(model, request),
            {
                "default": "DEFAULT",
                "custom": ["CUSTOM"],
                "selected": {"my-tasks-app": "DEFAULT"},
                "byID": {
                    "D": {"@id": "DEFAULT"},
                    "C": {"@id": "CUSTOM"},
                },
            },
        )

    @mock.patch.object(views, "offer_admin_ui", return_value=True)
    @mock.patch.object(views.UserView, "Query")
    @mock.patch.object(views.UserView, "ForUser")
    @mock.patch.object(views.UserView, "GetDefaultView")
    def test_get_all_views_admin(self, GetDefaultView, ForUser, Query, _):
        default_view = mock.MagicMock(cdb_object_id="D")
        custom_view = mock.MagicMock(cdb_object_id="C")
        default_view.toJSON.return_value = {"@id": "DEFAULT"}
        custom_view.toJSON.return_value = {"@id": "CUSTOM"}
        GetDefaultView.return_value = default_view
        ForUser.return_value = [custom_view]
        Query.return_value = [custom_view, default_view]
        request = mock.MagicMock(application_url="base")
        model = mock.MagicMock(spec=views.ViewBaseModel)
        self.assertEqual(
            views.ViewBaseModel.get_all_views(model, request),
            {
                "default": "DEFAULT",
                "custom": ["CUSTOM"],
                "selected": {"my-tasks-app": "DEFAULT"},
                "byID": {
                    "D": {"@id": "DEFAULT"},
                    "C": {"@id": "CUSTOM"},
                },
            },
        )


@pytest.mark.unit
class NewView(unittest.TestCase):
    @mock.patch.object(views, "View")
    @mock.patch.object(
        views.UserView, "GetCustomAttributes", return_value={"foo": "bar"}
    )
    @mock.patch.object(views, "run_operation")
    def test_new(self, run_operation, GetCustomAttributes, View):
        model = mock.MagicMock(spec=views.NewView)
        self.assertEqual(
            views.NewView.new(model, "name", {}),
            run_operation.return_value.cdb_object_id,
        )
        run_operation.assert_called_once_with("CDB_Create", views.UserView, foo="bar")
        View.assert_called_once_with(run_operation.return_value.cdb_object_id)
        View.return_value.select.assert_called_once()


@pytest.mark.unit
class View(unittest.TestCase):
    pass


@pytest.mark.integration
class ChangeViews(testcase.RollbackTestCase):
    PUBLIC_DEFAULT = "4fb33321-9570-11e8-ba1d-68f7284ff046"
    ROLE_VIEW = "8468ff8f-95d0-11e8-960a-68f7284ff046"

    def test_get_defaults_unchanged(self):
        model = views.ChangeViews()
        self.assertEqual(
            model.get_defaults([], {}),
            {"public": [self.PUBLIC_DEFAULT]},
        )

    def test_get_defaults_delete(self):
        model = views.ChangeViews()
        self.assertEqual(
            model.get_defaults([self.PUBLIC_DEFAULT], {}),
            {},
        )

    def test_get_defaults_change_from_public(self):
        model = views.ChangeViews()
        self.assertEqual(
            model.get_defaults([], {self.PUBLIC_DEFAULT: {"is_default": 0}}),
            {},
        )

    def test_get_defaults_change_to_public(self):
        model = views.ChangeViews()
        result = model.get_defaults(
            [], {self.ROLE_VIEW: {"subject_id": "public", "is_default": 1}}
        )

        self.assertEqual(list(result.keys()), ["public"])
        self.assertEqual(
            set(result["public"]), set([self.PUBLIC_DEFAULT, self.ROLE_VIEW])
        )

    def test_apply_all_changes_new_public_default(self):
        model = views.ChangeViews()
        result = model.apply_all_changes(
            [self.PUBLIC_DEFAULT],
            {self.ROLE_VIEW: {"subject_id": "public", "is_default": 1}},
        )
        self.assertEqual(result, [])

    @mock.patch.object(views.logging, "error")
    def test_apply_all_changes_delete_and_change(self, error):
        model = views.ChangeViews()
        result = model.apply_all_changes(
            [self.ROLE_VIEW],
            {self.ROLE_VIEW: {"foo": "bar"}},
        )
        self.assertEqual(result, [])
        error.assert_called_with(
            "view does not exist: '%s', ignoring...", self.ROLE_VIEW
        )

    def test_apply_all_changes_two_public_defaults(self):
        model = views.ChangeViews()
        result = model.apply_all_changes(
            [],
            {self.ROLE_VIEW: {"subject_id": "public", "is_default": 1}},
        )

        self.assertEqual(
            result,
            [
                'Es muss genau eine Standard-Benutzersicht für die Rolle "public" existieren '
                "(2 gefunden).",
                "Test View:\n"
                "- Es existiert bereits eine Standard-Benutzersicht für die Rolle 'Public'.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
