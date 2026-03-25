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
from cdb import auth, testcase, ue
from cs.documents import Document

from cs.pcs import projects_documents
from cs.pcs.projects import Project


@pytest.mark.unit
class ProjectsTest(testcase.RollbackTestCase):
    def test_getLastPrimaryMSPDocument_no_msp_z_nummer(self):
        "returns None, since no msp_z_nummer is given"
        prj = Project()
        prj.msp_z_nummer = None
        self.assertIsNone(prj.getLastPrimaryMSPDocument())

    @mock.patch.object(Document, "__maps_to__", "foo_maps_to")
    @mock.patch("cdb.kernel.get_prev_index", return_value="bar")
    @mock.patch.object(Document, "ByKeys")
    @mock.patch("cdb.cad.getMaxIndex", return_value="foo")
    def test_getLastPrimaryMSPDocument_with_obsolete_documents(
        self, getMaxIndex, byKeys, get_prev_index
    ):
        "returns not obsolete doc, after going through some obsolete docs"
        prj = Project()
        prj.msp_z_nummer = "baz"

        mock_doc_obsolete = mock.MagicMock(autospec=Document)
        mock_doc_obsolete.cdb_obsolete = True
        mock_doc_obsolete.z_nummer = "foo_z_nummer_1"
        mock_doc_obsolete.z_index = "foo_z_index_1"
        mock_doc_obsolete.__maps_to__ = "foo_maps_to_1"

        mock_doc_not_obsolete = mock.MagicMock(autospec=Document)
        mock_doc_not_obsolete.cdb_obsolete = False

        # byKeys will return obsolete doc on first two calls and not obsolete doc on third call
        byKeys.side_effect = [
            mock_doc_obsolete,
            mock_doc_obsolete,
            mock_doc_not_obsolete,
        ]

        # assert the not obsolete doc is returned
        self.assertEqual(mock_doc_not_obsolete, prj.getLastPrimaryMSPDocument())

        getMaxIndex.assert_called_once_with("baz", "foo_maps_to")
        # assert byKeys is called three times
        byKeys.assert_has_calls(
            [
                mock.call(z_nummer="baz", z_index="foo"),
                mock.call(z_nummer="baz", z_index="bar"),
                mock.call(z_nummer="baz", z_index="bar"),
            ]
        )
        # assert get_prev_index is called twice with the obsolete doc
        get_prev_index.assert_has_calls(
            [
                mock.call("foo_z_nummer_1", "foo_z_index_1", "foo_maps_to_1"),
                mock.call("foo_z_nummer_1", "foo_z_index_1", "foo_maps_to_1"),
            ]
        )

    @mock.patch.object(Document, "__maps_to__", "foo_maps_to")
    @mock.patch("cdb.kernel.get_prev_index")
    @mock.patch.object(Document, "ByKeys")
    @mock.patch("cdb.cad.getMaxIndex", return_value="foo")
    def test_getLastPrimaryMSPDocument_without_obsolete_documents(
        self, getMaxIndex, byKeys, get_prev_index
    ):
        "returns not obsolete doc without going through any obsolete docs"
        prj = Project()
        prj.msp_z_nummer = "baz"

        mock_doc_not_obsolete = mock.MagicMock(autospec=Document)
        mock_doc_not_obsolete.cdb_obsolete = False

        # byKeys will return not obsolete doc on first call
        byKeys.return_value = mock_doc_not_obsolete

        # assert the not obsolete doc is returned
        self.assertEqual(mock_doc_not_obsolete, prj.getLastPrimaryMSPDocument())

        getMaxIndex.assert_called_once_with("baz", "foo_maps_to")
        # assert byKeys is called once
        byKeys.assert_called_once_with(z_nummer="baz", z_index="foo")
        # assert get_prev_index was not called
        get_prev_index.assert_not_called()

    def test_on_cdbpcs_msp_schedule_now_1(self):
        """
        create messagebox if project is not msp_active
        and it is not set to be opened in msp anyway
        """
        prj = Project()
        # project is not msp_active
        prj.msp_active = False
        mock_ctx = mock.MagicMock(uses_webui=False)
        # open_in_msp_anyway is not given
        mock_ctx.dialog.get_attribute_names = mock.Mock(return_value=[])
        mock_ctx.show_message = mock.Mock()
        mock_msg_box = mock.MagicMock()
        mock_ctx.MessageBox = mock.Mock(return_value=mock_msg_box)
        # assert no return value is given
        self.assertIsNone(prj.on_cdbpcs_msp_schedule_now(mock_ctx))
        # assert message box is constructed and shown
        mock_ctx.dialog.get_attribute_names.assert_called_once()
        mock_ctx.MessageBox.assert_called_once_with(
            "cdbpcs_msp_msp_not_set_as_project_editor", [], "open_in_msp_anyway"
        )
        mock_msg_box.addYesButton.assert_called_once_with(is_dflt=1)
        mock_msg_box.addNoButton.assert_called_once()
        mock_ctx.show_message.assert_called_once_with(mock_msg_box)

    def test_on_cdbpcs_msp_schedule_now_2(self):
        """
        return nothing if project is not msp_active
        and it is set to be opened in msp anyway,
        but the mesagebox is not confirmed
        """
        prj = Project()
        # project is not msp_active
        prj.msp_active = False
        mock_ctx = mock.MagicMock(uses_webui=False)
        # open_in_msp_anyway is given
        mock_ctx.dialog.get_attribute_names = mock.Mock(
            return_value=["open_in_msp_anyway"]
        )
        mock_ctx.dialog.__getitem__.return_value = "bar"
        mock_ctx.MessageBox.kMsgBoxResultYes = "not bar"

        # assert no return value is given
        self.assertIsNone(prj.on_cdbpcs_msp_schedule_now(mock_ctx))
        mock_ctx.dialog.get_attribute_names.assert_called_once()
        mock_ctx.dialog.__getitem__.assert_called_once_with("open_in_msp_anyway")

    @mock.patch.object(projects_documents.Project, "getLastPrimaryMSPDocument")
    def test_on_cdbpcs_msp_schedule_now_3(self, getLastPrimaryMSPDocument):
        """
        setUp FollowUp Operation if project is not msp_active
        and it is set to be opened in msp anyway
        and the messagebox is confirmed
        and there is a last pimary msp document
        """
        prj = Project()
        # project is not msp_active
        prj.msp_active = False
        mock_ctx = mock.MagicMock(uses_webui=False)
        # open_in_msp_anyway is given
        mock_ctx.dialog.get_attribute_names = mock.Mock(
            return_value=["open_in_msp_anyway"]
        )
        # msgbox is confirmed
        mock_ctx.dialog.__getitem__.return_value = "bar"
        mock_ctx.MessageBox.kMsgBoxResultYes = "bar"
        mock_ctx.set_followUpOperation = mock.Mock()

        prj.on_cdbpcs_msp_schedule_now(mock_ctx)

        mock_ctx.dialog.get_attribute_names.assert_has_calls([])
        mock_ctx.dialog.__getitem__.assert_called_once_with("open_in_msp_anyway")
        getLastPrimaryMSPDocument.assert_called_once()
        # assert followup operation is not called
        mock_ctx.set_followUpOperation.assert_not_called()

    @mock.patch.object(projects_documents.Project, "addMSPSchedule", return_value=None)
    @mock.patch.object(
        projects_documents.Project, "getLastPrimaryMSPDocument", return_value=None
    )
    def test_on_cdbpcs_msp_schedule_now_4(
        self, getLastPrimaryMSPDocument, addMSPSchedule
    ):
        """
        raise ue.Exception if project is not msp_active
        and it is set to be opened in msp anyway
        and the messagebox is confirmed
        and there is no last primary msp document
        and no template
        """
        prj = Project()
        # project is not msp_active
        prj.msp_active = False
        mock_ctx = mock.MagicMock(uses_webui=False)
        # open_in_msp_anyway is given
        mock_ctx.dialog.get_attribute_names = mock.Mock(
            return_value=["open_in_msp_anyway"]
        )
        # msgbox is confirmed
        mock_ctx.dialog.__getitem__.return_value = "bar"
        mock_ctx.MessageBox.kMsgBoxResultYes = "bar"
        mock_ctx.set_followUpOperation = mock.Mock()
        # assert an ue.exception is raised
        with self.assertRaises(ue.Exception):
            prj.on_cdbpcs_msp_schedule_now(mock_ctx)

        mock_ctx.dialog.get_attribute_names.assert_called_once()
        mock_ctx.dialog.__getitem__.assert_called_once_with("open_in_msp_anyway")
        getLastPrimaryMSPDocument.assert_called_once()
        addMSPSchedule.assert_called_once_with(force=True)

    @mock.patch.object(projects_documents.Project, "addMSPSchedule")
    @mock.patch.object(
        projects_documents.Project, "getLastPrimaryMSPDocument", return_value=None
    )
    def test_on_cdbpcs_msp_schedule_now_5(
        self, getLastPrimaryMSPDocument, addMSPSchedule
    ):
        """
        setUp FollowUpOperation if project is not msp_active
        and it is set to be opened in msp anyway
        and the messagebox is confirmed
        and there is no last primary msp document
        but a template
        """
        prj = Project()
        # project is not msp_active
        prj.msp_active = False
        mock_ctx = mock.MagicMock(uses_webui=False)
        # open_in_msp_anyway is given
        mock_ctx.dialog.get_attribute_names = mock.Mock(
            return_value=["open_in_msp_anyway"]
        )
        # msgbox is confirmed
        mock_ctx.dialog.__getitem__.return_value = "bar"
        mock_ctx.MessageBox.kMsgBoxResultYes = "bar"
        mock_ctx.set_followUpOperation = mock.Mock()

        addMSPSchedule.return_value.z_nummer = "foo"
        prj.on_cdbpcs_msp_schedule_now(mock_ctx)

        mock_ctx.dialog.get_attribute_names.assert_has_calls([])
        mock_ctx.dialog.__getitem__.assert_called_once_with("open_in_msp_anyway")
        getLastPrimaryMSPDocument.assert_called_once()
        # assert msp doc was copied from template
        addMSPSchedule.assert_called_once_with(force=True)
        # assert followup operation is not called
        mock_ctx.set_followUpOperation.assert_not_called()

    def test_create_doc_instances(self):
        # not tested, method only calls ProjectTemplateDocRef.create_docs_instances
        pass

    @mock.patch.object(projects_documents.Project, "create_doc_instances")
    @mock.patch.object(projects_documents.Project, "_create_documents_from_templates")
    def test_handle_doc_templates_ctx_error(
        self, create_doc_from_templ, create_doc_instance
    ):
        "does nothing if ctx_error"

        prj = Project()
        mock_ctx = mock.Mock()
        mock_ctx.error = 1
        # assert nothing has been done
        self.assertIsNone(prj.handle_doc_templates(mock_ctx))
        create_doc_from_templ.assert_has_calls([])
        create_doc_instance.assert_has_calls([])

    @mock.patch.object(projects_documents.Project, "create_doc_instances")
    @mock.patch.object(projects_documents.Project, "_create_documents_from_templates")
    def test_handle_doc_templates_create_doc_instance(
        self, create_doc_from_templ, create_doc_instance
    ):
        "create doc instance for correct relship name"

        prj = Project()
        mock_ctx = mock.Mock()
        mock_ctx.error = 0
        mock_ctx.relationship_name = "cdbpcs_prj2doctmpl"

        prj.handle_doc_templates(mock_ctx)

        create_doc_from_templ.assert_has_calls([])
        create_doc_instance.assert_called_once()

    @mock.patch.object(projects_documents.Project, "create_doc_instances")
    @mock.patch.object(projects_documents.Project, "_create_documents_from_templates")
    def test_handle_doc_templates_create_doc_from_template(
        self, create_doc_from_templ, create_doc_instance
    ):
        "create doc from template for correct relship name"

        prj = Project()
        prj.template = False
        mock_ctx = mock.Mock()
        mock_ctx.error = 0
        mock_ctx.relationship_name = "cdbpcs_project2task_doctemplates"

        prj.handle_doc_templates(mock_ctx)

        create_doc_from_templ.assert_called_once_with(
            projects_documents.Task, projects_documents.TaskTemplateDocRef
        )
        create_doc_instance.assert_has_calls([])

    @mock.patch.object(projects_documents.Project, "create_doc_instances")
    @mock.patch.object(projects_documents.Project, "_create_documents_from_templates")
    def test_handle_doc_templates_not_create_doc_from_template(
        self, create_doc_from_templ, create_doc_instance
    ):
        "does not create doc from template since project is template"

        prj = Project()
        prj.template = True
        mock_ctx = mock.Mock()
        mock_ctx.error = 0
        mock_ctx.relationship_name = "cdbpcs_project2task_doctemplates"

        prj.handle_doc_templates(mock_ctx)

        create_doc_from_templ.assert_has_calls([])
        create_doc_instance.assert_has_calls([])

    def test__create_documents_from_templates(self):
        "a Document is created for each reference found by SQL Statement"

        prj = Project()
        prj.cdb_project_id = "foo"
        template_ref_cls = mock.Mock()
        template_ref_cls.GetTableName.return_value = "bar"
        with_templates_cls = mock.Mock()
        with_templates_cls.GetTableName.return_value = "baz"
        with_templates_cls._buildKeyJoin.return_value = "bam"

        mock_doc_to_copy = mock.Mock()
        ref = mock.Mock()
        ref.DocumentsToCopy = [mock_doc_to_copy]
        template_ref_cls.SQL.return_value = [ref]

        stmt = "SELECT bar.* FROM bar, baz WHERE bam"
        stmt += """ AND baz.cdb_project_id = 'foo'
                AND baz.status = bar.instantiation_state"""
        stmt += " AND bar.created_at is null"

        prj._create_documents_from_templates(with_templates_cls, template_ref_cls)

        template_ref_cls.GetTableName.assert_called_once()
        with_templates_cls.GetTableName.assert_called_once()
        with_templates_cls._buildKeyJoin.assert_called_once_with(template_ref_cls)

        template_ref_cls.SQL.assert_called_once_with(stmt)
        ref.create_doc_instances.assert_called_once()

    # Note: Can not mock auth.name
    @mock.patch.object(projects_documents, "kOperationCopy")
    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents.Project, "ByKeys")
    @mock.patch.object(projects_documents.Project, "getPersistentObject")
    def test_copyPrimaryMSPDocument(
        self, getPersistentObject, ByKeys, operation, kOperationCopy
    ):
        "copy Primary MSP Document from template if any"
        prj = Project(cdb_project_id="pid", template=False, msp_active=True)
        mock_ctx = mock.Mock()
        mock_ctx.cdbtemplate.cdb_project_id = "bar"
        mock_ctx.cdbtemplate.ce_baseline_id = ""
        # setup template, doc and copied doc
        mock_template = mock.MagicMock()
        mock_doc = mock.MagicMock()
        mock_copied_doc = mock.MagicMock()
        mock_copied_doc.z_nummer = "foo"
        operation.return_value = mock_copied_doc
        mock_template.getLastPrimaryMSPDocument.return_value = mock_doc
        # setup return values
        ByKeys.return_value = mock_template
        getPersistentObject.return_value = mock.MagicMock()

        self.assertEqual(prj.copyPrimaryMSPDocument(mock_ctx), mock_doc)
        ByKeys.assert_called_once_with(cdb_project_id="bar", ce_baseline_id="")
        mock_template.getLastPrimaryMSPDocument.assert_called_once()
        operation.assert_called_once_with(
            kOperationCopy,
            mock_doc,
            cdb_project_id="pid",
            autoren=auth.name,
            vorlagen_kz=False,
        )
        getPersistentObject.assert_called_once()
        self.assertEqual(getPersistentObject.return_value.msp_z_nummer, "foo")

    def test__copyPrimaryMSPDocument(self):
        "skipped: since it only calls copyPrimaryMSPDocument"
        pass

    def test_check_docs_delete_pre_documents(self):
        "raises UE Exception if any documents are assigned to the project pre delete"
        prj = Project()
        doc = mock.MagicMock()
        mock_ctx = mock.Mock()
        with mock.patch.object(Project, "Documents", doc):
            with self.assertRaises(ue.Exception):
                prj.check_docs_delete_pre(mock_ctx)

    def test_check_docs_delete_pre_no_documents(self):
        "raises no UE Exception if any documents are assigned to the project pre delete"
        prj = Project()
        mock_ctx = mock.Mock()
        with mock.patch.object(Project, "Documents", None):
            prj.check_docs_delete_pre(mock_ctx)

    def test__check_docs_delete_pre(self):
        "skipped, it only calls check_docs_delete_pre"
        pass

    @mock.patch.object(projects_documents.folders.Folder, "CopyFolderStructure")
    @mock.patch.object(projects_documents.folders.Folder, "Query")
    def test_copyFolders_with_Folders(self, query, copyFolderStructure):
        "copy folders of project and refresh context tables afterwards"
        prj = Project(cdb_project_id="foo")
        mock_ctx = mock.Mock()
        mock_ctx.cdbtemplate.cdb_project_id = "foo2"
        mock_ctx.refresh_tables = mock.Mock()
        query.return_value = ["bar", "baz"]

        prj.copyFolders(mock_ctx)
        query.assert_called_once_with(
            "cdb_project_id = 'foo2' and parent_id = 'root'", order_by="folder_id"
        )
        copyFolderStructure.assert_has_calls(
            [
                mock.call("bar", "foo", copy_docs=True),
                mock.call("baz", "foo", copy_docs=True),
            ]
        )
        mock_ctx.refresh_tables.assert_called_once_with(
            ["cdb_folder2doc", "cdb_folder"]
        )

    @mock.patch.object(projects_documents.folders.Folder, "CopyFolderStructure")
    @mock.patch.object(projects_documents.folders.Folder, "Query")
    def test_copyFolders_without_Folders(self, query, copyFolderStructure):
        "copy no folders if none are present"
        prj = Project(cdb_project_id="foo")
        mock_ctx = mock.Mock()
        mock_ctx.cdbtemplate.cdb_project_id = "foo2"
        mock_ctx.refresh_tables = mock.Mock()
        query.return_value = []

        prj.copyFolders(mock_ctx)
        query.assert_called_once_with(
            "cdb_project_id = 'foo2' and parent_id = 'root'", order_by="folder_id"
        )
        # since no folders exist,
        # none are copied and the context tables are not refreshed
        copyFolderStructure.assert_has_calls([])
        mock_ctx.refresh_tables.assert_has_calls([])

    def test__copyFolders(self):
        "skipped; only calls copyFolders"
        pass

    @mock.patch.object(projects_documents.folders.Folder, "Query")
    def test_deleteFolders(self, query):
        "delete any folder persent"
        prj = Project(cdb_project_id="foo")
        mock_ctx = mock.Mock()
        mock_folder_1 = mock.MagicMock(autospec=projects_documents.folders.Folder)
        mock_folder_2 = mock.MagicMock(autospec=projects_documents.folders.Folder)
        query.return_value = [mock_folder_1, mock_folder_2]

        prj.deleteFolders(mock_ctx)
        query.assert_called_once_with(
            "cdb_project_id = 'foo' and parent_id = 'root'", order_by="folder_id"
        )
        mock_folder_1.DeleteFolderStructure.assert_called_once_with(mock_ctx)
        mock_folder_2.DeleteFolderStructure.assert_called_once_with(mock_ctx)

    def test__deleteFolders(self):
        "skipped; only calls deleteFolders"
        pass

    def test_PredefineCopyStructLanguage(self):
        "skipped; only calls folders.Folder.PredefineCopyStructLanguage"
        pass

    @mock.patch.object(projects_documents.folders.Folder, "CopyFolderStruct")
    def test_CopyFoldStruct(self, CopyFolderStruct):
        "calls folders.Folder.CopyFolderStruct with cdb_project_id"
        prj = Project(cdb_project_id="foo")
        mock_ctx = mock.Mock()
        prj.CopyFoldStruct(mock_ctx)
        CopyFolderStruct.assert_called_once_with(mock_ctx, "foo")


@pytest.mark.unit
class TasksTest(testcase.RollbackTestCase):
    def test__get_Documents(self):
        "skipped, since method only returns result of SimpleJoinQuery"
        pass

    def test_create_doc_instances(self):
        "skipped, since method only calls TaskTemplateDocRef.create_docs_instances"
        pass

    @mock.patch.object(Document, "ByKeys")
    def test_searchTasksInSameProject_earlyAbort(self, DocByKeys):
        def check(mock_ctx):
            projects_documents.Task.searchTasksInSameProject(mock_ctx)
            DocByKeys.assert_not_called()

        # action = requery
        mock_ctx = mock.Mock()
        mock_ctx.action = "requery"
        check(mock_ctx)
        # wrong Dialog
        mock_ctx.action = "foo"
        mock_ctx.catalog_name = "OTHERNAME"
        mock_invoking = mock.Mock()
        mock_ctx.catalog_invoking_dialog = mock_invoking
        check(mock_ctx)
        # otherSource
        mock_ctx.catalog_name = "cdbpcs_tasks"
        mock_invoking.get_attribute_names.return_value = ["Some other field"]
        check(mock_ctx)
        # catalog_requery == True
        mock_invoking.get_attribute_names.return_value = ["z_nummer"]
        mock_ctx.catalog_requery = True
        check(mock_ctx)

    def _buildStdCtxMock(self):
        mock_ctx = mock.Mock()
        mock_ctx.action = "foo"
        mock_ctx.catalog_name = "cdbpcs_tasks"
        mock_ctx.catalog_requery = False
        mock_invoking = mock.Mock()
        mock_ctx.catalog_invoking_dialog = mock_invoking
        mock_invoking.get_attribute_names.return_value = ["z_nummer"]
        return mock_ctx

    @mock.patch.object(Document, "ByKeys")
    @mock.patch.object(Project, "ByKeys")
    def test_searchTasksInSameProject_noProject(self, PrjByKeys, DocByKeys):
        mock_ctx = self._buildStdCtxMock()
        mock_doc = mock.Mock()
        mock_doc.cdb_project_id = None
        DocByKeys.return_value = mock_doc

        projects_documents.Task.searchTasksInSameProject(mock_ctx)
        DocByKeys.assert_called_once()
        PrjByKeys.assert_not_called()

    @mock.patch.object(Document, "ByKeys")
    @mock.patch.object(Project, "ByKeys")
    def test_searchTasksInSameProject_pre_mask(self, PrjByKeys, DocByKeys):
        mock_ctx = self._buildStdCtxMock()
        mock_ctx.mode = "pre_mask"
        mock_doc = mock.Mock()
        mock_doc.cdb_project_id = "prj_id"
        DocByKeys.return_value = mock_doc
        mock_prj = mock.Mock()
        mock_prj.cdb_project_id = "prj_id"
        PrjByKeys.return_value = mock_prj

        # not in webui
        mock_ctx.uses_webui = False
        projects_documents.Task.searchTasksInSameProject(mock_ctx)
        DocByKeys.assert_called_once()
        mock_ctx.set.assert_not_called()

        # in webui
        mock_ctx.uses_webui = True
        projects_documents.Task.searchTasksInSameProject(mock_ctx)
        self.assertEqual(DocByKeys.call_count, 2)
        mock_ctx.set.assert_called_once_with("cdb_project_id", mock_prj.cdb_project_id)

    @mock.patch.object(Document, "ByKeys")
    @mock.patch.object(Project, "ByKeys")
    def test_searchTasksInSameProject_pre(self, PrjByKeys, DocByKeys):
        mock_ctx = self._buildStdCtxMock()
        mock_ctx.mode = "pre"
        mock_doc = mock.Mock()
        mock_doc.cdb_project_id = "prj_id"
        DocByKeys.return_value = mock_doc
        mock_prj = mock.Mock()
        mock_prj.cdb_project_id = "prj_id"
        PrjByKeys.return_value = mock_prj

        # in webui
        mock_ctx.uses_webui = True
        mock_ctx.cdb_project_id = None
        projects_documents.Task.searchTasksInSameProject(mock_ctx)
        DocByKeys.assert_called_once()
        mock_ctx.set.assert_not_called()
        # not in web ui
        mock_ctx.uses_webui = False
        projects_documents.Task.searchTasksInSameProject(mock_ctx)
        self.assertEqual(DocByKeys.call_count, 2)
        mock_ctx.set.assert_called_once_with("cdb_project_id", mock_prj.cdb_project_id)


@pytest.mark.unit
class DocumentsTest(testcase.RollbackTestCase):
    @mock.patch.object(projects_documents.folders.Folder, "ByKeys")
    def test_PresetFolderAttributes(self, ByKeys):
        doc = Document()
        ctx = mock.Mock(relationship_name="cdb_folder2doc")
        ctx.parent = {"folder_id": "foo"}
        mock_folder = mock.MagicMock()
        ByKeys.return_value = mock_folder

        doc.PresetFolderAttributes(ctx)

        ByKeys.assert_called_once_with(folder_id="foo")
        mock_folder.ApplyDefaults.assert_called_once_with(doc, overwrite=False)

    def test__PresetFolderAttributes(self):
        "skipped; only calls PresetFolderAttributes"
        pass

    @mock.patch.object(projects_documents, "ByID")
    def test__preset_project_id(self, ByID):
        doc = Document()
        ctx = mock.Mock(relationship_name="cdb_action2docs")
        ctx.parent = mock.Mock(cdb_object_id="foo")

        ByID.return_value = mock.MagicMock(
            spec=projects_documents.Action,
            cdb_project_id="bar",
        )

        doc._preset_project_id(ctx)

        ByID.assert_called_once_with("foo")
        ctx.set.assert_called_once_with("cdb_project_id", "bar")

    def test__preset_project_id_all_docs(self):
        doc = Document()
        ctx = mock.Mock(relationship_name="cdbpcs_project2all_docs")
        ctx.parent = mock.Mock(cdb_project_id="foo")
        doc._preset_project_id(ctx)
        ctx.set.assert_called_once_with("cdb_project_id", "foo")

    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents.Document, "ByKeys")
    def test_CopyFilesAtDragAndDrop_no_dnd_action(self, ByKeys, operation):
        doc = Document(z_nummer="foo1", z_index="foo2", cdb_object_id="foo3")
        ctx = mock.Mock(dragdrop_action_id=None)
        doc.CopyFilesAtDragAndDrop(ctx)
        ByKeys.assert_not_called()
        operation.assert_not_called()

    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents.Document, "ByKeys")
    def test_CopyFilesAtDragAndDrop_not_dragging_document(self, ByKeys, operation):
        doc = Document(z_nummer="foo1", z_index="foo2", cdb_object_id="foo3")
        ctx = mock.Mock(
            dragdrop_action_id="bar",
            dragged_obj=mock.Mock(
                z_nummer=None,
                z_index=None,
            ),
        )
        doc.CopyFilesAtDragAndDrop(ctx)
        ByKeys.assert_not_called()
        operation.assert_not_called()

    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents.Document, "ByKeys", return_value=None)
    def test_CopyFilesAtDragAndDrop_source_no_document(self, ByKeys, operation):
        doc = Document(z_nummer="foo1", z_index="foo2", cdb_object_id="foo3")
        ctx = mock.Mock(
            dragdrop_action_id="bar",
            dragged_obj=mock.Mock(
                z_nummer="baz1",
                z_index="baz2",
            ),
        )
        doc.CopyFilesAtDragAndDrop(ctx)
        ByKeys.assert_called_once_with("baz1", "baz2")
        operation.assert_not_called()

    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents.Document, "ByKeys")
    def test_CopyFilesAtDragAndDrop(self, ByKeys, operation):
        doc = Document(z_nummer="foo1", z_index="foo2", cdb_object_id="foo3")
        ctx = mock.Mock(
            dragdrop_action_id="bar",
            dragged_obj=mock.Mock(
                z_nummer="baz1",
                z_index="baz2",
            ),
        )
        file1 = mock.Mock(cdbf_derived_from=0)
        file2 = mock.Mock(cdbf_derived_from=0)
        file3 = mock.Mock(cdbf_derived_from=1)
        copied_doc = mock.Mock(Files=[file1, file2, file3])
        ByKeys.return_value = copied_doc

        doc.CopyFilesAtDragAndDrop(ctx)
        ByKeys.assert_called_once_with("baz1", "baz2")

        operation.assert_has_calls(
            [
                mock.call(
                    projects_documents.kOperationCopy, file1, cdbf_object_id="foo3"
                ),
                mock.call(
                    projects_documents.kOperationCopy, file2, cdbf_object_id="foo3"
                ),
            ]
        )

    def test_CheckFolderAssignment(self):
        "calls context method if context has correct params"
        doc = Document()
        ctx = mock.Mock(
            relationship_name="cdb_folder2valid_docs",
            action="index",
        )
        doc.CheckFolderAssignment(ctx)
        ctx.skip_relationship_assignment.assert_called_once()

    def test__CheckFolderAssignment(self):
        "skipped; only calls CheckFolderAssignment"
        pass

    def test_RemoveFolderAssignments_context_exists(self):
        "Folder Assignments are not removed if a contextObj exist"
        doc = Document()
        folderAssignments = mock.MagicMock(
            autospec=projects_documents.folders.Folder2doc
        )
        mock_ctx = mock.Mock()

        with mock.patch.object(Document, "FolderAssignments", folderAssignments):
            doc.RemoveFolderAssignments(mock_ctx)
            folderAssignments.DocDeleted.assert_has_calls([])

    def test_RemoveFolderAssignments_no_context_exists(self):
        "Folder Assignments are removed if no contextObj exist"
        doc = Document()
        mock_doc = mock.MagicMock(autospec=projects_documents.Document)
        folderAssignments = [mock_doc]

        with mock.patch.object(Document, "FolderAssignments", folderAssignments):
            doc.RemoveFolderAssignments(None)
            mock_doc.DocDeleted.assert_called_once()

    def test__RemoveFolderAssignments(self):
        "skipped; only calls RemoveFolderAssignments"
        pass


if __name__ == "__main__":
    unittest.main()
