#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import pytest
from mock import MagicMock, patch

from cs.pcs.timeschedule.web import rest_app


@pytest.mark.unit
class RestApp(unittest.TestCase):
    @patch.object(rest_app, "MOUNT", "MOUNT")
    @patch.object(rest_app, "get_internal")
    def test_get_app(self, get_internal):
        rest_app.RestApp.get_app("request")
        get_internal.assert_called_once_with("request")
        get_internal.return_value.child.assert_called_once_with("MOUNT")

    @patch.object(rest_app.RestApp, "__new__", autospec=True)
    def test__mount_rest_app(self, RestApp__new__):
        self.assertEqual(rest_app._mount_rest_app(), RestApp__new__.return_value)
        RestApp__new__.assert_called_once_with(rest_app.RestApp)

    @patch.object(rest_app.AppModel, "__new__", autospec=True)
    def test_get_app_data_model(self, AppModel__new__):
        self.assertEqual(
            rest_app.get_app_data_model("request", "foo"), AppModel__new__.return_value
        )
        AppModel__new__.assert_called_once_with(
            rest_app.AppModel,
            "foo",
        )

    def test_get_app_data(self):
        model = MagicMock(spec=rest_app.AppModel)
        self.assertEqual(
            rest_app.get_app_data(model, "request"), model.get_app_data.return_value
        )
        model.get_app_data.assert_called_once_with("request")

    def test_update_app_data(self):
        model = MagicMock(spec=rest_app.AppModel)
        self.assertEqual(
            rest_app.update_app_data(model, "request"),
            model.update_app_data.return_value,
        )
        model.update_app_data.assert_called_once_with("request")

    @patch.object(rest_app.DataModel, "__new__", autospec=True)
    def test_get_table_data_model(self, DataModel__new__):
        self.assertEqual(
            rest_app.get_table_data_model("request", "foo"),
            DataModel__new__.return_value,
        )
        DataModel__new__.assert_called_once_with(rest_app.DataModel, "foo")

    def test_get_data(self):
        model = MagicMock(spec=rest_app.DataModel)
        self.assertEqual(
            rest_app.get_data(model, "request"), model.get_data.return_value
        )
        model.get_data.assert_called_once_with("request")

    @patch.object(rest_app, "get_oids_from_json", autospec=True)
    def test_get_full_data(self, get_oids_from_json):
        model = MagicMock(spec=rest_app.DataModel)
        self.assertEqual(
            rest_app.get_full_data(model, "request"), model.get_full_data.return_value
        )
        model.get_full_data.assert_called_once_with(
            get_oids_from_json.return_value,
            None,
            None,
            [],
            "request",
        )
        get_oids_from_json.assert_called_once_with("request")

    def test_get_elements(self):
        model = MagicMock(spec=rest_app.ElementsModel, context_object_id="id")
        self.assertEqual(
            rest_app.get_elements(model, "request"),
            model.get_manage_elements_data.return_value,
        )
        model.get_manage_elements_data.assert_called_once_with("request")

    def test_get_related_names(self):
        model = MagicMock()
        self.assertEqual(
            rest_app.get_related_names(model, "request"),
            model.schedule_get_related_names.return_value,
        )
        model.schedule_get_related_names.assert_called_once_with("request")

    @patch.object(rest_app.UpdateModel, "__new__", autospec=True)
    def test_get_update_model(self, UpdateModel__new__):
        self.assertEqual(
            rest_app.get_update_model("request", "foo"), UpdateModel__new__.return_value
        )
        UpdateModel__new__.assert_called_once_with(
            rest_app.UpdateModel,
            "foo",
        )

    def test_get_changed_data(self):
        model = MagicMock(spec=rest_app.UpdateModel)
        self.assertEqual(
            rest_app.get_changed_data(model, "request"),
            model.get_changed_data.return_value,
        )
        model.get_changed_data.assert_called_once_with("request")

    @patch.object(rest_app.SetDatesModel, "__new__", autospec=True)
    def test_get_set_dates_model(self, SetDatesModel__new__):
        self.assertEqual(
            rest_app.get_set_dates_model("request", "foo", "bar"),
            SetDatesModel__new__.return_value,
        )
        SetDatesModel__new__.assert_called_once_with(
            rest_app.SetDatesModel,
            "foo",
            "bar",
        )

    def test_set_start(self):
        model = MagicMock(spec=rest_app.SetDatesModel)
        self.assertEqual(
            rest_app.set_start(model, "request"), model.set_start.return_value
        )
        model.set_start.assert_called_once_with("request")

    def test_set_end(self):
        model = MagicMock(spec=rest_app.SetDatesModel)
        self.assertEqual(rest_app.set_end(model, "request"), model.set_end.return_value)
        model.set_end.assert_called_once_with("request")

    def test_set_start_and_end(self):
        model = MagicMock(spec=rest_app.SetDatesModel)
        self.assertEqual(
            rest_app.set_start_and_end(model, "request"),
            model.set_start_and_end.return_value,
        )
        model.set_start_and_end.assert_called_once_with("request")

    @patch.object(rest_app.SetRelshipsModel, "__new__", autospec=True)
    def test_get_set_relships_model(self, SetRelshipsModel__new__):
        self.assertEqual(
            rest_app.get_set_relships_model("request", "foo", "bar", "baz"),
            SetRelshipsModel__new__.return_value,
        )
        SetRelshipsModel__new__.assert_called_once_with(
            rest_app.SetRelshipsModel,
            "foo",
            "bar",
            "baz",
        )

    def test_set_relships(self):
        model = MagicMock(spec=rest_app.SetRelshipsModel)
        self.assertEqual(
            rest_app.set_relships(model, "request"), model.set_relships.return_value
        )
        model.set_relships.assert_called_once_with("request")

    @patch.object(rest_app.SetAttributeModel, "__new__", autospec=True)
    def test_get_set_attribute_model(self, SetAttributeModel__new__):
        self.assertEqual(
            rest_app.get_set_attribute_model("request", "foo", "bar"),
            SetAttributeModel__new__.return_value,
        )
        SetAttributeModel__new__.assert_called_once_with(
            rest_app.SetAttributeModel,
            "foo",
            "bar",
        )

    def test_set_attribute(self):
        model = MagicMock(spec=rest_app.SetAttributeModel)
        self.assertEqual(
            rest_app.set_attribute(model, "request"), model.set_attribute.return_value
        )
        model.set_attribute.assert_called_once_with("request")

    @patch.object(rest_app.ElementsModel, "__new__", autospec=True)
    def test_get_elements_model(self, ElementsModel__new__):
        self.assertEqual(
            rest_app.get_elements_model("request", "foo"),
            ElementsModel__new__.return_value,
        )
        ElementsModel__new__.assert_called_once_with(
            rest_app.ElementsModel,
            "foo",
        )

    @patch.object(rest_app, "UpdateModel")
    def test_persist_elements(self, UpdateModel):
        # schedule for Ptest.msp.Export
        schedule_uuid = "2c73f111-6a21-11eb-928a-3ce1a147c610"
        model = MagicMock(
            spec=rest_app.ElementsModel,
            context_object_id=schedule_uuid,
        )
        model.get_data.return_value = {"data": True}
        request = MagicMock(json={"runOutsideTSApp": False})
        self.assertEqual(
            rest_app.persist_elements(model, request),
            UpdateModel.return_value.get_changed_data.return_value,
        )
        model.persist_elements.assert_called_once_with(request)
        UpdateModel.assert_called_once_with(schedule_uuid)
        UpdateModel.return_value.get_changed_data.assert_called_once_with(request)

    @patch.object(rest_app, "UpdateModel")
    def test_persist_elements_outside_ts_App(self, UpdateModel):
        # schedule for Ptest.msp.Export
        schedule_uuid = "2c73f111-6a21-11eb-928a-3ce1a147c610"
        model = MagicMock(
            spec=rest_app.ElementsModel,
            context_object_id=schedule_uuid,
        )
        model.get_data.return_value = {"data": True}
        request = MagicMock(json={"runOutsideTSApp": True})
        self.assertEqual(
            rest_app.persist_elements(model, request),
            None,
        )
        model.persist_elements.assert_called_once_with(request)
        UpdateModel.assert_not_called()

    @patch.object(rest_app.ReadOnlyModel, "__new__", autospec=True)
    def test_get_read_only_model(self, ReadOnlyModel__new__):
        self.assertEqual(
            rest_app.get_read_only_model("request", "foo"),
            ReadOnlyModel__new__.return_value,
        )
        ReadOnlyModel__new__.assert_called_once_with(
            rest_app.ReadOnlyModel,
            "foo",
        )

    def test_get_read_only(self):
        model = MagicMock(spec=rest_app.ReadOnlyModel)
        self.assertEqual(
            rest_app.get_read_only(model, "request"), model.get_read_only.return_value
        )
        model.get_read_only.assert_called_once_with("request")


if __name__ == "__main__":
    unittest.main()
