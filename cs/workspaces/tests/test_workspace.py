#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from cdb import cdbuuid, ElementsError
from cdb import constants
from cdb.objects.cdb_file import cdb_file_base
from cdb.objects.operations import operation, system_args
from cdb.testcase import RollbackTestCase

from cs.workspaces import Workspace, WsDocuments


class Test_Workspace(RollbackTestCase):
    def setUp(self):
        RollbackTestCase.setUp(self)
        # GIVEN: A workspace exists.
        z_nummer = "TestWorkspace"
        random = cdbuuid.create_uuid()
        z_nummer_random = "%s%s" % (z_nummer, random[:5])
        self.ws = Workspace.Create(
            z_nummer=z_nummer_random, z_index="", titel="TestWorkspace"
        )

    def tearDown(self):
        RollbackTestCase.tearDown(self)

    def test_deleteWorkspaceWithTeamspaceContent(self):
        # GIVEN: The workspace has Teamspace contents
        wsDocId = cdbuuid.create_uuid()
        WsDocuments._Create(
            cdb_object_id=wsDocId,
            ws_object_id=self.ws.cdb_object_id,
            doc_object_id="",
            create_object_id=wsDocId,
            cdb_lock="caddok",
        )

        # WHEN: I delete the workspace and it does contain Teamspace contents
        with self.assertRaises(ElementsError):
            # Message box should prevent to delete the workspace immediately
            operation(constants.kOperationDelete, self.ws)

        # THEN: The workspace should not be deleted immediately
        ws = Workspace.ByKeys(self.ws.z_nummer, self.ws.z_index)
        assert ws is not None

        # WHEN: I delete the workspace and click on the yes button
        operation(
            constants.kOperationDelete,
            self.ws,
            system_args(question_workspace_has_teamspace_content=1),
        )

        # THEN: The workspace should not be deleted immediately
        ws = Workspace.ByKeys(self.ws.z_nummer, self.ws.z_index)
        assert ws is None

        wsDocs = WsDocuments.Query("ws_object_id='%s'" % wsDocId)
        assert not wsDocs

        wsFiles = cdb_file_base.Query("cdbf_object_id='%s'" % wsDocId)
        assert not wsFiles

    def test_deleteWorkspaceWithoutTeamspaceContent(self):
        # WHEN: I delete the workspace and it does not contain Teamspace contents
        operation(constants.kOperationDelete, self.ws)

        # THEN: The workspace should be deleted immediately
        ws = Workspace.ByKeys(self.ws.z_nummer, self.ws.z_index)
        assert ws is None


if __name__ == "__main__":
    import nose
    import sys

    nose.runmodule(argv=sys.argv[:1])
