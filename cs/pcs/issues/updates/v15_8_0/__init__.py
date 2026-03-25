#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ddl, sqlapi
from cdb.comparch import protocol
from cdb.platform.mom.entities import Class

from cs.pcs.issues import Issue


class MigrateIssueIDWithHyphen:
    EXPECTED_FIELD_COLUMNS = {"issue_id": ddl.Char("issue_id", 11)}

    DEFAULT_TABLES = [
        # long texts
        ("cdbpcs_iss_txt", "issue_id"),
        ("cdbpcs_isss_txt", "issue_id"),
        # field_name = 'issue_id' OR predefined_field_name = 'issue_id'
        ("cdb_action2issue", "issue_id"),
        ("cdbpcs_iss_prot", "issue_id"),
        ("cdbpcs_iss_log", "issue_id"),
        ("cdbpcs_issue", "issue_id"),
        ("cdbpcs_doc2iss", "issue_id"),
        ("cdbpcs_part2iss", "issue_id"),  # cs.vp_pcs
        ("cdbrqm_specobject2issue", "issue_id"),  # cs.requirements
    ]

    UPDATE_PATTERN = {
        sqlapi.DBMS_ORACLE: "'{id_prefix}0' || SUBSTR({field}, {char_no})",
        sqlapi.DBMS_MSSQL: "'{id_prefix}0' + SUBSTRING({field}, {char_no}, LEN({field}))",
        sqlapi.DBMS_SQLITE: "REPLACE({field}, '{id_prefix}-', '{id_prefix}0')",
        sqlapi.DBMS_POSTGRES: "'{id_prefix}0' || SUBSTR({field}, {char_no})",
    }

    def __init__(self, tables=None):
        self.default = tables is None

        if self.default:
            tables = self.DEFAULT_TABLES

        self.tables = self.get_tables(tables)

    def log_error(self, msg):
        if self.default:
            # missing default tables/fields are ok, so just warn
            protocol.logWarning(msg)
        else:
            # missing custom tables/fields are considered errors
            logging.error(msg)

    def log_info(self, msg):
        if self.default:
            protocol.logMessage(msg)
        else:
            logging.info(msg)

    def log_warning(self, msg):
        if self.default:
            protocol.logWarning(msg)
        else:
            logging.warning(msg)

    def ensure_correct_field_column(self, table_info, field):
        if field not in self.EXPECTED_FIELD_COLUMNS:
            return

        column = table_info.getColumn(field)
        expected_column = self.EXPECTED_FIELD_COLUMNS[field]
        if not type(column) is type(expected_column):
            expected_column.notnull = column.notnull
            expected_column.comment = column.comment
            table_info.modifyAttributes(expected_column)

    def get_tables(self, tables):
        result = []

        for (table, field) in tables:
            table_info = ddl.Table(table)
            if table_info.exists():
                if table_info.hasColumn(field):
                    self.ensure_correct_field_column(table_info, field)
                    result.append((table, field))
                else:
                    self.log_error(f"ignoring unknown field '{table}.{field}'")
            else:
                self.log_error(f"ignoring unknown table '{table}'")

        return result

    def get_replace_stmt(self, id_prefix, char_no, field):
        dbms = sqlapi.SQLdbms()
        pattern = self.UPDATE_PATTERN.get(dbms, None)

        if pattern:
            return pattern.format(
                id_prefix=id_prefix,
                char_no=char_no,
                field=field,
            )

        raise RuntimeError(f"unknown DBMS: {dbms}")

    def get_stmt(self, prefix, table, field):
        char_no = len(prefix) + 2
        replace_stmt = self.get_replace_stmt(prefix, char_no, field)
        return (
            "{table} "
            "SET {field} = {replace_stmt} "
            "WHERE {field} LIKE '{ID_PREFIX}-%'".format(
                ID_PREFIX=prefix,
                table=table,
                field=field,
                replace_stmt=replace_stmt,
            )
        )

    def run(self):
        prefix = Issue.ID_PREFIX

        for table, field in self.tables:
            stmt = self.get_stmt(prefix, table, field)
            rows = sqlapi.SQLupdate(stmt)
            self.log_info(f"updated {rows} rows in '{table}'")

        self.log_warning(
            "Issue IDs migrated. Custom fields have to be migrated manually."
        )

        # reindex cdbpcs_issue
        # this is an asynchronous process and creates a job in TESJobQueue job queue
        Class.updateSearchIndexByClassname("cdbpcs_issue")


pre = []
post = [MigrateIssueIDWithHyphen]
