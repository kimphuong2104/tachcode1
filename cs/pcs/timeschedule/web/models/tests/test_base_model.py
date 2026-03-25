#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import pytest
from mock import MagicMock, call, patch
from webob.exc import HTTPNotFound

from cs.pcs.timeschedule.web.models import base_model


@pytest.mark.unit
class ScheduleBaseModel(unittest.TestCase):
    @patch.object(base_model.ScheduleBaseModel, "get_object_from_uuid", autospec=True)
    @patch.object(base_model.ScheduleBaseModel, "_check_read", autospec=True)
    def test___init__(self, _check_read, get_object_from_uuid):
        model = base_model.ScheduleBaseModel("foo")
        self.assertEqual(model.context_object_id, "foo")
        self.assertEqual(model.context_object, get_object_from_uuid.return_value)
        self.assertEqual(model.context_project, _check_read.return_value)
        get_object_from_uuid.assert_called_once_with(model, "foo")
        _check_read.assert_called_once_with(
            model, get_object_from_uuid.return_value.Project
        )
        self.assertEqual(
            model.column_group,
            get_object_from_uuid.return_value.schedule_column_group,
        )
        self.assertEqual(model.plugins, {})

    @patch.object(base_model.logging, "warning", autospec=True)
    @patch.object(base_model.ScheduleBaseModel, "get_object_from_uuid", autospec=True)
    @patch.object(base_model.ScheduleBaseModel, "_check_read", autospec=True)
    def test___init__no_Project_assigned(
        self, _check_read, get_object_from_uuid, warning
    ):
        "initializes context_project with None if none is assigned"
        get_object_from_uuid.return_value = MagicMock()
        get_object_from_uuid.return_value.Project = None
        model = base_model.ScheduleBaseModel("foo")
        self.assertEqual(model.context_object_id, "foo")
        self.assertEqual(model.context_object, get_object_from_uuid.return_value)
        self.assertIsNone(model.context_project)
        get_object_from_uuid.assert_called_once_with(model, "foo")
        _check_read.assert_has_calls([])
        warning.assert_called_once_with(
            "base_model: context object '%s' has no Project assigned",
            "foo",
        )

    def _get_model(self):
        # initialize model without calling __init__
        return base_model.ScheduleBaseModel.__new__(base_model.ScheduleBaseModel)

    def test__check_read_no_obj(self):
        "fails if no object given"
        model = self._get_model()
        # do not assert error message as it is constant and generic
        with self.assertRaises(HTTPNotFound):
            model._check_read(None)

    def test__check_read_no_attr(self):
        "fails if object has no CheckAccess attribute"
        model = self._get_model()
        # do not assert error message as it is constant and generic
        with self.assertRaises(AttributeError) as error:
            model._check_read("foo")
        self.assertEqual(
            "'str' object has no attribute 'CheckAccess'", str(error.exception)
        )

    def test__check_read_not_callable(self):
        "fails if object.CheckAccess is not callable"
        model = self._get_model()
        obj = MagicMock(CheckAccess="foo")
        # do not assert error message as it is constant and generic
        with self.assertRaises(TypeError) as error:
            model._check_read(obj)
        self.assertEqual("'str' object is not callable", str(error.exception))

    def test__check_read_denied(self):
        "fails if 'read' access denied"
        obj = MagicMock()
        obj.CheckAccess.return_value = False
        model = self._get_model()
        # do not assert error message as it is constant and generic
        with self.assertRaises(HTTPNotFound):
            model._check_read(obj)
        obj.CheckAccess.assert_called_once_with("read")

    def test__check_read(self):
        "returns the object if 'read' access granted"
        obj = MagicMock()
        model = self._get_model()
        self.assertEqual(model._check_read(obj), obj)
        obj.CheckAccess.assert_called_once_with("read")

    @patch.object(base_model.ScheduleBaseModel, "_check_read", autospec=True)
    @patch.object(base_model, "ByID", autospec=True)
    def test_get_object_from_uuid(self, ByID, _check_read):
        model = self._get_model()
        self.assertEqual(model.get_object_from_uuid("foo"), _check_read.return_value)
        ByID.assert_called_once_with("foo")
        _check_read.assert_called_once_with(model, ByID.return_value)

    @patch.object(base_model, "DEFAULT_SETTINGS", "DFLT")
    def _assert_default_user_settings(self, PersonalSettings):
        model = self._get_model()
        model.setting_id1 = "id1"
        self.assertEqual(model.get_user_settings("id2"), "DFLT")
        # first fallback is call to id2
        PersonalSettings.assert_has_calls([call(), call()])
        self.assertEqual(PersonalSettings.call_count, 2)

    @patch.object(
        base_model.util, "PersonalSettings", side_effect=KeyError, autospec=True
    )
    def test_get_user_settings_key_err(self, PersonalSettings):
        "returns default user settings if KeyError is raised"
        self._assert_default_user_settings(PersonalSettings)

    @patch.object(
        base_model.util, "PersonalSettings", side_effect=ValueError, autospec=True
    )
    def test_get_user_settings_value_err(self, PersonalSettings):
        "returns default user settings if ValueError is raised"
        self._assert_default_user_settings(PersonalSettings)

    @patch.object(
        base_model.util,
        "PersonalSettings",
        side_effect=NotImplementedError,
        autospec=True,
    )
    def test_get_user_settings_not_impl_err(self, PersonalSettings):
        "returns default user settings if NotImplementedError is raised"
        self._assert_default_user_settings(PersonalSettings)

    @patch.object(
        base_model.util, "PersonalSettings", side_effect=TypeError, autospec=True
    )
    def test_get_user_settings_type_err(self, PersonalSettings):
        "returns default user settings if TypeError is raised"
        self._assert_default_user_settings(PersonalSettings)

    @patch.object(base_model.json, "loads", autospec=True)
    @patch.object(base_model.util, "PersonalSettings", autospec=True)
    def test_get_user_settings(self, PersonalSettings, loads):
        "returns deserialized user settings"
        model = self._get_model()
        model.setting_id1 = "id1"
        self.assertEqual(model.get_user_settings("id2"), loads.return_value)
        PersonalSettings.return_value.getValue.assert_called_once_with(
            "id1",
            "id2",
        )
        loads.assert_called_once_with(
            PersonalSettings.return_value.getValue.return_value
        )


if __name__ == "__main__":
    unittest.main()
