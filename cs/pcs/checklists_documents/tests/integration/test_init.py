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
from cdb.objects.operations import operation
from cs.documents import Document
from mock import patch

from cs.pcs import checklists_documents
from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.checklists.tests.integration import util
from cs.pcs.checklists_documents import (
    ChecklistDocumentReference,
    CLItemDocumentReference,
    CLItemTemplateDocRef,
    CLTemplateDocRef,
)
from cs.pcs.projects import Project
from cs.pcs.projects.tests import common
from cs.pcs.projects_documents.tests.integration import common as DocumentsCommon

# do not import cs.pcs.checklists_documents.Checklist directly
# to test connection in bootstrapping


def method_is_connected(module, name, *slot):
    slot_names = [(x.__module__, x.__name__) for x in sig.find_slots(*slot)]
    return (module, name) in slot_names


@pytest.mark.integration
class ChecklistsDocumentsIntegrationTest(testcase.RollbackTestCase):
    @pytest.mark.dependency(depends=["cs.pcs.checklists"])
    def test_checklist_create_doc_instances_is_connected(self):
        "Checklist.create_doc_instances is connected to state_change.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "create_doc_instances",
                Checklist,
                "state_change",
                "post",
            )
        )

    @pytest.mark.dependency(depends=["cs.pcs.checklists"])
    def test_checklistitem_create_doc_instances_is_connected(self):
        "ChecklistItem.create_doc_instances is connected to state_change.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "create_doc_instances",
                ChecklistItem,
                "state_change",
                "post",
            )
        )

    @pytest.mark.dependency(depends=["cs.document"])
    def test__assign_doc_checklist_is_connected(self):
        "Document._assign_doc_checklist is connected to cdbpcs_checklist_assign.now"

        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "_assign_doc_checklist",
                Document,
                "cdbpcs_checklist_assign",
                "now",
            )
        )

    @pytest.mark.dependency(depends=["cs.document"])
    def test__check_doc_checklists_delete_pre_is_connected(self):
        "Document._check_doc_checklists_delete_pre is connected to delete.pre"

        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "_check_doc_checklists_delete_pre",
                Document,
                "delete",
                "pre",
            )
        )

    @pytest.mark.dependency(depends=["cs.document"])
    def test__doc_checklists_delete_post_is_connected(self):
        "Document._check_doc_checklists_delete_post is connected to delete.post"

        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "_doc_checklists_delete_post",
                Document,
                "delete",
                "post",
            )
        )

    @pytest.mark.dependency(depends=["cs.pcs.projects"])
    def test_handle_checklist_doc_templates_is_connected(self):
        "Project.handle_checklist_doc_templates is connected to copy.post"

        self.assertTrue(
            method_is_connected(
                "cs.pcs.checklists_documents",
                "handle_checklist_doc_templates",
                Project,
                "copy",
                "post",
            )
        )

    def test__checklist_template_documents_copied(self):
        p = common.generate_project()
        cl = common.generate_checklist(p)
        d = DocumentsCommon.generate_doc()
        templ_d = DocumentsCommon.generate_document_template(
            d,
            CLTemplateDocRef,
            checklist_id=cl.checklist_id,
            cdb_project_id=p.cdb_project_id,
        )
        cl_copy = operation("CDB_Copy", cl, checklist_id=1337)
        copied_cl = CLTemplateDocRef.KeywordQuery(checklist_id=cl_copy.checklist_id)
        self.assertEqual(len(copied_cl), 1)
        self.assertEqual(copied_cl[0].z_nummer, templ_d.z_nummer)

    def test__checklistItem_template_documents_copied(self):

        ROLE_ID = "Projektmitglied"
        SUBJECT_ID = "Projektmitglied"
        PERSNO = "test_user_00"

        p = common.generate_project()
        common.generate_user(PERSNO)
        common.assign_person_to_project(ROLE_ID, p, PERSNO)
        cl = common.generate_checklist(p)
        cli = common.generate_checklist_item(
            cl,
            subject_id=SUBJECT_ID,
            subject_type="PCS Role",
            cl_item_id=123,
            criterion="Criterion",
        )
        d = DocumentsCommon.generate_doc()
        templ_d = DocumentsCommon.generate_document_template(
            d,
            CLItemTemplateDocRef,
            checklist_id=cl.checklist_id,
            cdb_project_id=p.cdb_project_id,
            cl_item_id=cli.cl_item_id,
        )
        cli_copy = operation("CDB_Copy", cli, cl_item_id=456)
        copied_docRef = CLItemTemplateDocRef.KeywordQuery(
            cl_item_id=cli_copy.cl_item_id
        )
        self.assertEqual(len(copied_docRef), 1)
        self.assertEqual(copied_docRef[0].z_nummer, templ_d.z_nummer)


@pytest.mark.integration
class ChecklistDocumentsInstantiationIntegrationTestCase(testcase.RollbackTestCase):
    def create_checklist_documentTemplate(self, cl, doc):
        kwargs = {}
        kwargs["z_nummer"] = doc.z_nummer
        kwargs["tmpl_index"] = doc.z_index
        kwargs["cdb_project_id"] = cl.cdb_project_id
        kwargs["checklist_id"] = cl.checklist_id
        kwargs["instantiation_state"] = 20
        return CLTemplateDocRef.Create(**kwargs)

    def create_checklistItem_documentTemplate(self, cli, doc):
        kwargs = {}
        kwargs["z_nummer"] = doc.z_nummer
        kwargs["tmpl_index"] = doc.z_index
        kwargs["cdb_project_id"] = cli.cdb_project_id
        kwargs["checklist_id"] = cli.checklist_id
        kwargs["cl_item_id"] = cli.cl_item_id
        kwargs["instantiation_state"] = 20
        return CLItemTemplateDocRef.Create(**kwargs)

    def validate_cl_docs(self, cl, doc):
        documents = ChecklistDocumentReference.KeywordQuery(
            cdb_project_id=cl.cdb_project_id, checklist_id=cl.checklist_id
        )
        self.assertEqual(len(documents), 1)

    def validate_cli_docs(self, cli, doc):
        documents = CLItemDocumentReference.KeywordQuery(
            cdb_project_id=cli.cdb_project_id,
            checklist_id=cli.checklist_id,
            cl_item_id=cli.cl_item_id,
        )
        self.assertEqual(len(documents), 1)

    ######
    # Checklist Tests
    ######

    def test_cl_documentTemplate_instantiate(self):
        prj = util.create_project("myProjectId", "")
        cl = util.create_checklist(prj)
        docA = DocumentsCommon.generate_document(1, "docA", 200)
        self.create_checklist_documentTemplate(cl, docA)
        docB = DocumentsCommon.generate_document(2, "docB")
        self.create_checklist_documentTemplate(cl, docB)
        self.assertEqual(len(cl.Documents), 0)
        # status change and check if document was created
        try:
            prj.ChangeState(50, check_access=0)
            cl.ChangeState(20, check_access=0)
        except Exception as e:
            self.assertTrue(DocumentsCommon.checkErrorMsg(e, "docB"))
        self.validate_cl_docs(cl, docA)

    def test_cl_documentTemplate_copied_instantiate(self):
        prj = util.create_project("myProjectId", "")
        clA = util.create_checklist(prj)
        docA = DocumentsCommon.generate_document(1, "docA", 200)
        self.create_checklist_documentTemplate(clA, docA)
        docB = DocumentsCommon.generate_document(2, "docB")
        self.create_checklist_documentTemplate(clA, docB)
        self.assertEqual(len(clA.Documents), 0)
        # status change and check if document was created
        try:
            prj.ChangeState(50, check_access=0)
            clA.ChangeState(20, check_access=0)
        except Exception as e:
            self.assertTrue(DocumentsCommon.checkErrorMsg(e, "docB"))
        self.validate_cl_docs(clA, docA)
        # copy checklist A to project B
        clB = operation("CDB_Copy", clA, **{"checklist_id": 42})
        self.assertEqual(len(clB.Documents), 0)
        # status change and check if document was created
        try:
            clB.ChangeState(20, check_access=0)
        except Exception as e:
            self.assertTrue(DocumentsCommon.checkErrorMsg(e, "docB"))
        self.validate_cl_docs(clB, docA)

    ######
    # Checklist Item Tests
    ######
    @patch.object(checklists_documents, "logging")
    def test_clItem_documentTemplate_instantiate(self, logging):
        prj = util.create_project("myProjectId", "")
        cl = util.create_checklist(prj)
        cli = util.create_checklist_item(util.create_user("testUser"), prj, cl)
        docA = DocumentsCommon.generate_document(1, "docA", 200)
        self.create_checklistItem_documentTemplate(cli, docA)
        docB = DocumentsCommon.generate_document(2, "docB")
        self.create_checklistItem_documentTemplate(cli, docB)
        self.assertEqual(len(cl.Documents), 0)
        try:
            prj.ChangeState(50, check_access=0)
            cl.ChangeState(20, check_access=0)
            cli.ChangeState(20, check_access=0)
        except Exception:
            logging.error.assert_called_once()
        self.validate_cli_docs(cli, docA)

    def test_clItem_documentTemplate_copied_instantiate(self):
        prj = util.create_project("myProjectId", "")
        user = util.create_user("foo")
        util.assign_user_project_role(user, prj, role_id="Projektmitglied")
        cl = util.create_checklist(prj)
        cl.status = 0
        cliA = util.create_checklist_item(user, prj, cl, cl_item_id="111")

        # Create Documents and Template Documents
        docA = DocumentsCommon.generate_document(1, "docA", 200)
        self.create_checklistItem_documentTemplate(cliA, docA)
        docB = DocumentsCommon.generate_document(2, "docB")
        self.create_checklistItem_documentTemplate(cliA, docB)
        self.assertEqual(len(cliA.Documents), 0)

        try:
            prj.ChangeState(50, check_access=0)
            cl.ChangeState(20, check_access=0)
        except Exception as e:
            self.assertTrue(DocumentsCommon.checkErrorMsg(e, "docB"))
        self.validate_cli_docs(cliA, docA)

        # copy checklist Item A to checklist Item B
        cliB = operation("CDB_Copy", cliA, **{"cl_item_id": 42})
        self.assertEqual(len(cliB.Documents), 0)
        # status change and check if document was created
        try:
            cliB.ChangeState(20, check_access=0)
        except Exception as e:
            self.assertTrue(DocumentsCommon.checkErrorMsg(e, "docB"))
        self.validate_cli_docs(cliB, docA)


if __name__ == "__main__":
    unittest.main()
