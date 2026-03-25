#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import mock
import pytest

from cs.pcs.msp import workspace_connect
from cs.pcs.projects import Project


@pytest.mark.unit
class PublishToCE(unittest.TestCase):
    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_xml_to_ce_no_licence(self, _check_for_licence):
        _check_for_licence.return_value = "error"

        actual = workspace_connect.cs_pcs_xml_to_ce("params", "files")
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    def test_cs_pcs_xml_to_ce_error(self, _get_project_and_xml_doc, _check_for_licence):
        _check_for_licence.return_value = None
        _get_project_and_xml_doc.return_value = "prj", "xml", "error"

        actual = workspace_connect.cs_pcs_xml_to_ce("params", "files")
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_xml_to_ce_more_files(self, _check_for_licence):
        _check_for_licence.return_value = None
        with self.assertRaises(Exception):
            workspace_connect.cs_pcs_xml_to_ce("params", [0, 1])

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    @mock.patch("cs.pcs.msp.workspace_connect._save_xml_file_to_xml_doc")
    def test_cs_pcs_xml_to_ce_saving_fails(
        self, _save_xml_file_to_xml_doc, _get_project_and_xml_doc, _check_for_licence
    ):
        _check_for_licence.return_value = None

        prj = mock.MagicMock()
        prj.cdb_project_id = "prj_id"
        xml_doc = mock.MagicMock()
        xml_doc.z_nummer = "xml_doc_z_nummer"
        xml_doc.z_index = "xml_doc_z_index"
        _get_project_and_xml_doc.return_value = prj, xml_doc, None

        _save_xml_file_to_xml_doc.return_value = "error"
        mock_file = mock.MagicMock(local_fname="mock_filename")
        actual = workspace_connect.cs_pcs_xml_to_ce("params", [mock_file])
        expected = "error"
        self.assertEqual(actual, expected)

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    @mock.patch("cs.pcs.msp.workspace_connect._save_xml_file_to_xml_doc")
    def test_cs_pcs_xml_to_ce(
        self, _save_xml_file_to_xml_doc, _get_project_and_xml_doc, _check_for_licence
    ):
        _check_for_licence.return_value = None

        prj = mock.MagicMock()
        prj.cdb_project_id = "prj_id"
        xml_doc = mock.MagicMock()
        xml_doc.z_nummer = "xml_doc_z_nummer"
        xml_doc.z_index = "xml_doc_z_index"
        _get_project_and_xml_doc.return_value = prj, xml_doc, None

        _save_xml_file_to_xml_doc.return_value = None
        mock_file = mock.MagicMock(local_fname="mock_filename")
        actual = workspace_connect.cs_pcs_xml_to_ce("params", [mock_file])
        expected = ([], {}, [])
        self.assertEqual(actual, expected)


@pytest.mark.unit
class XmlFromCe(unittest.TestCase):
    @mock.patch.object(workspace_connect, "_check_wsm_installed", return_value=False)
    def test_cs_pcs_xml_from_ce_no_workspaces(self, _check_wsm_installed):

        with self.assertRaises(workspace_connect.ElementsError):
            workspace_connect.cs_pcs_xml_from_ce("params", "files")

        _check_wsm_installed.assert_called_once()

    @mock.patch.object(workspace_connect, "_check_wsm_installed", return_value=True)
    @mock.patch.object(workspace_connect, "_check_for_licence", return_value=True)
    def test_cs_pcs_xml_from_ce_no_licence(
        self, _check_for_licence, _check_wsm_installed
    ):

        mocked_wsm_module = mock.MagicMock()
        mocked_wsm_module.RemoteFile = mock.MagicMock()
        with mock.patch.dict(
            "sys.modules", {"cs.wsm.pkgs.applrpcutils": mocked_wsm_module}
        ):
            actual = workspace_connect.cs_pcs_xml_from_ce("params", "files")
        self.assertEqual(actual, True)

        _check_wsm_installed.assert_called_once()
        _check_for_licence.assert_called_once()
        mocked_wsm_module.RemoteFile.assert_not_called()

    @mock.patch.object(workspace_connect, "_check_wsm_installed", return_value=True)
    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence", return_value=None)
    @mock.patch(
        "cs.pcs.msp.workspace_connect._get_project_and_xml_doc",
        return_value=("prj", "xml", "error"),
    )
    def test_cs_pcs_xml_from_ce_error(
        self, _get_project_and_xml_doc, _check_for_licence, _check_wsm_installed
    ):

        mocked_wsm_module = mock.MagicMock()
        mocked_wsm_module.RemoteFile = mock.MagicMock()
        with mock.patch.dict(
            "sys.modules", {"cs.wsm.pkgs.applrpcutils": mocked_wsm_module}
        ):
            actual = workspace_connect.cs_pcs_xml_from_ce("params", "files")
        self.assertEqual(actual, "error")

        _check_wsm_installed.assert_called_once()
        _check_for_licence.assert_called_once()
        _get_project_and_xml_doc.assert_called_once()
        mocked_wsm_module.RemoteFile.assert_not_called()

    @mock.patch.object(workspace_connect, "_check_wsm_installed", return_value=True)
    @mock.patch.object(workspace_connect, "_check_for_licence", return_value=None)
    @mock.patch.object(workspace_connect, "_get_project_and_xml_doc")
    def test_cs_pcs_xml_from_ce_missing_key_reset_ids(
        self, _get_project_and_xml_doc, _check_for_licence, _check_wsm_installed
    ):

        prj = mock.MagicMock()
        prj.get_temp_export_xml_file.return_value = "mock_filename"
        prj.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS = ["attr1", "attr2"]
        _get_project_and_xml_doc.return_value = prj, None, None

        mocked_wsm_module = mock.MagicMock()
        mocked_wsm_module.RemoteFile = mock.MagicMock()
        with mock.patch.dict(
            "sys.modules", {"cs.wsm.pkgs.applrpcutils": mocked_wsm_module}
        ):
            errors, params, files = workspace_connect.cs_pcs_xml_from_ce({}, ["files"])
        self.assertEqual(errors, [])
        self.assertEqual(
            params,
            {
                "file": "update_xml",
                "TASK_UPDATABLE_MSP_ATTRS": prj.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS,
            },
        )
        self.assertEqual(files[0], mocked_wsm_module.RemoteFile.return_value)

        prj.Tasks.Update.assert_not_called()
        prj.Reload.assert_not_called()
        _check_wsm_installed.assert_called_once()
        _check_for_licence.assert_called_once()
        mocked_wsm_module.RemoteFile.assert_called_once_with(
            "update_xml", "mock_filename", "XML"
        )

    @mock.patch.object(workspace_connect, "_check_wsm_installed", return_value=True)
    @mock.patch.object(workspace_connect, "_check_for_licence", return_value=None)
    @mock.patch.object(workspace_connect, "_get_project_and_xml_doc")
    def test_cs_pcs_xml_from_ce_reset_msp_guids(
        self, _get_project_and_xml_doc, _check_for_licence, _check_wsm_installed
    ):

        prj = mock.MagicMock()
        prj.get_temp_export_xml_file.return_value = "mock_filename"
        prj.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS = ["attr1", "attr2"]
        _get_project_and_xml_doc.return_value = prj, None, None

        mocked_wsm_module = mock.MagicMock()
        mocked_wsm_module.RemoteFile = mock.MagicMock()
        with mock.patch.dict(
            "sys.modules", {"cs.wsm.pkgs.applrpcutils": mocked_wsm_module}
        ):
            errors, params, files = workspace_connect.cs_pcs_xml_from_ce(
                {"reset_ids": "True"}, ["files"]
            )
        self.assertEqual(errors, [])
        self.assertEqual(
            params,
            {
                "file": "update_xml",
                "TASK_UPDATABLE_MSP_ATTRS": prj.XML_EXPORT_CLASS.TASK_UPDATABLE_MSP_ATTRS,
            },
        )
        self.assertEqual(files[0], mocked_wsm_module.RemoteFile.return_value)

        prj.Tasks.Update.assert_called_once_with(msp_guid="")
        prj.Reload.assert_called_once()
        _check_wsm_installed.assert_called_once()
        _check_for_licence.assert_called_once()
        mocked_wsm_module.RemoteFile.assert_called_once_with(
            "update_xml", "mock_filename", "XML"
        )


@pytest.mark.unit
class GetActiveProjectLinkButtons(unittest.TestCase):
    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_get_active_buttons_no_licence(self, _check_for_licence):
        _check_for_licence.return_value = "error"

        actual = workspace_connect.cs_pcs_get_active_buttons("params", "files")
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_get_active_buttons_no_msp_edition(self, _check_for_licence):
        _check_for_licence.return_value = None

        with self.assertRaises(ValueError):
            workspace_connect.cs_pcs_get_active_buttons({}, "files")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    def test_cs_pcs_get_active_buttons_no_doc_keys(
        self, _get_project_and_xml_doc, _check_for_licence
    ):
        _check_for_licence.return_value = None
        _get_project_and_xml_doc.return_value = "prj", "xml", "error"

        actual = workspace_connect.cs_pcs_get_active_buttons(
            {"msp_edition": "foo"}, "files"
        )
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    @mock.patch("cs.pcs.msp.workspace_connect._get_active_projectlink_buttons")
    def test_cs_pcs_get_active_buttons(
        self,
        _get_active_projectlink_buttons,
        _get_project_and_xml_doc,
        _check_for_licence,
    ):
        _check_for_licence.return_value = None
        _get_project_and_xml_doc.return_value = "prj", "xml", None
        _get_active_projectlink_buttons.return_value = "active_button_list"
        actual = workspace_connect.cs_pcs_get_active_buttons(
            {"msp_edition": "foo"}, "files"
        )
        self.assertEqual(
            actual, ([], {"ACTIVE_PROJECTLINK_BUTTONS": "active_button_list"}, [])
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "correct_msp_edition,check_msp_edition_raises,can_publish,check_import_raises,can_update,expected",
    [
        (  # check_msp_edition returns False
            False,
            False,
            None,  # unused
            None,  # Unused
            None,  # unused
            [],
        ),
        (  # check_msp_edition raises error
            False,
            True,
            None,  # unused
            None,  # Unused
            None,  # unused
            [],
        ),
        (  # check_import_right return False
            # check_export_right return False
            True,
            False,
            False,
            False,
            False,
            [],
        ),
        (  # check_import_right raises Error
            # check_export_right return False
            True,
            False,
            False,
            True,
            False,
            [],
        ),
        (  # check_import_right return True
            # check_export_right return False
            True,
            False,
            True,
            False,
            False,
            ["PUBLISH_PROJECT"],
        ),
        (  # check_import_right return False
            # check_export_right return True
            True,
            False,
            False,
            False,
            True,
            ["UPDATE_PROJECT", "UPDATE_ATTRIBUTES"],
        ),
        (  # check_import_right raises Error
            # check_export_right return False
            True,
            False,
            False,
            True,
            True,
            ["UPDATE_PROJECT", "UPDATE_ATTRIBUTES"],
        ),
        (  # check_import_right return True
            # check_export_right return True
            True,
            False,
            True,
            False,
            True,
            ["PUBLISH_PROJECT", "UPDATE_PROJECT", "UPDATE_ATTRIBUTES"],
        ),
    ],
)
def test__get_active_projectlink_buttons(
    correct_msp_edition,
    check_msp_edition_raises,
    can_publish,
    check_import_raises,
    can_update,
    expected,
):
    mock_project = mock.MagicMock()
    mock_doc = mock.MagicMock()
    check_msp_edition_side_effect = (
        workspace_connect.ue.Exception("") if check_msp_edition_raises else None
    )
    check_import_side_effect = (
        workspace_connect.ue.Exception("") if check_import_raises else None
    )
    with (
        mock.patch.object(
            workspace_connect.XmlMergeImport,
            "check_msp_edition",
            return_value=correct_msp_edition,
            side_effect=check_msp_edition_side_effect,
        ) as check_msp_edition,
        mock.patch.object(
            workspace_connect.XmlMergeImport,
            "check_import_right",
            return_value=can_publish,
            side_effect=check_import_side_effect,
        ) as check_import_right,
        mock.patch.object(
            workspace_connect.XmlExport, "check_export_right", return_value=can_update
        ) as check_export_right,
    ):
        result = workspace_connect._get_active_projectlink_buttons(
            mock_project, mock_doc, "foo_msp_edition"
        )
    assert result == expected
    check_msp_edition.assert_called_once_with(mock_project, "foo_msp_edition")
    if correct_msp_edition and not check_msp_edition_raises:
        check_import_right.assert_called_once_with(mock_project, mock_doc, True)
        check_export_right.assert_called_once_with(mock_project, mock_doc, True)


@pytest.mark.unit
class GetProjectAndXmlDoc(unittest.TestCase):

    params = {"z_nummer": "mock_z_nummer", "z_index": "mock_z_index"}

    def _call_and_assert_error(self, error, args):
        a0, a1, a2 = workspace_connect._get_project_and_xml_doc(self.params)
        self.assertEqual(a0, None)
        self.assertEqual(a1, None)
        self.assertEqual(a2, ([(1, error, args)], {}, []))

    def test_get_project_and_xml_doc_keyerror(self):
        with self.assertRaises(ValueError):
            workspace_connect._get_project_and_xml_doc({})

        with self.assertRaises(ValueError):
            workspace_connect._get_project_and_xml_doc({"z_nummer": 1})

    @mock.patch("cs.pcs.msp.workspace_connect.get_and_check_object")
    def test_get_project_and_xml_doc_no_doc(self, get_and_check_object):
        get_and_check_object.return_value = None

        self._call_and_assert_error("cdbpcs_msp_no_mpp_files", [])

    @mock.patch.object(Project, "KeywordQuery")
    @mock.patch("cs.pcs.msp.workspace_connect.get_and_check_object")
    def test_get_project_and_xml_doc_no_project(
        self, get_and_check_object, ProjectKeywordQuery
    ):
        xml_doc = mock.MagicMock(cdb_project_id="mock_prj_id")
        get_and_check_object.return_value = xml_doc
        ProjectKeywordQuery.return_value = None

        self._call_and_assert_error("cdbpcs_projects_not_found", ["mock_prj_id"])

    @mock.patch.object(Project, "KeywordQuery")
    @mock.patch("cs.pcs.msp.workspace_connect.get_and_check_object")
    def test_get_project_and_xml_doc_no_msp_doc(
        self, get_and_check_object, ProjectKeywordQuery
    ):
        xml_doc = mock.MagicMock(cdb_project_id="mock_prj_id")
        get_and_check_object.return_value = xml_doc

        prj = mock.MagicMock()
        prj.getLastPrimaryMSPDocument.return_value = None
        ProjectKeywordQuery.return_value = [prj]

        self._call_and_assert_error("cdbpcs_msp_no_primary_mpp", ["mock_prj_id"])

    def _build_wrong_doc_testdata(self, z_nummer_append, z_index_append):
        latest_xml_doc = mock.MagicMock()
        latest_xml_doc.z_nummer = self.params["z_nummer"] + z_nummer_append
        latest_xml_doc.z_index = self.params["z_index"] + z_index_append
        prj = mock.MagicMock()
        prj.getLastPrimaryMSPDocument.return_value = latest_xml_doc

        return prj

    @mock.patch.object(Project, "KeywordQuery")
    @mock.patch("cs.pcs.msp.workspace_connect.get_and_check_object")
    def test_get_project_and_xml_doc_wrong_doc(
        self, get_and_check_object, ProjectKeywordQuery
    ):
        xml_doc = mock.MagicMock(cdb_project_id="mock_prj_id", **self.params)
        get_and_check_object.return_value = xml_doc

        prj = self._build_wrong_doc_testdata("2", "")
        ProjectKeywordQuery.return_value = [prj]

        # wrong z_nummer
        self._call_and_assert_error(
            "cdbpcs_msp_xml_not_from_latest_mpp", ["mock_prj_id"]
        )

        # wrong z_index
        prj = self._build_wrong_doc_testdata("", "2")
        ProjectKeywordQuery.return_value = [prj]
        self._call_and_assert_error(
            "cdbpcs_msp_xml_not_from_latest_mpp", ["mock_prj_id"]
        )

        # wrong z_index and z_nummer
        prj = self._build_wrong_doc_testdata("2", "2")
        ProjectKeywordQuery.return_value = [prj]
        self._call_and_assert_error(
            "cdbpcs_msp_xml_not_from_latest_mpp", ["mock_prj_id"]
        )

    @mock.patch.object(Project, "KeywordQuery")
    @mock.patch("cs.pcs.msp.workspace_connect.get_and_check_object")
    def test_get_project_and_xml_doc(self, get_and_check_object, ProjectKeywordQuery):
        xml_doc = mock.MagicMock(cdb_project_id="mock_prj_id", **self.params)
        get_and_check_object.return_value = xml_doc

        prj = self._build_wrong_doc_testdata("", "")
        ProjectKeywordQuery.return_value = [prj]

        a0, a1, a2 = workspace_connect._get_project_and_xml_doc(self.params)
        self.assertEqual(a0, prj)
        self.assertEqual(a1, xml_doc)
        self.assertEqual(a2, None)


@pytest.mark.unit
class CheckForLicence(unittest.TestCase):
    @mock.patch("cs.pcs.msp.workspace_connect.get_license")
    def test_check_for_licence_no_licence(self, get_license):
        get_license.return_value = True

        self.assertIsNone(workspace_connect._check_for_licence())

    @mock.patch("cs.pcs.msp.workspace_connect.get_license")
    def test_check_for_licence(self, get_license):
        get_license.return_value = False

        actual = workspace_connect._check_for_licence()
        expected = (
            None,
            None,
            ([(1, "cdbfls_nolicforfeature", ["PROJECTS_030"])], {}, []),
        )
        self.assertEqual(actual, expected)


@pytest.mark.unit
class CheckForWorspacesInstalled(unittest.TestCase):
    @mock.patch.object(workspace_connect.Package, "ByKeys", return_value=None)
    def test__check_wsm_installed_false(self, mock_ByKeys):
        self.assertFalse(workspace_connect._check_wsm_installed())
        mock_ByKeys.assert_called_once_with(name="cs.workspaces")

    @mock.patch.object(workspace_connect.Package, "ByKeys", return_value="foo_package")
    def test__check_wsm_installed_false(self, mock_ByKeys):
        self.assertTrue(workspace_connect._check_wsm_installed())
        mock_ByKeys.assert_called_once_with(name="cs.workspaces")


@pytest.mark.unit
class SaveXmlToDoc(unittest.TestCase):
    def _mock_xml_doc(self):
        mock_xml_doc = mock.MagicMock()
        mock_xml_doc.GetDescription.return_value = "mock_description"
        f1 = mock.MagicMock(
            cdbf_type="MS-Project", cdbf_primary="1", cdb_object_id="mock_obj_id"
        )
        f2 = mock.MagicMock(
            cdbf_type="XML", cdbf_primary="0", cdbf_derived_from=f1.cdb_object_id
        )
        mock_xml_doc.Files = [f1, f2]
        return mock_xml_doc

    def test_save_xml_file_to_xml_doc_no_primary_mpp(self):
        mock_xml_doc = self._mock_xml_doc()
        mock_xml_doc.Files = []

        actual = workspace_connect._save_xml_file_to_xml_doc(mock_xml_doc, "")
        expected = (
            [
                (
                    1,
                    "cdbpcs_not_exactly_one_primary_msp_file_in_document",
                    [mock_xml_doc.cdb_project_id],
                )
            ],
            {},
            [],
        )
        self.assertEqual(actual, expected)

    def test_save_xml_file_to_xml_doc_many_primary_mpp(self):
        mock_xml_doc = self._mock_xml_doc()
        f3 = mock.MagicMock(cdbf_type="MS-Project", cdbf_primary="1")
        mock_xml_doc.Files.append(f3)

        actual = workspace_connect._save_xml_file_to_xml_doc(mock_xml_doc, "")
        expected = (
            [
                (
                    1,
                    "cdbpcs_not_exactly_one_primary_msp_file_in_document",
                    [mock_xml_doc.cdb_project_id],
                )
            ],
            {},
            [],
        )
        self.assertEqual(actual, expected)

    def test_save_xml_file_to_xml_doc_many_xml(self):
        mock_xml_doc = self._mock_xml_doc()
        f3 = mock.MagicMock(
            cdbf_type="XML",
            cdbf_primary="0",
            cdbf_derived_from=mock_xml_doc.Files[0].cdb_object_id,
        )
        mock_xml_doc.Files.append(f3)

        actual = workspace_connect._save_xml_file_to_xml_doc(mock_xml_doc, "")
        expected = (
            [
                (
                    1,
                    "cdbpcs_multiple_xml_files_in_document",
                    [mock_xml_doc.GetDescription()],
                )
            ],
            {},
            [],
        )
        self.assertEqual(actual, expected)

    @mock.patch.object(workspace_connect.CDB_File, "NewFromFile")
    def test_save_xml_file_to_xml_doc_new(self, NewFromFile):
        mock_xml_doc = self._mock_xml_doc()
        mock_xml_doc.Files.pop()

        actual = workspace_connect._save_xml_file_to_xml_doc(mock_xml_doc, "mock_path")
        expected = None
        self.assertEqual(actual, expected)
        NewFromFile.assert_called_once_with(
            mock_xml_doc.cdb_object_id,
            "mock_path",
            False,
            additional_args={"cdbf_derived_from": "mock_obj_id"},
        )

    def test_save_xml_file_to_xml_doc_checkin(self):
        mock_xml_doc = self._mock_xml_doc()

        actual = workspace_connect._save_xml_file_to_xml_doc(mock_xml_doc, "mock_path")
        expected = None
        self.assertEqual(actual, expected)
        mock_xml_doc.Files[1].checkin_file.assert_called_once_with("mock_path")


@pytest.mark.unit
class GetSyncStatus(unittest.TestCase):
    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_get_sync_status_no_licence(self, _check_for_licence):
        _check_for_licence.return_value = "error"

        actual = workspace_connect.cs_pcs_get_sync_status("params", "files")
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    def test_cs_pcs_get_sync_status_no_msp_edition(self, _check_for_licence):
        _check_for_licence.return_value = None

        with self.assertRaises(ValueError):
            workspace_connect.cs_pcs_get_sync_status({}, "files")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    def test_cs_pcs_get_sync_status_no_doc_keys(
        self, _get_project_and_xml_doc, _check_for_licence
    ):
        _check_for_licence.return_value = None
        _get_project_and_xml_doc.return_value = "prj", "xml", "error"

        actual = workspace_connect.cs_pcs_get_sync_status({}, "files")
        self.assertEqual(actual, "error")

    @mock.patch("cs.pcs.msp.workspace_connect._check_for_licence")
    @mock.patch("cs.pcs.msp.workspace_connect._get_project_and_xml_doc")
    @mock.patch("cs.pcs.msp.workspace_connect._get_list_of_synced_project_tasks")
    def test_cs_pcs_get_sync_status(
        self,
        _get_list_of_synced_project_tasks,
        _get_project_and_xml_doc,
        _check_for_licence,
    ):
        _check_for_licence.return_value = None
        _get_project_and_xml_doc.return_value = "prj", "xml", None
        _get_list_of_synced_project_tasks.return_value = (
            "ALL",
            "STARTED",
            "DISCARDED",
            "ADDED",
        )
        actual = workspace_connect.cs_pcs_get_sync_status({}, "files")
        self.assertEqual(
            actual,
            (
                [],
                {
                    "TASK_GUIDS_ALL": "ALL",
                    "TASK_GUIDS_STARTED": "STARTED",
                    "TASK_GUIDS_DISCARDED": "DISCARDED",
                    "TASK_WERE_ADDED": "ADDED",
                },
                [],
            ),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "project,exp_task_guids,exp_task_guids_started,exp_task_guids_discarded,exp_tasks_were_added",
    [
        # no tasks - no task guids
        (
            mock.MagicMock(Tasks=[]),  # project
            [],  # all task guids
            [],  # started task guids
            [],  # discarded task guids
            False,  # task were added
        ),
        # only discarded tasks
        (
            mock.MagicMock(
                Tasks=[
                    mock.MagicMock(msp_guid="foo", status=180, percent_complet=0),
                    mock.MagicMock(msp_guid="bar", status=180, percent_complet=0),
                ]
            ),  # project
            ["foo", "bar"],  # all task guids
            [],  # started task guids
            ["foo", "bar"],  # discarded task guids
            False,  # task were added
        ),
        # only started tasks
        (
            mock.MagicMock(
                Tasks=[
                    mock.MagicMock(msp_guid="foo", status=50, percent_complet=10),
                    mock.MagicMock(msp_guid="bar", status=50, percent_complet=10),
                ]
            ),  # project
            ["foo", "bar"],  # all task guids
            ["foo", "bar"],  # started task guids
            [],  # discarded task guids
            False,  # task were added
        ),
        # only added tasks
        (
            mock.MagicMock(
                Tasks=[
                    mock.MagicMock(msp_guid="", status=50, percent_complet=0),
                    mock.MagicMock(msp_guid=None, status=50, percent_complet=0),
                ]
            ),  # project
            [],  # all task guids
            [],  # started task guids
            [],  # discarded task guids
            True,  # task were added
        ),
        # combination - discarded, started, added
        (
            mock.MagicMock(
                Tasks=[
                    mock.MagicMock(msp_guid="foo", status=180, percent_complet=0),
                    mock.MagicMock(msp_guid="bar", status=50, percent_complet=10),
                    mock.MagicMock(msp_guid="bam", status=180, percent_complet=10),
                    mock.MagicMock(msp_guid="", status=180, percent_complet=10),
                ]
            ),  # project
            ["foo", "bar", "bam"],  # all task guids
            ["bar", "bam"],  # started task guids
            ["foo", "bam"],  # discarded task guids
            True,  # task were added
        ),
    ],
)
def test__get_list_of_synced_project_taks(
    project,
    exp_task_guids,
    exp_task_guids_started,
    exp_task_guids_discarded,
    exp_tasks_were_added,
):
    (
        actual_task_guids,
        actual_task_guids_started,
        actual_task_guids_discarded,
        actual_tasks_were_added,
    ) = workspace_connect._get_list_of_synced_project_tasks(project)
    assert actual_task_guids == exp_task_guids
    assert actual_task_guids_started == exp_task_guids_started
    assert actual_task_guids_discarded == exp_task_guids_discarded
    assert actual_tasks_were_added == exp_tasks_were_added


if __name__ == "__main__":
    unittest.main()
