#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import sqlapi, testcase, ue
from cs.documents import Document

from cs.pcs.issues import Issue


@pytest.mark.unit
class IssuesTest(testcase.RollbackTestCase):
    def test__get_Documents(self):
        "not tested, method only calls SimpleJoinQuery and returns the result"
        pass

    @mock.patch.object(Document, "ByKeys")
    def test_setDefaultsByDocument_not_adopting_project_number(self, byKeys):
        "do not adopt project number from relationship context"
        mock_ctx = mock.Mock()
        mock_ctx.relationship_name = "bar"
        issue = Issue()
        issue.setDefaultsByDocument(mock_ctx)
        # assert byKeys was not called
        self.assertIsNone(issue.cdb_project_id)
        self.assertFalse(byKeys.called)

    @mock.patch.object(Document, "ByKeys")
    def test_setDefaultsByDocument_adopting_project_number(self, byKeys):
        "adopt project number from relationship context"
        mock_ctx = mock.Mock()
        mock_ctx.relationship_name = "cdbpcs_doc2issues"
        mock_ctx.parent.z_nummer = "baz1"
        mock_ctx.parent.z_index = "baz2"
        mock_doc = mock.Mock()
        mock_doc.cdb_project_id = "bar"
        byKeys.return_value = mock_doc
        issue = Issue()
        issue.setDefaultsByDocument(mock_ctx)
        # assert byKeys was called with given params
        self.assertEqual(issue.cdb_project_id, "bar")
        byKeys.assert_called_once_with(z_nummer="baz1", z_index="baz2")


@pytest.mark.unit
class DocumentsTest(testcase.RollbackTestCase):
    def test__getIssues(self):
        "not tested, method only calls SimpleJoinQuery and returns the result"
        pass

    def test__check_doc_issues_delete_pre_more_than_zero_issues(self):
        "raises exception since document has reference to issues"
        mock_ctx = mock.Mock()  # unused
        doc = Document()

        with mock.patch.object(Document, "Issues", ["not empty"]):
            with self.assertRaises(ue.Exception):
                doc._check_doc_issues_delete_pre(mock_ctx)

    def test__check_doc_issues_delete_pre_zero_issues(self):
        "raises no exception since document has no reference to issues"
        mock_ctx = mock.Mock()  # unused
        doc = Document()

        with mock.patch.object(Document, "Issues", []):
            doc._check_doc_issues_delete_pre(mock_ctx)

    @mock.patch.object(sqlapi, "SQLdelete")
    def test__doc_issues_delete_post_ctx_error(self, mock_sqlapi):
        "relation assignment not deleted because of ctx.error"
        mock_ctx = mock.Mock()
        mock_ctx.error = "foo"
        doc = Document()
        doc._doc_issues_delete_post(mock_ctx)
        # sqlapi.SQLdelete is not called
        self.assertFalse(mock_sqlapi.called)

    @mock.patch.object(sqlapi, "SQLdelete")
    def test__doc_issues_delete_post_no_ctx_error(self, mock_sqlapi):
        "relation assignment is deleted, since no ctx.error is given"
        mock_ctx = mock.Mock()
        mock_ctx.error = None
        doc = Document()
        doc.z_nummer = "foo"
        doc.z_index = "bar"
        doc._doc_issues_delete_post(mock_ctx)
        # sqlapi.SQLdelete is called
        mock_sqlapi.assert_called_once_with(
            "from cdbpcs_doc2iss where z_nummer = 'foo' and z_index = 'bar'"
        )


if __name__ == "__main__":
    unittest.main()
