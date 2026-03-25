#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs import efforts
from cs.pcs.efforts import sqlapi


@pytest.mark.unit
class TimeSheetTest(testcase.RollbackTestCase):
    @mock.patch.object(sqlapi, "RecordSet2", return_value=["foo"])
    def test_check_last_effort(self, RecordSet2):
        task = efforts.Task(effort_act=5.0)
        with mock.patch.object(
            efforts.TimeSheet, "Task", new_callable=mock.PropertyMock, return_value=task
        ):
            obj = efforts.TimeSheet(task_id="bass")
            obj.checkLastEffort("ctx")
            RecordSet2.assert_called_once_with("cdbpcs_time_sheet", "task_id = 'bass'")
            self.assertEqual(obj.Task.effort_act, 5.0)

    @mock.patch.object(sqlapi, "RecordSet2", return_value=[])
    def test_check_last_effort_reset(self, RecordSet2):
        task = efforts.Task(effort_act=5.0)
        with mock.patch.object(
            efforts.TimeSheet, "Task", new_callable=mock.PropertyMock, return_value=task
        ):
            obj = efforts.TimeSheet(task_id="bass")
            obj.checkLastEffort("ctx")
            RecordSet2.assert_called_once_with("cdbpcs_time_sheet", "task_id = 'bass'")
            self.assertEqual(obj.Task.effort_act, None)

    @mock.patch.object(efforts.CatalogProjectTaskProposals, "KeywordQuery")
    def test_prioritize_selected_task_batch(self, kwQuery):
        ctx = mock.MagicMock(interactive=0, uses_webui=False)
        obj = efforts.TimeSheet()
        obj.prioritize_selected_task(ctx)
        kwQuery.assert_not_called()

    @mock.patch.object(efforts, "auth")
    @mock.patch.object(efforts.datetime, "datetime")
    @mock.patch.object(efforts.CatalogProjectTaskProposals, "KeywordQuery")
    def test_prioritize_selected_task_update(self, kwQuery, dt, auth):
        ctx = mock.MagicMock(interactive=1)
        dt.now.return_value = "now"
        auth.persno = "person"
        kwQuery.return_value = [mock.MagicMock()]
        obj = efforts.TimeSheet()
        obj.cdb_project_id = "p1"
        obj.task_id = "t1"

        obj.prioritize_selected_task(ctx)
        kwQuery.assert_called_once_with(
            catalog_name=efforts.EFFORTS_TASK_CATALOG,
            catalog_personalnummer="person",
            cdb_project_id="p1",
            task_id="t1",
            ce_baseline_id="",
        )
        kwQuery.return_value[0].Update.assert_called_once_with(catalog_sel_time="now")

    @mock.patch.object(efforts, "auth")
    @mock.patch.object(efforts.datetime, "datetime")
    @mock.patch.object(efforts.CatalogProjectTaskProposals, "Create")
    @mock.patch.object(efforts.CatalogProjectTaskProposals, "KeywordQuery")
    def test_prioritize_selected_task_create(self, kwQuery, create, dt, auth):
        ctx = mock.MagicMock(interactive=1)
        dt.now.return_value = "now"
        auth.persno = "person"
        kwQuery.return_value = []
        obj = efforts.TimeSheet()
        obj.cdb_project_id = "p1"
        obj.task_id = "t1"

        obj.prioritize_selected_task(ctx)
        kwQuery.assert_called_once_with(
            catalog_name=efforts.EFFORTS_TASK_CATALOG,
            catalog_personalnummer="person",
            cdb_project_id="p1",
            task_id="t1",
            ce_baseline_id="",
        )
        create.assert_called_once_with(
            catalog_name=efforts.EFFORTS_TASK_CATALOG,
            catalog_personalnummer="person",
            cdb_project_id="p1",
            task_id="t1",
            catalog_sel_time="now",
            ce_baseline_id="",
        )

    def test_set_read_only_set_writeable(self):
        obj = efforts.TimeSheet()
        ctx = mock.MagicMock()
        del ctx.uses_webui

        ctx.dialog.get_attribute_names.return_value = ["cdb_project_id", "project_name"]

        self.assertEquals(obj.set_read_only(ctx), None)
        ctx.set_writeable.assert_called_once_with("task_name")
        ctx.set_readonly.assert_not_called()

    def test_set_read_only_set_readonly(self):
        obj = efforts.TimeSheet()
        ctx = mock.MagicMock()
        ctx.uses_webui = False

        ctx.dialog.get_attribute_names.return_value = ["cdb_project_id", "project_name"]
        ctx.dialog.cdb_project_id = ""
        self.assertEquals(obj.set_read_only(ctx), None)
        ctx.set_writeable.assert_not_called()
        ctx.set_readonly.assert_called_once_with("task_name")

    def test_set_read_only_webui(self):
        obj = efforts.TimeSheet()
        ctx = mock.MagicMock()
        ctx.uses_webui = True

        self.assertEquals(obj.set_read_only(ctx), None)
        ctx.set_writeable.assert_not_called()
        ctx.set_readonly.assert_not_called()


if __name__ == "__main__":
    unittest.main()
