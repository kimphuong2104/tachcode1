#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import pytest
from cdb import auth, testcase
from mock import MagicMock, call, patch

from cs.pcs.efforts import catalogs
from cs.pcs.projects.tasks import Task


@pytest.mark.unit
class CatalogDescriptionData(testcase.RollbackTestCase):
    @patch("cs.pcs.efforts.catalogs.gui.CDBCatalogContent.__init__")
    def test__init__(self, init):
        catalog = MagicMock()
        cdef = MagicMock()
        cdef.getProjection = MagicMock(return_value="tabledef")
        catalog.getTabularDataDefName = MagicMock(return_value="tabledefname")
        catalog.getClassDefSearchedOn = MagicMock(return_value=cdef)

        catalog_description_data = catalogs.CatalogDescriptionData(
            catalog, "proj1", "task1"
        )
        cdef.getProjection.assert_called_once_with("tabledefname", True)

        init.assert_called_once_with(catalog_description_data, "tabledef")
        self.assertEqual(catalog_description_data.task_id, "task1")
        self.assertEqual(catalog_description_data.cdb_project_id, "proj1")

        catalog.getClassDefSearchedOn = MagicMock(return_value=None)
        init.reset_mock()
        catalog_description_data = catalogs.CatalogDescriptionData(
            catalog, "proj1", "task1"
        )
        init.assert_called_once_with(catalog_description_data, "tabledefname")

    @patch("cs.pcs.efforts.TimeSheet.KeywordQuery")
    @patch("cs.pcs.efforts.catalogs.Rule.ByKeys")
    def test__initData(self, ruleByKeys, kwQuery):
        catalog = MagicMock()
        cdef = MagicMock()
        cdef.getProjection = MagicMock(return_value="tabledef")
        catalog.getTabularDataDefName = MagicMock(return_value="tabledefname")
        catalog.getClassDefSearchedOn = MagicMock(return_value=cdef)

        getObjects = MagicMock(
            return_value=[
                MagicMock(GetDescription=lambda: "description", checklist_id="clid")
            ]
        )
        ruleByKeys.return_value = MagicMock(getObjects=getObjects)

        kwQuery.return_value = [MagicMock(description="description1")]

        description_data = catalogs.CatalogDescriptionData(catalog, "proj1", "task1")

        description_data._initData()

        self.assertEqual(
            description_data.data,
            [
                {"description": "description"},
                {"description": "description1"},
            ],
        )

        kwQuery.assert_has_calls(
            [
                call(
                    person_id=auth.persno,
                    cdb_project_id=description_data.cdb_project_id,
                    task_id=description_data.task_id,
                )
            ]
        )

        self.assertEqual(ruleByKeys.call_count, 3)


@pytest.mark.unit
class TasksHook(testcase.RollbackTestCase):
    def test_on_query_catalog_pre_mask(self):
        ctx = MagicMock(catalog_name="cdbpcs_tasks_for_efforts")
        ctx.set_fields_readonly = MagicMock()
        task = Task()
        task.on_query_catalog_pre_mask(ctx)
        ctx.set_fields_readonly.assert_called_once_with(
            ["cdb_project_id", "project_name"]
        )


if __name__ == "__main__":
    unittest.main()
