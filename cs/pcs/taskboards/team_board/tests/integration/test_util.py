#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from cdb import sig, sqlapi, testcase


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestTeamBoardUtil(testcase.RollbackTestCase):
    def test_get_valid_boards_sql_condition_signal_emit(self):
        "Emitting signal: get_valid_board_object_ids"
        char = "''"
        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            char = "chr(1)"

        # compare actual result to expected result
        project_result = (
            "SELECT cdbpcs_project.taskboard_oid FROM"
            " cdbpcs_project cdbpcs_project WHERE"
            " ((cdbpcs_project.status IN (0,50))"
            " AND (cdbpcs_project.template!=1)"
            " AND (cdbpcs_project.ce_baseline_id=''))"
            f" AND cdbpcs_project.taskboard_oid != {char}"
            " AND cdbpcs_project.taskboard_oid IS NOT NULL"
        )
        task_result = (
            "SELECT cdbpcs_task.taskboard_oid FROM "
            "cdbpcs_task cdbpcs_task WHERE "
            "((cdbpcs_task.cdbpcs_frozen!=1) "
            "AND (cdbpcs_task.ce_baseline_id='')) "
            f"AND cdbpcs_task.taskboard_oid != {char} "
            "AND cdbpcs_task.taskboard_oid IS NOT NULL"
        )

        self.maxDiff = None
        result_actual = sig.emit("get_valid_board_object_ids")()
        result_actual_norm = []
        for ra in result_actual:
            for i in range(10):
                ra = ra.replace(str(i) + ".", ".")
                ra = ra.replace(str(i) + " ", " ")
            result_actual_norm.append(ra)
        result_expected = [project_result, task_result]
        self.assertEqual(result_actual_norm, result_expected)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
