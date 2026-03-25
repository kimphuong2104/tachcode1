#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import pytest
from cdb import sqlapi, testcase

from cs.pcs.projects import Project, data_sources, indicators
from cs.pcs.projects.common.lists.list import ListDataProvider
from cs.pcs.projects.tasks import Task

# define constants for repeating ids/names
TEST_DATA_SOURCE = "TEST_DATA_SOURCE"
TEST_INDICATOR = "TEST_INDICATOR"
PROJECT_REST_NAME = "project"
TASK_REST_NAME = "project_task"


@pytest.mark.integration
class ListIntegration(testcase.RollbackTestCase):
    def _create_project(self, pid, bid):
        return Project.Create(cdb_project_id=pid, ce_baseline_id=bid)

    def _create_task(self, pid, bid, tid, **kwargs):
        return Task.Create(
            cdb_project_id=pid, ce_baseline_id=bid, task_id=tid, **kwargs
        )

    def tearDown(self):
        super().tearDown()
        sqlapi.SQLdelete(f"FROM cdbpcs_indicator WHERE name = '{TEST_INDICATOR}'")
        sqlapi.SQLdelete(
            f"FROM cdbpcs_data_source WHERE data_source_id = '{TEST_DATA_SOURCE}'"
        )
        data_sources.DataSource.CompileToView(PROJECT_REST_NAME)
        data_sources.DataSource.CompileToView(TASK_REST_NAME)

    def test__resolveDataSourceSQL(self):

        # create an simple indicator
        ds = data_sources.DataSource.Create(
            data_source_id=TEST_DATA_SOURCE,
            rest_visible_name=PROJECT_REST_NAME,
            resulting_classname="cdbpcs_task",
        )
        ds.SetText(
            f"cdbpcs_indicator_ds_table_{sqlapi.SQLdbms()}",
            "cdbpcs_task",
        )
        ds.SetText(
            f"cdbpcs_indicator_ds_where_{sqlapi.SQLdbms()}",
            "1=1",
        )
        ds.SetText("cdbpcs_indicator_ds_order_by", "task_name ASC")
        indicators.Indicator.Create(
            name=TEST_INDICATOR,
            rest_visible_name=PROJECT_REST_NAME,
            # pylint: disable-next=consider-using-f-string
            data_source_pattern="{}".format("{" + TEST_DATA_SOURCE + "}"),
        )
        data_sources.DataSource.CompileToView(PROJECT_REST_NAME)

        # create a project with a task
        p = self._create_project("TEST_PROJECT", "")
        t = self._create_task("TEST_PROJECT", "", "1", task_name="TEST_TASK")

        # create DataProvider
        ldp = ListDataProvider(
            name="TEST_DATENPROVIDER",
            classname="cdbpcs_task",
            data_source_id=TEST_DATA_SOURCE,
            rest_visible_name=PROJECT_REST_NAME,
            # uses the by default existing Task_Default ListItemConfig
            list_item_cfg_object_id="f2f0e7d2-f62c-11e9-9ccc-207918bb3392",
        )

        objectIds, error = ldp._resolveDataSourceSQL(
            f"{p.cdb_project_id}@{p.ce_baseline_id}"
        )

        self.assertListEqual(objectIds, [t.cdb_object_id])
        self.assertFalse(error)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
