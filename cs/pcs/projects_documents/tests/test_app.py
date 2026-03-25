#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import

__revision__ = "$Id$"

import datetime
import unittest

import mock
import pytest
from cdb import sqlapi, testcase

from cs.pcs.projects.tests import common as ProjectsCommon
from cs.pcs.projects_documents import TaskTemplateDocRef
from cs.pcs.projects_documents.tests.integration import common
from cs.pcs.projects_documents.web import rest_app
from cs.pcs.projects_documents.web.rest_app.models import doc_templates_model


@pytest.mark.unit
class DocTemplateApp(testcase.RollbackTestCase):
    @mock.patch.object(rest_app, "get_url_patterns")
    @mock.patch.object(rest_app.InternalDocTemplatesApp, "get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            rest_app.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [("doc_templates", doc_templates_model.DocTemplatesModel, ["object_id"])],
        )

    @mock.patch.object(doc_templates_model, "quote")
    def test__get_icon_url_no_query(self, quote):
        self.assertEqual(
            doc_templates_model.get_icon_url("foo", ""),
            f"/resources/icons/byname/{quote.return_value}",
        )
        quote.assert_called_once_with("foo")

    @mock.patch.object(doc_templates_model, "urlencode")
    @mock.patch.object(doc_templates_model, "quote")
    def test__get_icon_url(self, quote, urlencode):
        self.assertEqual(
            doc_templates_model.get_icon_url("foo", "bar"),
            f"/resources/icons/byname/{quote.return_value}?{urlencode.return_value}",
        )
        quote.assert_called_once_with("foo")
        urlencode.assert_called_once_with("bar")

    @mock.patch.object(doc_templates_model, "get_status_label")
    def test_get_status(self, get_status_label):
        self.assertEqual(
            doc_templates_model.get_status_label("foo", "bar"),
            get_status_label.return_value,
        )

    def test_get_column_data_txt_non_icon(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        column = {"attribute": "foo"}
        data = {"foo": "bar"}
        self.assertEqual(docTemplateModel.get_columns_data(data, column), "bar")

    def test_get_column_data_float_non_icon(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        column = {"attribute": "foo"}
        data = {"foo": 1.1}
        self.assertEqual(docTemplateModel.get_columns_data(data, column), 1.1)

    def test_get_column_data_date_non_icon(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        column = {"attribute": "foo"}
        data = {"foo": datetime.date(2020, 6, 30)}
        self.assertEqual(docTemplateModel.get_columns_data(data, column), "2020-06-30")

    @mock.patch.object(doc_templates_model.IconCache, "getIcon", return_value="bar")
    def test_get_column_data_icon(self, src):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        column = {"attribute": "foo", "kind": 100}
        data = {"foo": datetime.date(2020, 6, 30)}
        self.assertEqual(
            docTemplateModel.get_columns_data(data, column), {"icon": {"src": "bar"}}
        )

    def test_update_doc_title(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        templates_data1 = {"title_index": "foo", "z_nummer": 1}
        templates_data2 = {"title_index": "bar", "z_nummer": 2}
        doc_templates_row1 = {"z_index": "foo", "z_nummer": 1, "titel": "titel1"}
        doc_templates_row2 = {"z_index": "bar", "z_nummer": 2, "titel": "titel2"}
        doc_templates_data = [templates_data1, templates_data2]
        doc_templates_rows = [doc_templates_row1, doc_templates_row2]
        _ = docTemplateModel.update_doc_title(doc_templates_data, doc_templates_rows), {
            "icon": {"src": "bar"}
        }
        self.assertEqual(
            templates_data1, {"title_index": "foo", "z_nummer": 1, "title": "titel1"}
        )
        self.assertEqual(
            templates_data2, {"title_index": "bar", "z_nummer": 2, "title": "titel2"}
        )

    def test_update_cond_stmt_tmpl_index_empty(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        templates_data1 = {"tmpl_index": "", "z_nummer": 1}
        doc_templates_data = [templates_data1]
        stmt_cond = []
        docTemplateModel.update_cond_stmt(doc_templates_data, stmt_cond)
        self.assertEqual(
            templates_data1, {"tmpl_index": "", "z_nummer": 1, "title_index": ""}
        )
        self.assertEqual(stmt_cond, ["z_nummer = '1' "])

    @mock.patch.object(doc_templates_model.Document, "KeywordQuery")
    @mock.patch.object(doc_templates_model.AbstractTemplateDocRef, "get_valid_doc")
    def test_update_cond_stmt_tmpl_index_equal_valid_index(
        self, get_valid_doc, KeywordQuery
    ):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        mock_doc = mock.Mock()
        mock_doc.z_index = "c"
        get_valid_doc.return_value = mock_doc
        templates_data1 = {"tmpl_index": "valid_index", "z_nummer": 1}
        doc_templates_data = [templates_data1]
        stmt_cond = []
        docTemplateModel.update_cond_stmt(doc_templates_data, stmt_cond)
        self.assertEqual(
            templates_data1,
            {"tmpl_index": "valid_index", "z_nummer": 1, "title_index": "c"},
        )
        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            length_field = "LEN"
        else:
            length_field = "LENGTH"
        self.assertEqual(
            stmt_cond,
            [
                f"(z_nummer = '1'  AND "
                f"((z_index >= 'c' AND {length_field}(z_index) = 1) OR {length_field}(z_index) > 1)) "
            ],
        )

    def test_update_cond_stmt_tmpl_index_equal_specific_index(self):
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        templates_data1 = {"tmpl_index": "c", "z_nummer": 1}
        doc_templates_data = [templates_data1]
        stmt_cond = []
        docTemplateModel.update_cond_stmt(doc_templates_data, stmt_cond)
        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            length_field = "LEN"
        else:
            length_field = "LENGTH"
        self.assertEqual(
            templates_data1, {"tmpl_index": "c", "z_nummer": 1, "title_index": "c"}
        )

        self.assertEqual(
            stmt_cond,
            [
                f"(z_nummer = '1'  AND "
                f"((z_index >= 'c' AND {length_field}(z_index) = 1) OR {length_field}(z_index) > 1)) "
            ],
        )

    @mock.patch.object(
        doc_templates_model.DocTemplatesModel, "get_columns_data", return_value="a"
    )
    @mock.patch.object(doc_templates_model, "get_webui_link", return_value="url")
    @mock.patch.object(doc_templates_model.rest, "get_collection_app")
    def test_get_row_data(self, get_collection_app, get_webui_link, get_columns_data):
        request = mock.MagicMock(application_url="application_url")
        request.view.return_value = {"@id": "bar"}
        document = {"cdb_object_id": "foo"}
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        row_data = docTemplateModel.get_row_data(document, ["a"], request)
        self.assertEqual(
            row_data,
            {
                "id": "foo",
                "@id": "bar",
                "persistent_id": "foo",
                "restLink": "bar",
                "uiLink": "url",
                "columns": ["a"],
            },
        )

    @mock.patch.object(doc_templates_model.DocTemplatesModel, "update_doc_title")
    @mock.patch.object(doc_templates_model.ColumnsModel, "get_columns")
    @mock.patch.object(doc_templates_model.Document, "Query", return_value=[])
    @mock.patch.object(doc_templates_model, "get_restlink", return_value="url")
    @mock.patch.object(doc_templates_model, "ByID")
    @mock.patch.object(doc_templates_model.rest, "get_collection_app")
    @mock.patch.object(
        doc_templates_model.AbstractTemplateDocRef,
        "get_instantion_state_txt",
        return_value="bar",
    )
    def test_doc_templates_data(
        self,
        get_instantion_state_txt,
        get_collection_app,
        ByID,
        get_rest_link,
        Query,
        get_columns,
        update_doc_title,
    ):
        doc_template_reference_mock = mock.MagicMock(
            z_nummer="foo", instantiation_state="bar", tmpl_index="a"
        )
        ByID.return_value = mock.MagicMock(cdb_project_id="foo1")
        ByID.return_value.get_doc_template_references.return_value = [
            doc_template_reference_mock
        ]
        request = mock.MagicMock(application_url="application_url")
        docTemplateModel = doc_templates_model.DocTemplatesModel("object")
        doc_template_data = docTemplateModel.get_doc_templates_data(request)
        object_doc_templates = [
            {
                "title_index": "a",
                "instantiation_state": "bar",
                "instantiation_state_txt": "bar",
                "z_nummer": "foo",
                "restLink": "url",
                "project_id": "foo1",
                "tmpl_index": "a",
            }
        ]
        # pylint: disable=unnecessary-dunder-call
        x = get_columns.return_value.__getitem__()
        self.assertEqual(
            doc_template_data,
            {
                "rows": [],
                "columns": x,
                "initGroupBy": [],
                "object_doc_templates": object_doc_templates,
            },
        )


@pytest.mark.integration
class ProjectDocumentsTemplateIntegrationTest(testcase.RollbackTestCase):
    @mock.patch.object(
        doc_templates_model.ColumnsModel, "get_columns", return_value={"columns": []}
    )
    @mock.patch.object(doc_templates_model, "get_restlink", return_value="url")
    def test_get_doc_template_data(self, get_restlink, get_columns):
        p = ProjectsCommon.generate_project()
        task = ProjectsCommon.generate_task(p, "taskFoo")
        d = common.generate_doc()
        common.generate_document_template(
            d,
            TaskTemplateDocRef,
            task_id=task.task_id,
            cdb_project_id=p.cdb_project_id,
            tmpl_index="valid_index",
        )
        request = mock.MagicMock(application_url="application_url")
        request.view.return_value = {
            "@id": "bar",
            "z_index": "a",
            "z_title": "docTitle",
        }
        object_model = doc_templates_model.DocTemplatesModel(
            object_id=task.cdb_object_id
        )
        result = object_model.get_doc_templates_data(request)
        self.assertEqual(
            result["object_doc_templates"],
            [
                {
                    "restLink": "url",
                    "z_nummer": "foo",
                    "instantiation_state": None,
                    "tmpl_index": "<Zuletzt freigegebener Index>",
                    "instantiation_state_txt": "",
                    "project_id": "project_id",
                    "title_index": "",
                    "title": "<fehlendes Dokument>",
                }
            ],
        )
        self.assertEqual(
            result["rows"],
            [
                {
                    "@id": "bar",
                    "z_index": "a",
                    "z_title": "docTitle",
                    "id": d.cdb_object_id,
                    "restLink": "bar",
                    "persistent_id": d.cdb_object_id,
                    "uiLink": "/info/document/foo@",
                    "columns": [],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
