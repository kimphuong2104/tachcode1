# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import pytest
from cdb import testcase
from cdb.util import ErrorMessage
from mock import MagicMock, call, patch

from cs.pcs.timeschedule.web import mapping


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class ColumnDefinition(unittest.TestCase):
    @patch.object(mapping.ColumnDefinition, "KeywordQuery")
    def test_ByGroup(self, KeywordQuery):
        # cache miss
        mapping.ColumnDefinition.ByGroup.cache_clear()
        self.assertEqual(
            mapping.ColumnDefinition.ByGroup("GROUP"), KeywordQuery.return_value
        )
        KeywordQuery.assert_called_once_with(
            colgroup="GROUP",
            order_by="col_position",
        )
        # cache hit
        self.assertEqual(
            mapping.ColumnDefinition.ByGroup("GROUP"), KeywordQuery.return_value
        )
        KeywordQuery.assert_called_once_with(
            colgroup="GROUP",
            order_by="col_position",
        )


@pytest.mark.unit
class ColumnMapping(unittest.TestCase):
    @patch.object(mapping.ColumnMapping, "__txt_field__", "foo")
    @patch.object(mapping.ColumnMapping, "GetText")
    @patch.object(mapping.json, "loads")
    def test_get_json_value(self, loads, GetText):
        "returns JSON-deserialized long text"
        colmap = mapping.ColumnMapping()
        self.assertEqual(colmap.get_json_value(), loads.return_value)
        GetText.assert_called_once_with("foo")
        loads.assert_called_once_with(GetText.return_value)

    def test_GetFieldWhitelist_invalid_plugin(self):
        "fails if plugin does not specify required fields"
        plugin = MagicMock()
        plugin.GetRequiredFields.return_value = None

        with self.assertRaises(TypeError) as error:
            mapping.ColumnMapping.GetFieldWhitelist(plugin)

        self.assertEqual("'NoneType' object is not iterable", str(error.exception))

    @patch.object(mapping.ColumnMapping, "KeywordQuery")
    def test_GetFieldWhitelist_invalid_mapping(self, KeywordQuery):
        "fails if mapping does not contain valid mapping"
        plugin = MagicMock()
        plugin.GetRequiredFields.return_value = set()

        invalid_mapping = MagicMock()
        invalid_mapping.get_json_value.return_value = None
        KeywordQuery.return_value = [invalid_mapping]

        with self.assertRaises(AttributeError) as error:
            mapping.ColumnMapping.GetFieldWhitelist(plugin)

        self.assertEqual(
            "'NoneType' object has no attribute 'values'", str(error.exception)
        )
        KeywordQuery.assert_called_once_with(classname=plugin.classname)

    @patch.object(mapping.ColumnMapping, "__component__", "#")
    @patch("cs.pcs.timeschedule.web.rest_objects.REST_WHITELIST", set(["a", "b"]))
    @patch.object(mapping.ColumnMapping, "KeywordQuery")
    def test_GetFieldWhitelist(self, KeywordQuery):
        "combines whitelist from plugin and mapping, removes global list"
        plugin = MagicMock()
        plugin.GetRequiredFields.return_value = set(["b", "c", "#"])

        simple_mapping = MagicMock()
        simple_mapping.get_json_value.return_value = "d"
        complex_mapping = MagicMock()
        complex_mapping.get_json_value.return_value = {"foo": "e"}
        KeywordQuery.return_value = [simple_mapping, complex_mapping]

        self.assertEqual(
            mapping.ColumnMapping.GetFieldWhitelist(plugin),
            set(["cdb_object_id", "c", "d", "e"]),
        )

        simple_mapping.get_json_value.assert_called_once_with()
        complex_mapping.get_json_value.assert_called_once_with()
        plugin.GetRequiredFields.assert_called_once_with()
        KeywordQuery.assert_called_once_with(classname=plugin.classname)

    @patch.object(mapping.ColumnMapping, "KeywordQuery")
    @patch.object(mapping, "get_restname")
    def test_ByColumns(self, get_restname, KeywordQuery):
        "returns mapping for given colgroup and ids"
        get_restname.return_value = "restname"
        shadowed_mapping = MagicMock(classname="class", id="simple")
        shadowed_mapping.get_json_value.return_value = "shadowed"
        simple_mapping = MagicMock(classname="class", id="simple", readonly=1)
        simple_mapping.get_json_value.return_value = "foo"
        complex_mapping = MagicMock(classname="class", id="complex", readonly=0)
        complex_mapping.get_json_value.return_value = {"BAR": "bar"}
        KeywordQuery.return_value = [
            shadowed_mapping,
            simple_mapping,
            complex_mapping,
        ]
        self.assertEqual(
            mapping.ColumnMapping.ByColumns("g", ["i"]),
            {
                "restname": {
                    "simple": {"field": "foo", "readonly": True},
                    "complex": {"field": {"BAR": "bar"}, "readonly": False},
                }
            },
        )
        KeywordQuery.assert_called_once_with(
            colgroup="g",
            id=["i"],
            order_by="classname",
        )
        get_restname.assert_has_calls([call("class"), call("class"), call("class")])
        simple_mapping.get_json_value.assert_called_once_with()
        complex_mapping.get_json_value.assert_called_once_with()

    def test_validate_missing_dialog_attr(self):
        "fails if long text is missing in ctx.dialog"
        colmap = mapping.ColumnMapping()
        colmap.__txt_field__ = "foo"
        ctx = MagicMock(dialog={})

        with self.assertRaises(KeyError) as error:
            colmap.validate(ctx)

        self.assertEqual("'foo'", str(error.exception))

    def test_validate_missing_invalid_json(self):
        "fails if long text value is not JSON-deserializable"
        colmap = mapping.ColumnMapping()
        colmap.__txt_field__ = "foo"
        ctx = MagicMock(dialog={"foo": "'"})

        with self.assertRaises(ErrorMessage) as error:
            colmap.validate(ctx)

        self.assertEqual(
            "Frontend-Mapping ist kein gültiges JSON.", str(error.exception)
        )

    def test_validate_missing_invalid_mapping(self):
        "fails if long text value is invalid mapping"
        colmap = mapping.ColumnMapping()
        colmap.__txt_field__ = "foo"
        ctx = MagicMock(dialog={"foo": '{"complex": null}'})

        with self.assertRaises(ErrorMessage) as error:
            colmap.validate(ctx)

        self.assertEqual(
            "Frontend-Mapping ist weder string noch dict mit ausschließlich "
            "string-Werten.",
            str(error.exception),
        )

    def test_validate_str(self):
        "recognizes simple string as valid"
        colmap = mapping.ColumnMapping()
        colmap.__txt_field__ = "foo"
        ctx = MagicMock(dialog={"foo": '"simple"'})
        self.assertIsNone(colmap.validate(ctx))

    def test_validate_dict(self):
        "recognizes dict with string values as valid"
        colmap = mapping.ColumnMapping()
        colmap.__txt_field__ = "foo"
        ctx = MagicMock(dialog={"foo": '{"complex": "O(N2)"}'})
        self.assertIsNone(colmap.validate(ctx))


if __name__ == "__main__":
    unittest.main()
