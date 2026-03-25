#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access


from datetime import datetime

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import pytest
from cdb import sqlapi, testcase

from cs.pcs.projects.common import sql_mass_data


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test_get_table_columns_unknown_table(self):
        self.assertEqual(
            sql_mass_data.get_table_columns("unknown_table", lambda x: True),
            [],
        )

    def test_get_table_columns(self):
        self.assertEqual(
            sql_mass_data.get_table_columns("cdbpcs_new_uuids", lambda x: True),
            ["opid", "old_uuid", "new_uuid"],
        )

    def test_get_table_columns_filter(self):
        self.assertEqual(
            sql_mass_data.get_table_columns(
                "cdbpcs_new_uuids", lambda x: x.endswith("uuid")
            ),
            ["old_uuid", "new_uuid"],
        )

    def test__make_row_literals(self):
        table_info = sql_mass_data.util.tables["cdbpcs_task"]
        rows = (
            ("cdb_cdate", datetime(2021, 12, 10, 5, 6, 7, 8)),
            ("status", "42"),
            ("status", 42),
            ("task_name", "Robert L; Tables"),
            ("task_name", "'value' -- innocent column"),
        )

        self.assertEqual(
            sql_mass_data._make_row_literals(table_info, rows),
            (
                f"{sqlapi.SQLdate_literal('10.12.2021 05:06:07')}, "
                "42, "
                "42, "
                "'Robert L; Tables', "
                "'''value'' -- innocent column'"
            ),
        )


@pytest.mark.integration
class MassData(testcase.RollbackTestCase):
    def test_sql_mass_insert(self):
        sqlapi.SQLdelete("FROM cdbpcs_issue WHERE cdb_project_id = 'P001'")
        self.assertIsNone(
            sql_mass_data.sql_mass_insert(
                "cdbpcs_issue",
                ("cdb_project_id", "issue_id", "issue_name", "cdb_object_id"),
                (
                    ("P001", "ISS-001", "1st issue", "i1"),
                    ("P001", "ISS-002", "2nd issue", "i2"),
                    ("P001", "ISS-003", "3rd issue", "i3"),
                ),
            )
        )
        result = sqlapi.RecordSet2("cdbpcs_issue", "cdb_project_id = 'P001'")
        self.assertEqual(
            [x.issue_name for x in result],
            ["1st issue", "2nd issue", "3rd issue"],
        )

    def test_sql_mass_copy(self):
        sqlapi.SQLdelete("FROM cdbpcs_task WHERE cdb_project_id = 'test_sql_mass_copy'")
        # expected SQL statements:
        # (1-3) schema (cdb_columns, cdb_tables, cdb_keys)
        # (4) select existing UUIDs from cdbpcs_task with given condition
        # (5-12) 8x insert into cdbpcs_new_uuids (3792 // batchsize=500)
        # (13) the "copy" insert into cdbpcs_task
        # (14) insert into cdb_object
        # (15) delete from cdbpcs_new_uuids
        with testcase.max_sql(15):
            self.assertIsNone(
                sql_mass_data.sql_mass_copy(
                    "cdbpcs_task",
                    "cdb_project_id = 'Ptest.msp.big' AND ce_baseline_id = ''",
                    {"cdb_project_id": "test_sql_mass_copy"},
                )
            )

        result = sqlapi.RecordSet2(
            "cdbpcs_task", "cdb_project_id = 'test_sql_mass_copy'"
        )
        self.assertEqual(len(result), 3792)
        self.assertEqual(
            {x.cdb_project_id for x in result},
            set(["test_sql_mass_copy"]),
        )

        cdb_object = sqlapi.RecordSet2(
            "cdb_object",
            "id IN (SELECT cdb_object_id FROM cdbpcs_task "
            "WHERE cdb_project_id = 'test_sql_mass_copy')",
        )
        self.assertEqual(len(cdb_object), 3792)
        self.assertEqual(
            {x.relation for x in cdb_object},
            set(["cdbpcs_task"]),
        )


@pytest.mark.unit
class NewUUIDs(unittest.TestCase):
    def test_generate(self):
        # expected SQL statements:
        # (1) INSERT INTO cdbpcs_new_uuids
        # (2) SELECT FROM cdbpcs_new_uuids (inline KeywordQuery)
        # (3) DELETE FROM cdbpcs_new_uuids
        with testcase.max_sql(3):
            with sql_mass_data.NewUUIDs.generate(["foo", "bar"]) as opid:
                entries = sql_mass_data.NewUUIDs.KeywordQuery(opid=opid)
                self.assertEqual(
                    set(entries.old_uuid),
                    set(["foo", "bar"]),
                )
                self.assertTrue(entries[0].new_uuid)

        entries = sql_mass_data.NewUUIDs.KeywordQuery(opid=opid)
        self.assertFalse(len(entries))


if __name__ == "__main__":
    unittest.main()
