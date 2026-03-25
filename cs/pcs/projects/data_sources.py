#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import logging

from cdb import sqlapi, util
from cdb.dberrors import DBError
from cdb.objects import Object


class DataSource(Object):
    __classname__ = "cdbpcs_data_source"
    __maps_to__ = "cdbpcs_data_source"

    event_map = {
        (("create", "copy", "modify"), "pre"): "validate",
        (("create", "copy", "modify", "delete"), "post"): "recompile_view",
    }

    def validate(self, ctx):
        dbms = sqlapi.SQLdbms()
        table_attr = f"cdbpcs_indicator_ds_table_{dbms}"
        where_attr = f"cdbpcs_indicator_ds_where_{dbms}"
        order_by_attr = "cdbpcs_indicator_ds_order_by"
        table = ctx.dialog[table_attr]
        where = ctx.dialog[where_attr]
        order_by = ctx.dialog[order_by_attr]

        try:
            if order_by:
                sqlapi.RecordSet2(table, where, addtl=f"ORDER BY {order_by}")
            else:
                sqlapi.RecordSet2(table, where)
        except DBError as error:
            logging.exception("failed to validate indicator")
            raise util.ErrorMessage("cdbpcs_indicator_invalid", error)

    def get_table(self):
        field = f"cdbpcs_indicator_ds_table_{sqlapi.SQLdbms()}"
        return self.GetText(field)

    def get_where(self):
        field = f"cdbpcs_indicator_ds_where_{sqlapi.SQLdbms()}"
        return self.GetText(field) or "1=1"

    def get_order_by(self):
        field = "cdbpcs_indicator_ds_order_by"
        text = self.GetText(field)
        if text:
            return f"ORDER BY {text}"
        else:
            return ""

    def get_datasource_db_field(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            from cdb.mssql import CollationDefault

            return (
                f"CAST ('{self.data_source_id}' AS "
                f"NVARCHAR({DataSource.data_source_id.length})) "
                f"COLLATE {CollationDefault.get_default_collation()}"
            )

        return f"'{self.data_source_id}'"

    def get_single_view_statement(self, keys):
        data_source = self.get_datasource_db_field()
        return """
            SELECT
                {data_source} AS data_source,
                COUNT(*) AS quantity,
                {keys}

            FROM {table}
            WHERE {where}
            GROUP BY {keys}
            """.format(
            data_source=data_source,
            keys=",".join(keys),
            table=self.get_table(),
            where=self.get_where(),
        )

    @classmethod
    def GetCombinedViewStatement(cls, restname, keys):
        data_sources = cls.KeywordQuery(rest_visible_name=restname)
        stmts = [ds.get_single_view_statement(keys) for ds in data_sources]
        return " UNION ".join(stmts)

    @classmethod
    def CompileToView(cls, restname):
        """
        Recreates (e.g. repairs) view from current configuration.

        :param restname: Restname of the class for which a view shall be compiled
        :return: True if the compile was successful else raises an Excpetion
        """
        from cdb.platform.mom.relations import DDUserDefinedView

        from cs.pcs.projects.indicators import map_restname_to_view

        if restname not in map_restname_to_view:
            logging.info("Please compile the relevant view manually.")
            return

        view = DDUserDefinedView.ByKeys(map_restname_to_view[restname])

        try:
            view.rebuild()
        except RuntimeError:
            logging.exception("CompileToView failed")
            raise

        logging.info("CompileToView succeeded")
        return True

    def recompile_view(self, ctx=None):
        self.CompileToView(self.rest_visible_name)
