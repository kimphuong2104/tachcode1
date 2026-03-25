#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb import sqlapi, ddl
from cdb.comparch import protocol
from cdb.comparch.updutils import install_objects


class UpdateDocTemplateColumns:
    def run(self):
        tmpl_tables = [
            "cdbpcs_task2doctmpl",
            "cdbpcs_prj2doctmpl",
            "cdbpcs_cl2doctmpl",
            "cdbpcs_cli2doctmpl",
        ]
        for t in tmpl_tables:
            table = ddl.Table(t)
            if table and table.exists():
                self.init_tmpl_index_column(table, t)
                self.drop_table_columns(table)

    def init_tmpl_index_column(self, table, tmpl_table):

        if not table.hasColumn("tmpl_index"):
            raise RuntimeError(f"Expected DB column '{tmpl_table}.tmpl_index to exist")

        if not table.hasColumn("use_selected_index") and table.hasColumn("z_index"):
            # When updating from cs.pcs < 15.4.1 to >= 15.7.1
            protocol.logMessage(
                (
                    f"{tmpl_table}: Attribute 'use_selected_index' not found "
                    "document index 'z_index' is always used."
                )
            )
            stmt = f"{tmpl_table} SET tmpl_index = z_index"
            cnt = sqlapi.SQLupdate(stmt)
            protocol.logMessage(f"{tmpl_table}: {cnt} record(s) updated.")

        elif table.hasColumn("z_index"):
            protocol.logMessage(
                (
                    f"{tmpl_table}: Index to be used is updated "
                    "based on the 'use_selected_index' attribute."
                )
            )
            if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                stmt = (
                    f"{tmpl_table} SET tmpl_index = CASE "
                    "WHEN CAST(use_selected_index AS INTEGER) = 1 THEN z_index "
                    "ELSE 'valid_index' END"
                )
            else:
                stmt = (
                    f"{tmpl_table} SET tmpl_index = CASE "
                    "WHEN use_selected_index = 1 THEN z_index "
                    "ELSE 'valid_index' END"
                )

            cnt = sqlapi.SQLupdate(stmt)
            protocol.logMessage(f"{tmpl_table}: {cnt} record(s) updated.")

    def drop_table_columns(self, table):
        if table.hasColumn("use_selected_index"):
            table.dropAttributes("use_selected_index")
        if table.hasColumn("z_index"):
            table.dropAttributes("z_index")


RELSHIP_OPERATION_NAMES = ["cdb_create_doc_from_template", "CDB_Create", "CDB_Index"]


class InsertRelshipOpAdjustment:
    """This script reverts deleted patch of Relship Operation Adjustments"""

    def run(self):

        for op_name in RELSHIP_OPERATION_NAMES:
            install_objects(
                module_id="cs.pcs.projects_documents",
                objects=[
                    (
                        "relship_op_adjustment",
                        {
                            "relship_name": "cdbpcs_project2all_docs",
                            "op_name": op_name,
                            "link_class": 0,
                        },
                    )
                ],
            )


post = [UpdateDocTemplateColumns, InsertRelshipOpAdjustment]
