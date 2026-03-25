# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


import unittest

import mock
from cdb import sqlapi

from cs.actions.catalogs import (
    CatalogActionResponsibleData,
    ResponsibleCatalog,
    format_in_condition,
    partition,
)


class Utility(unittest.TestCase):
    def test_partition_negative(self):
        with self.assertRaises(ValueError):
            next(partition("ABCDE", -1))

    def test_partition_zero(self):
        with self.assertRaises(ValueError):
            next(partition("ABCDE", 0))

    def test_partition(self):
        self.assertEqual(
            list(partition("ABCDE", 2)),
            ["AB", "CD", "E"],
        )

    def test_partition_large(self):
        self.assertEqual(
            list(partition("ABCDE", 10)),
            ["ABCDE"],
        )

    def test_format_in_condition_no_values(self):
        "valid but impossible condition"
        self.assertEqual(
            format_in_condition("foo", [], 3),
            "1=0",
        )

    def test_format_in_condition(self):
        "limits expressions in a single IN-clause"
        self.assertEqual(
            format_in_condition("foo", range(7), 3),
            "foo IN (0,1,2) OR foo IN (3,4,5) OR foo IN (6)",
        )


class CatalogActionResponsibleDataTestCase(unittest.TestCase):
    @mock.patch.object(sqlapi, "RecordSet2", return_value=[])
    def test_initData(self, recordSet):
        cat = mock.MagicMock(CatalogActionResponsibleData)
        cat.getSQLCondition.return_value = "cdb_project_id = ''"
        cat.data = None
        cat.cdb_project_id = ""

        CatalogActionResponsibleData._initData(cat, False)

        recordSet.assert_called_once_with(
            "cdb_action_resp_brows", "cdb_project_id = ''", addtl=" ORDER BY order_by"
        )

    @mock.patch.object(sqlapi, "RecordSet2", return_value=[])
    def test_initDataWithCondition(self, recordSet):
        cat = mock.MagicMock(CatalogActionResponsibleData)
        cat.getSQLCondition.return_value = "cdb_project_id = 'foo'"
        cat.data = None
        cat.cdb_project_id = "1234"

        CatalogActionResponsibleData._initData(cat, False)

        recordSet.assert_called_once_with(
            "cdb_action_resp_brows",
            "cdb_project_id = 'foo'",
            addtl=" ORDER BY order_by",
        )

    def test_onSearchChangedNoSearchArgs(self):
        cat = mock.MagicMock(CatalogActionResponsibleData)
        cat.getSearchArgs.return_value = []

        CatalogActionResponsibleData.onSearchChanged(cat)

        cat._initData.assert_called_once_with(True)
        self.assertEqual(cat.cdb_project_id, None)

    def test_onSearchChangedSearchArgs(self):
        arg = mock.MagicMock()
        arg.name = "foo"
        cat = mock.MagicMock(CatalogActionResponsibleData)
        cat.getSearchArgs.return_value = [arg]

        CatalogActionResponsibleData.onSearchChanged(cat)

        cat._initData.assert_called_once_with(True)
        self.assertEqual(cat.cdb_project_id, None)

    def test_onSearchChangedProject(self):
        arg = mock.MagicMock()
        arg.name = "foo"
        arg1 = mock.MagicMock()
        arg1.name = "cdb_project_id"
        arg1.value = "project_id"
        cat = mock.MagicMock(CatalogActionResponsibleData)
        cat.getSearchArgs.return_value = [arg, arg1]

        CatalogActionResponsibleData.onSearchChanged(cat)

        cat._initData.assert_called_once_with(True)
        self.assertEqual(cat.cdb_project_id, "project_id")


class ResponsibleCatalogTestCase(unittest.TestCase):
    def test_preMask_otherCatalog(self):
        ctx = mock.MagicMock()
        ctx.catalog_name = "Some other catalog"
        cat = mock.MagicMock(ResponsibleCatalog)

        ResponsibleCatalog.on_query_catalog_pre_mask(cat, ctx)

        ctx.set_fields_writeable.assert_not_called()

    def test_preMask(self):
        ctx = mock.MagicMock()
        ctx.catalog_name = "cdb_action_resp_brows"
        cat = mock.MagicMock(ResponsibleCatalog)

        ResponsibleCatalog.on_query_catalog_pre_mask(cat, ctx)

        ctx.set_fields_writeable.assert_called_once_with(["cdb_project_id"])
