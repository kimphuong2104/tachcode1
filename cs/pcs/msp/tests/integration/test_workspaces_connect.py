#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import testcase

from cs.pcs.msp.tests.integration.test_exports import MSPExport, assertXMLEqual
from cs.pcs.msp.workspace_connect import (
    _check_wsm_installed,
    cs_pcs_get_active_buttons,
    cs_pcs_get_sync_status,
    cs_pcs_xml_from_ce,
)

# Test for MSPImport is part of test_imports.py


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPExport(MSPExport):
    def test_export_project_for_workspaces(self):
        # call cs_pcs_xml_from_ce as WSD would via sig and verify
        # that the XML file exists at the returned location and has the correct
        # content
        # Note: We skip resetting msp_guids here to avoid needing a seperate file to compare against
        # Note: Only works if cs.workspaces is installed, skipped otherwise
        self.PROJECT_ID = "Ptest.msp.small"
        parameters = {
            "z_nummer": "Dtest.msp.small",
            "z_index": "",
            "reset_ids": "False",
        }

        # if cs.workspaces is installed do the full test
        if _check_wsm_installed():
            result = cs_pcs_xml_from_ce(parameters, [])

            result_path = result[2][0].local_fname
            # verify xml exist at given path and has correct content
            assertXMLEqual(result_path, self.expected_path)
        else:
            # else skip the test - testcase already covered by unit test
            self.skipTest("Skip Test - cs.workspaces is not installed")


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class ProjectLinkGetActiveButtons(testcase.RollbackTestCase):
    def test_get_active_buttons_for_workspace(self):
        # call cs_pcs_get_active_buttons as WSD would via sig and verifiy that
        # the returned list of active buttons has the correct content
        # Note: Only works if cs.workspaces is installed, skipped otherwise
        self.PROJECT_ID = "Ptest.msp.small"
        parameters = {
            "z_nummer": "Dtest.msp.small",
            "z_index": "",
            "msp_edition": "pjEditionProfessional",
        }

        # if cs.workspaces is installed do the full test
        if _check_wsm_installed():
            result = cs_pcs_get_active_buttons(parameters, [])

            assert result[1]["ACTIVE_PROJECTLINK_BUTTONS"] == [
                "PUBLISH_PROJECT",
                "UPDATE_PROJECT",
                "UPDATE_ATTRIBUTES",
            ]
        else:
            # else skip the test - testcase already covered by unit test
            self.skipTest("Skip Test - cs.workspaces is not installed")


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class ProjectLinkGetSyncStatus(testcase.RollbackTestCase):
    def test_get_sync_status_for_workspaces(self):
        # call cs_pcs_get_active_buttons as WSD would via sig and verifiy that
        # the returned list of msp synced tasks has the correct content
        # Note: Only works if cs.workspaces is installed, skipped otherwise
        self.PROJECT_ID = "Ptest.msp.small"
        parameters = {
            "z_nummer": "Dtest.msp.small",
            "z_index": "",
        }

        # if cs.workspaces is installed do the full test
        if _check_wsm_installed():
            result = cs_pcs_get_sync_status(parameters, [])

            # Ptest.msp.small has 24 tasks - all 24 synced (0 added), 1 discared and 4 started
            assert len(result[1]["TASK_GUIDS_ALL"]) == 24
            assert len(result[1]["TASK_GUIDS_STARTED"]) == 4
            assert len(result[1]["TASK_GUIDS_DISCARDED"]) == 1
            assert result[1]["TASK_WERE_ADDED"] is False
        else:
            # else skip the test - testcase already covered by unit test
            self.skipTest("Skip Test - cs.workspaces is not installed")


if __name__ == "__main__":
    unittest.main()
