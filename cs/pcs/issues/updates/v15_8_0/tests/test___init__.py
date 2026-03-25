#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from cdb import testcase

from cs.pcs.issues import Issue
from cs.pcs.issues.updates import v15_8_0


@pytest.mark.integration
class MigrateIssueIDWithHyphen(testcase.RollbackTestCase):
    def test_run(self):
        v15_8_0.sqlapi.SQLdelete("FROM cdbpcs_issue")
        Issue.Create(issue_id="AISS-123456", cdb_project_id="foo")
        Issue.Create(issue_id="ISS-000123?", cdb_project_id="foo")
        Issue.Create(issue_id="ISS-1234567", cdb_project_id="foo")
        Issue.Create(issue_id="ISS123?", cdb_project_id="foo")
        Issue.Create(issue_id="ISS12345678", cdb_project_id="foo")

        self.assertIsNone(v15_8_0.MigrateIssueIDWithHyphen().run())

        expected = [
            "AISS-123456",
            "ISS0000123?",
            "ISS01234567",
            "ISS123?",
            "ISS12345678",
        ]

        # Somewhat misleadingly named but assertCountEqual
        # does look at the elements and not just the
        # number of elements
        self.assertCountEqual(Issue.Query().issue_id, expected)


if __name__ == "__main__":
    unittest.main()
