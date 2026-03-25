#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import mock
import pytest
from cdb import testcase, ue

from cs.pcs.msp import Project
from cs.pcs.msp.web.exports import APP
from cs.pcs.projects.tests import common


@pytest.mark.unit
class TestMSPProject(testcase.RollbackTestCase):
    def test_on_export_to_xml_now_web(self):
        """Test export to xml web"""
        ctx = mock.MagicMock(uses_webui=True)

        proj = common.generate_project(cdb_project_id="proj1")

        proj.on_export_to_xml_now(ctx)

        ctx.url.assert_called_once_with(f"/internal/{APP}/export/proj1")

    def test_on_export_to_xml_now_win(self):
        ctx = mock.MagicMock(uses_webui=False)
        ctx.dialog = {"xml_filename": "client_path"}

        XML_EXPORT_CLASS = mock.MagicMock()
        XML_EXPORT_CLASS.generate_xml_from_project.return_value = "tmp_file"

        proj = common.generate_project()
        proj.XML_EXPORT_CLASS = XML_EXPORT_CLASS

        proj.on_export_to_xml_now(ctx)

        XML_EXPORT_CLASS.generate_xml_from_project.assert_called_once_with(proj)
        ctx.upload_to_client.assert_called_once_with("tmp_file", "client_path")

    def test_on_cdbpcs_msp_import_preview_now_no_primary(self):
        mock_prj = mock.MagicMock(Project)
        mock_prj.getLastPrimaryMSPDocument.return_value = False

        with self.assertRaises(ue.Exception):
            Project.on_cdbpcs_msp_import_preview_now(mock_prj, "ctx")

    def test_on_cdbpcs_msp_import_preview_now_no_primary(self):
        mock_prj = mock.MagicMock(Project)
        mock_primary = mock.MagicMock(z_nummer="mock_nr", z_index="mock_index")
        mock_prj.getLastPrimaryMSPDocument.return_value = mock_primary
        mock_prj.cdb_project_id = "mock_prj_id"
        mock_ctx = mock.Mock()

        Project.on_cdbpcs_msp_import_preview_now(mock_prj, mock_ctx)

        url = "/cs-pcs-msp-imports-result?cdb_project_id=mock_prj_id&z_nummer=mock_nr&z_index=mock_index"
        mock_ctx.url.assert_called_once_with(url)
