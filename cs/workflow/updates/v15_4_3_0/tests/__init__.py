#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from cdb import ddl
from cdb import sqlapi
from cdb import testcase
from cs.workflow.updates.v15_4_3_0 import InitSortableIDForCdbwf_protocol


def setup_module():
    testcase.run_level_setup()


class TestInitSortableIDForCdbwf_protocol(testcase.RollbackTestCase):
    "integration test simulating initializer for sortable protocol IDs"
    TABLE = "cdbwf_protocol_test"
    DATA = [
        ("P2345678901234567890", "1234567890"),
        ("P2345678901234567890", "5"),
        ("P2345678901234567891", "5"),
    ]

    def _create_testdata(self):
        t = ddl.Table(
            self.TABLE,
            [
                ddl.Char("cdbprot_sortable_id", 31),
                ddl.Char("cdb_process_id", 20),
                ddl.Integer("entry_id"),
                ddl.PrimaryKey("cdb_process_id", "entry_id"),
            ],
        )
        t.create()
        for (pid, eid) in self.DATA:
            sqlapi.SQLinsert(
                "INTO {} VALUES ('', '{}', '{}')".format(
                    self.TABLE, pid, eid))

    def test_get_sortable_id(self):
        self._create_testdata()
        condition = InitSortableIDForCdbwf_protocol.get_sortable_id(
            self.TABLE, "cdbprot_sortable_id",
            "cdb_process_id", "entry_id")
        rset = sqlapi.RecordSet2(
            sql="SELECT {} AS x FROM {} ORDER BY x".format(
                condition, self.TABLE))
        self.assertEqual(len(rset), 3)  # == len(self.DATA)
        self.assertEqual(
            dict(rset[0]),
            {"x": "0000000000P23456789012345678905"}
        )
        self.assertEqual(
            dict(rset[1]),
            {"x": "0000000000P23456789012345678915"}
        )
        self.assertEqual(
            dict(rset[2]),
            {"x": "0P23456789012345678901234567890"}
        )
