#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from cdb import sig, testcase
from cs.documents import Document

from cs.pcs.issues import Issue

# do not import cs.pcs.issues_documents.Issue directly
# to test connection in bootstrapping


def method_is_connected(module, name, *slot):
    slot_names = [(x.__module__, x.__name__) for x in sig.find_slots(*slot)]
    return (module, name) in slot_names


@pytest.mark.integration
class IssueDocumentsIntegrationTest(testcase.RollbackTestCase):

    # ----------- test connection for Issues --------------------
    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_setDefaultsByDocument_is_connected_to_create_pre_mask(self):
        "Issue.setDefaultsByDocument is connected to create.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.issues_documents",
                "setDefaultsByDocument",
                Issue,
                "create",
                "pre_mask",
            )
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_setDefaultsByDocument_is_connected_to_copy_pre_mask(self):
        "Issue.setDefaultsByDocument is connected to copy.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.issues_documents",
                "setDefaultsByDocument",
                Issue,
                "copy",
                "pre_mask",
            )
        )

    # ----------- test connection for Document --------------------
    @pytest.mark.dependency(depends=["cs.documents"])
    def test__check_doc_issues_delete_pre_is_connected(self):
        "Document._check_doc_issues_delete_pre is connected to delete.pre"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.issues_documents",
                "_check_doc_issues_delete_pre",
                Document,
                "delete",
                "pre",
            )
        )

    @pytest.mark.dependency(depends=["cs.documents"])
    def test__doc_issues_delete_post_is_connected(self):
        "Document._doc_issues_delete_post is connected to delete.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.issues_documents",
                "_doc_issues_delete_post",
                Document,
                "delete",
                "post",
            )
        )


if __name__ == "__main__":
    unittest.main()
