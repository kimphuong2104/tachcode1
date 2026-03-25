#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest

from cdb import sqlapi, testcase
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import db_tools


@pytest.mark.integration
class DBTools(testcase.RollbackTestCase):
    def test_get_expression_one_partial_page(self):
        oor = db_tools.OneOfReduced("cdbpcs_prj_demand_v")
        oor.max_inlist_value = 3
        self.assertEqual(
            oor.get_expression("task_object_id", range(2)),
            "(task_object_id IN ('0','1'))",
        )

    def test_get_expression_one_page(self):
        oor = db_tools.OneOfReduced("cdbpcs_prj_demand_v")
        oor.max_inlist_value = 3
        self.assertEqual(
            oor.get_expression("task_object_id", range(3)),
            "(task_object_id IN ('0','1','2'))",
        )

    def test_get_expression_exact_fit(self):
        oor = db_tools.OneOfReduced("cdbpcs_prj_demand_v")
        oor.max_inlist_value = 3

        if db_tools.is_oracle():
            expected = "((task_object_id IN ('0','1','2')) OR (task_object_id IN ('3','4','5')))"
        else:
            expected = "(task_object_id IN ('0','1','2','3','4','5'))"

        self.assertEqual(
            oor.get_expression("task_object_id", range(6)),
            expected,
        )

    def test_get_expression_partial_page(self):
        oor = db_tools.OneOfReduced("cdbpcs_prj_demand_v")
        oor.max_inlist_value = 3

        if db_tools.is_oracle():
            expected = (
                "((task_object_id IN ('0','1','2')) OR (task_object_id IN ('3','4')))"
            )
        else:
            expected = "(task_object_id IN ('0','1','2','3','4'))"

        self.assertEqual(
            oor.get_expression("task_object_id", range(5)),
            expected,
        )

    def test_get_task_uuids(self):
        objs = []
        uuids = set()

        pid = "Ptest.db_tools"
        for i in range(2):
            task = Task.Create(
                cdb_project_id=pid,
                task_id="Ptest.{}".format(i),
                ce_baseline_id="",
            )
            objs.append(task)
            uuids.add(task.cdb_object_id)

        self.assertEqual(
            set(db_tools.get_task_uuids(objs)),
            uuids,
        )


def test_get_time_frame_overlap_condition():
    date_query = db_tools.get_time_frame_overlap_condition(
        "start_time_fcast", "end_time_fcast", date(2022, 9, 2), date(2022, 12, 29))

    rset = sqlapi.RecordSet2(
        "cdbpcs_task",
        f"cdb_project_id = 'Ptest.ResSched' AND {date_query}"
    )
    assert [x["task_name"] for x in rset] == [
        "Group Task 1",
        "Sub Task 1.2",
        "Group Task 2",
        "Sub Task 2.2",
    ]
