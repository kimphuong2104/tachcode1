#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.taskmanager.web import util


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test__convert_rest_id(self):
        pattern = mock.MagicMock()
        self.assertEqual(
            util._convert_rest_id(pattern, "foo"),
            pattern.match.return_value.groupdict.return_value,
        )
        pattern.match.assert_called_once_with("foo")

    def test__convert_rest_id_no_match(self):
        pattern = mock.MagicMock()
        pattern.match.return_value = None
        self.assertEqual(
            util._convert_rest_id(pattern, "foo"),
            {},
        )
        pattern.match.assert_called_once_with("foo")

    def test_get_classname_from_rest_id(self):
        self.assertEqual(
            util.get_classname_from_rest_id("base/api/v1/class/foo/bar"),
            "foo",
        )

    def test_get_classname_from_rest_id_no_match(self):
        self.assertEqual(
            util.get_classname_from_rest_id("base/api/v1/class/Foo/bar"),
            None,
        )

    @mock.patch.object(util, "get_object_from_rest_name")
    def test__get_uuid(self, get_object_from_rest_name):
        self.assertEqual(
            util._get_uuid("foo", "bar"),
            get_object_from_rest_name.return_value.cdb_object_id,
        )
        get_object_from_rest_name.assert_called_once_with("foo", "bar")

    @mock.patch.object(util.logging, "error")
    @mock.patch.object(util, "get_object_from_rest_name", return_value=None)
    def test__get_uuid_no_object(self, get_object_from_rest_name, error):
        self.assertEqual(
            util._get_uuid("foo", "bar"),
            None,
        )
        error.assert_called_once()
        get_object_from_rest_name.assert_called_once_with("foo", "bar")

    @mock.patch.object(util, "decode_key_component")
    def test__decode_pkeys(self, decode_key_component):
        self.assertEqual(
            util._decode_pkeys("fo'o"),
            decode_key_component.return_value,
        )
        decode_key_component.assert_called_once_with("fo''o")

    def test__decode_pkeys_no_key(self):
        self.assertEqual(
            util._decode_pkeys(""),
            None,
        )

    @mock.patch.object(util, "_get_uuid")
    def test_get_uuid_from_rest_id(self, _get_uuid):
        self.assertEqual(
            util.get_uuid_from_rest_id("base/api/v1/collection/foo/b~C3~A4r@1"),
            _get_uuid.return_value,
        )
        _get_uuid.assert_called_once_with("foo", "bär@1")

    def test_get_uuid_from_rest_id_no_match(self):
        self.assertEqual(
            util.get_uuid_from_rest_id("base/api/v1/class/Foo/bar@1/"),
            None,
        )

    def test_get_pkeys_from_rest_id(self):
        self.assertEqual(
            util.get_pkeys_from_rest_id("base/api/v1/collection/foo/b~C3~A4r@1"),
            "bär@1",
        )

    def test_get_pkeys_from_rest_id_no_match(self):
        self.assertEqual(
            util.get_pkeys_from_rest_id("base/api/v1/class/Foo/bar@1/"),
            None,
        )

    @mock.patch.object(util, "get_v1")
    def test_get_collection_app(self, get_v1):
        self.assertEqual(
            util.get_collection_app("foo"),
            get_v1.return_value.child.return_value,
        )
        get_v1.assert_called_once_with("foo")
        get_v1.return_value.child.assert_called_once_with("collection")

    @mock.patch.object(util, "get_v1")
    @mock.patch.object(util, "_get_dummy_request", return_value="dummy")
    def test_get_collection_app_dummy(self, _get_dummy_request, get_v1):
        self.assertEqual(
            util.get_collection_app(None),
            get_v1.return_value.child.return_value,
        )
        get_v1.assert_called_once_with("dummy")
        get_v1.return_value.child.assert_called_once_with("collection")

    def test_get_rest_object_no_object(self):
        self.assertIsNone(util.get_rest_object(None, None, None))

    def test_get_rest_object(self):
        request = mock.MagicMock()
        self.assertEqual(
            util.get_rest_object("obj", "app", request),
            request.view.return_value,
        )
        request.view.assert_called_once_with("obj", app="app", name="relship-target")

    @mock.patch.object(util, "_get_dummy_request")
    def test_get_rest_object_dummy(self, _get_dummy_request):
        self.assertEqual(
            util.get_rest_object("obj", "app", None),
            _get_dummy_request.return_value.view.return_value,
        )
        _get_dummy_request.return_value.view.assert_called_once_with(
            "obj", app="app", name="relship-target"
        )

    def test_get_rest_key_from_key(self):
        result = "føö"
        result = result.encode("utf-8")
        result = result.decode("latin-1")
        self.assertEqual(util.get_rest_key_from_key(result), "f~C3~B8~C3~B6")

    @mock.patch.object(util, "get_object_rest_id")
    @mock.patch.object(util, "ByID")
    def test_get_rest_id_from_uuid(self, ByID, get_object_rest_id):
        self.assertEqual(
            util.get_rest_id_from_uuid("foo", "R"),
            get_object_rest_id.return_value,
        )
        get_object_rest_id.assert_called_once_with(ByID.return_value, "R")

    @mock.patch.object(util, "ByID", return_value=None)
    def test_get_rest_id_from_uuid_no_object(self, ByID):
        self.assertEqual(
            util.get_rest_id_from_uuid("foo", "R"),
            None,
        )

    @mock.patch.object(util, "rest_key", return_value="key")
    @mock.patch.object(util, "rest_name", return_value="name")
    def test_get_object_rest_id(self, rest_name, rest_key):
        request = mock.MagicMock(application_url="base")
        self.assertEqual(
            util.get_object_rest_id("obj", request),
            "base/api/v1/collection/name/key",
        )
        rest_name.assert_called_once_with("obj")
        rest_key.assert_called_once_with("obj")

    @mock.patch.object(util, "rest_key", return_value="key")
    @mock.patch.object(util, "rest_name", return_value="name")
    def test_get_object_ui_link(self, rest_name, rest_key):
        request = mock.MagicMock(application_url="base")
        self.assertEqual(
            util.get_object_ui_link("obj", request),
            "base/info/name/key",
        )
        rest_name.assert_called_once_with("obj")
        rest_key.assert_called_once_with("obj")

    def test_get_class_rest_id(self):
        request = mock.MagicMock(application_url="base")
        self.assertEqual(
            util.get_class_rest_id("classname", request),
            "base/api/v1/class/classname",
        )

    def test_partition(self):
        self.assertEqual(
            list(util.partition("foo", 2)),
            ["fo", "o"],
        )

    def test_partition_invalid_size(self):
        with self.assertRaises(ValueError):
            list(util.partition("foo", 0))

    def test_format_in_condition(self):
        self.assertEqual(
            util.format_in_condition("col", "abc", 2),
            "col IN ('a','b') OR col IN ('c')",
        )

    def test_format_in_condition_no_values(self):
        self.assertEqual(util.format_in_condition("col", None), "1=0")

    @mock.patch.object(
        util.sqlapi,
        "RecordSet2",
        return_value=[
            {"a": "one", "b": "eins"},
            {"a": "two", "b": "eins"},
            {"a": "one", "b": "zwei"},
        ],
    )
    def test_get_grouped_data(self, RecordSet2):
        self.assertEqual(
            util.get_grouped_data("T", "C", "a", "b", foo="bar"),
            {
                "one": {
                    "eins": [{"a": "one", "b": "eins"}],
                    "zwei": [{"a": "one", "b": "zwei"}],
                },
                "two": {
                    "eins": [{"a": "two", "b": "eins"}],
                },
            },
        )
        RecordSet2.assert_called_once_with("T", "C", access="read")


if __name__ == "__main__":
    unittest.main()
