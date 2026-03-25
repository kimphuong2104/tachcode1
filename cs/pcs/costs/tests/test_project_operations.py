# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.testcase import RollbackTestCase
from cdb.validationkit.op import operation as interactive_operation
from cs.pcs.costs.sheets import CostSheet

from .utils import create_costposition, create_costsheet, create_project, create_task


class TestProjectOperations(RollbackTestCase):
    def test_create_costsheet(self):
        """Copy a project"""
        project = create_project()
        task = create_task(project.cdb_project_id)
        cost_sheet = create_costsheet(project.cdb_project_id, "Budget")

        user_input = {
            "costsheet_object_id": cost_sheet.cdb_object_id,
            "task_object_id": task.cdb_object_id,
            "name_de": "TEST POSITION",
            "costs": 0,
        }

        cost_position = create_costposition("MATC", **user_input)
        task.Reload()
        self.assertTrue(cost_position.Task)
        self.assertEqual(cost_position.task_object_id, task.cdb_object_id)

        user_input = {}
        preset = {}
        project2 = interactive_operation("CDB_Copy", project, user_input, preset)
        self.assertEqual(len(project2.Tasks), 1)
        task2 = project2.Tasks[0]
        cost_sheets = CostSheet.KeywordQuery(cdb_project_id=project2.cdb_project_id)
        self.assertEqual(len(cost_sheets), 1)
        cost_sheet2 = cost_sheets[0]
        self.assertEqual(cost_sheet2.status, CostSheet.NEW.status)
        self.assertEqual(cost_sheet2.c_index, 0)
        self.assertEqual(len(cost_sheet2.Positions), 1)
        cost_position2 = cost_sheet2.Positions[0]
        self.assertEqual(cost_position2.task_object_id, task2.cdb_object_id)
