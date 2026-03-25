#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import unittest

from cdb import sqlapi, testcase

from cs.pcs.projects.tests.common import generate_project, generate_task
from cs.pcs.projects.updates.v15_7_0 import update_finishedby

time1 = "2022-04-26 00:00:00"
time2 = "2022-04-28 05:00:00"


class UpdateFinishedBy(testcase.RollbackTestCase):
    def _prepare_test(self):
        time1 = sqlapi.SQLdbms_date(datetime.datetime(2022, 4, 26, 0, 10, 0))
        time2 = sqlapi.SQLdbms_date(datetime.datetime(2022, 4, 28, 0, 11, 0))
        self.project = generate_project(
            project_name="bar", cdb_project_id="foo", status=50
        )
        self.task = generate_task(self.project, "TASK-1", cdb_finishedby="foo1")
        count = 0
        for status in [0, 20, 50, 200]:
            count += 1
            sqlapi.SQLinsert(
                f"INTO cdbpcs_tsk_prot (cdb_project_id, task_id, cdbprot_newstate, cdbprot_zeit, "
                f"cdbprot_persnum, cdbprot_sortable_id) Values('foo', 'TASK-1', {status}, {time1}, "
                f"'A_{count}', 'id1_{count}')"
            )

            sqlapi.SQLinsert(
                f"INTO cdbpcs_tsk_prot (cdb_project_id, task_id, cdbprot_newstate, cdbprot_zeit, "
                f"cdbprot_persnum, cdbprot_sortable_id) Values('foo', 'TASK-1', {status}, {time2}, "
                f"'B_{count}', 'id2_{count}')"
            )

    def test_run_task_not_in_status(self):
        self._prepare_test()
        update_finishedby.main()
        tx = sqlapi.SQLselect(
            "cdb_finishedby FROM cdbpcs_task where cdb_project_id='foo'"
        )
        self.assertEqual(sqlapi.SQLstring(tx, 0, 0), "foo1")

    def test_run_task_in_status(self):
        self._prepare_test()
        self.task.Update(status=200)
        update_finishedby.main()
        tx = sqlapi.SQLselect(
            "cdb_finishedby FROM cdbpcs_task where cdb_project_id='foo'"
        )
        self.assertEqual(sqlapi.SQLstring(tx, 0, 0), "B_4")


if __name__ == "__main__":
    unittest.main()
