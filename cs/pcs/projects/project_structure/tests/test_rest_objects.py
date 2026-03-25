#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import pytest
from mock import MagicMock, call, patch

from cs.pcs.projects.project_structure import rest_objects
from cs.pcs.projects.project_structure.util import PCS_RECORD


def identity(arg):
    return arg


@pytest.mark.unit
class Utility(unittest.TestCase):
    @patch.object(rest_objects, "pcs_record2rest_object", autospec=True)
    def test_rest_objects_by_oid_no_addtl(self, pcs_record2rest_object):
        "returns rest objects /wo addtl data"
        record_a = MagicMock(cdb_object_id="oid_a")
        record_b = MagicMock(cdb_object_id="oid_b")
        records = [
            PCS_RECORD("a", record_a),
            PCS_RECORD("b", record_b),
        ]
        self.assertEqual(
            rest_objects.rest_objects_by_oid(records, "request"),
            {
                "oid_a": pcs_record2rest_object.return_value,
                "oid_b": pcs_record2rest_object.return_value,
            },
        )
        pcs_record2rest_object.assert_has_calls(
            [
                call(records[0], "request", {}),
                call(records[1], "request", {}),
            ]
        )
        self.assertEqual(pcs_record2rest_object.call_count, 2)

    @patch.object(rest_objects, "pcs_record2rest_object", autospec=True)
    def test_rest_objects_by_oid(self, pcs_record2rest_object):
        "returns rest objects"
        record_a = MagicMock(cdb_object_id="oid_a")
        record_b = MagicMock(cdb_object_id="oid_b")
        records = [
            PCS_RECORD("a", record_a),
            PCS_RECORD("b", record_b),
        ]
        addtl = MagicMock()
        self.assertEqual(
            rest_objects.rest_objects_by_oid(records, "request", addtl),
            {
                "oid_a": pcs_record2rest_object.return_value,
                "oid_b": pcs_record2rest_object.return_value,
            },
        )
        pcs_record2rest_object.assert_has_calls(
            [
                call(records[0], "request", addtl.return_value),
                call(records[1], "request", addtl.return_value),
            ]
        )
        self.assertEqual(pcs_record2rest_object.call_count, 2)
        addtl.assert_has_calls(
            [
                call(records[0], "request"),
                call(records[1], "request"),
            ],
            any_order=True,
        )
        self.assertEqual(addtl.call_count, 2)

    @patch.object(
        rest_objects,
        "pcs_record2rest_object",
        autospec=True,
        side_effect=[
            {"system:navigation_id": "A"},
            {"system:navigation_id": "B"},
        ],
    )
    def test_rest_objects_by_restkey_no_addtl(self, pcs_record2rest_object):
        "returns rest objects /wo addtl data"
        records = ["rec_1", "rec_2"]
        self.assertEqual(
            rest_objects.rest_objects_by_restkey(records, "request"),
            {
                "A": {"system:navigation_id": "A"},
                "B": {"system:navigation_id": "B"},
            },
        )
        pcs_record2rest_object.assert_has_calls(
            [
                call("rec_1", "request", {}),
                call("rec_2", "request", {}),
            ]
        )
        self.assertEqual(pcs_record2rest_object.call_count, 2)

    @patch.object(
        rest_objects,
        "pcs_record2rest_object",
        autospec=True,
        side_effect=[
            {"system:navigation_id": "A"},
            {"system:navigation_id": "B"},
        ],
    )
    def test_rest_objects_by_restkey(self, pcs_record2rest_object):
        "returns rest objects"
        records = ["rec_1", "rec_2"]
        addtl = MagicMock()
        self.assertEqual(
            rest_objects.rest_objects_by_restkey(records, "request", addtl),
            {
                "A": {"system:navigation_id": "A"},
                "B": {"system:navigation_id": "B"},
            },
        )
        pcs_record2rest_object.assert_has_calls(
            [
                call("rec_1", "request", addtl.return_value),
                call("rec_2", "request", addtl.return_value),
            ]
        )
        self.assertEqual(pcs_record2rest_object.call_count, 2)
        addtl.assert_has_calls(
            [
                call("rec_1", "request"),
                call("rec_2", "request"),
            ],
            any_order=True,
        )
        self.assertEqual(addtl.call_count, 2)

    @patch.object(rest_objects, "get_rest_sysattrs", autospec=True)
    @patch.object(rest_objects, "get_classname", autospec=True)
    def test_pcs_record2rest_object(self, get_classname, get_rest_sysattrs):
        "returns complete REST object"
        get_rest_sysattrs.return_value = {"a": "a", "b": "b"}
        pcs_record = PCS_RECORD("table", "record")

        self.assertEqual(
            rest_objects.pcs_record2rest_object(pcs_record, "request", {"a": "A"}),
            {"a": "A", "b": "b"},
        )
        get_classname.assert_called_once_with("table")
        get_rest_sysattrs.assert_called_once_with(
            "record", get_classname.return_value, "request"
        )


if __name__ == "__main__":
    unittest.main()
