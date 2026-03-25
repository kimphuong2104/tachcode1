#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import datetime
import unittest

import cdb
import mock
import pytest
from cdb import testcase, ue, util
from cs.documents import Document

from cs.pcs import projects_documents
from cs.pcs.projects_documents import initial_index, valid_index

NOW = datetime.datetime(2022, 8, 5, 1, 2, 3)


@pytest.mark.unit
class AbstractTemplateDocRefTest(testcase.RollbackTestCase):
    # NOTE: In this test class, we do not test on AbstractTemplateDocRef,
    # but rather on ProjectTemplateDocRef, since AbstractTemplateDocRef is no
    # CDB_Object Class and mocking all required CDB_Object-related stuff
    # is too much overhead

    @mock.patch.object(projects_documents.Document, "ByKeys")
    def test__get_document_to_copy_use_selected_index(self, docByKeys):
        "get document to copy of selected index"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef(
            z_nummer="foo", tmpl_index="bar"
        )

        mock_doc = mock.MagicMock(spec=projects_documents.Document)
        mock_doc.MatchRule.return_value = True
        docByKeys.return_value = mock_doc

        self.assertEqual(atdr._get_document_to_copy(), [mock_doc])
        docByKeys.assert_called_once_with(z_nummer="foo", z_index="bar")
        mock_doc.MatchRule.assert_called_once_with(
            "cdbpcs: Index-dependent Valid Documents for Instantiation"
        )

    @mock.patch.object(projects_documents.Document, "ByKeys")
    def test__get_document_to_copy_use_selected_index_not_matching(self, docByKeys):
        "get document to copy of selected index, but it does not match the rule"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef(
            z_nummer="foo", tmpl_index="bar"
        )

        mock_doc = mock.MagicMock(spec=projects_documents.Document)
        mock_doc.MatchRule.return_value = False
        docByKeys.return_value = mock_doc

        self.assertEqual(atdr._get_document_to_copy(), [])
        docByKeys.assert_called_once_with(z_nummer="foo", z_index="bar")
        mock_doc.MatchRule.assert_called_once_with(
            "cdbpcs: Index-dependent Valid Documents for Instantiation"
        )

    @mock.patch.object(projects_documents.Document, "KeywordQuery")
    def test__get_document_to_copy_not_use_selected_index(self, docKeywordQuery):
        "get documents to copy"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef(
            z_nummer="foo", tmpl_index=valid_index
        )

        mock_docs = []

        mock_docs.append(mock.MagicMock(spec=projects_documents.Document))
        mock_docs[0].MatchRule.return_value = True
        mock_docs.append(mock.MagicMock(spec=projects_documents.Document))
        mock_docs[1].MatchRule.return_value = False

        docKeywordQuery.return_value = mock_docs

        self.assertEqual(atdr._get_document_to_copy(), [mock_docs[0]])
        docKeywordQuery.assert_called_once_with(z_nummer="foo")
        for mock_version in mock_docs:
            mock_version.MatchRule.assert_called_once_with(
                "cdbpcs: Documents valid for Instantiation"
            )

    @mock.patch.object(projects_documents.Document, "KeywordQuery")
    def test__get_document_to_copy_not_use_selected_index_no_docs(
        self, docKeywordQuery
    ):
        "get documents to copy, but there are not any"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef(
            z_nummer="foo", tmpl_index=valid_index
        )
        docKeywordQuery.return_value = []

        self.assertEqual(atdr._get_document_to_copy(), [])
        docKeywordQuery.assert_called_once_with(z_nummer="foo")

    def test__get_referer(self):
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        mock_class = mock.Mock()
        mock_class.ByKeys = mock.Mock(return_value="bar")
        mock_get_referer_keys = mock.Mock(return_value={"foo": "foo"})
        atdr = projects_documents.ProjectTemplateDocRef()
        atdr.__referer_cls__ = mock_class
        atdr._get_referer_keys = mock_get_referer_keys
        self.assertEqual(atdr._get_referer(), "bar")
        mock_class.ByKeys.assert_called_once_with(foo="foo")

    def test__get_referer_keys(self):
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        # set any values on ProjectTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef(
            z_nummer="foo", tmpl_index="bar"
        )
        mock_class = mock.Mock()
        mock_class.KeyNames = mock.Mock(return_value=["z_nummer", "tmpl_index"])
        atdr.__referer_cls__ = mock_class
        self.assertEqual(
            atdr._get_referer_keys(), {"z_nummer": "foo", "tmpl_index": "bar"}
        )
        mock_class.KeyNames.assert_called_once()

    @mock.patch.object(cdb.misc, "kLogMsg")
    @mock.patch.object(cdb.misc, "cdblogv")
    def test__find_document_templates_no_ref_table(self, cdblogv, kLogMsg):
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef()
        mock_templateDocRef = mock.MagicMock(
            spec=projects_documents.ProjectTemplateDocRef
        )
        mock_templateDocRef.GetTableName = mock.Mock(
            side_effect=cdb.objects.TableNotFound("foo")
        )

        self.assertEqual(
            projects_documents.AbstractTemplateDocRef._find_document_templates(
                atdr, mock_templateDocRef
            ),
            [],
        )
        mock_templateDocRef.GetTableName.assert_called_once()
        cdblogv.assert_called_once_with(
            kLogMsg, 1, "WithDocumentTemplates: Table not found: foo"
        )

    def test__find_document_templates(self):
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = mock.Mock(spec=projects_documents.ProjectTemplateDocRef)
        atdr.GetTableName = mock.Mock(return_value="bar_table")
        atdr.JoinCondition = mock.Mock(return_value="foo_condition")

        mock_invalid_ref = mock.Mock()
        mock_invalid_ref.DocumentsToCopy = None
        mock_valid_ref = mock.Mock()
        mock_valid_ref.DocumentsToCopy = mock.Mock()
        mock_templateDocRef = mock.MagicMock(
            spec=projects_documents.ProjectTemplateDocRef
        )
        mock_templateDocRef.GetTableName = mock.Mock(return_value="foo_table")
        mock_templateDocRef.SQL = mock.Mock(
            return_value=[mock_valid_ref, mock_invalid_ref]
        )

        self.assertEqual(
            projects_documents.AbstractTemplateDocRef._find_document_templates(
                atdr, mock_templateDocRef
            ),
            ([mock_valid_ref], [mock_invalid_ref]),
        )
        mock_templateDocRef.GetTableName.assert_called_once()
        atdr.GetTableName.assert_called_once()
        atdr.JoinCondition.assert_called_once_with(mock_templateDocRef)
        mock_templateDocRef.SQL.assert_called_once_with(
            "SELECT foo_table.* FROM foo_table, bar_table WHERE foo_condition"
            " AND bar_table.status = foo_table.instantiation_state"
            " AND foo_table.created_at is null"
        )

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(
        projects_documents.AbstractTemplateDocRef,
        "_find_document_templates",
    )
    def test_create_docs_instances(self, _find_document_templates, CDBMsg):
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = mock.Mock(spec=projects_documents.ProjectTemplateDocRef)
        mock_templateDocRef = mock.MagicMock(
            spec=projects_documents.ProjectTemplateDocRef
        )

        mock_invalid_ref_1 = mock.Mock(z_nummer="foo_1", tmpl_index="bar_1")
        mock_invalid_ref_1.create_doc_instances = mock.Mock()
        mock_invalid_ref_2 = mock.Mock(z_nummer="foo_2", tmpl_index="bar_2")
        mock_invalid_ref_2.create_doc_instances = mock.Mock()
        mock_valid_ref = mock.Mock()
        mock_valid_ref.create_doc_instances = mock.Mock()
        _find_document_templates.return_value = (
            [mock_valid_ref],
            [mock_invalid_ref_1, mock_invalid_ref_2],
        )

        with self.assertRaises(ue.Exception):
            projects_documents.AbstractTemplateDocRef.create_docs_instances(
                atdr, mock_templateDocRef
            )

        _find_document_templates.assert_called_once_with(atdr, mock_templateDocRef)
        # only create_doc_instances of valid refs is called
        mock_valid_ref.create_doc_instances.assert_called_once()
        mock_invalid_ref_1.create_doc_instances.assert_has_calls([])
        mock_invalid_ref_2.create_doc_instances.assert_has_calls([])
        # check if exception is correctly called
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_no_valid_docs")
        CDBMsg.return_value.addReplacement.assert_has_calls(
            [
                mock.call("\n\n- foo_1/bar_1\n- foo_2/bar_2"),
            ]
        )
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 1)

    @mock.patch.object(projects_documents, "kOperationCopy")
    @mock.patch.object(projects_documents, "operation")
    @mock.patch.object(projects_documents, "datetime")
    @mock.patch.object(projects_documents.ProjectTemplateDocRef, "_assign_new_doc")
    @mock.patch.object(projects_documents.ProjectTemplateDocRef, "_get_referer")
    def test_create_doc_instances(
        self, _get_referer, _assign_new_doc, dt, operation, kOperationCopy
    ):
        dt.datetime.utcnow.return_value = NOW

        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef()
        mock_doc = mock.Mock()
        copied_doc = mock.Mock()
        operation.return_value = copied_doc

        # the ref returned by _get_referer is either a Project or has a Project
        # referenced, it is here mocked to be both
        mock_ref = mock.Mock()
        mock_ref.isPartOfTemplateProject = mock.Mock(retunr_value=False)
        mock_ref.Project = mock.Mock()
        mock_ref.Project.isPartOfTemplateProject = mock.Mock(return_value=False)
        _get_referer.return_value = mock_ref

        with mock.patch.object(
            projects_documents.ProjectTemplateDocRef, "DocumentsToCopy", [mock_doc]
        ):
            self.assertEqual(atdr.create_doc_instances(bar="bar"), [copied_doc])

            self.assertEqual(atdr.created_at, NOW)

        operation.assert_called_once_with(
            kOperationCopy, mock_doc, vorlagen_kz=0, bar="bar", cdb_project_id=None
        )
        _assign_new_doc.assert_has_calls([mock.call(copied_doc)])

        _get_referer.assert_called_once()

        mock_ref.isPartOfTemplateProject.assert_called_once_with(mock_ref)
        mock_ref.Project.isPartOfTemplateProject.assert_called_once_with(mock_ref)

    def test_assignBy(self):
        "skipped, since method only calls getattr."
        pass

    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "_get_referer_keys")
    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "assignBy")
    def test__assign_new_doc_no_assign_cls(self, assignBy, _get_referer_keys):
        "assign new doc, but without an assign class"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef()
        assignBy.return_value = None
        _get_referer_keys.return_value = {"foo": "foo"}
        mock_doc = mock.Mock()
        mock_doc.Update = mock.Mock()

        atdr._assign_new_doc(mock_doc)

        assignBy.assert_called_once()
        _get_referer_keys.assert_called_once()
        mock_doc.Update.assert_called_once_with(foo="foo")

    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "KeyDict")
    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "_get_referer_keys")
    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "assignBy")
    def test__assign_new_doc(self, assignBy, _get_referer_keys, KeyDict):
        "assign new doc"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef()

        mock_class = mock.Mock()
        mock_class.Create = mock.Mock()
        assignBy.return_value = mock_class

        KeyDict.return_value = {"baz": "baz"}

        mock_doc = mock.Mock()
        mock_doc.Update = mock.Mock()
        mock_doc.KeyDict = mock.Mock(return_value={"bar": "bar"})

        atdr._assign_new_doc(mock_doc)

        assignBy.assert_called_once()
        KeyDict.assert_called_once()
        mock_doc.KeyDict.assert_called_once()
        mock_class.Create.assert_called_once_with(bar="bar", baz="baz")
        _get_referer_keys.assert_has_calls([])
        mock_doc.Update.assert_has_calls([])

    @mock.patch.object(projects_documents.AbstractTemplateDocRef, "followUpAction")
    @mock.patch.object(
        projects_documents.AbstractTemplateDocRef, "create_doc_instances"
    )
    def test_on_CDB_WithDocTemplates_New_now(
        self, mock_create_doc_instances, mock_followUpAction
    ):
        "call FollowUpAction for each created document"
        # NOTE: Using ProjectTemplateDocRef instead of AbstractTemplateDocRef
        atdr = projects_documents.ProjectTemplateDocRef()
        mock_ctx = mock.Mock()
        mock_create_doc_instances.return_value = ["foo", "bar", "baz"]
        atdr.on_CDB_WithDocTemplates_New_now(mock_ctx)
        mock_create_doc_instances.assert_called_once()
        mock_followUpAction.assert_has_calls(
            [
                mock.call("foo", mock_ctx),
                mock.call("bar", mock_ctx),
                mock.call("baz", mock_ctx),
            ]
        )

    def test_followUpAction(self):
        "skipped, since methods only calls ctx.set_followUpOperation."
        pass

    @mock.patch.object(cdb.platform.olc.StateDefinition, "ByKeys")
    def test_set_mask_fields_empty_instantiation_state(self, olcByKeys):
        # mock_AbstractTemplateDocRef:
        mock_atdr = mock.MagicMock(projects_documents.AbstractTemplateDocRef)
        mock_ctx = mock.MagicMock()
        olcByKeys.return_value = "ByKeys"
        mock_atdr.instantiation_state = ""
        mock_atdr.tmpl_index = "Foo"
        projects_documents.AbstractTemplateDocRef.set_mask_fields(mock_atdr, mock_ctx)

        olcByKeys.assert_not_called()
        mock_ctx.set.assert_has_calls(
            [
                mock.call(
                    "instantiation_state_name",
                    mock_atdr.get_instantion_state_txt(
                        None, mock_atdr.Referer.cdb_objektart
                    ),
                )
            ]
        )

    @mock.patch.object(cdb.platform.olc.StateDefinition, "ByKeys")
    def test_set_mask_fields_none_instantiation_state(self, olcByKeys):
        # mock_AbstractTemplateDocRef:
        mock_atdr = mock.MagicMock(projects_documents.AbstractTemplateDocRef)
        mock_ctx = mock.MagicMock()
        olcByKeys.return_value = "ByKeys"
        mock_atdr.instantiation_state = None
        mock_atdr.tmpl_index = None
        projects_documents.AbstractTemplateDocRef.set_mask_fields(mock_atdr, mock_ctx)

        olcByKeys.assert_not_called()
        mock_ctx.set.assert_has_calls(
            [
                mock.call(
                    "instantiation_state_name",
                    mock_atdr.get_instantion_state_txt(
                        None, mock_atdr.Referer.cdb_objektart
                    ),
                )
            ]
        )

    def test_set_mask_fields_valid_index(self):
        # mock_AbstractTemplateDocRef:
        mock_atdr = mock.MagicMock(projects_documents.AbstractTemplateDocRef)
        mock_ctx = mock.MagicMock()
        mock_atdr.instantiation_state = None
        mock_atdr.tmpl_index = valid_index
        projects_documents.AbstractTemplateDocRef.set_mask_fields(mock_atdr, mock_ctx)

        mock_ctx.set.assert_has_calls(
            [
                mock.call(
                    "instantiation_state_name",
                    mock_atdr.get_instantion_state_txt(
                        None, mock_atdr.Referer.cdb_objektart
                    ),
                ),
                mock.call("tmpl_index", util.get_label(valid_index)),
            ]
        )

    def test_set_mask_fields_empty_index(self):
        # mock_AbstractTemplateDocRef:
        mock_atdr = mock.MagicMock(projects_documents.AbstractTemplateDocRef)
        mock_ctx = mock.MagicMock()
        mock_atdr.instantiation_state = None
        mock_atdr.tmpl_index = ""
        projects_documents.AbstractTemplateDocRef.set_mask_fields(mock_atdr, mock_ctx)

        mock_ctx.set.assert_has_calls(
            [
                mock.call(
                    "instantiation_state_name",
                    mock_atdr.get_instantion_state_txt(
                        None, mock_atdr.Referer.cdb_objektart
                    ),
                ),
                mock.call("tmpl_index", util.get_label(initial_index)),
            ]
        )

    def test_set_mask_fields_diffferent_index(self):
        # mock_AbstractTemplateDocRef:
        mock_atdr = mock.MagicMock(projects_documents.AbstractTemplateDocRef)
        mock_ctx = mock.MagicMock()
        mock_atdr.instantiation_state = None
        mock_atdr.tmpl_index = "My Special Index"
        projects_documents.AbstractTemplateDocRef.set_mask_fields(mock_atdr, mock_ctx)

        mock_ctx.set.assert_has_calls(
            [
                mock.call(
                    "instantiation_state_name",
                    mock_atdr.get_instantion_state_txt(
                        None, mock_atdr.Referer.cdb_objektart
                    ),
                ),
            ]
        )

    def test_get_instantion_state_txt_empty_instantiation(self):
        # mock_AbstractTemplateDocRef:
        instantiation_state = None
        objektart = "cdbpcs_project"
        instantiation_state_name = (
            projects_documents.AbstractTemplateDocRef.get_instantion_state_txt(
                instantiation_state, objektart
            )
        )
        self.assertEqual(instantiation_state_name, "")

    def test_get_instantion_state_txt_project_new(self):
        # mock_AbstractTemplateDocRef:
        instantiation_state = 0
        objektart = "cdbpcs_project"
        instantiation_state_name = (
            projects_documents.AbstractTemplateDocRef.get_instantion_state_txt(
                instantiation_state, objektart
            )
        )
        self.assertEqual(instantiation_state_name, "Neu")

    def test_get_instantion_state_txt_checklist_evaluation(self):
        # mock_AbstractTemplateDocRef:
        instantiation_state = 20
        objektart = "cdbpcs_checklist"
        instantiation_state_name = (
            projects_documents.AbstractTemplateDocRef.get_instantion_state_txt(
                instantiation_state, objektart
            )
        )
        self.assertEqual(instantiation_state_name, "Bewertung")


@pytest.mark.unit
class StandAloneMethodsTest(testcase.RollbackTestCase):
    @mock.patch("cs.pcs.checklists_documents.CLTemplateDocRef")
    def test_delete_invalid_doc_templates(self, CLTemplateDocRef):
        "delete all checklist template document references with only documents in status 180"

        mock_ctx = mock.Mock()
        mock_doc = mock.Mock()
        mock_doc.z_nummer = "foo"
        mock_ctx.object = mock_doc
        mock_doc_to_copy = mock.Mock()
        mock_doc_to_copy.status = 0
        # setup template ref without documents
        mock_template_ref_without_docs = mock.MagicMock()
        mock_template_ref_without_docs.DocumentsToCopy = []
        # setup template ref with documents
        mock_template_ref_with_docs = mock.MagicMock()
        mock_template_ref_with_docs.DocumentsToCopy = []
        CLTemplateDocRef.KeywordQuery.return_value = [
            mock_template_ref_without_docs,
            mock_template_ref_with_docs,
        ]
        # tested method is losely connected to signal emitted by Document
        projects_documents.delete_invalid_doc_templates(Document, mock_ctx)
        CLTemplateDocRef.KeywordQuery.assert_called_once_with(z_nummer="foo")

        # assert only template without docs in status 180 is deleted
        mock_template_ref_without_docs.Delete.assert_called_once()
        mock_template_ref_with_docs.Delete.assert_has_calls([])

    @mock.patch.object(projects_documents.Project, "KeywordQuery")
    def test_delete_msp_time_schedule(self, get_project):
        mock_ctx = mock.Mock()
        mock_doc = mock.Mock()
        mock_doc.z_nummer = "foo"
        mock_ctx.object = mock_doc

        mock_prj = mock.MagicMock()
        get_project.return_value = [mock_prj]
        with self.assertRaises(ue.Exception):
            projects_documents.delete_msp_time_schedule(Document, mock_ctx)

        get_project.assert_called_once_with(msp_z_nummer="foo")
        mock_prj.GetDescription.assert_called_once()


if __name__ == "__main__":
    unittest.main()
