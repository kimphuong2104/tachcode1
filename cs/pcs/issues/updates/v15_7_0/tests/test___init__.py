#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.issues import Issue
from cs.pcs.issues.updates import v15_7_0


def is_oracle():
    return v15_7_0.sqlapi.SQLdbms() == v15_7_0.sqlapi.DBMS_ORACLE


def is_postgres():
    return v15_7_0.sqlapi.SQLdbms() == v15_7_0.sqlapi.DBMS_POSTGRES


@pytest.mark.integration
class MigrateIssueID(testcase.RollbackTestCase):
    @mock.patch.object(v15_7_0.logging, "error")
    def test_ignore_missing(self, error):
        update = v15_7_0.MigrateIssueID(
            [
                ("cdbpcs_issue", "issue_id"),
                ("does_not_exist", "issue_id"),
                ("cdbpcs_issue", "does_not_exist"),
            ]
        )
        self.assertEqual(update.tables, [("cdbpcs_issue", "issue_id")])
        error.assert_has_calls(
            [
                mock.call("ignoring unknown table 'does_not_exist'"),
                mock.call("ignoring unknown field 'cdbpcs_issue.does_not_exist'"),
            ]
        )

    def test_run(self):
        v15_7_0.sqlapi.SQLdelete("FROM cdbpcs_issue")
        Issue.Create(issue_id="123?", cdb_project_id="foo")
        Issue.Create(issue_id="123456", cdb_project_id="foo")
        Issue.Create(issue_id="1234567", cdb_project_id="foo")
        Issue.Create(issue_id="123456789", cdb_project_id="foo")

        self.assertIsNone(v15_7_0.MigrateIssueID().run())

        if is_oracle() or is_postgres():
            # Oracle's and PostgreSQL's LPAD cuts chars from the end
            # but we don't bother as this is undefined behavior anyway
            expected = ["ISS0000123?", "ISS00123456", "ISS01234567", "ISS12345678"]
        else:
            expected = ["ISS0000123?", "ISS00123456", "ISS01234567", "ISS23456789"]

        self.assertEqual(Issue.Query().issue_id, expected)

    def test_custom_fields(self):
        v15_7_0.sqlapi.SQLdelete("FROM cdbpcs_issue")
        Issue.Create(issue_id="test001", cdb_project_id="123?")
        Issue.Create(issue_id="test002", cdb_project_id="123456")
        Issue.Create(issue_id="test003", cdb_project_id="1234567")
        Issue.Create(issue_id="test004", cdb_project_id="123456789")

        self.assertIsNone(
            v15_7_0.MigrateIssueID(
                [
                    ("cdbpcs_issue", "cdb_project_id"),
                ]
            ).run()
        )
        issues = Issue.Query()
        self.assertEqual(issues.issue_id, ["test001", "test002", "test003", "test004"])

        if is_oracle() or is_postgres():
            # Oracle's and PostgreSQL's LPAD cuts chars from the end
            # but we don't bother as this is undefined behavior anyway
            expected = ["ISS0000123?", "ISS00123456", "ISS01234567", "ISS12345678"]
        else:
            expected = ["ISS0000123?", "ISS00123456", "ISS01234567", "ISS23456789"]

        self.assertEqual(issues.cdb_project_id, expected)


if __name__ == "__main__":
    unittest.main()
