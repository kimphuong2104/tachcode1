#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import testcase
from cdb.platform.uberserver import Services
from cs.workflow.updates.v15_3_0_13 import UpdateWFServices


def setup_module():
    testcase.run_level_setup()


class UpdateV15_3_0_13_TestCase(testcase.RollbackTestCase):
    def _UpdateWFServices(self, init_args, expected_result):
        wf_server = "cs.workflow.services.WFServer"

        def get_wf_svcs():
            return Services.KeywordQuery(svcname=wf_server)

        get_wf_svcs().Update(arguments=init_args)

        UpdateWFServices().run()

        for svc in get_wf_svcs():
            self.assertEqual(svc.arguments, expected_result)

    def test_UpdateWFServices(self):
        self._UpdateWFServices(
            "{'--user': 'caddok'}",
            "--svcuser cs.workflow.svcuser")
        self._UpdateWFServices(
            "{'--user': 'caddok', '--svcuser': 'existing_user'}",
            "--svcuser existing_user")
        self._UpdateWFServices(
            "--svcuser existing_user",
            "--svcuser existing_user")
        self._UpdateWFServices("test", "test")
        self._UpdateWFServices(None, None)
