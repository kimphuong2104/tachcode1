# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Tests for the user defined view cdbvp_resp_brows
"""

import unittest
import cdbwrapc

from cdb import rte
from cdb import sqlapi
from cdb import testcase
from cs.vp import products


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@testcase.without_error_logging
def run_level_setup():
    rte.ensure_run_level(rte.DATABASE_CONNECTED,
                         prog="nosetests",
                         user="caddok",
                         init_pylogging=False)
    # Necessary for nosetest - powerscript did it on its own
    cdbwrapc.init_corbaorb()


# generate_cdbvp_resp_brows will run with cdbpkg sync on runlevel rte.DATABASE_CONNECTED
# if we use testcase.PlatformTestcase the tests will run with runlevel rte.USER_IMPERSONATED
# so we need to use unittest.TestCase and set the runlevel explicitly (s. E051159)
class VPRespBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_level_setup()

    def test_generate_cdbvp_resp_brows(self):
        "The function generate_cdbvp_resp_brows generates valid sql"
        stmt = products.generate_cdbvp_resp_brows()
        rs = sqlapi.RecordSet2(sql=stmt)
        self.assertGreater(len(rs), 0)

    def test_collation(self):
        "Collation is set properly on mssql"
        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            from cdb.mssql import CollationDefault
            rows = CollationDefault.find_wrong_collations()

            self.assertNotIn(
                "cdbvp_resp_brows", [row.table_name for row in rows],
                "wrong collation in view cdbvp_resp_brows"
            )
        else:
            self.skipTest("only relevant for MS SQL")
