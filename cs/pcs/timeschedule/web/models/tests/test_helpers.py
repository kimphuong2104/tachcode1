#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from datetime import date

import mock
import pytest
from cdb import testcase

from cs.pcs.timeschedule.web.models import helpers


@pytest.mark.unit
class Utility(unittest.TestCase):
    @testcase.without_error_logging
    def test_get_date_no_dict(self):
        "fails if payload is not a dict"
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.get_date("foo", "foo")

    @testcase.without_error_logging
    def test_get_date_no_str(self):
        "fails if key is not a str"
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.get_date({"foo": "bar"}, 1)

    @testcase.without_error_logging
    def test_get_date_no_key(self):
        "fails if key is missing in payload"
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.get_date({"foo": "bar"}, "baz")

    def test_get_date_iso_without_time(self):
        self.assertEqual(
            helpers.get_date({"foo": "2022-08-01"}, "foo"),
            date(2022, 8, 1),
        )

    def test_get_date_iso_with_time(self):
        self.assertEqual(
            helpers.get_date({"foo": "2022-08-01T10:11:12.000Z"}, "foo"),
            date(2022, 8, 1),
        )

    @mock.patch.object(helpers.logging, "exception")
    def test_get_date_iso_invalid(self, log_exc):
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.get_date({"foo": "x"}, "foo")

        log_exc.assert_called_once_with(
            "tried to convert ISO date '%s' from %s",
            "foo",
            {"foo": "x"},
        )

    def test_get_date_legacy_without_time(self):
        self.assertEqual(
            helpers.get_date({"foo": "01.08.2022"}, "foo", False),
            date(2022, 8, 1),
        )

    def test_get_date_legacy_with_time(self):
        self.assertEqual(
            helpers.get_date({"foo": "01.08.2022 10:11:12"}, "foo", False),
            date(2022, 8, 1),
        )

    @mock.patch.object(helpers.logging, "exception")
    def test_get_date_legacy_invalid(self, log_exc):
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.get_date({"foo": "x"}, "foo", False)

        log_exc.assert_called_once_with(
            "tried to convert legacy date '%s' from %s",
            "foo",
            {"foo": "x"},
        )

    @mock.patch.object(helpers, "format_in_condition", autospec=True)
    def test_get_oid_query_str_default_attr(self, format_in_condition):
        "defaults to attr 'cdb_object_id'"
        self.assertEqual(
            helpers.get_oid_query_str("foo"), format_in_condition.return_value
        )

        format_in_condition.assert_called_once_with("cdb_object_id", "foo")

    @mock.patch.object(helpers, "format_in_condition", autospec=True)
    def test_get_oid_query_str(self, format_in_condition):
        "uses given attr"
        self.assertEqual(
            helpers.get_oid_query_str("foo", "bar"), format_in_condition.return_value
        )

        format_in_condition.assert_called_once_with("bar", "foo")

    @mock.patch.object(helpers, "get_oid_query_str", autospec=True)
    @mock.patch.object(helpers.sqlapi, "RecordSet2", autospec=True)
    def test_get_pcs_oids(self, RecordSet2, get_oid_query_str):
        "returns oids with their respective table names"
        RecordSet2.return_value = [
            mock.MagicMock(id=1, relation="relation1"),
            mock.MagicMock(id=2, relation="relation2"),
        ]
        self.assertEqual(
            helpers.get_pcs_oids("oids"),
            [
                helpers.PCS_OID(1, "relation1"),
                helpers.PCS_OID(2, "relation2"),
            ],
        )
        RecordSet2.assert_called_once_with(
            "cdb_object",
            get_oid_query_str.return_value,
        )
        get_oid_query_str.assert_called_once_with("oids", "id")

    def test_get_oids_by_relation_not_iter(self):
        "fails if resolved_oids is not iterable"
        with self.assertRaises(ValueError) as error:
            helpers.get_oids_by_relation(None)
        self.assertEqual(
            "value (or one of its values) is not iterable: 'None'", str(error.exception)
        )

    def test_get_oids_by_relation_not_iter2(self):
        "fails if any value in resolved_oids is not iterable"
        with self.assertRaises(ValueError) as error:
            helpers.get_oids_by_relation([None])
        self.assertEqual(
            "value (or one of its values) is not iterable: '[None]'",
            str(error.exception),
        )

    def test_get_oids_by_relation_no2(self):
        "fails if any value in resolved_oids contains less than 2 values"
        with self.assertRaises(ValueError) as error:
            helpers.get_oids_by_relation([(1,)])
        self.assertEqual(
            "each value must contain at least 2 values: '[(1,)]'",
            str(error.exception),
        )

    def test_get_oids_by_relation(self):
        "returns oids indexed by relation"
        self.assertEqual(
            helpers.get_oids_by_relation(
                [
                    (1, "foo"),
                    (2, "bar"),
                    (3, "foo"),
                ]
            ),
            [
                ("bar", [2]),
                ("foo", [1, 3]),
            ],
        )

    def test_get_node(self):
        "returns new node dict"
        self.assertEqual(
            helpers.get_node(5, True, "node_id"),
            {
                "id": "node_id",
                "rowNumber": 5,
                "expanded": True,
                "children": [],
            },
        )


if __name__ == "__main__":
    unittest.main()
