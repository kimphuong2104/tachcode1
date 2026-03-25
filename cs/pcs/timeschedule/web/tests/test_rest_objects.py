#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from mock import MagicMock, call, patch

from cs.pcs.timeschedule.web import rest_objects


def identity(arg):
    return arg


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test_get_rest_objects_no_iter(self):
        "fails if record_tuples are not iterable"
        with self.assertRaises(TypeError) as error:
            rest_objects.get_rest_objects("foo", None, None, "bar")
        self.assertEqual("'NoneType' object is not iterable", str(error.exception))

    def test_get_rest_objects_plugin_no_dict(self):
        "fails if plugin is no dict"
        with self.assertRaises(TypeError) as error:
            rest_objects.get_rest_objects(None, None, [("foo", "bar")], None)
        self.assertEqual("'NoneType' object is not subscriptable", str(error.exception))

    def test_get_rest_objects_missing_plugin(self):
        "fails if plugin is missing"
        with self.assertRaises(KeyError) as error:
            rest_objects.get_rest_objects({}, None, [("foo", "bar")], None)
        self.assertEqual("'foo'", str(error.exception))

    @patch.object(rest_objects, "record2rest_object", autospec=True)
    def test_get_rest_objects(self, record2rest_object):
        "returns rest objects"
        plugins = {
            "a": "plugin_a",
            "b": "plugin_b",
        }
        records = [
            ("a", "record_a"),
            ("b", "record_b"),
        ]
        self.assertEqual(
            rest_objects.get_rest_objects(plugins, "CG", records, "request"),
            2 * [record2rest_object.return_value],
        )
        record2rest_object.assert_has_calls(
            [
                call("plugin_a", "CG", "record_a", "request"),
                call("plugin_b", "CG", "record_b", "request"),
            ]
        )
        self.assertEqual(record2rest_object.call_count, 2)

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects, "is_cdb_pq", autospec=True)
    def test_get_sqltype_long_text(self, is_cdb_pq, error):
        "returns None for long_text"
        adef = MagicMock()
        adef.is_text.return_value = True
        self.assertIsNone(rest_objects.get_sqltype(adef))
        error.assert_called_once_with(
            "'%s': cannot handle %s attribute '%s'",
            adef.getClassDef.return_value.getClassname.return_value,
            "text",
            adef.getIdentifier.return_value,
        )
        self.assertEqual(is_cdb_pq.call_count, 0)

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects, "is_cdb_pq", autospec=True, return_value=True)
    def test_get_sqltype_pq(self, is_cdb_pq, error):
        "returns None for physical quantity"
        adef = MagicMock()
        adef.is_text.return_value = False
        adef.is_mapped.return_value = False
        adef.is_joined.return_value = False
        adef.is_multilang.return_value = False
        adef.is_virtual.return_value = False
        self.assertIsNone(rest_objects.get_sqltype(adef))
        is_cdb_pq.assert_called_once_with(adef.getSQLType.return_value)
        error.assert_called_once_with(
            "'%s': cannot handle PQ '%s'",
            adef.getClassDef.return_value.getClassname.return_value,
            adef.getIdentifier.return_value,
        )

    @patch.object(rest_objects, "UNSUPPORTED_SQL_TYPES", [])
    @patch.object(rest_objects, "is_cdb_pq", autospec=True, return_value=False)
    def test_get_sqltype(self, is_cdb_pq):
        "returns sqltype"
        adef = MagicMock()
        self.assertEqual(rest_objects.get_sqltype(adef), adef.getSQLType.return_value)
        is_cdb_pq.assert_called_once_with(adef.getSQLType.return_value)

    @patch.object(rest_objects.logging, "error", autospec=True)
    @patch.object(rest_objects, "get_sqltype", autospec=True)
    @patch.object(rest_objects, "CDBClassDef", autospec=True)
    @patch.object(
        rest_objects.ColumnMapping,
        "GetFieldWhitelist",
        # "b" included twice intentionally
        return_value=["pq", "txt", "a", "b", "b", "invisible", "missing"],
    )
    def test_get_attributes(self, GetFieldWhitelist, CDBClassDef, get_sqltype, error):
        "returns whitelisted, supported attributes, logs missing"

        def _get_sqltype(adef):
            if adef.getName() in ["pq", "txt"]:
                return None
            return 1

        get_sqltype.side_effect = _get_sqltype
        adef_pq = MagicMock()
        adef_pq.getName.return_value = "pq"
        adef_txt = MagicMock()
        adef_txt.getName.return_value = "txt"
        adef_a = MagicMock()
        adef_a.getName.return_value = "a"
        adef_b = MagicMock()
        adef_b.getName.return_value = "b"
        adef_invisible = MagicMock()
        adef_invisible.getName.return_value = "invisible"
        adef_invisible.rest_visible.return_value = False
        adef_not_whitelisted = MagicMock()
        adef_not_whitelisted.getName.return_value = "not whitelisted"
        CDBClassDef.return_value.getAttributeDefs.return_value = [
            # adef_a included twice intentionally
            adef_pq,
            adef_txt,
            adef_a,
            adef_a,
            adef_b,
            adef_invisible,
            adef_not_whitelisted,
        ]
        plugin = MagicMock()
        self.assertEqual(
            rest_objects.get_attributes(plugin, "GROUP"), [("a", 1), ("a", 1), ("b", 1)]
        )
        GetFieldWhitelist.assert_called_once_with(plugin, colgroup="GROUP")
        CDBClassDef.assert_called_once_with(plugin.classname)
        CDBClassDef.return_value.getAttributeDefs.assert_called_once_with()
        get_sqltype.assert_has_calls(
            [
                call(adef_pq),
                call(adef_txt),
                call(adef_a),
                call(adef_a),
                call(adef_b),
            ]
        )
        self.assertEqual(get_sqltype.call_count, 5)
        error.assert_called_once_with(
            "'%s': missing attributes %s in mapping",
            plugin.classname,
            set(["pq", "txt", "missing", "invisible"]),
        )

    @patch.object(rest_objects, "to_python_rep", autospec=True)
    @patch.object(rest_objects, "get_attributes", autospec=True)
    def test_mapped_data_missing(self, get_attributes, to_python_rep):
        "fails if attribute is missing in record"
        plugin = MagicMock()
        record = {"foo": "f"}
        get_attributes.return_value = [("bar", "B")]
        with self.assertRaises(KeyError) as error:
            rest_objects.mapped_data(plugin, "CG", record, "bam")
        self.assertEqual("'bar'", str(error.exception))
        get_attributes.assert_called_once_with(plugin, "CG")
        self.assertEqual(to_python_rep.call_count, 0)

    @patch.object(rest_objects, "dump", autospec=True)
    @patch.object(rest_objects, "CDBClassDef", autospec=True)
    @patch.object(rest_objects, "to_python_rep", autospec=True)
    @patch.object(rest_objects, "get_attributes", autospec=True)
    def test_mapped_data(self, get_attributes, to_python_rep, CDBClassDef, dump):
        "returns mapped REST object"
        plugin = MagicMock()
        record = {"foo": "f", "bar": "b", "ignore": "_"}
        get_attributes.return_value = [
            ("foo", "F"),
            ("bar", "B"),
        ]
        self.assertEqual(
            rest_objects.mapped_data(plugin, "CG", record, "bam"), dump.return_value
        )
        get_attributes.assert_called_once_with(plugin, "CG")
        to_python_rep.assert_has_calls(
            [
                call("F", "f"),
                call("B", "b"),
            ]
        )
        self.assertEqual(to_python_rep.call_count, 2)
        CDBClassDef.assert_called_once_with("bam")
        dump.assert_called_once_with(
            {
                "foo": to_python_rep.return_value,
                "bar": to_python_rep.return_value,
            },
            CDBClassDef.return_value,
        )

    @patch.object(rest_objects, "get_rest_sysattrs", autospec=True)
    @patch.object(rest_objects, "mapped_data", autospec=True)
    def test_record2rest_object_nosubj(self, mapped_data, get_rest_sysattrs):
        "returns complete REST object if no subject can be found"
        mapped_data.return_value = {
            "foo": "f",
            "overwritten": "old",
            "subject_id": "foo",
        }
        get_rest_sysattrs.return_value = {"overwritten": "new"}
        plugin = MagicMock()
        plugin.GetResponsible.return_value = None
        record = MagicMock(get=MagicMock(return_value=None))
        self.assertEqual(
            rest_objects.record2rest_object(plugin, "CG", record, "request"),
            {
                "foo": "f",
                "overwritten": "new",
                "subject_id": "foo",
                "system:description": plugin.GetDescription.return_value,
                "system:icon_link": plugin.GetObjectIcon.return_value,
            },
        )
        mapped_data.assert_called_once_with(plugin, "CG", record, plugin.classname)
        get_rest_sysattrs.assert_called_once_with(record, plugin.classname, "request")
        plugin.GetResponsible.assert_called_once_with(record)
        plugin.GetDescription.assert_called_once_with(record)
        plugin.GetObjectIcon.assert_called_once_with(record)

    @patch.object(rest_objects, "get_rest_sysattrs", autospec=True)
    @patch.object(rest_objects, "mapped_data", autospec=True)
    def test_record2rest_object(self, mapped_data, get_rest_sysattrs):
        "returns complete REST object"
        mapped_data.return_value = {
            "foo": "f",
            "overwritten": "old",
            "subject_id": "foo",
        }
        get_rest_sysattrs.return_value = {"overwritten": "new"}
        plugin = MagicMock()
        record = MagicMock(get=MagicMock(return_value=None))
        self.assertEqual(
            rest_objects.record2rest_object(plugin, "CG", record, "request"),
            {
                "foo": "f",
                "overwritten": "new",
                "subject_id": plugin.GetResponsible.return_value["subject_id"],
                "subject_type": plugin.GetResponsible.return_value["subject_type"],
                "system:description": plugin.GetDescription.return_value,
                "system:icon_link": plugin.GetObjectIcon.return_value,
            },
        )
        mapped_data.assert_called_once_with(plugin, "CG", record, plugin.classname)
        get_rest_sysattrs.assert_called_once_with(record, plugin.classname, "request")
        plugin.GetResponsible.assert_called_once_with(record)
        plugin.GetDescription.assert_called_once_with(record)
        plugin.GetObjectIcon.assert_called_once_with(record)

    @patch.object(rest_objects, "RELSHIP_FIELDS", ["a", "b"])
    def test_relships2json_missing(self):
        "fails if whitelisted field is missing"
        with self.assertRaises(KeyError) as error:
            rest_objects.relships2json([{"a": "a1"}])

        self.assertEqual(str(error.exception), "'b'")

    @patch.object(rest_objects, "RELSHIP_FIELDS", ["a", "b"])
    def test_relships2json(self):
        "returns JSON-serializable, whitelisted relship data"
        relships = [
            {"a": "a1", "b": "b1", "c": "c1"},
            {"a": "a2", "b": "b2", "C": "C2"},
        ]
        self.assertEqual(
            rest_objects.relships2json(relships),
            [
                {"a": "a1", "b": "b1"},
                {"a": "a2", "b": "b2"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
