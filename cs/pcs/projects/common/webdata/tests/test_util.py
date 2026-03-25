#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects.common.webdata import util


def three_args(a, b, c):
    return f"{a}.{b}.{c}"


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(util.logging, "exception", autospec=True)
    def test__get_classinfo_no_def(self, exception):
        "fails if classdef cannot be determined"
        getter = mock.MagicMock(side_effect=util.ElementsError)

        with self.assertRaises(util.HTTPBadRequest):
            util._get_classinfo(getter, "foo")

        getter.assert_called_once_with("foo")
        getter.return_value.getPrimaryTable.assert_not_called()
        exception.assert_called_once_with("_get_classinfo")

    @mock.patch.object(util.logging, "error", autospec=True)
    def test__get_classinfo_no_def2(self, error):
        "fails if classdef cannot be determined (return None)"
        getter = mock.MagicMock(return_value=None)

        with self.assertRaises(util.HTTPBadRequest):
            util._get_classinfo(getter, "foo")

        getter.assert_called_once_with("foo")
        error.assert_called_once_with("cannot find class def for %s(%s)", getter, "foo")

    @mock.patch.object(util, "CDBClassDef", autospec=True)
    def test__get_classinfo(self, CDBClassDef):
        "returns tuple with class def and primary table"
        getter = mock.MagicMock()

        self.assertEqual(
            util._get_classinfo(getter, "foo"),
            (
                getter.return_value,
                getter.return_value.getPrimaryTable.return_value,
            ),
        )
        getter.assert_called_once_with("foo")
        getter.return_value.getPrimaryTable.assert_called_once_with()

    @mock.patch.object(util, "_get_classinfo")
    def test_get_classinfo(self, _get_classinfo):
        "resolves classinfo for classname"
        self.assertEqual(
            util.get_classinfo("foo"),
            _get_classinfo.return_value,
        )
        _get_classinfo.assert_called_once_with(util.CDBClassDef, "foo")

    @mock.patch.object(util, "_get_classinfo")
    def test_get_classinfo_REST(self, _get_classinfo):
        "resolves classinfo for restname"
        self.assertEqual(
            util.get_classinfo_REST("foo"),
            _get_classinfo.return_value,
        )
        _get_classinfo.assert_called_once_with(util.CDBClassDef.findByRESTName, "foo")

    @mock.patch.object(util.sqlapi, "make_literal", autospec=True)
    def test__build_literal_null(self, make_literal):
        "returns safe SQL literal (NULL value)"
        self.assertEqual(
            util._build_literal("foo", "bar", None),
            f'{"bar"}{" IS "}{make_literal.return_value}',
        )
        make_literal.assert_called_once_with("foo", "bar", None)

    @mock.patch.object(util.sqlapi, "make_literal", autospec=True)
    def test__build_literal(self, make_literal):
        "returns safe SQL literal (non-NULL value)"
        self.assertEqual(
            util._build_literal("foo", "bar", "baz"),
            f'{"bar"}{"="}{make_literal.return_value}',
        )
        make_literal.assert_called_once_with("foo", "bar", "baz")

    @mock.patch.object(util.logging, "exception")
    def test__get_single_sql_condition_error(self, exception):
        "raises IndexError if lenghts of keys and values differs"
        with self.assertRaises(IndexError):
            util._get_single_sql_condition("ti", "abc", "AB")

        exception.assert_called_once_with(
            "_get_single_sql_condition: "
            "length of keys and values does not match, %s, %s",
            "abc",
            "AB",
        )

    @mock.patch.object(util, "_build_literal", autospec=True, side_effect=three_args)
    def test__get_single_sql_condition(self, _build_literal):
        "returns SQL condition for single set of key values"
        self.assertEqual(
            util._get_single_sql_condition("ti", "abc", "ABC"),
            "ti.a.A AND ti.b.B AND ti.c.C",
        )
        _build_literal.assert_has_calls(
            [
                mock.call("ti", "a", "A"),
            ]
        )
        self.assertEqual(_build_literal.call_count, 3)

    def test_get_sql_condition_no_keynames(self):
        "returns 1=2 if no keynames are given"
        self.assertEqual(util.get_sql_condition("foo", [], "ABC"), "1=2")

    def test_get_sql_condition_no_rest_keys(self):
        "returns 1=2 if no rest_keys are given"
        self.assertEqual(util.get_sql_condition("foo", "abc", []), "1=2")

    @mock.patch.object(util, "SQL_CHUNKSIZE", 2)
    @mock.patch.object(
        util, "_get_single_sql_condition", autospec=True, side_effect=three_args
    )
    @mock.patch.object(util.cdbutil, "tables", {"foo": "FOO"})
    def test_get_sql_condition(self, _get_single_sql_condition):
        "returns SQL condition for multiple sets of key values"
        self.assertEqual(
            util.get_sql_condition("foo", "abc", "ABC"),
            "((FOO.abc.A) OR (FOO.abc.B)) OR ((FOO.abc.C))",
        )
        _get_single_sql_condition.assert_has_calls(
            [
                mock.call("FOO", "abc", "A"),
                mock.call("FOO", "abc", "B"),
                mock.call("FOO", "abc", "C"),
            ]
        )
        self.assertEqual(_get_single_sql_condition.call_count, 3)

    def test_get_rest_key_empty_keynames(self):
        "returns empty string if no keynames were given"
        self.assertEqual(util.get_rest_key("foo", []), "")

    @mock.patch(
        "cs.platform.web.rest.support._REPLACEMENTS", {"A": "AA", "B": "BB", "C": "CC"}
    )
    @mock.patch(
        "cs.platform.web.rest.generic.convert.dump_value",
        autospec=True,
        side_effect=lambda x: x,
    )
    def test_get_rest_key(self, dump_value):
        "returns record's REST key"
        record = {"a": "A", "b": "B", "c": "C"}
        self.assertEqual(util.get_rest_key(record, "abc"), "AA@BB@CC")
        dump_value.assert_has_calls(
            [
                mock.call("A"),
                mock.call("B"),
                mock.call("C"),
            ]
        )

    def test_filter_dict_missing_field(self):
        "fails if field is missing in record"
        with self.assertRaises(KeyError):
            util.filter_dict({"foo": "bar", "x": "X"}, ["bar"], "cldef")

    def test_filter_dict(self):
        "returns filtered record"
        cldef = mock.MagicMock(spec=util.CDBClassDef)
        attr_foo = mock.MagicMock()
        attr_foo.getName.return_value = "foo"
        attr_missing = mock.MagicMock()
        attr_missing.getName.return_value = "missing"
        cldef.getAttributeDefs.return_value = [attr_foo, attr_missing]
        self.assertEqual(
            util.filter_dict({"foo": "bar", "x": "X"}, ["foo"], cldef), {"foo": "bar"}
        )
        cldef.getAttributeDefs.assert_called_once_with()
        attr_foo.getName.assert_called_once_with()
        attr_missing.getName.assert_called_once_with()

    @mock.patch.object(util, "defaultdict", autospec=True)
    def test__merge_results(self, defaultdict):
        "calls updater and returns defaultdict"
        updater = mock.MagicMock()
        self.assertEqual(
            util._merge_results("foo", updater, "aA", "bB"), defaultdict.return_value
        )
        defaultdict.assert_called_once_with("foo")
        updater.assert_has_calls(
            [
                mock.call(defaultdict.return_value, "aA", "a"),
                mock.call(defaultdict.return_value, "aA", "A"),
                mock.call(defaultdict.return_value, "bB", "b"),
                mock.call(defaultdict.return_value, "bB", "B"),
            ]
        )
        self.assertEqual(updater.call_count, 4)

    def test_merge_results_dict(self):
        "merges nested dicts"
        a = {
            "foo": {"a": "A"},
            "bar": {"a": "A"},
        }
        b = {
            "foo": {"b": "B"},
            "baz": {"b": "B"},
        }
        self.assertEqual(
            util.merge_results_dict(a, b),
            {
                "foo": {"a": "A", "b": "B"},
                "bar": {"a": "A"},
                "baz": {"b": "B"},
            },
        )

    def test_merge_results_str(self):
        "merges dicts with string values"
        a = {
            "foo": "a",
            "bar": "a",
        }
        b = {
            "foo": "b",
            "baz": "b",
        }
        self.assertEqual(
            util.merge_results_str(a, b),
            {
                "foo": "ab",
                "bar": "a",
                "baz": "b",
            },
        )

    @mock.patch.object(util.kernel, "MappedAttributes", autospec=True)
    def test_get_mapped_referers(self, MappedAttributes):
        "returns source attributes of requested mapped attributes"
        attr1 = mock.MagicMock(spec=util.kernel.MappedAttribute)
        attr2 = mock.MagicMock(spec=util.kernel.MappedAttribute)
        attr3 = mock.MagicMock(spec=util.kernel.MappedAttribute)
        attr1.getName.return_value = "a"
        attr2.getName.return_value = "b"
        attr3.getName.return_value = "not requested"
        MappedAttributes.return_value = [attr1, attr2, attr3]

        self.assertEqual(
            util.get_mapped_referers("foo", "abc"),
            {
                attr1.getName.return_value: attr1.getReferer.return_value,
                attr2.getName.return_value: attr2.getReferer.return_value,
            },
        )

        MappedAttributes.assert_called_once_with("foo")
        attr1.getReferer.assert_called_once_with()
        attr2.getReferer.assert_called_once_with()
        attr3.getReferer.assert_not_called()
        self.assertEqual(attr1.getName.call_count, 2)
        self.assertEqual(attr2.getName.call_count, 2)
        self.assertEqual(attr3.getName.call_count, 1)

    @mock.patch.object(util.logging, "error", autospec=True)
    def test__get_mapped_attr_no_source_attr(self, error):
        "fails if no source attribute is found"
        mapped = mock.MagicMock(spec=util.kernel.MappedAttributes)
        with self.assertRaises(util.HTTPBadRequest):
            util._get_mapped_attr(mapped, {}, None, "A")

        error.assert_called_once_with(
            "get_mapped_attrs no referer found: '%s' (%s)",
            "A",
            {},
        )
        mapped.getValue.assert_not_called()

    def test__get_mapped_attr_no_value(self):
        "returns empty string if source value is empty"
        mapped = mock.MagicMock(spec=util.kernel.MappedAttributes)
        refs = {"A": "a"}
        self.assertEqual(util._get_mapped_attr(mapped, refs, {}, "A"), "")
        mapped.getValue.assert_not_called()

    def test__get_mapped_attr(self):
        "returns mapped attr"
        mapped = mock.MagicMock(spec=util.kernel.MappedAttributes)
        refs = {
            "A": "a",
            "B": "b",
        }
        record = {
            "a": "val a",
            "b": "val b",
        }
        self.assertEqual(
            util._get_mapped_attr(mapped, refs, record, "A"),
            mapped.getValue.return_value,
        )
        mapped.getValue.assert_called_once_with("A", "val a")

    @mock.patch.object(util, "_get_mapped_attr", autospec=True)
    @mock.patch.object(util.kernel, "MappedAttributes", autospec=True)
    def test_get_mapped_attrs(self, MappedAttributes, _get_mapped_attr):
        "returns mapped attributes"
        self.assertEqual(
            util.get_mapped_attrs("foo", "record", "refs", "abc"),
            {
                "a": _get_mapped_attr.return_value,
                "b": _get_mapped_attr.return_value,
                "c": _get_mapped_attr.return_value,
            },
        )
        MappedAttributes.assert_called_once_with("foo")
        _get_mapped_attr.assert_has_calls(
            [
                mock.call(MappedAttributes.return_value, "refs", "record", "a"),
                mock.call(MappedAttributes.return_value, "refs", "record", "b"),
                mock.call(MappedAttributes.return_value, "refs", "record", "c"),
            ]
        )
        self.assertEqual(_get_mapped_attr.call_count, 3)

    @mock.patch.object(util.sqlapi, "RecordSet2")
    def test_get_grouped_data(self, RecordSet2):
        "groups DB data by given keys and applies transformation function"

        # mock return value for DB Query
        rv = mock.MagicMock(key1="key1", key2="key2")
        rv.__getitem__ = getattr

        RecordSet2.return_value = [rv, rv]

        transformation = mock.MagicMock()

        def call_transformation(x):
            return transformation(x)

        self.assertDictEqual(
            util.get_grouped_data(
                "foo_table",
                "foo_condition",
                "key1",
                "key2",
                transform_func=call_transformation,
            ),
            {
                "key1": {
                    "key2": [transformation.return_value, transformation.return_value]
                }
            },
        )

        RecordSet2.assert_called_once_with("foo_table", "foo_condition", access="read")
        transformation.assert_has_calls(
            [
                mock.call(rv),
                mock.call(rv),
            ]
        )


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects"])
class UtilityIntegration(unittest.TestCase):
    def test_get_classinfo(self):
        "returns class definition and table name"
        result = util.get_classinfo("cdbpcs_task")
        self.assertEqual(len(result), 2)
        self.assertTrue(isinstance(result[0], util.CDBClassDef))
        self.assertEqual(result[1], "cdbpcs_task")

    def test_get_sql_condition(self):
        "returns quoted SQL condition"
        table = "cdbpcs_task"
        keynames = ["cdb_project_id", "task_id"]
        rest_keys = [["P1", "T1"], ["P2", "T'2"]]
        self.assertEqual(
            util.get_sql_condition(table, keynames, rest_keys),
            "((cdb_project_id='P1' AND task_id='T1') OR "
            "(cdb_project_id='P2' AND task_id='T''2'))",
        )

    def test_get_rest_key(self):
        "returns escaped REST key"
        record = {"cdb_project_id": "P1", "task_id": "T1ä"}
        keynames = ["cdb_project_id", "task_id"]
        self.assertEqual(util.get_rest_key(record, keynames), "P1@T1~C3~A4")

    def test_get_mapped_referers(self):
        "returns source attributes of requested mapped attributes"
        self.assertEqual(
            util.get_mapped_referers(
                "cdbpcs_task",
                [
                    "mapped_subject_name_en",
                    "mapped_calendar_profile_id",
                    "foo",
                ],
            ),
            {
                "mapped_subject_name_en": "subject_id",
                "mapped_calendar_profile_id": "cdb_project_id",
            },
        )

    @testcase.without_error_logging
    def test_get_mapped_attrs_unknown(self):
        "fails if unknown mapped attribute is requested"
        classname = "cdbpcs_task"
        record = {}
        names = ["foo"]
        refs = util.get_mapped_referers(classname, names)
        with self.assertRaises(util.HTTPBadRequest):
            util.get_mapped_attrs(classname, record, refs, names)

    def test_get_mapped_attrs(self):
        "returns requested mapped attributes"
        classname = "cdbpcs_task"
        record = {"subject_id": "vendorsupport"}
        names = [
            "mapped_subject_name_en",
            "mapped_calendar_profile_id",
        ]
        refs = util.get_mapped_referers(classname, names)
        self.assertEqual(
            util.get_mapped_attrs(classname, record, refs, names),
            {
                "mapped_subject_name_en": "Vendor Support",
                "mapped_calendar_profile_id": "",
            },
        )

    def test_get_oids_from_json_no_ids(self):
        "fails if request does not contain 'objectIDs'"
        request = mock.MagicMock(json={})
        with self.assertRaises(KeyError) as error:
            util.get_oids_from_json(request)

        self.assertEqual("'objectIDs'", str(error.exception))

    @mock.patch.object(util.logging, "error")
    def test_get_oids_from_json_no_list(self, error):
        "fails if 'objectIDs' is no list"
        request = mock.MagicMock(json={"objectIDs": "a, b"})
        # do not assert error message as it is constant and generic
        with self.assertRaises(util.HTTPBadRequest):
            util.get_oids_from_json(request)

        error.assert_called_once_with("malformed 'object_ids': %s", "a, b")

    def test_get_oids_from_json(self):
        "extracts cdb_object_ids from request's JSON payload"
        request = mock.MagicMock(json={"objectIDs": ["a", "b"]})
        self.assertEqual(util.get_oids_from_json(request), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
