#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for retrieving operation info using
REST-API Calls
"""

from __future__ import absolute_import

from cdb import testcase, sqlapi
from cs.platform.web.root import Root
import unittest

from webtest import TestApp as Client
from cs.webtest import RestReferer, RestRefererNM, RestRefererNMLink, RestReferenceChild


class TestOperations(testcase.RollbackTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    def setUp(self):
        """
        Set up the test case
        """
        try:
            from cs.restgenericfixture import Foo
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        self.c = Client(Root())

        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestOperations, self).setUp()

    def test_opinfo_for_activated_op(self):
        """
        Retrieve information for an operation that is fully available
        in Web-UI
        """
        response = self.c.get('/internal/uisupport/operation/class/rest_foo/CDB_Search')
        json = response.json
        for attr in ["submit_url", "icon", "form_url", "label", "tooltip"]:
            self.assertTrue(attr in json,
                            "Failed to retrieve '%s' from opinfo" % (attr))
            self.assertTrue(json[attr],
                            "Attr %s should contain a value" % (attr))
        for attr, value in [("activation_mode", 0),
                            ("opname", "CDB_Search"),
                            ("presentation_id", "editor"),
                            ("essential", False),
                            ("classname", "rest_foo")]:
            self.assertTrue(attr in json,
                            "Failed to retrieve '%s' from opinfo" % (attr))
            self.assertEqual(json[attr], value)

    def test_opinfo_for_webui_deactivated_op(self):
        """
        Retrieve information for an operation that is generally available but
        cannot be used with form based operations (disabled using
        Web-UI-Operation configuration.
        """
        try:
            from cs.webtest import OpActivation
        except ImportError:
            raise unittest.SkipTest("this test needs cs.webtest")

        response = self.c.get('/internal/uisupport/operation/class/cswebtest_op_activation/CDB_ShowObject')
        json = response.json
        for attr, value in [("submit_url", False),
                            ("icon", True),
                            ("form_url", False),
                            ("label", True),
                            ("presentation_id", False),
                            ("tooltip", True)]:
            self.assertTrue(attr in json,
                            "Failed to retrieve '%s' from opinfo" % (attr))
            if value:
                self.assertTrue(json[attr],
                                "Attr %s should contain a value" % (attr))
            else:
                self.assertFalse(json[attr],
                                 "Attr %s should not contain a value" % (attr))

        for attr, value in [("activation_mode", 2),
                            ("opname", "CDB_ShowObject"),
                            ("essential", False),
                            ("classname", "cswebtest_op_activation")]:
            self.assertTrue(attr in json,
                            "Failed to retrieve '%s' from opinfo" % (attr))
            self.assertEqual(json[attr], value)

    def test_opinfo_for_op_the_user_cannot_access(self):
        """
        Retrieve information for an operation that is not
        available for the user. We expect 404 (HTTPNotFound)
        """
        # Unknown class
        with testcase.error_logging_disabled():
            self.c.get('/internal/uisupport/operation/class/unknown_class/CDB_Create',
                       status=404)

        # Unknown operation
        with testcase.error_logging_disabled():
            self.c.get('/internal/uisupport/operation/class/rest_foo/unknown',
                       status=404)

    def test_opinfo_for_class(self):
        """
        Retrieve information for all operations of the class.
        """
        response = self.c.get('/internal/uisupport/operation/class/rest_complex/')
        json = response.json
        self.assertTrue(isinstance(json, list),
                        "Result should be a list")
        # We expect at least CDB_ShowObject
        self.assertTrue(json)
        for op in json:
            op_url = "/internal/uisupport/operation/class/rest_complex/%s" % (op["opname"])
            self.assertEqual(op,
                             self.c.get(op_url).json)


class TestRelshipOperations(testcase.RollbackTestCase):
    """
    Test that the form & operation links returned for relship contexts point
    to the correct URLs
    """
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestRelshipOperations, self).setUp()
        sqlapi.SQLupdate("cdb_operations SET offer_in_web_ui=1  WHERE classname='cdb_global_subj_base' AND name='CDB_SelectAndAssign'")
        self.c = Client(Root())
        self.parent = RelshipParent.Create(id=42, name="parent")
        self.testuser = 'caddok'

    def test_opinfo(self):
        response = self.c.get('/internal/uisupport/operation/relship/rest_rel_parent/42/DD_Children').json
        parent_ops = response["reference_opinfo"][1]
        for opname in ['CDB_ShowObject', 'CDB_Create']:
            ops = [op for op in parent_ops if op['opname'] == opname]
            self.assertEqual(len(ops), 1)
            self.assertEqual(ops[0]['form_url'],
                             'http://localhost/internal/uisupport/form/operation/relship/rest_rel_parent/42/DD_Children/%s/%s' % (opname, ops[0]['classname']))
            self.assertEqual(ops[0]['submit_url'],
                             'http://localhost/internal/uisupport/operation/relship/rest_rel_parent/42/DD_Children/%s/run' % opname)

    def test_opinfo_link_for_select_and_assign(self):
        response = self.c.get(
            '/internal/uisupport/operation/relship/angestellter/{testuser}/RoleAssignmentGeneralRoles'.format(
                testuser=self.testuser
            )
        ).json
        link_ops = response["link_opinfo"][1]
        for opname in ['CDB_SelectAndAssign']:
            ops = [op for op in link_ops if op['opname'] == opname]
            self.assertEqual(len(ops), 1)
            self.assertIn('catalog_url', ops[0])
            catalog_response = self.c.get(ops[0]['catalog_url'])
            self.assertIn('catalog', catalog_response.json)
            catalog = catalog_response.json['catalog']
            for k, v in {
                'itemsURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/items",
                'selectURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/selected_values?parent_classname=angestellter&parent_keys={testuser}&relship=RoleAssignmentGeneralRoles".format(testuser=self.testuser),
                'label': "",
                'valueCheckURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/valueCheck",
                'queryFormURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/query_form",
                'catalogTableURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/tabular_with_values?allow_multi_select=true",
                'typeAheadURL': "http://localhost/internal/uisupport/catalog/cdb_global_role/typeAhead"
            }.items():
                self.assertIn(k, catalog)
                self.assertEqual(v, catalog[k])

    def test_opinfo_for_single_op(self):
        response = self.c.get('/internal/uisupport/operation/relship/reference/rest_rel_parent/42/DD_Children/CDB_ShowObject').json
        self.assertEqual(response['form_url'],
                         'http://localhost/internal/uisupport/form/operation/relship/rest_rel_parent/42/DD_Children/CDB_ShowObject/%s' % response['classname'])
        self.assertEqual(response['submit_url'],
                         'http://localhost/internal/uisupport/operation/relship/rest_rel_parent/42/DD_Children/CDB_ShowObject/run')


RELSHIP_OPINFO_URL_PATTERN = \
    "/internal/uisupport/operation/relship" \
    "/%(referer_class)s/%(rest_keys)s/%(relship_name)s"


RELSHIP_OPINFO_URL_PATTERN_TARGET = \
    "/internal/uisupport/operation/relship" \
    "/%(referer_class)s/%(rest_keys)s/%(relship_name)s?target_classname=%(reference_class)s"


class TestRelshipSubclassing(testcase.RollbackTestCase):
    def setUp(self):
        try:
            from cs.restgenericfixture import Complex
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestRelshipSubclassing, self).setUp()
        self.c = Client(Root())

    def test_create_child_of_abc(self):
        """
        Request CDB_Create on subclass of abstract base class
        and try to get form for it.
        """
        url = RELSHIP_OPINFO_URL_PATTERN % {
            "referer_class": "cdb_class",
            "rest_keys": "cdb_person",
            "relship_name": "Attribute",
        }
        response = self.c.get(url).json
        op = next(op for op in response["reference_opinfo"][1]
                  if op["opname"] == "CDB_Create" and op["classname"] == "cdbdd_char_field")
        response = self.c.get(op["form_url"]).json
        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "cdbdd_char_field")


class TestRequestAndRunNMOp(testcase.RollbackTestCase):
    def setUp(self):
        try:
            from cs.restgenericfixture import Complex
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestRequestAndRunNMOp, self).setUp()
        self.c = Client(Root())
        self.referer = RestRefererNM.Create()
        self.reference = RestReferenceChild.Create()
        self.link = RestRefererNMLink.Create(
            referer_id=self.referer.cdb_object_id,
            reference_id=self.reference.cdb_object_id,
        )

    def test_remove_link(self):
        """
        Request CDB_Delete on link class and try to get form for it.
        """
        url = RELSHIP_OPINFO_URL_PATTERN_TARGET % {
            "referer_class": "rest_referer_nm",
            "rest_keys": self.referer.cdb_object_id,
            "relship_name": "RestReferer2RestReference",
            "reference_class": "rest_reference_child",
        }
        response = self.c.get(url).json
        op = next(op for op in response["link_opinfo"][1]
                  if op["opname"] == "CDB_Delete$RelshipFromReference")
        response = self.c.post_json(
            op["form_url"],
            dict(object_navigation_id=[self.reference.cdb_object_id])
        ).json
        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "rest_referer_nm_link")

        # Execute operation
        response = self.c.post_json(op['submit_url'], dict(
            object_navigation_id=[self.reference.cdb_object_id],
            operation_state=response['operation_state'],
            values=response['values']
        )).json


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
