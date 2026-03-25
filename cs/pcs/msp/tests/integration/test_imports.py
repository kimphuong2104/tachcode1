#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import unittest

import mock
import pytest
from cdb import testcase
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cs.documents import Document

from cs.pcs.msp.workspace_connect import cs_pcs_xml_to_ce
from cs.pcs.projects.tests import common


def generate_msp_doc(**args):
    kwargs = {
        "titel": "fooMSPDoc",
        "z_nummer": "fooMSPDoc",
        "z_categ1": "145",  # Projektdokumentation
        "z_categ2": "181",  # Projektplan
    }
    kwargs.update(**args)
    return operation("CDB_Create", Document, **kwargs)


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPImport(testcase.RollbackTestCase):
    PROJECT_ID = "import_project"

    @property
    def expected_path_base(self):
        return os.path.join(
            os.path.dirname(__file__),
            "test_data",
            f"{self.PROJECT_ID}",
        )

    @property
    def expected_xml_path(self):
        return f"{self.expected_path_base}.xml"

    @property
    def expected_mpp_path(self):
        return f"{self.expected_path_base}.mpp"

    def test_import_project_for_workspaces(self):
        # call cs_pcs_xml_to_ce as WSD would via sig and verify
        # that the xml exists at the project's document

        # Setup Test Data
        # create document with primary .mpp file
        doc = generate_msp_doc(**{"cdb_project_id": self.PROJECT_ID})
        CDB_File.NewFromFile(
            doc.cdb_object_id,
            self.expected_mpp_path,
            primary=True,
            additional_args={"cdbf_type": "MS-Project"},
        )
        # create project
        kwargs = {
            "cdb_project_id": self.PROJECT_ID,
            "msp_active": True,
            "msp_z_nummer": doc.z_nummer,
        }
        prj = common.generate_project(**kwargs)

        parameters = {"z_nummer": doc.z_nummer, "z_index": ""}
        # Note: Mock RemoteFileObject instead of creating dependency to cs.workspaces
        mock_remote_file_obj = mock.MagicMock(local_fname=self.expected_xml_path)
        result = cs_pcs_xml_to_ce(parameters, [mock_remote_file_obj])

        assert result == ([], {}, [])

        # Verify only one Document exist at the project with .mpp and .xml file
        assert len(prj.Documents) == 1
        prj_doc = prj.Documents[0]
        assert (
            prj_doc.cdb_project_id == doc.cdb_project_id
            and prj_doc.z_nummer == doc.z_nummer
            and prj_doc.z_index == doc.z_index
        )
        assert len(prj_doc.Files) == 2
        msp_file = prj_doc.Files[0]
        assert msp_file.cdbf_type == "MS-Project"
        xml_file = prj_doc.Files[1]
        assert xml_file.cdbf_type == "XML"


if __name__ == "__main__":
    unittest.main()
