#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from mock import MagicMock, call, patch

from cs.pcs.projects.common import rest_objects
from cs.pcs.projects.project_structure.util import PCS_RECORD


def identity(arg):
    return arg


@pytest.mark.unit
class Utility(unittest.TestCase):
    @patch.object(rest_objects, "dump_value", autospec=True)
    @patch.object(rest_objects, "_REPLACEMENTS", {"\xc3": "x", "\xa4": "o"})
    def test_rest_key(self, dump_value):
        "returns rest key"
        record = MagicMock()
        record.thead.dbkeys.return_value = "ab"
        dump_value.return_value = "ä"
        self.assertEqual(rest_objects.rest_key(record), "xo@xo")
        record.thead.dbkeys.assert_called_once_with()
        self.assertEqual(record.thead.dbkeys.call_count, 1)
        dump_value.assert_has_calls(2 * [call(record.__getitem__.return_value)])
        self.assertEqual(dump_value.call_count, 2)

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects.Class, "ByRelation", return_value=None)
    def test_get_classname_not_found(self, ByRelation, error):
        "returns None for unknown class"
        rest_objects.get_classname.cache_clear()
        # cache miss
        self.assertIsNone(rest_objects.get_classname("foo"))
        # cache hit
        self.assertIsNone(rest_objects.get_classname("foo"))
        ByRelation.assert_called_once_with("foo")
        error.assert_called_once_with(
            "could not determine classname for relation: %s", "foo"
        )

    # can't autospec classmethod ByRelation in Py2 :(
    @patch.object(rest_objects.Class, "ByRelation")
    def test_get_classname(self, ByRelation):
        "returns classname for given relation"
        rest_objects.get_classname.cache_clear()
        # cache miss
        self.assertEqual(
            rest_objects.get_classname("foo"), ByRelation.return_value.classname
        )
        # cache hit
        self.assertEqual(
            rest_objects.get_classname("foo"), ByRelation.return_value.classname
        )
        ByRelation.assert_called_once_with("foo")

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects, "rest_name_for_class_name", autospec=True)
    def test_get_rest_sysattr_patterns_none(self, rest_name_for_class_name, error):
        "logs error if no classname given"
        rest_objects.get_rest_sysattr_patterns.cache_clear()
        # cache miss
        self.assertIsNone(rest_objects.get_rest_sysattr_patterns(None))
        # cache hit
        self.assertIsNone(rest_objects.get_rest_sysattr_patterns(None))
        self.assertEqual(rest_name_for_class_name.call_count, 0)
        error.assert_called_once_with(
            "could not get REST system attribute patterns for classname: %s",
            None,
        )

    @patch.object(
        rest_objects, "rest_name_for_class_name", return_value="bar", autospec=True
    )
    def test_get_rest_sysattr_patterns(self, rest_name_for_class_name):
        "returns system attribute patterns"
        expected = {
            "@id": "{base}/api/v1/collection/bar/{restkey}",
            "@context": "{base}/api/v1/context/foo",
            "@type": "{base}/api/v1/class/foo",
            "system:classname": "foo",
            "system:navigation_id": "{restkey}",
            "system:ui_link": "{base}/info/bar/{restkey}",
        }
        rest_objects.get_rest_sysattr_patterns.cache_clear()
        # cache miss
        self.assertEqual(rest_objects.get_rest_sysattr_patterns("foo"), expected)
        # cache hit
        self.assertEqual(rest_objects.get_rest_sysattr_patterns("foo"), expected)
        rest_name_for_class_name.assert_called_once_with("foo")

    @patch.object(rest_objects, "kOperationShowObject", "info")
    @patch.object(rest_objects, "CDBClassDef", autospec=True)
    @patch.object(rest_objects, "Cdbcmsg", autospec=True)
    def test_get_cdbpc_url(self, Cdbcmsg, CDBClassDef):
        "returns legacy URL"
        CDBClassDef.return_value.getKeyNames.return_value = ["a", "b"]
        self.assertEqual(
            rest_objects.get_cdbpc_url({"a": "A", "b": "B"}, "foo"),
            Cdbcmsg.return_value.cdbwin_url.return_value,
        )
        Cdbcmsg.assert_called_once_with("foo", "info", True)
        CDBClassDef.assert_called_once_with("foo")
        CDBClassDef.return_value.getPrimaryTable.assert_called_once_with()
        table_name = CDBClassDef.return_value.getPrimaryTable.return_value
        Cdbcmsg.return_value.add_item.assert_has_calls(
            [
                call("a", table_name, "A"),
                call("b", table_name, "B"),
            ]
        )
        self.assertEqual(Cdbcmsg.return_value.add_item.call_count, 2)
        Cdbcmsg.return_value.cdbwin_url.assert_called_once_with()

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(
        rest_objects, "get_rest_sysattr_patterns", autospec=True, return_value=None
    )
    def test_get_rest_sysattrs_no_patterns(self, get_rest_sysattr_patterns, error):
        "returns empty system attributes if no patterns found"
        request = MagicMock()
        self.assertEqual(rest_objects.get_rest_sysattrs("record", "foo", request), {})
        get_rest_sysattr_patterns.assert_called_once_with("foo")
        error.assert_called_once_with(
            "could not get REST system attributes for classname: %s", "foo"
        )

    @patch.object(rest_objects, "get_cdbpc_url", autospec=True)
    @patch.object(rest_objects, "is_cdbpc", return_value=True)
    @patch.object(rest_objects, "unquote", autospec=True)
    @patch.object(rest_objects, "rest_key", autospec=True)
    @patch.object(
        rest_objects,
        "get_rest_sysattr_patterns",
        autospec=True,
        return_value={
            "_base": "{base}",
            "_restkey": "{restkey}",
        },
    )
    def test_get_rest_sysattrs_cdbpc(
        self,
        get_rest_sysattr_patterns,
        rest_key,
        unquote,
        is_cdbpc,
        get_cdbpc_url,
    ):
        "returns system attributes (CDBPC)"
        request = MagicMock()
        self.assertEqual(
            rest_objects.get_rest_sysattrs("record", "foo", request),
            {
                "_base": unquote.return_value,
                "_restkey": unquote.return_value,
                "system:ui_link": unquote.return_value,
            },
        )
        get_cdbpc_url.assert_called_once_with("record", "foo")
        get_rest_sysattr_patterns.assert_called_once_with("foo")
        rest_key.assert_called_once_with("record")
        unquote.assert_has_calls(
            [
                call(f"{request.application_url}"),
                call(f"{rest_key.return_value}"),
                call(get_cdbpc_url.return_value.format.return_value),
            ],
            any_order=True,
        )
        self.assertEqual(unquote.call_count, 3)

    @patch.object(rest_objects, "unquote", autospec=True)
    @patch.object(rest_objects, "rest_key", autospec=True)
    @patch.object(
        rest_objects,
        "get_rest_sysattr_patterns",
        autospec=True,
        return_value={
            "_base": "{base}",
            "_restkey": "{restkey}",
        },
    )
    def test_get_rest_sysattrs(self, get_rest_sysattr_patterns, rest_key, unquote):
        "returns system attributes"
        request = MagicMock()
        self.assertEqual(
            rest_objects.get_rest_sysattrs("record", "foo", request),
            {
                "_base": unquote.return_value,
                "_restkey": unquote.return_value,
            },
        )
        get_rest_sysattr_patterns.assert_called_once_with("foo")
        rest_key.assert_called_once_with("record")
        unquote.assert_has_calls(
            [
                call(f"{request.application_url}"),
                call(f"{rest_key.return_value}"),
            ],
            any_order=True,
        )
        self.assertEqual(unquote.call_count, 2)

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects, "rest_key", autospec=True)
    @patch.object(rest_objects, "get_classname", autospec=True)
    @patch.object(
        rest_objects, "get_rest_sysattr_patterns", autospec=True, return_value={}
    )
    @patch.object(rest_objects, "unquote", autospec=True)
    def test_get_restlinks_in_batch_err(
        self, unquote, get_rest_sysattr_patterns, get_classname, rest_key, log_error
    ):
        "fails if classname cannot be determined"
        record_a = MagicMock(cdb_object_id="a")
        record_b = MagicMock(cdb_object_id="b")
        tuples = [("rel_a", record_a), ("rel_b", record_b)]
        request = MagicMock()

        with self.assertRaises(ValueError) as error:
            rest_objects.get_restlinks_in_batch(tuples, request)

        error_msg = f"cannot get links: '{tuples}', '{request}'"
        self.assertEqual(error_msg, str(error.exception))
        log_error.assert_called_once_with(error_msg, exc_info=1)

        get_classname.assert_called_once_with("rel_a")
        get_rest_sysattr_patterns.assert_called_once_with(
            get_classname.return_value,
        )
        self.assertEqual(unquote.call_count, 0)

    @patch.object(rest_objects, "rest_key", autospec=True)
    @patch.object(rest_objects, "get_classname", autospec=True)
    @patch.object(
        rest_objects,
        "get_rest_sysattr_patterns",
        autospec=True,
        return_value={"@id": "{base}/{restkey}"},
    )
    @patch.object(rest_objects, "unquote", autospec=True)
    def test_get_restlinks_in_batch(
        self, unquote, get_rest_sysattr_patterns, get_classname, rest_key
    ):
        "returns restlinks dict"
        record_a = MagicMock(cdb_object_id="a")
        record_b = MagicMock(cdb_object_id="b")
        tuples = [("rel_a", record_a), ("rel_b", record_b)]

        request = MagicMock()
        self.assertEqual(
            rest_objects.get_restlinks_in_batch(tuples, request),
            {
                "a": unquote.return_value,
                "b": unquote.return_value,
            },
        )
        get_classname.assert_has_calls([call("rel_a"), call("rel_b")])
        self.assertEqual(get_classname.call_count, 2)
        get_rest_sysattr_patterns.assert_has_calls(
            [
                call(get_classname.return_value),
                call(get_classname.return_value),
            ]
        )
        self.assertEqual(get_rest_sysattr_patterns.call_count, 2)
        link = f"{request.application_url}/{rest_key.return_value}"
        unquote.assert_has_calls([call(link), call(link)])
        self.assertEqual(unquote.call_count, 2)

    def test_get_project_id_in_batch(self):
        "returns mapped project Ids"
        record_a = MagicMock(cdb_object_id="oid_a", cdb_project_id="pid_a")
        record_b = MagicMock(cdb_object_id="oid_b", cdb_project_id="pid_b")
        records = [
            PCS_RECORD("a", record_a),
            PCS_RECORD("b", record_b),
        ]
        self.assertEqual(
            rest_objects.get_project_id_in_batch(records, "request"),
            {"oid_a": "pid_a", "oid_b": "pid_b"},
        )


if __name__ == "__main__":
    unittest.main()
