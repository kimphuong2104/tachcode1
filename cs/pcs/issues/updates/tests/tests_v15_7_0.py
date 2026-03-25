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
from cdb.comparch import protocol
from cdb.objects.org import Person

from cs.pcs.issues import Issue
from cs.pcs.issues.updates.v15_7_0 import MigrateIssueReportedBy


@pytest.mark.unit
class TestMigrateIssueReportedBy(testcase.RollbackTestCase):
    @mock.patch.object(Issue, "Query")
    @mock.patch.object(Person, "Query")
    def test_run(self, personQuery, issueQuery):
        def getIssue(reported_by):
            return mock.MagicMock(reported_by=reported_by)

        all_issues = [getIssue("name1"), getIssue("name2"), getIssue("name3")]
        issueQuery.return_value = all_issues

        personQuery.return_value = [mock.MagicMock(personalnummer="123")]

        MigrateIssueReportedBy().run()

        issueQuery.assert_called_once()
        personQuery.assert_has_calls(
            [
                mock.call("name='name1'"),
                mock.call("name='name2'"),
                mock.call("name='name3'"),
            ]
        )

        result = [i.reported_by_persno for i in all_issues]
        self.assertEqual(result, ["123", "123", "123"])

    @mock.patch.object(Issue, "Query")
    @mock.patch.object(Person, "Query")
    @mock.patch.object(protocol, "logWarning")
    def test_run_duplicate_persons(self, logWarning, personQuery, issueQuery):
        def getIssue(reported_by):
            return mock.MagicMock(
                reported_by=reported_by, reported_by_persno=reported_by
            )

        all_issues = [getIssue("name1"), getIssue("name2"), getIssue("name3")]
        issueQuery.return_value = all_issues

        personQuery.return_value = [
            mock.MagicMock(personalnummer="123"),
            mock.MagicMock(personalnummer="123"),
        ]

        MigrateIssueReportedBy().run()

        issueQuery.assert_called_once()
        personQuery.assert_has_calls(
            [
                mock.call("name='name1'"),
                mock.call("name='name2'"),
                mock.call("name='name3'"),
            ]
        )

        result = [i.reported_by_persno for i in all_issues]
        self.assertEqual(result, ["name1", "name2", "name3"])
        self.assertEqual(3, logWarning.call_count)


if __name__ == "__main__":
    unittest.main()
