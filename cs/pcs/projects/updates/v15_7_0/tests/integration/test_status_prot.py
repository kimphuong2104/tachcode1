#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import ddl, sqlapi, testcase, util
from cdb.comparch import protocol

from cs.pcs.projects.updates.helpers import initialize_sortable_id
from cs.pcs.projects.updates.v15_7_0 import InitSortableID_Project


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.acceptance
class InitSortableIDIntegration(testcase.RollbackTestCase):
    __table_name__ = "cdbpcs_prj_prot"

    def _reload_table(self):
        util.tables.reload(self.__table_name__)
        return ddl.Table(self.__table_name__)

    def _add_column(self, column):
        table = self._reload_table()
        if not table.hasColumn(column.colname):
            table.addAttributes(column)

    def _drop_column(self, colname):
        table = self._reload_table()
        if table.hasColumn(colname):
            table.dropAttributes(colname)

    def _setup_table_scheme(self):
        sqlapi.SQLdelete(f"FROM {self.__table_name__}")
        self._drop_column("cdbprot_zaehler")
        self._add_column(ddl.Integer("cdbprot_zaehler"))
        table = self._reload_table()
        table.setPrimaryKey(ddl.PrimaryKey("cdbprot_zaehler"))
        self._drop_column("cdbprot_sortable_id")
        self._add_column(ddl.Char("cdbprot_sortable_id", 31, 0))

    def _update_table_entries(self, no_of_entries):
        count = 0
        for _ in range(no_of_entries):
            count += 1
            sqlapi.SQLinsert(
                f"INTO {self.__table_name__} (cdb_project_id, cdbprot_zaehler)"
                f" VALUES ({count}, {count})"
            )

    def _setup_sortable_id(self):
        table = self._reload_table()
        sqlapi.SQLdelete(f"FROM {self.__table_name__}")
        self._add_column(ddl.Integer("cdbprot_sortable_id"))
        table.setPrimaryKey(ddl.PrimaryKey("cdbprot_sortable_id"))
        self._drop_column("cdbprot_zaehler")

    @mock.patch.object(protocol, "logMessage")
    def test_project_initSortableID_no_uninitialized(self, logMessage):
        self._setup_sortable_id()
        InitSortableID_Project().run()
        logMessage.assert_called_once_with(
            "No need to migrate protocol ==> no cdbprot_zaehler"
        )

    @mock.patch.object(protocol, "logMessage")
    def test_project_initSortableID_no_entries(self, logMessage):
        self._setup_table_scheme()
        InitSortableID_Project().run()
        logMessage.assert_called_once_with("Done! Did not find any uninitialized row")

    @mock.patch.object(protocol, "logWarning")
    def test_project_initSortableID__max_limit(self, logWarning):
        self._setup_table_scheme()
        sqlapi.SQLinsert(
            f"INTO {self.__table_name__} (cdb_project_id, cdbprot_zaehler)"
            " VALUES ('max_limit', 999999999999)"
        )
        InitSortableID_Project().run()
        logWarning.assert_called_once_with(
            f"Cannot initialize {self.__table_name__}.cdbprot_sortable_id. "
            "Entry IDs with more than 10 digits exist, so we cannot "
            "guarantee sortability. "
            "Please migrate manually (takes some time)."
        )

    def test_project_initSortableID_lessthan_blocksize(self):
        self._setup_table_scheme()
        self._update_table_entries(5)
        InitSortableID_Project().run()
        self.assertTrue(util.column_exists(self.__table_name__, "cdbprot_sortable_id"))
        self.assertFalse(util.column_exists(self.__table_name__, "cdbprot_zaehler"))
        sql_entries = sqlapi.RecordSet2(
            sql=f"SELECT * FROM {self.__table_name__} WHERE cdb_project_id ='2'"
        )
        self.assertEqual(
            sql_entries[0].cdbprot_sortable_id, "0000000000000000000000000000002"
        )

    def test_project_initSortableID_morethan_blocksize(self):
        self._setup_table_scheme()
        self._update_table_entries(6)
        initialize_sortable_id(self.__table_name__, 3)
        self.assertTrue(util.column_exists(self.__table_name__, "cdbprot_sortable_id"))
        self.assertFalse(util.column_exists(self.__table_name__, "cdbprot_zaehler"))
        sql_entries = sqlapi.RecordSet2(
            sql=f"SELECT * FROM {self.__table_name__} WHERE cdb_project_id IN ('2', '5')"
            f" ORDER BY cdbprot_sortable_id"
        )
        self.assertEqual(
            sql_entries[0].cdbprot_sortable_id, "0000000000000000000000000000002"
        )
        self.assertEqual(
            sql_entries[1].cdbprot_sortable_id, "0000000000000000000000000000005"
        )


if __name__ == "__main__":
    unittest.main()
