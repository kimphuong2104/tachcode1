#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import unittest

import mock

from cs.pcs.projects import schedule_sql


class Utility(unittest.TestCase):
    def test_load_query_pattern_escape(self):
        with self.assertRaises(RuntimeError):
            schedule_sql.load_query_pattern("../missing file")

    def test_load_query_pattern_missing(self):
        self.assertIsNone(
            schedule_sql.load_query_pattern("missing file"),
        )

    @mock.patch.object(schedule_sql.os.path, "isfile")
    def test_load_query_pattern_ok(self, isfile):
        schedule_sql.load_query_pattern.cache_clear()
        self.assertIsNotNone(
            schedule_sql.load_query_pattern("merge_task_changes_mssql.sql"),
        )
        isfile.assert_called_once()
        # also cached
        self.assertIsNotNone(
            schedule_sql.load_query_pattern("merge_task_changes_mssql.sql"),
        )
        isfile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
