#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module test_forms

This is the documentation for the test_forms module.
"""

from cdb import sqlapi
from cdb import testcase
from cdb.objects.org import CommonRole
from cs.workflow import get_cdbwf_resp_browser_schema
from cs.workflow import generate_cdbwf_resp_browser
from cs.workflow import generate_cdbwf_resp_mapping


def setup_module():
    testcase.run_level_setup()


class UtilityViewsTestCase(testcase.RollbackTestCase):
    def test_get_cdbwf_resp_browser_schema(self):
        expected = set([
            "subject_id",
            "description_de",
            "description_cs",
            "description_en",
            "description_es",
            "description_fr",
            "description_it",
            "description_ja",
            "description_ko",
            "description_pl",
            "description_pt",
            "description_tr",
            "description_zh",
            "subject_type",
            "subject_name_cs",
            "subject_name_de",
            "subject_name_en",
            "subject_name_es",
            "subject_name_fr",
            "subject_name_it",
            "subject_name_ja",
            "subject_name_ko",
            "subject_name_pl",
            "subject_name_pt",
            "subject_name_tr",
            "subject_name_zh",
            "cdb_project_id",
            "order_by",
        ])
        self.assertEqual(
            set(get_cdbwf_resp_browser_schema()),
            expected
        )

    def test_generate_cdbwf_resp_browser(self):
        CommonRole.Query().Update(is_org_role=0)
        CommonRole.KeywordQuery(
            role_id=["Documentation", "Engineering"]).Update(is_org_role=1)
        select = generate_cdbwf_resp_browser()
        self.assertEqual(type(select), str)

    def test_generate_cdbwf_resp_mapping(self):
        select = generate_cdbwf_resp_mapping()
        self.assertEqual(type(select), str)
        self.assertGreater(len(sqlapi.RecordSet2(sql=select)), 41)

    def test_collation(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            from cdb.mssql import CollationDefault
            rows = CollationDefault.find_wrong_collations()

            own_tables = [
                row.table_name
                for row in sqlapi.RecordSet2(
                    "cdbdd_table",
                    "cdb_module_id='cs.workflow'"
                )
            ]
            broken = set([
                row.table_name
                for row in rows if row.table_name in own_tables
            ])

            self.assertEqual(
                len(broken),
                0,
                msg="views containing wrong collations: {}".format(
                    [dict(row) for row in rows if row.table_name in broken]
                )
            )
        else:
            self.skipTest("only relevant for MS SQL")
