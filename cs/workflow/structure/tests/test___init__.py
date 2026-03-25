#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock, unittest
from cs.workflow import structure


class Utility(unittest.TestCase):
    @mock.patch.object(structure, "open", create=True)
    @mock.patch.object(structure.os.path, "abspath")
    @mock.patch.object(structure.os.path, "dirname")
    @mock.patch.object(structure.misc, "jail_filename")
    def test_load_query_pattern(self, jail_filename, dirname, abspath,
                                mock_open):
        read = mock_open.return_value.__enter__.return_value.read
        self.assertEqual(
            structure.load_query_pattern("foo"),
            read.return_value,
        )
        mock_open.assert_called_once_with(jail_filename.return_value, "r")
        read.assert_called_once_with()
        jail_filename.assert_called_once_with(abspath.return_value, "foo")
        abspath.assert_called_once_with(dirname.return_value)
        dirname.assert_called_once_with(structure.__file__)

    @mock.patch("cdb.mssql.CollationDefault.get_default_collation")
    @mock.patch.object(structure, "load_query_pattern")
    @mock.patch.object(structure.sqlapi, "SQLdbms", return_value="MSSQL")
    @mock.patch.object(structure.sqlapi, "DBMS_MSSQL", "MSSQL")
    def test_get_query_pattern_mssql(self, SQLdbms, load_query_pattern,
                                     get_default_collation):
        self.assertEqual(
            structure.get_query_pattern("pattern"),
            load_query_pattern.return_value.format.return_value,
        )
        SQLdbms.assert_called_once_with()
        get_default_collation.assert_called_once_with()
        load_query_pattern.assert_called_once_with("pattern_mssql.sql")
        load_query_pattern.return_value.format.assert_called_once_with(
            collation=get_default_collation.return_value,
        )

    @mock.patch.object(structure, "load_query_pattern")
    @mock.patch.object(structure.sqlapi, "SQLdbms", return_value="LITE")
    @mock.patch.object(structure.sqlapi, "DBMS_SQLITE", "LITE")
    def test_get_query_pattern_sqlite(self, SQLdbms, load_query_pattern):
        self.assertEqual(
            structure.get_query_pattern("pattern"),
            load_query_pattern.return_value,
        )
        SQLdbms.assert_called_once_with()
        load_query_pattern.assert_called_once_with("pattern_sqlite.sql")

    @mock.patch.object(structure, "load_query_pattern")
    @mock.patch.object(structure.sqlapi, "SQLdbms", return_value="ORA")
    @mock.patch.object(structure.sqlapi, "DBMS_ORACLE", "ORA")
    def test_get_query_pattern_oracle(self, SQLdbms, load_query_pattern):
        self.assertEqual(
            structure.get_query_pattern("pattern"),
            load_query_pattern.return_value,
        )
        SQLdbms.assert_called_once_with()
        load_query_pattern.assert_called_once_with("pattern_oracle.sql")

    @mock.patch.object(structure, "load_query_pattern")
    @mock.patch.object(structure.sqlapi, "SQLdbms", return_value="?")
    def test_get_query_pattern_unknown(self, SQLdbms, load_query_pattern):
        with self.assertRaises(UnboundLocalError):
            structure.get_query_pattern("pattern")

        SQLdbms.assert_called_once_with()
        load_query_pattern.assert_not_called()
