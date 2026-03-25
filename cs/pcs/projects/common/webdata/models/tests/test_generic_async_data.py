#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects.common.webdata.models import generic_async_data


@pytest.mark.unit
class GenericAsyncDataModel(unittest.TestCase):
    def test___init__(self):
        "initializes model"
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        self.assertIsNone(generic_async_data.GenericAsyncDataModel.__init__(model))
        self.assertEqual(model.classdefs, {})
        self.assertEqual(model.tables, {})
        self.assertEqual(model.keynames, {})

    @mock.patch.object(
        generic_async_data.util,
        "get_classinfo",
        autospec=True,
        return_value=(mock.MagicMock(), "tbl"),
    )
    def test__resolve_class(self, get_classinfo):
        "resolves class info"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            classdefs={},
            tables={},
            keynames={},
        )
        self.assertIsNone(
            generic_async_data.GenericAsyncDataModel._resolve_class(model, "foo")
        )
        self.assertEqual(
            model.classdefs,
            {"foo": get_classinfo.return_value[0]},
        )
        self.assertEqual(
            model.tables,
            {"foo": get_classinfo.return_value[1]},
        )
        self.assertEqual(
            model.keynames,
            {"foo": get_classinfo.return_value[0].getKeyNames.return_value},
        )
        get_classinfo.assert_called_once_with("foo")
        get_classinfo.return_value[0].getKeyNames.assert_has_calls(
            [
                mock.call(),  # called two times, why?
            ]
        )

    def test_read_payload(self):
        "resolves class info for payload"
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        request = mock.MagicMock(
            json={
                "class1": "A",
                "class2": "B",
            }
        )
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.read_payload(model, request),
            {
                "class1": model._resolve_query.return_value,
                "class2": model._resolve_query.return_value,
            },
        )
        model._resolve_query.assert_has_calls(
            [
                mock.call("class1", "A"),
                mock.call("class2", "B"),
            ],
            any_order=True,
        )

    @mock.patch.object(generic_async_data.logging, "error")
    def test__resolve_query_missing_keys(self, error):
        "fails if 'keys' is missing"
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        query = {
            "fields": "F",
            "mapped": "M",
            "texts": "T",
        }

        with self.assertRaises(generic_async_data.HTTPBadRequest):
            generic_async_data.GenericAsyncDataModel._resolve_query(model, "foo", query)

        error.assert_called_once_with(
            "GenericAsyncDataModel request missing 'keys': %s",
            query,
        )
        model._resolve_class.assert_called_once_with("foo")

    @mock.patch.object(generic_async_data.util, "get_sql_condition")
    @mock.patch.object(generic_async_data, "values_from_rest_key")
    def test__resolve_query(self, values_from_rest_key, get_sql_condition):
        "resolve query for one classname"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            tables={"foo": "table"},
            keynames={"foo": "keynames"},
        )
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel._resolve_query(
                model,
                "foo",
                {
                    "keys": "AB",
                    "fields": "F",
                    "mapped": "M",
                    "texts": "T",
                },
            ),
            (get_sql_condition.return_value, "F", "M", "T"),
        )
        model._resolve_class.assert_called_once_with("foo")
        get_sql_condition.assert_called_once_with(
            "table", "keynames", 2 * [values_from_rest_key.return_value]
        )
        values_from_rest_key.assert_has_calls(
            [
                mock.call("A"),
                mock.call("B"),
            ]
        )

    @mock.patch.object(generic_async_data.sqlapi, "RecordSet2", autospec=True)
    def test__get_data(self, RecordSet2):
        "returns access-checked records"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            tables={"foo": "table"},
        )
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel._get_data(model, "foo", "a=o"),
            RecordSet2.return_value,
        )
        RecordSet2.assert_called_once_with("table", "a=o", access="read")

    @mock.patch.object(generic_async_data.util, "filter_dict", autospec=True)
    @mock.patch.object(generic_async_data.util, "get_rest_key", autospec=True)
    def test_get_fields(self, get_rest_key, filter_dict):
        "returns dict with requested fields only"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            keynames={"foo": ["k_a", "k_b"]},
            classdefs={"foo": "cldef"},
        )
        data = ["r_a", "r_b"]
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.get_fields(
                model, "foo", data, "fields"
            ),
            {get_rest_key.return_value: filter_dict.return_value},
        )
        get_rest_key.assert_has_calls(
            [
                mock.call("r_a", ["k_a", "k_b"]),
                mock.call("r_b", ["k_a", "k_b"]),
            ],
            any_order=True,
        )  # ignore calls to __hash__
        self.assertEqual(get_rest_key.call_count, 2)
        filter_dict.assert_has_calls(
            [
                mock.call("r_a", "fields", "cldef"),
                mock.call("r_b", "fields", "cldef"),
            ]
        )
        self.assertEqual(filter_dict.call_count, 2)

    @mock.patch.object(generic_async_data.util, "get_mapped_attrs", autospec=True)
    @mock.patch.object(generic_async_data.util, "get_rest_key", autospec=True)
    @mock.patch.object(generic_async_data.util, "get_mapped_referers", autospec=True)
    def test_get_mapped(self, get_mapped_referers, get_rest_key, get_mapped_attrs):
        "returns dict with mapped attributes"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            keynames={"foo": ["k_a", "k_b"]},
        )
        data = ["r_a", "r_b"]
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.get_mapped(
                model, "foo", data, "M"
            ),
            {get_rest_key.return_value: get_mapped_attrs.return_value},
        )
        get_mapped_referers.assert_called_once_with("foo", "M")
        get_rest_key.assert_has_calls(
            [
                mock.call("r_a", ["k_a", "k_b"]),
                mock.call("r_b", ["k_a", "k_b"]),
            ],
            any_order=True,
        )  # ignore calls to __hash__
        self.assertEqual(get_rest_key.call_count, 2)
        get_mapped_attrs.assert_has_calls(
            [
                mock.call("foo", "r_a", get_mapped_referers.return_value, "M"),
                mock.call("foo", "r_b", get_mapped_referers.return_value, "M"),
            ]
        )
        self.assertEqual(get_mapped_attrs.call_count, 2)

    @mock.patch.object(
        generic_async_data.util,
        "merge_results_str",
        autospec=True,
        # keep implementation, we just want to assert calls
        side_effect=generic_async_data.util.merge_results_str,
    )
    @mock.patch.object(
        generic_async_data.util, "get_rest_key", autospec=True, return_value="foo"
    )
    @mock.patch.object(generic_async_data.sqlapi, "RecordSet2", autospec=True)
    def test_get_text(self, RecordSet2, get_rest_key, merge_results_str):
        "returns dict with one resolved long text attribute"
        r_a = mock.MagicMock(
            spec=generic_async_data.sqlapi.Record,
            text="r_a.text ",
        )
        r_b = mock.MagicMock(
            spec=generic_async_data.sqlapi.Record,
            text="r_b.text ",
        )
        RecordSet2.return_value = [r_a, r_b]
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.get_text(
                model, ["k_a", "k_b"], "key_a, key_b", "cond", "tbl"
            ),
            {"foo": {"tbl": "r_a.text r_b.text "}},
        )
        RecordSet2.assert_called_once_with(
            "tbl",
            "cond",
            addtl="ORDER BY key_a, key_b, zeile",
        )
        get_rest_key.assert_has_calls(
            [
                mock.call(r_a, ["k_a", "k_b"]),
                mock.call(r_b, ["k_a", "k_b"]),
            ]
        )
        merge_results_str.assert_called_once_with(
            {"foo": "r_a.text "},
            {"foo": "r_b.text "},
        )

    @mock.patch.object(generic_async_data.logging, "exception", autospec=True)
    @mock.patch.object(
        generic_async_data.sqlapi,
        "RecordSet2",
        autospec=True,
        side_effect=generic_async_data.dberrors.DBConstraintViolation(1, 2, 3),
    )
    @testcase.without_error_logging
    def test_get_text_unknown(self, RecordSet2, exception):
        "fails if db table for text is missing"
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        with self.assertRaises(generic_async_data.HTTPBadRequest):
            generic_async_data.GenericAsyncDataModel.get_text(
                model, [], "K", "C", "tbl"
            )

        RecordSet2.assert_called_once_with(
            "tbl",
            "C",
            addtl="ORDER BY K, zeile",
        )
        exception.assert_called_once_with("get_text")

    @mock.patch.object(generic_async_data.util, "merge_results_dict", autospec=True)
    @mock.patch.object(generic_async_data.util, "get_sql_condition", autospec=True)
    def test_get_texts(self, get_sql_condition, merge_results_dict):
        "returns dict with resolved long texts"
        model = mock.MagicMock(
            spec=generic_async_data.GenericAsyncDataModel,
            tables={"foo": "table"},
            keynames={"foo": ["k_a", "k_b"]},
        )
        data = [
            {"k_a": "r_a_a", "k_b": "r_a_b"},
            {"k_a": "r_b_a", "k_b": "r_b_b"},
        ]
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.get_texts(
                model, "foo", data, "12"
            ),
            merge_results_dict.return_value,
        )
        get_sql_condition.assert_called_once_with(
            "table",
            ["k_a", "k_b"],
            [
                ["r_a_a", "r_a_b"],
                ["r_b_a", "r_b_b"],
            ],
        )
        merge_results_dict.assert_called_once_with(
            model.get_text.return_value,
            model.get_text.return_value,
        )
        model.get_text.assert_has_calls(
            [
                mock.call(
                    ["k_a", "k_b"], "k_a, k_b", get_sql_condition.return_value, "1"
                ),
                mock.call(
                    ["k_a", "k_b"], "k_a, k_b", get_sql_condition.return_value, "2"
                ),
            ]
        )
        self.assertEqual(model.get_text.call_count, 2)

    @mock.patch.object(generic_async_data.util, "merge_results_dict", autospec=True)
    def test_get_data(self, merge_results_dict):
        "returns dict with all resolved data"
        model = mock.MagicMock(spec=generic_async_data.GenericAsyncDataModel)
        model.read_payload.return_value = {
            "foo": ("cond", "fields", "mapped", "texts"),
        }
        self.assertEqual(
            generic_async_data.GenericAsyncDataModel.get_data(model, "request"),
            {"foo": merge_results_dict.return_value},
        )
        model.read_payload.assert_called_once_with("request")
        model._get_data.assert_called_once_with("foo", "cond")
        data = model._get_data.return_value
        model.get_fields.assert_called_once_with("foo", data, "fields")
        model.get_mapped.assert_called_once_with("foo", data, "mapped")
        model.get_texts.assert_called_once_with("foo", data, "texts")
        merge_results_dict.assert_called_once_with(
            model.get_fields.return_value,
            model.get_mapped.return_value,
            model.get_texts.return_value,
        )


if __name__ == "__main__":
    unittest.main()
