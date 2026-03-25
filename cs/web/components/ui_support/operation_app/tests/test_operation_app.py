#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import json

from webtest import TestApp as Client

from cdb import testcase
from cs.platform.web.root import Root
from cdb.testcase import error_logging_disabled


class TestCreateApp(testcase.RollbackTestCase):
    """
    Tests for getting a started create operation (e.g. a presented form) by an URL
    """

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    def setUp(self):
        testcase.RollbackTestCase.setUp(self)
        self.client = Client(Root())

    def test_invalid_operation_raises_an_404(self):
        """ Check whether create app returns a 404 for invalid entities """
        with error_logging_disabled():
            res = self.client.get("/operation/CDB_Delete/organization", status=404)
            self.assertEqual(res.status_code, 404)

    def test_invalid_entity_raises_an_404(self):
        """ Check whether create app returns a 404 for invalid entities """
        with error_logging_disabled():
            res = self.client.get("/operation/CDB_Create/does_not_exist", status=404)
            self.assertEqual(res.status_code, 404)

    def test_valid_entity_without_params(self):
        """ Check whether create app returns all needed information to show an empty create operation form within the frontend """
        response = self.client.get("/operation/CDB_Create/organization", status=200)
        application_root_base_data = response.lxml.xpath(
            '//*[@id="application-root-base-data"]'
        )
        app_setup = {}
        if application_root_base_data:
            application_root_base_data = {
                k: v for (k, v) in application_root_base_data[0].items()
            }
            app_setup = json.loads(
                json.loads(
                    application_root_base_data.get('data-app-setup')
                )
            )
        self.assertIn("appSettings", app_setup)
        self.assertIn("currentOperation", app_setup["appSettings"])
        self.assertEqual("cdb_organization", app_setup["appSettings"]["currentOperation"].get(
            'classname', '')
        )
        self.assertEqual("CDB_Create", app_setup["appSettings"]["currentOperation"].get(
            'opname', '')
        )
        self.assertIn("currentOperationParams", app_setup["appSettings"])
        self.assertEqual({}, app_setup["appSettings"]["currentOperationParams"])

    def test_valid_entity_with_params(self):
        """ Check whether create app returns all needed information to show an pre-filled create operation form within the frontend """
        response = self.client.get(
            '/operation/CDB_Create/organization?p={"cdb_org.name":"Testname",'
            '"cdb_org_type.org_type":"Lieferant"}',
            status=200
        )
        application_root_base_data = response.lxml.xpath(
            '//*[@id="application-root-base-data"]'
        )
        app_setup = {}
        if application_root_base_data:
            application_root_base_data = {
                k: v for (k, v) in application_root_base_data[0].items()
            }
            app_setup = json.loads(
                json.loads(
                    application_root_base_data.get('data-app-setup')
                )
            )
        self.assertIn("appSettings", app_setup)
        self.assertIn("currentOperation", app_setup["appSettings"])
        self.assertEqual("cdb_organization", app_setup["appSettings"]["currentOperation"].get(
            'classname', '')
        )
        self.assertEqual("CDB_Create", app_setup["appSettings"]["currentOperation"].get(
            'opname', '')
        )
        self.assertIn("currentOperationParams", app_setup["appSettings"])
        self.assertEqual({
            "cdb_org.name": "Testname",
            "cdb_org_type.org_type": "Lieferant"
        }, app_setup["appSettings"]["currentOperationParams"])
