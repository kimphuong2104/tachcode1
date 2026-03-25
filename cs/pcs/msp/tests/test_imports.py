#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import sqlapi, testcase

from cs.pcs.msp import imports


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TestXmlMergeImport(unittest.TestCase):
    @mock.patch.object(imports.sqlapi, "make_literal")
    @mock.patch.object(imports.sqlapi, "SQLdelete")
    @mock.patch.object(imports.Task, "MakeChangeControlAttributes")
    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports.sqlapi, "SQLinsert")
    def test_insert_new_tasks_mssql_with_different(
        self, SQLinsert, logger, MakeChangeControlAttributes, SQLdelete, make_literal
    ):
        tasks_to_insert = [
            {"cdb_object_id": "oid1", "task_name": "foo"},
            {"cdb_object_id": "oid2"},
        ]
        MakeChangeControlAttributes.return_value = {
            "cdb_cdate": "today",
            "cdb_cpersno": "cpersno",
            "cdb_mdate": "today",
            "cdb_mpersno": "mpersno",
        }

        def side_effect(table, attr, value):
            return f"'{value}'"

        make_literal.side_effect = side_effect

        xmlmerge = imports.XmlMergeImport()
        xmlmerge.db_type = sqlapi.DBMS_MSSQL
        xmlmerge.insert_new_tasks(tasks_to_insert)
        MakeChangeControlAttributes.assert_called_once_with()
        SQLdelete.assert_called_once_with(
            "FROM cdbpcs_task WHERE cdb_object_id IN ('oid1', 'oid2')"
        )
        calls = [
            mock.call(
                "INTO cdbpcs_task (cdb_cdate, cdb_cpersno, cdb_mdate, cdb_mpersno, cdb_object_id,"
                " task_name) VALUES ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'oid1', 'foo'), ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'oid2', NULL)"
            ),
            mock.call(
                """INTO cdb_object (id, relation)
                SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
                WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                            WHERE relation = 'cdbpcs_task')"""
            ),
        ]
        SQLinsert.assert_has_calls(calls)

    @mock.patch.object(imports.sqlapi, "make_literal")
    @mock.patch.object(imports.sqlapi, "SQLdelete")
    @mock.patch.object(imports.Task, "MakeChangeControlAttributes")
    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports.sqlapi, "SQLinsert")
    def test_insert_new_tasks_mssql_without_oid(
        self, SQLinsert, logger, MakeChangeControlAttributes, SQLdelete, make_literal
    ):
        tasks_to_insert = [{"task_name": "foo"}, {"task_name": "bar"}]
        MakeChangeControlAttributes.return_value = {
            "cdb_cdate": "today",
            "cdb_cpersno": "cpersno",
            "cdb_mdate": "today",
            "cdb_mpersno": "mpersno",
        }

        def side_effect(table, attr, value):
            return f"'{value}'"

        make_literal.side_effect = side_effect
        xmlmerge = imports.XmlMergeImport()
        xmlmerge.db_type = sqlapi.DBMS_MSSQL
        xmlmerge.insert_new_tasks(tasks_to_insert)
        MakeChangeControlAttributes.assert_called_once_with()
        SQLdelete.assert_not_called()
        calls = [
            mock.call(
                "INTO cdbpcs_task (cdb_cdate, cdb_cpersno, cdb_mdate, cdb_mpersno,"
                " task_name) VALUES ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'foo'), ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'bar')"
            ),
            mock.call(
                """INTO cdb_object (id, relation)
                SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
                WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                            WHERE relation = 'cdbpcs_task')"""
            ),
        ]
        SQLinsert.assert_has_calls(calls)

    @mock.patch.object(imports.sqlapi, "make_literal")
    @mock.patch.object(imports.sqlapi, "SQLdelete")
    @mock.patch.object(imports.Task, "MakeChangeControlAttributes")
    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports.sqlapi, "SQLinsert")
    def test_insert_new_tasks_mssql_with_same(
        self, SQLinsert, logger, MakeChangeControlAttributes, SQLdelete, make_literal
    ):
        tasks_to_insert = [{"cdb_object_id": "oid1"}, {"cdb_object_id": "oid2"}]
        MakeChangeControlAttributes.return_value = {
            "cdb_cdate": "today",
            "cdb_cpersno": "cpersno",
            "cdb_mdate": "today",
            "cdb_mpersno": "mpersno",
        }

        def side_effect(table, attr, value):
            return f"'{value}'"

        make_literal.side_effect = side_effect
        xmlmerge = imports.XmlMergeImport()
        xmlmerge.db_type = sqlapi.DBMS_MSSQL
        xmlmerge.insert_new_tasks(tasks_to_insert)
        MakeChangeControlAttributes.assert_called_once_with()
        SQLdelete.assert_called_once_with(
            "FROM cdbpcs_task WHERE cdb_object_id IN ('oid1', 'oid2')"
        )
        calls = [
            mock.call(
                "INTO cdbpcs_task (cdb_cdate, cdb_cpersno, cdb_mdate, cdb_mpersno, cdb_object_id)"
                " VALUES ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'oid1'), ('today',"
                " 'cpersno', 'today', 'mpersno',"
                " 'oid2')"
            ),
            mock.call(
                """INTO cdb_object (id, relation)
                SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
                WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                            WHERE relation = 'cdbpcs_task')"""
            ),
        ]
        SQLinsert.assert_has_calls(calls)

    @mock.patch.object(imports.sqlapi, "make_literal")
    @mock.patch.object(imports.sqlapi, "SQLdelete")
    @mock.patch.object(imports.Task, "MakeChangeControlAttributes")
    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports.sqlapi, "SQLinsert")
    def test_insert_new_tasks_oracle_with_different(
        self, SQLinsert, logger, MakeChangeControlAttributes, SQLdelete, make_literal
    ):
        tasks_to_insert = [
            {"cdb_object_id": "oid1", "task_name": "foo"},
            {"cdb_object_id": "oid2"},
        ]
        MakeChangeControlAttributes.return_value = {
            "cdb_cdate": "today",
            "cdb_cpersno": "cpersno",
            "cdb_mdate": "today",
            "cdb_mpersno": "mpersno",
        }

        def side_effect(table, attr, value):
            return f"'{value}'"

        make_literal.side_effect = side_effect
        xmlmerge = imports.XmlMergeImport()
        xmlmerge.db_type = sqlapi.DBMS_ORACLE
        xmlmerge.insert_new_tasks(tasks_to_insert)
        MakeChangeControlAttributes.assert_called_once_with()
        SQLdelete.assert_called_once_with(
            "FROM cdbpcs_task WHERE cdb_object_id IN ('oid1', 'oid2')"
        )
        calls = [
            mock.call(
                "INTO cdbpcs_task (cdb_cdate, cdb_cpersno, cdb_mdate, cdb_mpersno, cdb_object_id,"
                " task_name) SELECT 'today',"
                " 'cpersno', 'today',"
                " 'mpersno', 'oid1', 'foo' FROM dual UNION ALL SELECT"
                " 'today',"
                " 'cpersno', 'today',"
                " 'mpersno', 'oid2', NULL FROM dual "
            ),
            mock.call(
                """INTO cdb_object (id, relation)
                SELECT cdb_object_id, 'cdbpcs_task' FROM cdbpcs_task
                WHERE cdb_object_id NOT IN (SELECT id FROM cdb_object
                                            WHERE relation = 'cdbpcs_task')"""
            ),
        ]
        SQLinsert.assert_has_calls(calls)

    @mock.patch.object(imports.Task, "MakeChangeControlAttributes")
    @mock.patch.object(imports, "logger")
    def test_insert_new_tasks_no_task(self, logger, MakeChangeControlAttributes):
        tasks_to_insert = []
        xmlmerge = imports.XmlMergeImport()
        xmlmerge.insert_new_tasks(tasks_to_insert)
        MakeChangeControlAttributes.assert_not_called()

    @mock.patch.object(imports.Document, "ByKeys", return_value=None)
    def test__get_xml_file_object_from_document_no_document(self, doc_by_keys):
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(imports.ue.Exception("cdbpcs_no_msp_document", "foo", "bar")),
        )

        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_not_exactly_one_mpp(self, doc_by_keys):
        mock_mpp_file_a = mock.MagicMock(cdbf_type="MS-Project", cdbf_primary="1")
        mock_mpp_file_b = mock.MagicMock(cdbf_type="MS-Project", cdbf_primary="1")
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_mpp_file_a, mock_mpp_file_b]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(
                imports.ue.Exception(
                    "cdbpcs_not_exactly_one_primary_msp_file_in_document",
                    mock_doc.GetDescription.return_value,
                )
            ),
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_no_xml(self, doc_by_keys):
        mock_mpp_file = mock.MagicMock(cdbf_type="MS-Project", cdbf_primary="1")
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_mpp_file]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(
                imports.ue.Exception(
                    "cdbpcs_xml_file_not_found_in_document",
                    mock_doc.GetDescription.return_value,
                )
            ),
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_more_than_one_xml(self, doc_by_keys):
        mock_mpp_file = mock.MagicMock(
            cdbf_type="MS-Project", cdbf_primary="1", cdb_object_id="bar"
        )
        mock_xml_file_a = mock.MagicMock(
            cdbf_type="XML", cdbf_primary="0", cdbf_derived_from="bar"
        )
        mock_xml_file_b = mock.MagicMock(
            cdbf_type="XML", cdbf_primary="0", cdbf_derived_from="bar"
        )
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_mpp_file, mock_xml_file_a, mock_xml_file_b]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(
                imports.ue.Exception(
                    "cdbpcs_multiple_xml_files_in_document",
                    mock_doc.GetDescription.return_value,
                )
            ),
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document(self, doc_by_keys):
        mock_mpp_file = mock.MagicMock(
            cdbf_type="MS-Project", cdbf_primary="1", cdb_object_id="bar"
        )
        mock_xml_file = mock.MagicMock(
            cdbf_type="XML", cdbf_primary="0", cdbf_derived_from="bar"
        )
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_mpp_file, mock_xml_file]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        self.assertEqual(
            xmlmerge._get_xml_file_object_from_document(
                {"z_nummer": "foo", "z_index": "bar"}
            ),
            mock_xml_file,
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys", return_value=None)
    def test__get_xml_file_object_from_document_for_import_no_document(
        self, doc_by_keys
    ):

        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document_for_import(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(imports.ue.Exception("cdbpcs_no_msp_document", "foo", "bar")),
        )

        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_for_import_no_xml(self, doc_by_keys):
        mock_doc = mock.MagicMock()
        mock_doc.Files = []
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document_for_import(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(
                imports.ue.Exception(
                    "cdbpcs_xml_file_not_found_in_document",
                    mock_doc.GetDescription.return_value,
                )
            ),
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_for_import_more_than_one_xml(
        self, doc_by_keys
    ):
        mock_xml_file_a = mock.MagicMock(cdbf_type="XML")
        mock_xml_file_b = mock.MagicMock(cdbf_type="XML")
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_xml_file_a, mock_xml_file_b]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        with self.assertRaises(imports.ue.Exception) as error:
            xmlmerge._get_xml_file_object_from_document_for_import(
                {"z_nummer": "foo", "z_index": "bar"}
            )

        self.assertEqual(
            str(error.exception),
            str(
                imports.ue.Exception(
                    "cdbpcs_multiple_xml_files_in_document",
                    mock_doc.GetDescription.return_value,
                )
            ),
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    @mock.patch.object(imports.Document, "ByKeys")
    def test__get_xml_file_object_from_document_for_import(self, doc_by_keys):
        mock_xml_file = mock.MagicMock(cdbf_type="XML")
        mock_doc = mock.MagicMock()
        mock_doc.Files = [mock_xml_file]
        doc_by_keys.return_value = mock_doc
        xmlmerge = imports.XmlMergeImport()
        self.assertEqual(
            xmlmerge._get_xml_file_object_from_document_for_import(
                {"z_nummer": "foo", "z_index": "bar"}
            ),
            mock_xml_file,
        )
        doc_by_keys.assert_called_once_with(z_nummer="foo", z_index="bar")

    def assert_custom_exception_check_import(self, exception_param, *params):
        with self.assertRaises(imports.ue.Exception) as error:
            imports.XmlMergeImport.check_import_right(*params)
        self.assertEqual(
            str(error.exception), str(imports.ue.Exception(*exception_param))
        )

    @mock.patch.object(imports, "logger")
    def test_check_import_right_no_msp(self, logger):
        proj = mock.MagicMock(msp_active=0)
        self.assert_custom_exception_check_import(
            ["cdbpcs_msp_msp_not_set_as_project_editor_short"], proj
        )

    @mock.patch.object(imports, "logger")
    def test_check_import_right_different_doc(self, logger):
        proj = mock.MagicMock(msp_active=1)
        proj.getLastPrimaryMSPDocument.return_value = "document2"
        self.assert_custom_exception_check_import(
            ["cdbpcs_msp_document_not_primary_msp_document"], proj, "document1", True
        )

    @mock.patch.object(imports, "logger")
    def test_check_import_right_no_access(self, logger):
        proj = mock.MagicMock(msp_active=1)
        proj.CheckAccess.return_value = False
        self.assert_custom_exception_check_import(
            ["cdbpcs_msp_missing_project_save_right"], proj
        )

    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports, "auth")
    def test_check_import_right_locked_by(self, auth, logger):
        auth.persno = "me"
        proj = mock.MagicMock(msp_active=1, mapped_locked_by_name="you")
        proj.CheckAccess.return_value = True
        self.assert_custom_exception_check_import(["pcs_tbd_locked", "you"], proj)

    @mock.patch.object(imports, "logger")
    @mock.patch.object(imports, "emit")
    def test_check_import_right_can_publish_signal(self, emit, logger):
        proj = mock.MagicMock(msp_active=1, locked_by="")
        proj.CheckAccess.return_value = True
        emit.return_value = lambda x: [False]

        self.assertEqual(imports.XmlMergeImport.check_import_right(proj), False)

    def test_check_msp_edition_raises_error(self):
        project = mock.MagicMock(msp_active=1)
        msp_edition = "pjEditionStandard"
        with self.assertRaises(imports.ue.Exception) as error:
            imports.XmlMergeImport.check_msp_edition(project, msp_edition)

        self.assertEqual(
            str(error.exception),
            str(imports.ue.Exception("cdbpcs_msp_edition_conflict")),
        )

    def test_check_msp_edition_no_error_professional(self):
        project = mock.MagicMock(msp_active=1)
        msp_edition = "pjEditionProfessional"

        self.assertEqual(
            imports.XmlMergeImport.check_msp_edition(project, msp_edition), None
        )

    def test_check_msp_edition_no_error_standard(self):
        project = mock.MagicMock(msp_active=2)
        msp_edition = "pjEditionStandard"

        self.assertEqual(
            imports.XmlMergeImport.check_msp_edition(project, msp_edition), None
        )


if __name__ == "__main__":
    unittest.main()
