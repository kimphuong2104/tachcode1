# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb.testcase import RollbackTestCase
from cdb.validationkit.op import operation as interactive_operation
from cs.pcs.costs.sheets import CostSheet

from .utils import create_costsheet, create_project


class TestSheetOperations(RollbackTestCase):
    def test_create_costsheet(self):
        """Create a new costsheet"""
        project = create_project()
        cost_sheet = create_costsheet(project.cdb_project_id, "Budget")
        self.assertEqual(cost_sheet.status, CostSheet.NEW.status)
        self.assertEqual(cost_sheet.c_index, 0)
        self.assertEqual(cost_sheet.name_de, f"{project.project_name}: Budget")

    def test_create_two_costsheets_fail(self):
        """Try to create two new costsheets with the same cost significance and fail"""
        project = create_project()
        cost_sheet = create_costsheet(project.cdb_project_id, "Budget")
        self.assertEqual(cost_sheet.status, CostSheet.NEW.status)
        self.assertEqual(cost_sheet.c_index, 0)
        self.assertEqual(cost_sheet.name_de, f"{project.project_name}: Budget")
        with self.assertRaises(RuntimeError):
            create_costsheet(project.cdb_project_id, "Budget")

    def test_create_two_costsheets(self):
        """Create two new costsheets with different cost significances"""
        project = create_project()
        cost_sheet = create_costsheet(project.cdb_project_id, "Budget")
        self.assertEqual(cost_sheet.status, CostSheet.NEW.status)
        self.assertEqual(cost_sheet.c_index, 0)
        self.assertEqual(cost_sheet.name_de, f"{project.project_name}: Budget")
        cost_sheet2 = create_costsheet(project.cdb_project_id, "Plan")
        self.assertEqual(cost_sheet2.status, CostSheet.NEW.status)
        self.assertEqual(cost_sheet2.c_index, 0)
        self.assertEqual(cost_sheet2.name_de, f"{project.project_name}: Plan")

    def test_create_costsheets_invalid_project_status(self):
        """Try to create a new costsheets on a project with status not in 0,50 and fail"""
        project = create_project()
        project.status = 200

        with self.assertRaises(RuntimeError):
            create_costsheet(project.cdb_project_id, "Budget")

    def test_copy_costsheet_fail(self):
        """Try to copy a costsheets with same cost significances and fail"""
        project = create_project()
        cost_sheet = create_costsheet(project.cdb_project_id, "Budget")

        rs = sqlapi.RecordSet2("cdbpcs_cost_significance", "name_de = 'Budget'")
        cs = None
        if len(rs):
            cs = rs[0]
        user_input = {}
        preset = {
            "cdb_project_id": project.cdb_project_id,
            "costsignificance_object_id": cs.cdb_object_id,
        }
        with self.assertRaises(RuntimeError):
            interactive_operation("CDB_Copy", cost_sheet, user_input, preset)
