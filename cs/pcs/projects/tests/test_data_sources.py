#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import data_sources


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class DataSource(unittest.TestCase):
    @mock.patch.object(data_sources.DataSource, "KeywordQuery")
    def test_GetCombinedViewStatement(self, KeywordQuery):
        "returns UNION of single data source statements"
        a = mock.MagicMock()
        a.get_single_view_statement.return_value = "A"
        b = mock.MagicMock()
        b.get_single_view_statement.return_value = "B"
        KeywordQuery.return_value = [a, b]
        self.assertEqual(
            data_sources.DataSource.GetCombinedViewStatement("foo", ["bar"]),
            "A UNION B",
        )
        KeywordQuery.assert_called_once_with(rest_visible_name="foo")
        a.get_single_view_statement.assert_called_once_with(["bar"])
        b.get_single_view_statement.assert_called_once_with(["bar"])

    @mock.patch.object(data_sources.logging, "exception")
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView")
    def test_CompileToView_fail(self, DDUDView, exception):
        "recompile fails"
        DDUDView.ByKeys.return_value.rebuild.side_effect = RuntimeError
        with self.assertRaises(RuntimeError):
            data_sources.DataSource.CompileToView("project")
        DDUDView.ByKeys.assert_called_once_with("cdbpcs_project_indicators_v")
        DDUDView.ByKeys.return_value.rebuild.assert_called_once_with()
        exception.assert_called_once_with("CompileToView failed")

    @mock.patch.object(data_sources.logging, "exception")
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView")
    def test_CompileToView_fail(self, DDUDView, exception):
        "recompile fails"
        DDUDView.ByKeys.return_value.rebuild.side_effect = RuntimeError
        with self.assertRaises(RuntimeError):
            data_sources.DataSource.CompileToView("project_task")
        DDUDView.ByKeys.assert_called_once_with("cdbpcs_task_indicators_v")
        DDUDView.ByKeys.return_value.rebuild.assert_called_once_with()
        exception.assert_called_once_with("CompileToView failed")

    @mock.patch.object(data_sources.logging, "info")
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView")
    def test_CompileToView(self, DDUDView, info):
        "recompiles data source view"
        restname = "project"
        self.assertTrue(data_sources.DataSource.CompileToView(restname))
        DDUDView.ByKeys.assert_called_once_with("cdbpcs_project_indicators_v")
        DDUDView.ByKeys.return_value.rebuild.assert_called_once_with()
        info.assert_called_once_with("CompileToView succeeded")

    @mock.patch.object(data_sources.logging, "info")
    @mock.patch("cdb.platform.mom.relations.DDUserDefinedView")
    def test_CompileToView(self, DDUDView, info):
        "recompiles data source view"
        restname = "project_task"
        self.assertTrue(data_sources.DataSource.CompileToView(restname))
        DDUDView.ByKeys.assert_called_once_with("cdbpcs_task_indicators_v")
        DDUDView.ByKeys.return_value.rebuild.assert_called_once_with()
        info.assert_called_once_with("CompileToView succeeded")

    @mock.patch.object(data_sources.sqlapi, "SQLdbms")
    def test_get_table(self, SQLdbms):
        "returns table long text"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        self.assertEqual(
            data_sources.DataSource.get_table(datasource),
            datasource.GetText.return_value,
        )
        datasource.GetText.assert_called_once_with(
            f"cdbpcs_indicator_ds_table_{SQLdbms.return_value}",
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(data_sources.sqlapi, "SQLdbms")
    def test_get_where_fallback(self, SQLdbms):
        "returns 1=1 if where long text is empty"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        datasource.GetText.return_value = None
        self.assertEqual(data_sources.DataSource.get_where(datasource), "1=1")
        datasource.GetText.assert_called_once_with(
            f"cdbpcs_indicator_ds_where_{SQLdbms.return_value}",
        )
        SQLdbms.assert_called_once_with()

    @mock.patch.object(data_sources.sqlapi, "SQLdbms")
    def test_get_where(self, SQLdbms):
        "returns where long text"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        self.assertEqual(
            data_sources.DataSource.get_where(datasource),
            datasource.GetText.return_value,
        )
        datasource.GetText.assert_called_once_with(
            f"cdbpcs_indicator_ds_where_{SQLdbms.return_value}",
        )
        SQLdbms.assert_called_once_with()

    def test_get_order_by(self):
        "returns order_by long text"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        datasource.GetText = mock.Mock(return_value="foo")
        self.assertEqual(
            data_sources.DataSource.get_order_by(datasource), "ORDER BY foo"
        )
        datasource.GetText.assert_called_once_with(
            "cdbpcs_indicator_ds_order_by",
        )

    def test_get_order_by_no_value(self):
        "returns no value if order_by long text is empty"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        datasource.GetText = mock.Mock(return_value="")
        self.assertEqual(data_sources.DataSource.get_order_by(datasource), "")
        datasource.GetText.assert_called_once_with(
            "cdbpcs_indicator_ds_order_by",
        )

    @mock.patch("cdb.mssql.CollationDefault.get_default_collation")
    @mock.patch.object(
        data_sources.sqlapi, "SQLdbms", return_value=data_sources.sqlapi.DBMS_MSSQL
    )
    def test_get_indicator_db_field_ms(self, SQLdbms, get_default_collation):
        "returns indicator db field for MS SQL"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        self.assertEqual(
            data_sources.DataSource.get_datasource_db_field(datasource),
            f"CAST ('{datasource.data_source_id}' AS "
            f"NVARCHAR({data_sources.DataSource.data_source_id.length})) "
            f"COLLATE {get_default_collation.return_value}",
        )
        SQLdbms.assert_called_once_with()
        get_default_collation.assert_called_once_with()

    @mock.patch.object(data_sources.sqlapi, "SQLdbms")
    def test_get_indicator_db_field(self, SQLdbms):
        "returns indicator db field for non-MS SQL dbmses"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        self.assertEqual(
            data_sources.DataSource.get_datasource_db_field(datasource),
            f"'{datasource.data_source_id}'",
        )
        SQLdbms.assert_called_once_with()

    def test_get_single_view_statement(self):
        "returns single select statement"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        self.assertEqual(
            data_sources.DataSource.get_single_view_statement(
                datasource, ["cdb_project_id"]
            ),
            f"""
            SELECT
                {datasource.get_datasource_db_field.return_value} AS data_source,
                COUNT(*) AS quantity,
                cdb_project_id

            FROM {datasource.get_table.return_value}
            WHERE {datasource.get_where.return_value}
            GROUP BY cdb_project_id
            """,
        )
        datasource.get_datasource_db_field.assert_called_once_with()
        datasource.get_table.assert_called_once_with()
        datasource.get_where.assert_called_once_with()

    def test_recompile_view_event_map(self):
        "recompile view event handler is active"
        key = (("create", "copy", "modify", "delete"), "post")
        self.assertIn(
            "recompile_view",
            data_sources.DataSource.GetEventMap()[key],
        )

    def test_validate_event_map(self):
        "validation event handler is active"
        key = (("create", "copy", "modify"), "pre")
        self.assertIn(
            "validate",
            data_sources.DataSource.GetEventMap()[key],
        )

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(data_sources.logging, "exception")
    @mock.patch.object(
        data_sources.sqlapi, "RecordSet2", side_effect=data_sources.DBError(1, 2, 3)
    )
    @mock.patch.object(data_sources.sqlapi, "SQLdbms", return_value="X")
    def test_validate_fails(self, SQLdbms, RecordSet2, exception, CDBMsg):
        "failed validation (event handler)"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        ctx = mock.MagicMock()
        with self.assertRaises(data_sources.util.ErrorMessage):
            data_sources.DataSource.validate(datasource, ctx)

        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_indicator_invalid",
        )
        CDBMsg.return_value.addReplacement.assert_called_once_with(
            str(RecordSet2.side_effect),
        )

        SQLdbms.assert_called_once_with()
        RecordSet2.assert_called_once_with(
            ctx.dialog["cdbpcs_indicator_ds_table_X"],
            ctx.dialog["cdbpcs_indicator_ds_where_X"],
            addtl=f"ORDER BY {ctx.dialog['cdbpcs_indicator_ds_order_by']}",
        )
        exception.assert_called_once_with("failed to validate indicator")

    @mock.patch.object(data_sources.sqlapi, "RecordSet2")
    @mock.patch.object(data_sources.sqlapi, "SQLdbms", return_value="X")
    def test_validate(self, SQLdbms, RecordSet2):
        "validate (event handler)"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        ctx = mock.MagicMock()
        self.assertIsNone(
            data_sources.DataSource.validate(
                datasource,
                ctx,
            )
        )
        SQLdbms.assert_called_once_with()
        RecordSet2.assert_called_once_with(
            ctx.dialog["cdbpcs_indicator_ds_table_X"],
            ctx.dialog["cdbpcs_indicator_ds_where_X"],
            addtl=f"ORDER BY {ctx.dialog['cdbpcs_indicator_ds_order_by']}",
        )

    def test_recompile_view(self):
        "recompile view (event handler)"
        datasource = mock.MagicMock(spec=data_sources.DataSource)
        datasource.rest_visible_name = "foo"
        self.assertIsNone(
            data_sources.DataSource.recompile_view(
                datasource,
                None,
            )
        )
        datasource.CompileToView.assert_called_once_with(datasource.rest_visible_name)


if __name__ == "__main__":
    unittest.main()
