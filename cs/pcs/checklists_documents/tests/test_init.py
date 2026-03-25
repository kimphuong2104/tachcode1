#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import sqlapi, testcase, ue
from cs.documents import Document

from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.checklists_documents import CLItemTemplateDocRef, CLTemplateDocRef
from cs.pcs.projects import Project


@pytest.mark.unit
class ChecklistTest(testcase.RollbackTestCase):
    def test__get_Documents(self):
        # not tested, method only calls SimpleJoinQuery and returns the result
        pass

    @mock.patch("cs.pcs.checklists_documents.CLTemplateDocRef")
    def test_create_doc_instances(self, mockCLTemplateDocRef):
        mockCLTemplateDocRef.create_docs_instances = mock.Mock()
        cl = Checklist()
        mock_ctx = mock.Mock()
        mock_ctx.error = "foo"
        cl.create_doc_instances(mock_ctx)

        self.assertEqual(mockCLTemplateDocRef.create_docs_instances.call_args_list, [])

        mockCLTemplateDocRef.create_docs_instances = mock.Mock()
        mock_ctx.error = None
        cl.create_doc_instances(mock_ctx)
        mockCLTemplateDocRef.create_docs_instances.assert_called_with(
            cl, mockCLTemplateDocRef
        )

    def test__preset_project_from_doc(self):
        # not tested, method only makes one DB Call to retrieve cdb_project_id
        pass


@pytest.mark.unit
class ChecklistItemTest(testcase.RollbackTestCase):
    def test__get_Documents(self):
        # not tested, method only calls SimpleJoinQuery and returns the result
        pass

    @mock.patch("cs.pcs.checklists_documents.CLItemTemplateDocRef")
    def test_create_doc_instances(self, mockCLItemTemplateDocRef):
        mockCLItemTemplateDocRef.create_docs_instances = mock.Mock()
        cl_item = ChecklistItem()
        mock_ctx = mock.Mock()
        mock_ctx.error = "foo"
        cl_item.create_doc_instances(mock_ctx)

        self.assertEqual(
            mockCLItemTemplateDocRef.create_docs_instances.call_args_list, []
        )

        mockCLItemTemplateDocRef.create_docs_instances = mock.Mock()
        mock_ctx.error = None
        cl_item.create_doc_instances(mock_ctx)
        mockCLItemTemplateDocRef.create_docs_instances.assert_called_with(
            cl_item, mockCLItemTemplateDocRef
        )


@pytest.mark.unit
class DocumentTest(testcase.RollbackTestCase):
    def test__getChecklists(self):
        # not tested, method only calls SimpleJoinQuery and returns the result
        pass

    def test_create_relationship_object(self):
        # not tested, only calls ChecklistDocumentReference.Create
        pass

    @mock.patch("cs.pcs.checklists_documents.Checklist")
    def test__assign_doc_checklist(self, mockChecklist):
        doc = Document()
        mock_ctx = mock.Mock()
        mockChecklist.cdbpcs_checklist_assign = mock.Mock(
            return_value=("project_id", "cl_id")
        )
        doc.create_relationship_object = mock.Mock()
        doc._assign_doc_checklist(mock_ctx)
        mockChecklist.cdbpcs_checklist_assign.assert_called_with(doc, mock_ctx)
        doc.create_relationship_object.assert_called_with("project_id", "cl_id")

    def test__check_doc_checklists_delete_pre(self):
        doc = Document()
        mock_ctx = mock.Mock()
        with mock.patch.object(Document, "Checklists", []):
            doc._check_doc_checklists_delete_pre(mock_ctx)

        with mock.patch.object(Document, "Checklists", ["not empty"]):
            with self.assertRaises(ue.Exception):
                doc._check_doc_checklists_delete_pre(mock_ctx)

    @mock.patch.object(sqlapi, "SQLdelete")
    def test__doc_checklists_delete_post_with_ctx_error(self, mock_sqlapi):
        doc = Document()
        mock_ctx = mock.Mock()
        mock_ctx.error = "foo"
        doc._doc_checklists_delete_post(mock_ctx)
        # assert it was called not once
        mock_sqlapi.assert_not_called()

    @mock.patch.object(sqlapi, "SQLdelete")
    def test__doc_checklists_delete_post_without_ctx_error(self, mock_sqlapi):
        doc = Document(z_nummer="foo", z_index="bar")
        mock_ctx = mock.Mock()
        mock_ctx.error = None
        doc._doc_checklists_delete_post(mock_ctx)
        # assert it was called twice
        mock_sqlapi.assert_has_calls(
            [
                mock.call(
                    "from cdbpcs_doc2cl where z_nummer = 'foo' and z_index = 'bar'"
                ),
                mock.call(
                    "from cdbpcs_doc2cli where z_nummer = 'foo' and z_index = 'bar'"
                ),
            ]
        )


@pytest.mark.unit
class ProjectTest(testcase.RollbackTestCase):
    def test_handle_checklist_doc_templates_ctx_error_or_project_is_template(self):

        project = Project()
        mock_ctx = mock.Mock()

        # a) if context has error and project is no template
        project.template = False
        mock_ctx.error = 1
        with mock.patch.object(
            Project, "_create_documents_from_templates"
        ) as mocked_function:
            project.handle_checklist_doc_templates(mock_ctx)
        # _create_documents_from_templates not called
        mocked_function.assert_not_called()

        # b) if context has erro and project is template
        project.template = True
        mock_ctx.error = 0
        with mock.patch.object(
            Project, "_create_documents_from_templates"
        ) as mocked_function:
            project.handle_checklist_doc_templates(mock_ctx)
        # _create_documents_from_templates not called
        mocked_function.assert_not_called()

    def test_handle_checklist_doc_templates(self):
        project = Project()
        mock_ctx = mock.Mock()

        # if context has error and project is no template
        project.template = False
        mock_ctx.error = 0
        with mock.patch.object(
            Project, "_create_documents_from_templates"
        ) as mocked_function:
            project.handle_checklist_doc_templates(mock_ctx)
        # _create_documents_from_templates has been called 2 times
        mocked_function.assert_has_calls(
            [
                mock.call(ChecklistItem, CLItemTemplateDocRef),
                mock.call(Checklist, CLTemplateDocRef),
            ]
        )


if __name__ == "__main__":
    unittest.main()
