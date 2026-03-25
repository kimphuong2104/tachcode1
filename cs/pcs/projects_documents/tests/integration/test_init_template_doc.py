# coding: utf-8

import pytest
from cdb import testcase
from cdb.objects.operations import operation
from cs.documents import Document

from cs.pcs.projects.tests import common as ProjectsCommon
from cs.pcs.projects_documents import (
    ProjectTemplateDocRef,
    TaskTemplateDocRef,
    valid_index,
)
from cs.pcs.projects_documents.tests.integration import common


@pytest.mark.integration
class ProjectDocumentsTemplateIntegrationTest(testcase.RollbackTestCase):
    def test__project_template_documents_copied(self):
        p = ProjectsCommon.generate_project()
        d = common.generate_doc()
        templ_d = common.generate_document_template(
            d, ProjectTemplateDocRef, cdb_project_id=p.cdb_project_id
        )
        p_copy = common.copy_project(p)
        copied_doc = ProjectTemplateDocRef.KeywordQuery(
            cdb_project_id=p_copy.cdb_project_id
        )
        self.assertEqual(len(copied_doc), 1)
        self.assertEqual(copied_doc[0].z_nummer, templ_d.z_nummer)

    def test__task_template_documents_copied(self):
        p = ProjectsCommon.generate_project()
        task = ProjectsCommon.generate_task(p, "taskFoo")
        d = common.generate_doc()
        templ_d = common.generate_document_template(
            d, TaskTemplateDocRef, task_id=task.task_id, cdb_project_id=p.cdb_project_id
        )
        p_copy = common.copy_project(p)
        copied_doc = TaskTemplateDocRef.KeywordQuery(
            cdb_project_id=p_copy.cdb_project_id
        )
        self.assertEqual(len(copied_doc), 1)
        self.assertEqual(copied_doc[0].z_nummer, templ_d.z_nummer)

    def test__project_template_documents_instantiated(self):
        "Create new document from project document template with empty index of released document"
        p = ProjectsCommon.generate_project()
        d = common.generate_doc(vorlagen_kz=True)
        d.ChangeState(200)
        templ_d = common.generate_document_template(
            d, ProjectTemplateDocRef, cdb_project_id=p.cdb_project_id
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(docs[0].z_nummer, docs[1].z_nummer)
        self.assertEqual(docs[0].titel, docs[1].titel)

    def test__project_template_documents_not_released(self):
        "Do not create new document from project document template with empty index of NOT released document"
        p = ProjectsCommon.generate_project()
        d = common.generate_doc(vorlagen_kz=True)
        templ_d = common.generate_document_template(
            d, ProjectTemplateDocRef, cdb_project_id=p.cdb_project_id
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].z_nummer, d.z_nummer)

    def test__project_template_documents_instantiated_valid_index(self):
        "Create new document from project document template with valid_index of released document"
        p = ProjectsCommon.generate_project()
        d = common.generate_doc(vorlagen_kz=True)
        d.ChangeState(200)
        templ_d = common.generate_document_template(
            d,
            ProjectTemplateDocRef,
            cdb_project_id=p.cdb_project_id,
            tmpl_index=valid_index,
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(docs[0].z_nummer, docs[1].z_nummer)
        self.assertEqual(docs[0].titel, docs[1].titel)

    def test__project_template_documents_not_released_valid_index(self):
        "Do not create new document from project document template with valid_index of NOT released document"
        p = ProjectsCommon.generate_project()
        d = common.generate_doc(vorlagen_kz=True)
        templ_d = common.generate_document_template(
            d,
            ProjectTemplateDocRef,
            cdb_project_id=p.cdb_project_id,
            tmpl_index=valid_index,
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].z_nummer, d.z_nummer)


@pytest.mark.integration
class TaskDocumentsTemplateIntegrationTest(testcase.RollbackTestCase):
    def test__task_template_documents_instantiated(self):
        "Create new document from task document template with empty index of released document"
        p = ProjectsCommon.generate_project()
        t = ProjectsCommon.generate_project_task(p)
        d = common.generate_doc(vorlagen_kz=True)
        d.ChangeState(200)
        templ_d = common.generate_document_template(
            d, TaskTemplateDocRef, cdb_project_id=p.cdb_project_id, task_id=t.task_id
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(docs[0].z_nummer, docs[1].z_nummer)
        self.assertEqual(docs[0].titel, docs[1].titel)

    def test__task_template_documents_not_released(self):
        "Do not create new document from task document template with empty index of NOT released document"
        p = ProjectsCommon.generate_project()
        t = ProjectsCommon.generate_project_task(p)
        d = common.generate_doc(vorlagen_kz=True)
        templ_d = common.generate_document_template(
            d, TaskTemplateDocRef, cdb_project_id=p.cdb_project_id, task_id=t.task_id
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].z_nummer, d.z_nummer)

    def test__task_template_documents_instantiated_valid_index(self):
        "Create new document from task document template with valid_index of released document"
        p = ProjectsCommon.generate_project()
        t = ProjectsCommon.generate_project_task(p)
        d = common.generate_doc(vorlagen_kz=True)
        d.ChangeState(200)
        templ_d = common.generate_document_template(
            d,
            TaskTemplateDocRef,
            cdb_project_id=p.cdb_project_id,
            task_id=t.task_id,
            tmpl_index=valid_index,
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(docs[0].z_nummer, docs[1].z_nummer)
        self.assertEqual(docs[0].titel, docs[1].titel)

    def test__task_template_documents_not_released_valid_index(self):
        "Do not create new document from task document template with valid_index of NOT released document"
        p = ProjectsCommon.generate_project()
        t = ProjectsCommon.generate_project_task(p)
        d = common.generate_doc(vorlagen_kz=True)
        templ_d = common.generate_document_template(
            d,
            TaskTemplateDocRef,
            cdb_project_id=p.cdb_project_id,
            task_id=t.task_id,
            tmpl_index=valid_index,
        )
        operation("CDB_WithDocTemplates_New", templ_d)
        docs = Document.KeywordQuery(titel=d.titel)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].z_nummer, d.z_nummer)
