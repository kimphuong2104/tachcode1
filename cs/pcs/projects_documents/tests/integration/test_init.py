#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import unittest
from contextlib import contextmanager

import pytest
from cdb import ElementsError, constants, sig, sqlapi, testcase, util
from cdb.objects.operations import operation
from cs.documents import Document, DocumentCategory

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.tests import common
from cs.pcs.projects_documents import (
    DocTemplateColumns,
    ProjectTemplateDocRef,
    TaskDocumentReference,
    TaskTemplateDocRef,
)
from cs.pcs.projects_documents.tests.integration import common as documentsCommon

# do not import cs.pcs.projects_documents.Project directly
# to test connection in bootstrapping

# kwargs for documents to be sorted by numeric schema
NUMERIC_INDEX_SCHEMA_KWARGS = [
    {
        "z_index": "7",
        "titel": "Seven",
        "z_status": 0,
        "cdb_obsolete": 0,
        "z_bemerkung": "0004",
    },
    {
        "z_index": "10",
        "titel": "Ten",
        "z_status": 0,
        "cdb_obsolete": 0,
        "z_bemerkung": "0003",
    },
    {
        "z_index": "9",
        "titel": "Nine",
        "z_status": 0,
        "cdb_obsolete": 0,
        "z_bemerkung": "0002",
    },
    {
        "z_index": "150",
        "titel": "150",
        "z_status": 0,
        "cdb_obsolete": 0,
        "z_bemerkung": "0001",
    },
]

# kwargs for documents to be sorted by cdb_date
SORTING_BY_CDB_CDATE_KWARGS = NUMERIC_INDEX_SCHEMA_KWARGS

# kwargs for documents to be sorted by alternative attribute z_bemerkung
SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS = NUMERIC_INDEX_SCHEMA_KWARGS

# kwargs for documents to be sorted by alpha numeric schema
ALPHA_NUMERIC_SCHEMA_KWARGS = [
    {"z_index": "", "titel": "Empty", "z_status": 0, "cdb_obsolete": 0},
    {"z_index": "a", "titel": "A", "z_status": 0, "cdb_obsolete": 0},
    {"z_index": "b", "titel": "B", "z_status": 0, "cdb_obsolete": 0},
    {"z_index": "aa", "titel": "AA", "z_status": 0, "cdb_obsolete": 0},
]


def setUpModule():
    testcase.run_level_setup()


def method_is_connected(module, name, *slot):
    slot_names = [(x.__module__, x.__name__) for x in sig.find_slots(*slot)]
    return (module, name) in slot_names


@contextmanager
def temp_sort_attribute(new_sort_attr=None):
    if new_sort_attr:
        key = constants.kVersioningIndexOrderDoc
        settings = sqlapi.RecordSet2("cdb_setting", f"setting_id = '{key}'")
        original_values = [x.default_val for x in settings]
        for setting in settings:
            setting.update(default_val=new_sort_attr)
        util.reload_cache("cdb_setting", util.kLocalReload)

        yield

        for setting, original_value in zip(settings, original_values):
            setting.update(default_val=original_value)
        util.reload_cache("cdb_setting", util.kLocalReload)
    else:
        yield


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects"])
class ProjectDocumentsConnectionIntegrationTest(testcase.RollbackTestCase):
    def test_project_create_doc_instances_is_connected(self):
        "Project.create_doc_instances is connected to state_change.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "create_doc_instances",
                Project,
                "state_change",
                "post",
            )
        )

    def test_project_handle_doc_templates_is_connected(self):
        "Project.handle_doc_templates is connected to relship_copy.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "handle_doc_templates",
                Project,
                "relship_copy",
                "post",
            )
        )

    def test_project_msp_active_doc_modify_post_is_connected(self):
        "Project.msp_active_doc_modify_post is connected to modify.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "msp_active_doc_modify_post",
                Project,
                "modify",
                "post",
            )
        )

    def test_project_msp_active_doc_create_post_is_connected(self):
        "Project.msp_active_doc_create_post is connected to create.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "msp_active_doc_create_post",
                Project,
                "create",
                "post",
            )
        )

    def test_project_msp_active_doc_copy_post_is_connected(self):
        "Project.msp_active_doc_copy_post is connected to copy.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "msp_active_doc_copy_post",
                Project,
                "copy",
                "post",
            )
        )

    @pytest.mark.dependency(depends=["cs.pcs.projects"])
    def test_project_check_docs_delete_pre_is_connected(self):
        "Project.check_docs_delete_pre is connected to delete.pre"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "check_docs_delete_pre",
                Project,
                "delete",
                "pre",
            )
        )

    def test_project__copyFolders_is_connected(self):
        "Project._copyFolders is connected to copy.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_copyFolders",
                Project,
                "copy",
                "post",
            )
        )

    def test_project__deleteFolders_is_connected(self):
        "Project._deleteFolders is connected to delete.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_deleteFolders",
                Project,
                "delete",
                "post",
            )
        )

    def test_PredefineCopyStructLanguage_is_connected(self):
        "Project.PredefineCopyStructLanguage is connected to cdb_copyfolderstruct_pcs.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "PredefineCopyStructLanguage",
                Project,
                "cdb_copyfolderstruct_pcs",
                "pre_mask",
            )
        )

    def test_CopyFoldStruct_is_connected(self):
        "Project.CopyFoldStruct is connected to cdb_copyfolderstruct_pcs.now"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "CopyFoldStruct",
                Project,
                "cdb_copyfolderstruct_pcs",
                "now",
            )
        )


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects.tasks"])
class TaskDocumentsConnectionIntegrationTest(testcase.RollbackTestCase):
    def test_create_doc_instances_is_connected(self):
        "Task.create_doc_instances is connected to state_change.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "create_doc_instances",
                Task,
                "state_change",
                "post",
            )
        )


@pytest.mark.dependency(name="integration", depends=["cs.documents"])
class DocumentsConnectionIntegrationTest(testcase.RollbackTestCase):
    def test_delete_invalid_doc_templates_is_connected(self):
        "Document.delete_invalid_doc_templates is connected to state_change.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "delete_invalid_doc_templates",
                Document,
                "state_change",
                "post",
            )
        )

    def test_delete_msp_time_schedule_is_connected(self):
        "Document.delete_msp_time_schedule is connected to delete.pre"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "delete_msp_time_schedule",
                Document,
                "delete",
                "pre",
            )
        )

    def test__PresetFolderAttributes_is_connected_to_copy_pre_mask(self):
        "Document._PresetFolderAttributes is connected to copy.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_PresetFolderAttributes",
                Document,
                "copy",
                "pre_mask",
            )
        )

    def test__PresetFolderAttributes_is_connected_to_create_pre_mask(self):
        "Document._PresetFolderAttributes is connected to create.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_PresetFolderAttributes",
                Document,
                "create",
                "pre_mask",
            )
        )

    def test__preset_project_id_is_connected(self):
        "Document._preset_project_id is connected to create.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_preset_project_id",
                Document,
                "create",
                "pre_mask",
            )
        )

    def test__preset_project_id_is_connected_templ(self):
        "Document._preset_project_id is connected to cdb_create_doc_from_template.pre_mask"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_preset_project_id",
                Document,
                "cdb_create_doc_from_template",
                "pre_mask",
            )
        )

    def test_CopyFilesAtDragAndDrop_is_connected(self):
        "Document.CopyFilesAtDragAndDrop is connected to create.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "CopyFilesAtDragAndDrop",
                Document,
                "create",
                "post",
            )
        )

    def test__CheckFolderAssignment_is_connected(self):
        "Document._CheckFolderAssignment is connected to index.pre"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_CheckFolderAssignment",
                Document,
                "index",
                "pre",
            )
        )

    def test__RemoveFolderAssignments_is_connected(self):
        "Document._RemoveFolderAssignments is connected to delete.post"
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects_documents",
                "_RemoveFolderAssignments",
                Document,
                "delete",
                "post",
            )
        )


@pytest.mark.integration
class ProjectDocuments_MSP_TS_Document_IntegrationTest(testcase.RollbackTestCase):
    # ----------- integration tests for determining MSP/TS Document -----------

    def generate_document(self, index, **args):
        # constants copied from test/accepttests/steps/common.py
        doc_approve_maincategs = ("316", "144")
        doc_approve_categ = "170"

        doc_maincateg = []

        for doc_approve_maincateg in doc_approve_maincategs:
            doc_maincateg = DocumentCategory.ByKeys(categ_id=doc_approve_maincateg)
            if doc_maincateg:
                break

        doc_categ = DocumentCategory.ByKeys(categ_id=doc_approve_categ)

        kwargs = {
            "z_categ1": doc_maincateg.categ_id,
            "z_categ2": doc_categ.categ_id,
            "cdb_classname": "document",
            "z_art": "doc_approve",
        }
        kwargs.update(Document.MakeChangeControlAttributes())
        kwargs.update(**args)
        # ensure documents are created at different time points
        kwargs.update(
            {"cdb_cdate": datetime.datetime.now() + datetime.timedelta(minutes=index)}
        )
        return Document.Create(**kwargs)

    def determine_project_document(
        self, doc_kwargs, obsoleteIndices, sort_attribute=None
    ):
        docs = {}
        # 1. Generate a project
        prj = common.generate_project()
        # 2. Create Document with several indices and other attributes
        # according to sorting schema
        x = 0
        for kwargs in doc_kwargs:
            kwargs["z_nummer"] = "z_nummer"
            kwargs["cdb_project_id"] = prj.cdb_project_id
            doc = self.generate_document(index=x, **kwargs)
            docs[doc.z_index] = doc
            x += 1
        prj.Update(msp_z_nummer="z_nummer")
        # 3. Set some indices to obsolete
        for obsoleteIndex in obsoleteIndices:
            if obsoleteIndex in docs:
                docs[obsoleteIndex].Update(cdb_obsolete=1)
        # 4. determine MSP/TS Document to use with getLastPrimaryMSPDocument

        with temp_sort_attribute(sort_attribute):
            return prj.getLastPrimaryMSPDocument()

    # ----------- by numeric index schema------------------------------------------
    def test_get_MSP_TS_Document_numeric_index_schema_01(self):
        self.assertEqual(
            "150",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["7", "9", "10"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_02(self):
        self.assertEqual(
            "9",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["7", "10", "150"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_03(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["7", "9", "150"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_04(self):
        self.assertEqual(
            "7",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["9", "10", "150"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_05(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["7", "150"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_06(self):
        self.assertEqual(
            "150",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["9", "10"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_07(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["150"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_numeric_index_schema_08(self):
        self.assertIsNone(
            self.determine_project_document(
                NUMERIC_INDEX_SCHEMA_KWARGS, ["7", "9", "10", "150"]
            )
        )

    # ----------- by alpha numeric schema------------------------------------------
    def test_get_MSP_TS_Document_alpha_numeric_schema_01(self):
        self.assertEqual(
            "",
            self.determine_project_document(
                ALPHA_NUMERIC_SCHEMA_KWARGS, ["a", "b", "aa"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_alpha_numeric_schema_02(self):
        self.assertEqual(
            "aa",
            self.determine_project_document(ALPHA_NUMERIC_SCHEMA_KWARGS, [""]).z_index,
        )

    def test_get_MSP_TS_Document_alpha_numeric_schema_03(self):
        self.assertEqual(
            "a",
            self.determine_project_document(
                ALPHA_NUMERIC_SCHEMA_KWARGS, ["", "b", "aa"]
            ).z_index,
        )

    def test_get_MSP_TS_Document_alpha_numeric_schema_04(self):
        self.assertEqual(
            "b",
            self.determine_project_document(
                ALPHA_NUMERIC_SCHEMA_KWARGS, ["aa"]
            ).z_index,
        )

    # ----------- by sorting by cdb_cdate ------------------------------------------
    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_01(self):
        self.assertEqual(
            "150",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS,
                ["7", "9", "10"],
                sort_attribute="cdb_cdate",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_02(self):
        self.assertEqual(
            "9",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS,
                ["7", "10", "150"],
                sort_attribute="cdb_cdate",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_03(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS,
                ["7", "9", "150"],
                sort_attribute="cdb_cdate",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_04(self):
        self.assertEqual(
            "7",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS,
                ["9", "10", "150"],
                sort_attribute="cdb_cdate",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_05(self):
        self.assertEqual(
            "9",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS, ["7", "150"], sort_attribute="cdb_cdate"
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_06(self):
        self.assertEqual(
            "150",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS, ["9", "10"], sort_attribute="cdb_cdate"
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_07(self):
        self.assertEqual(
            "9",
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS, ["150"], sort_attribute="cdb_cdate"
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_cdb_cdate_08(self):
        self.assertIsNone(
            self.determine_project_document(
                SORTING_BY_CDB_CDATE_KWARGS,
                ["7", "9", "10", "150"],
                sort_attribute="cdb_cdate",
            )
        )

    # ----------- by sorting by alternative attribute (z_bemerkung) ---------------
    def test_get_MSP_TS_Document_sorting_by_alternative_attr_01(self):
        self.assertEqual(
            "150",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["7", "9", "10"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_02(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["7", "9", "150"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_03(self):
        self.assertEqual(
            "7",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["9", "10", "150"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_04(self):
        self.assertEqual(
            "9",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["7", "10", "150"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_05(self):
        self.assertEqual(
            "10",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["7", "150"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_06(self):
        self.assertEqual(
            "7",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["9", "10"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_07(self):
        self.assertEqual(
            "7",
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["150"],
                sort_attribute="z_bemerkung",
            ).z_index,
        )

    def test_get_MSP_TS_Document_sorting_by_alternative_attr_08(self):
        self.assertIsNone(
            self.determine_project_document(
                SORTING_BY_ALTERNATIVE_ATTRIBUTE_KWARGS,
                ["7", "9", "10", "150"],
                sort_attribute="z_bemerkung",
            )
        )


@pytest.mark.integration
class ProjectDocumentsIntegrationTestCase(testcase.RollbackTestCase):
    def create_project_documentTemplate(self, prj, doc):
        kwargs = {}
        kwargs["z_nummer"] = doc.z_nummer
        kwargs["tmpl_index"] = doc.z_index
        kwargs["cdb_project_id"] = prj.cdb_project_id
        kwargs["instantiation_state"] = 50
        return ProjectTemplateDocRef.Create(**kwargs)

    def create_task_documentTemplate(self, task, doc):
        kwargs = {}
        kwargs["z_nummer"] = doc.z_nummer
        kwargs["tmpl_index"] = doc.z_index
        kwargs["cdb_project_id"] = task.cdb_project_id
        kwargs["task_id"] = task.task_id
        kwargs["instantiation_state"] = 20
        return TaskTemplateDocRef.Create(**kwargs)

    def validate_prj_docs(self, prj, doc):
        documents = Document.KeywordQuery(cdb_project_id=prj.cdb_project_id)
        self.assertEqual(len(documents), 1)

    def validate_task_docs(self, task, doc):
        documents = TaskDocumentReference.KeywordQuery(
            cdb_project_id=task.cdb_project_id, task_id=task.task_id
        )
        self.assertEqual(len(documents), 1)

    ######
    # Project Tests
    ######

    def test_project_documentTemplate_instantiate(self):
        prj = common.generate_project()
        docA = documentsCommon.generate_document(1, "docA", 200)
        self.create_project_documentTemplate(prj, docA)
        docB = documentsCommon.generate_document(1, "docB")
        self.create_project_documentTemplate(prj, docB)

        self.assertEqual(len(prj.Documents), 0)
        # status change and check if document was created
        try:
            prj.ChangeState(50, check_access=0)
        except Exception as e:
            self.assertTrue(
                "Es wurde kein gültiges Dokument für Vorlagenquellen gefunden mit Dokumentnummer und Index: \n\n- docB_nummer/docB_Index"  # noqa
                in str(e)
            )
        self.validate_prj_docs(prj, docA)

    def test_project_documentTemplate_copied_instantiate(self):
        prjA = common.generate_project()
        docA = documentsCommon.generate_document(1, "docA", 200)
        self.create_project_documentTemplate(prjA, docA)
        docB = documentsCommon.generate_document(1, "docB")
        self.create_project_documentTemplate(prjA, docB)
        self.assertEqual(len(prjA.Documents), 0)

        with self.assertRaises(ElementsError) as exc:
            prjA.ChangeState(50, check_access=0)

        self.assertTrue(documentsCommon.checkErrorMsg(exc.exception, "docB"))

        self.validate_prj_docs(prjA, docA)
        # copy project A to project B
        prjB = operation("CDB_Copy", prjA, **{"cdb_project_id": "project_id_B"})
        # status change and check if document was created
        with self.assertRaises(ElementsError) as exc:
            prjB.ChangeState(50, check_access=0)

        self.assertTrue(documentsCommon.checkErrorMsg(exc.exception, "docB"))
        self.validate_prj_docs(prjB, docA)

    ######
    # Task Tests
    ######

    def test_task_documentTemplate_instantiate(self):
        prj = common.generate_project()
        task = common.generate_task(prj, "myTaskID")
        docA = documentsCommon.generate_document(1, "docA", 200)
        self.create_task_documentTemplate(task, docA)
        docB = documentsCommon.generate_document(1, "docB")
        self.create_task_documentTemplate(task, docB)
        self.assertEqual(len(task.Documents), 0)
        # status change and check if document was created
        prj.ChangeState(50, check_access=0)

        with self.assertRaises(ElementsError) as exc:
            task.ChangeState(20, check_access=0)

        self.assertEqual(str(exc.exception), "Die Statusänderung ist nicht möglich.")
        self.validate_task_docs(task, docA)

    def test_task_documentTemplate_copied_instantiate(self):
        prj = common.generate_project()
        taskA = common.generate_task(prj, "myTaskID")
        docA = documentsCommon.generate_document(1, "docA", 200)
        self.create_task_documentTemplate(taskA, docA)
        docB = documentsCommon.generate_document(1, "docB")
        self.create_task_documentTemplate(taskA, docB)
        self.assertEqual(len(taskA.Documents), 0)

        prj.ChangeState(50, check_access=0)
        with self.assertRaises(ElementsError) as exc:
            taskA.ChangeState(20, check_access=0)

        self.assertEqual(str(exc.exception), "Die Statusänderung ist nicht möglich.")

        self.validate_task_docs(taskA, docA)
        # copy project A to project B
        taskB = operation("CDB_Copy", taskA, **{"task_id": "myTaskIdB"})
        self.assertEqual(len(taskB.Documents), 0)
        # status change and check if document was created
        with self.assertRaises(ElementsError) as exc:
            taskB.ChangeState(20, check_access=0)

        self.assertTrue(documentsCommon.checkErrorMsg(exc.exception, "docB"))
        self.validate_task_docs(taskB, docA)


@pytest.mark.integration
class DocumentsColumnTest(testcase.RollbackTestCase):
    classname = "cdbpcs_prj2doctmpl"

    def generate_document(self, z_nummer, z_index, titel, z_status):
        kwargs = {
            "z_nummer": z_nummer,
            "z_index": z_index,
            "titel": titel,
            "z_status": z_status,
        }
        return Document.Create(**kwargs)

    def test_getColumnData_specific_index_not_valid(self):
        self.generate_document("foo1", "bar1", "foo", 0)
        data = [
            {"tmpl_index": "bar1", "z_nummer": "foo1", "instantiation_state": "200"}
        ]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Abgeschlossen",
                    "used_version": "bar1",
                    "z_index": "<kein passender Index gefunden>",
                }
            ],
        )

    def test_getColumnData_empty_index_not_valid(self):
        self.generate_document("foo1", "", "foo", 0)
        data = [{"tmpl_index": "", "z_nummer": "foo1", "instantiation_state": "0"}]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Neu",
                    "used_version": "<leerer Index>",
                    "z_index": "<kein passender Index gefunden>",
                }
            ],
        )

    def test_getColumnData_empty_index_valid(self):
        self.generate_document("foo1", "", "foo", 200)
        data = [{"tmpl_index": "", "z_nummer": "foo1", "instantiation_state": "200"}]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Abgeschlossen",
                    "used_version": "<leerer Index>",
                    "z_index": "<leerer Index>",
                }
            ],
        )

    def test_getColumnData_valid_index_not_found(self):
        self.generate_document("foo1", "", "foo", 0)
        data = [
            {
                "tmpl_index": "valid_index",
                "z_nummer": "foo1",
                "instantiation_state": "0",
            }
        ]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Neu",
                    "used_version": "<Zuletzt freigegebener Index>",
                    "z_index": "<kein passender Index gefunden>",
                }
            ],
        )

    def test_getColumnData_valid_index_empty_tmpl_index(self):
        self.generate_document("foo1", "", "foo", 190)
        data = [
            {
                "tmpl_index": "valid_index",
                "z_nummer": "foo1",
                "instantiation_state": "0",
            }
        ]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Neu",
                    "used_version": "<Zuletzt freigegebener Index>",
                    "z_index": "<leerer Index>",
                }
            ],
        )

    def test_getColumnData_valid_index_specific_tmpl_index(self):
        self.generate_document("foo1", "bar1", "foo", 190)
        data = [
            {
                "tmpl_index": "valid_index",
                "z_nummer": "foo1",
                "instantiation_state": "0",
            }
        ]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "foo",
                    "create_on_status": "Neu",
                    "used_version": "<Zuletzt freigegebener Index>",
                    "z_index": "bar1",
                }
            ],
        )

    def test_getColumnData_missing_document(self):
        data = [
            {
                "tmpl_index": "valid_index",
                "z_nummer": "foo1",
                "instantiation_state": "0",
            }
        ]
        result = DocTemplateColumns.getColumnData(self.classname, data)
        self.assertEqual(
            result,
            [
                {
                    "doc_title": "<fehlendes Dokument>",
                    "create_on_status": "Neu",
                    "used_version": "<Zuletzt freigegebener Index>",
                    "z_index": "<fehlendes Dokument>",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
