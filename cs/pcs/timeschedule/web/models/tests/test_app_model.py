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
from webob.exc import HTTPBadRequest, HTTPInternalServerError

from cs.pcs.timeschedule.web.models import app_model


@pytest.mark.unit
class AppModel(unittest.TestCase):
    def test__serialize_column_missing_attrs(self):
        "fails if column is missing attributes"
        model = MagicMock(spec=app_model.AppModel)
        with self.assertRaises(AttributeError) as error:
            app_model.AppModel._serialize_column(model, None)
        self.assertEqual(
            "'NoneType' object has no attribute 'label'", str(error.exception)
        )

    @patch.object(app_model.util, "get_label", autospec=True)
    def test__serialize_column(self, get_label):
        "serializes a column definition"
        column = MagicMock(
            visible=1,
            col_position=10,
            width="48px",
            id="my_col_jackson",
            label="L",
            component="frontend-component",
            show_baseline_data=False,
        )
        model = MagicMock(spec=app_model.AppModel)
        self.assertEqual(
            app_model.AppModel._serialize_column(
                model,
                column,
            ),
            {
                "visible": 1,
                "position": 10,
                "width": "48px",
                "id": "my_col_jackson",
                "label": get_label.return_value,
                "contentRenderer": "frontend-component",
                "showBaselineData": False,
            },
        )
        get_label.assert_has_calls([call("L")])

    @patch.object(app_model.ColumnDefinition, "ByGroup", return_value=None)
    def test__get_table_settings_not_iterable(self, ByGroup):
        "fails if columns are not iterable"
        model = MagicMock(
            spec=app_model.AppModel,
            column_group="GROUP",
        )
        with self.assertRaises(TypeError) as error:
            app_model.AppModel._get_table_settings(model)
        self.assertEqual("'NoneType' object is not iterable", str(error.exception))
        ByGroup.assert_called_once_with("GROUP")

    @patch.object(app_model.ColumnMapping, "ByColumns", side_effect=ValueError)
    @patch.object(app_model.ColumnDefinition, "ByGroup")
    def test__get_table_settings_columns_error(self, ByGroup, ByColumns):
        "fails if columns raise ValueError"
        model = MagicMock(
            spec=app_model.AppModel,
            column_group="GROUP",
        )
        with self.assertRaises(HTTPInternalServerError):
            app_model.AppModel._get_table_settings(model)
        ByGroup.assert_called_once_with("GROUP")
        ByColumns.assert_called_once_with("GROUP", [])

    @patch.object(app_model, "CDBClassDef")
    @patch.object(app_model.ColumnMapping, "ByColumns")
    @patch.object(app_model.ColumnDefinition, "ByGroup")
    def test__get_table_settings(self, ByGroup, ByColumns, CDBClassDef):
        "returns settings for frontend table"
        column_a = MagicMock(id="a")
        column_b = MagicMock(id="b")
        ByGroup.return_value = [column_a, column_b]
        model = MagicMock(
            spec=app_model.AppModel,
            plugins={"F": MagicMock(classname="foo", olc_attr="olc")},
            column_group="GROUP",
        )
        classDef = MagicMock()
        classDef.getDesignation = MagicMock(return_value="bar")
        classDef.getSubClassNames = MagicMock(return_value=[])
        CDBClassDef.return_value = classDef
        self.assertEqual(
            app_model.AppModel._get_table_settings(model),
            {
                "columns": [
                    model._serialize_column.return_value,
                    model._serialize_column.return_value,
                ],
                "mapping": ByColumns.return_value,
                "plugins": {
                    "foo": {
                        "label": "bar",
                        "olcFieldName": "olc",
                        "rootClassName": "foo",
                    }
                },
            },
        )
        ByGroup.assert_called_once_with("GROUP")
        ByColumns.assert_called_once_with("GROUP", ["a", "b"])
        model._serialize_column.assert_has_calls(
            [
                call(column_a),
                call(column_b),
            ]
        )
        CDBClassDef.assert_called_once_with("foo")
        classDef.getDesignation.assert_called_once()

    @patch.object(app_model, "CDBClassDef")
    @patch.object(app_model.ColumnMapping, "ByColumns")
    @patch.object(app_model.ColumnDefinition, "ByGroup")
    def test__get_table_settings_sub_classes(self, ByGroup, ByColumns, CDBClassDef):
        "returns settings for frontend table"
        column_a = MagicMock(id="a")
        column_b = MagicMock(id="b")
        ByGroup.return_value = [column_a, column_b]
        model = MagicMock(
            spec=app_model.AppModel,
            plugins={"F": MagicMock(classname="foo", olc_attr="olc")},
            column_group="GROUP",
        )
        classDef_rootClass = MagicMock()
        classDef_rootClass.getDesignation = MagicMock(return_value="bar")
        classDef_rootClass.getSubClassNames = MagicMock(return_value=["baz"])
        classDef_subClass = MagicMock()
        classDef_subClass.getDesignation = MagicMock(return_value="bam")
        CDBClassDef.side_effect = [classDef_rootClass, classDef_subClass]
        self.assertEqual(
            app_model.AppModel._get_table_settings(model),
            {
                "columns": [
                    model._serialize_column.return_value,
                    model._serialize_column.return_value,
                ],
                "mapping": ByColumns.return_value,
                "plugins": {
                    "foo": {
                        "label": "bar",
                        "rootClassName": "foo",
                        "olcFieldName": "olc",
                    },
                    "baz": {
                        "label": "bam",
                        "rootClassName": "foo",
                        "olcFieldName": "olc",
                    },
                },
            },
        )
        ByGroup.assert_called_once_with("GROUP")
        ByColumns.assert_called_once_with("GROUP", ["a", "b"])
        model._serialize_column.assert_has_calls(
            [
                call(column_a),
                call(column_b),
            ]
        )
        CDBClassDef.assert_has_calls([call("foo"), call("baz")])
        classDef_rootClass.getDesignation.assert_called_once()
        classDef_subClass.getDesignation.assert_called_once()

    @patch.object(app_model, "get_collection_app", autospec=True)
    def test_get_app_data_no_items(self, get_collection_app):
        "fails if user settings don't support __getitem__"
        request = MagicMock()
        model = MagicMock(
            spec=app_model.AppModel,
            context_object="foo",
            context_object_id="bar",
        )
        model.get_user_settings.return_value = None
        with self.assertRaises(TypeError) as error:
            app_model.AppModel.get_app_data(model, request)
        self.assertEqual("'NoneType' object is not subscriptable", str(error.exception))
        request.view.assert_called_once_with(
            "foo",
            app=get_collection_app.return_value,
            name="relship-target",
        )
        get_collection_app.assert_called_once_with(request)
        model.get_user_settings.assert_called_once_with("bar")

    @patch.object(app_model, "get_collection_app", autospec=True)
    def test_get_app_data_invalid(self, get_collection_app):
        "fails if user settings contain invalid value"
        request = MagicMock()
        model = MagicMock(
            spec=app_model.AppModel,
            context_object="foo",
            context_object_id="bar",
        )
        model.get_user_settings.return_value = {
            "tableWidth": 0,
        }
        with self.assertRaises(KeyError) as error:
            app_model.AppModel.get_app_data(model, request)
        self.assertEqual("'collapsedRows'", str(error.exception))
        request.view.assert_called_once_with(
            "foo",
            app=get_collection_app.return_value,
            name="relship-target",
        )
        get_collection_app.assert_called_once_with(request)
        model.get_user_settings.assert_called_once_with("bar")

    @patch.object(app_model, "get_collection_app", autospec=True)
    def test_get_app_data(self, get_collection_app):
        "serializes application-level settings"
        request = MagicMock()
        model = MagicMock(
            spec=app_model.AppModel,
            context_object="foo",
            context_object_id="bar",
        )
        model.get_user_settings.return_value = {
            "tableWidth": "unused",
            "collapsedRows": "C",
        }
        self.assertEqual(
            app_model.AppModel.get_app_data(model, request),
            {
                "collapsedRows": "C",
                "contextObject": request.view.return_value,
                "table": model._get_table_settings.return_value,
            },
        )
        request.view.assert_called_once_with(
            "foo",
            app=get_collection_app.return_value,
            name="relship-target",
        )
        get_collection_app.assert_called_once_with(request)
        model.get_user_settings.assert_called_once_with("bar")
        model._get_table_settings.assert_called_once_with()

    def test__update_user_settings_attr_err(self):
        "fails if old settings are not a dict"
        model = MagicMock(
            spec=app_model.AppModel,
            context_object_id="foo",
        )
        model.get_user_settings.return_value = None
        with self.assertRaises(AttributeError) as error:
            app_model.AppModel._update_user_settings(model)
        self.assertEqual(
            "'NoneType' object has no attribute 'update'", str(error.exception)
        )
        model.get_user_settings.assert_called_once_with("foo")

    def test__update_user_settings_type_err(self):
        "fails if new settings are not JSON-serializable"
        model = MagicMock(
            spec=app_model.AppModel,
            context_object_id="foo",
        )
        model.get_user_settings.return_value = {}
        with self.assertRaises(TypeError) as error:
            app_model.AppModel._update_user_settings(
                model,
                foo=max,
            )
        self.assertEqual(
            ("Object of type builtin_function_or_method is not JSON serializable"),
            str(error.exception),
        )
        model.get_user_settings.assert_called_once_with("foo")

    @patch.object(app_model.util, "PersonalSettings", autospec=True)
    @patch.object(app_model.json, "dumps", autospec=True)
    def test__update_user_settings(self, dumps, PersonalSettings):
        "persists existing settings merged with provided updates"
        expected = {
            "foo": "bar",
            "bar": "foos",
            "baz": "lee",
        }
        model = MagicMock(
            spec=app_model.AppModel,
            setting_id1="ID1",
            context_object_id="ID2",
        )
        model.get_user_settings.return_value = {
            "foo": "foo",
            "bar": "foos",
        }
        self.assertEqual(
            app_model.AppModel._update_user_settings(
                model,
                foo="bar",
                baz="lee",
            ),
            expected,
        )
        model.get_user_settings.assert_called_once_with("ID2")
        dumps.assert_called_once_with(expected)
        PersonalSettings.assert_called_once_with()
        PersonalSettings.return_value.setValue.assert_called_once_with(
            "ID1",
            "ID2",
            dumps.return_value,
        )

    def test_update_app_data_no_json(self):
        "fails if request is missing json"
        model = MagicMock(spec=app_model.AppModel)
        with self.assertRaises(AttributeError) as error:
            app_model.AppModel.update_app_data(model, None)
        self.assertEqual(
            "'NoneType' object has no attribute 'json'", str(error.exception)
        )

    def test_update_app_data_no_has_key(self):
        "fails if request.json is not a dict"
        request = MagicMock(json=None)
        model = MagicMock(spec=app_model.AppModel)
        with self.assertRaises(TypeError) as error:
            app_model.AppModel.update_app_data(
                model,
                request,
            )
        self.assertEqual("'NoneType' object is not subscriptable", str(error.exception))

    def test_update_app_data(self):
        "updates app settings"
        request = MagicMock(
            json={
                "tableWidth": "unused",
                "collapsedRows": "C",
            }
        )
        model = MagicMock(spec=app_model.AppModel)
        self.assertIsNone(
            app_model.AppModel.update_app_data(
                model,
                request,
            )
        )
        model._update_user_settings.assert_called_once_with(collapsedRows="C")

    @patch.object(app_model.logging, "error", autospec=True)
    def test_update_app_data_missing_collapsed(self, logging_error):
        "fails if JSON is missing collapsedRows"
        json = {
            "tableWidth": "T",
        }
        request = MagicMock(json=json)
        model = MagicMock(spec=app_model.AppModel)
        # do not assert error message as it is constant and generic
        with self.assertRaises(HTTPBadRequest):
            app_model.AppModel.update_app_data(
                model,
                request,
            )
        logging_error.assert_called_once_with(
            "update_app_data: invalid JSON payload: %s",
            json,
        )


if __name__ == "__main__":
    unittest.main()
