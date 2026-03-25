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
from cdb.objects.org import Person
from cdb.platform.mom.entities import Class

from cs.pcs.issues import Issue
from cs.pcs.projects.updates.v15_7_0 import InitSortableIDBase


class InitSortableID_Issue(InitSortableIDBase):
    """
    Initializes the new primary key ``cdbpcs_iss_prot.cdbprot_sortable_id``.
    """

    __table_name__ = "cdbpcs_iss_prot"


class MigrateIssueReportedBy:
    def run(self):
        all_issues = Issue.Query()
        for issue in all_issues:
            if issue.reported_by:
                condition = f"name='{issue.reported_by}'"
                person = Person.Query(condition)

                # update reported_by_persno when one and only one person is
                # found against the current reported_by name
                if person and len(person) == 1:
                    person = person[0]
                    issue.reported_by_persno = person.personalnummer
                else:
                    protocol.logWarning(
                        "Please manually fill the Reported By field of Open Issue: "
                        f"Issue No.: {issue.issue_id}, Title: {issue.issue_name}, "
                        f"Alias: {issue.reported_by}"
                    )


class MigrateIssueID:
    """
    See
    :ref:`Release Notes <pcs_release_notes_15_7_0_0_devs_migrate_issue_id>`
    for details.
    """

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
    ZFILL_PATTERN = {
        sqlapi.DBMS_ORACLE: "LPAD({field}, {padding}, '0')",
        sqlapi.DBMS_MSSQL: "RIGHT('{fill}' + ISNULL({field}, ''), {padding})",
        sqlapi.DBMS_SQLITE: ("SUBSTR('{fill}' || {field}, -{padding}, {padding})"),
        sqlapi.DBMS_POSTGRES: "LPAD({field}, {padding}, '0')",
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

    def get_zfill_stmt(self, padding, field):
        dbms = sqlapi.SQLdbms()
        pattern = self.ZFILL_PATTERN.get(dbms, None)

        if pattern:
            return pattern.format(
                padding=padding,
                fill="0" * padding,
                field=field,
            )

        raise RuntimeError(f"unknown DBMS: {dbms}")

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

    def get_stmt(self, prefix, padding, table, field):
        return (
            "{table} "
            "SET {field} = '{ID_PREFIX}' {strcat} {padded_value} "
            "WHERE {field} NOT LIKE '{ID_PREFIX}%'".format(
                ID_PREFIX=prefix,
                strcat=sqlapi.SQLstrcat(),
                padded_value=self.get_zfill_stmt(padding, field),
                table=table,
                field=field,
            )
        )

    def run(self):
        prefix = Issue.ID_PREFIX
        padding = None

        for field in sqlapi.RecordSet2(
            "cdbdd_field", "classname = 'cdbpcs_issue' AND field_name = 'issue_id'"
        ):
            padding = field.data_length - len(prefix)

        if padding is None:
            raise ValueError("missing field definition cdbpcs_issue.issue_id")

        for table, field in self.tables:
            stmt = self.get_stmt(prefix, padding, table, field)
            rows = sqlapi.SQLupdate(stmt)
            self.log_info(f"updated {rows} rows in '{table}'")

        self.log_warning(
            "Issue IDs migrated. "
            "Custom fields have to be migrated manually. "
            "You can list custom fields to be migrated by running "
            "'powerscript -m cs.pcs.issues.updates.v15_7_0.check_issue_id_col'."
        )

        # reindex cdbpcs_issue
        # this is an asynchronous process and creates a job in TESJobQueue job queue
        Class.updateSearchIndexByClassname("cdbpcs_issue")


pre = [InitSortableID_Issue]
post = [MigrateIssueReportedBy, MigrateIssueID]
