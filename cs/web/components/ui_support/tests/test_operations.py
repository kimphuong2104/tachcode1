#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

import unittest
from datetime import datetime
from webtest import TestApp as Client
from cs.platform.web.root import Root
from cdb import testcase


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

        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestOperations, self).setUp()

        self.created = Foo.Create(
            name="cmdf",
            nr=1,
            nr_fl=2.4
        )

        app = Root()
        self.c = Client(app)

    def test_object_operation_CDBModify(self):
        oid = self.created.ID()
        json = {
            u'object_navigation_id': oid,
            u'values': {
                u'name': u'othercmd',
                u'nr': 66,
                u'nr_fl': 3.1415,
                u'dt': '12.01.2010 23:44:12'
            }
        }
        with testcase.error_logging_disabled():
            self.c.post_json('/internal/uisupport/operation/class/rest_foo/CDB_Modify/run', json)
            response = self.c.get(u'/api/v1/collection/foo/%s' % oid)

        self.created.Reload()
        self.assertEqual(response.json['name'], 'othercmd')
        self.assertEqual(response.json['nr'], 66)
        self.assertAlmostEqual(response.json['nr_fl'], 3.1415)
        self.assertEqual(self.created.dt, datetime(2010, 1, 12, 23, 44, 12, 0))
        self.assertEqual(response.json['dt'], '2010-01-12T23:44:12',
                         response.json['dt'])

    def test_object_operation_CDBModify_Nulldate(self):
        # All None values are excluded from operation arguments,
        # because None or empty date values cause an exception during operation
        # execution
        oid = self.created.ID()
        json = {
            u'object_navigation_id': oid,
            u'values': {
                u'name': u'othercmd',
                u'nr': 66,
                u'nr_fl': 3.1415,
                u'dt': None
            }
        }
        with testcase.error_logging_disabled():
            self.c.post_json('/internal/uisupport/operation/class/rest_foo/CDB_Modify/run', json)
            response = self.c.get(u'/api/v1/collection/foo/%s' % oid)

        self.created.Reload()
        self.assertEqual(response.json['name'], 'othercmd')
        self.assertEqual(response.json['nr'], 66)
        self.assertAlmostEqual(response.json['nr_fl'], 3.1415)
        self.assertIsNone(self.created.dt)
        self.assertIsNone(response.json.get('dt'))

    def test_object_operation_CDBModify_Noargs(self):
        oid = self.created.ID()
        json = {
            u'object_navigation_id': oid,
            u'values': {
            }
        }
        with testcase.error_logging_disabled():
            self.c.post_json('/internal/uisupport/operation/class/rest_foo/CDB_Modify/run', json)
            response = self.c.get(u'/api/v1/collection/foo/%s' % oid)

        self.created.Reload()
        self.assertEqual(response.json['name'], 'cmdf')
        self.assertEqual(response.json['nr'], 1)
        self.assertEqual(response.json['nr_fl'], 2.4)

    def test_object_operation_CDBSearch(self):
        json = {
            u'object_navigation_id': None,
            u'values': {
            }
        }
        with testcase.error_logging_disabled():
            response = self.c.post_json(
                '/internal/uisupport/operation/class/rest_foo/CDB_Search/run', json)

        self.assertTrue("rows" in response.json, "response should have rows")
        self.assertTrue("icon_url" in response.json, "response should have icon_url")
        self.assertTrue("label" in response.json, "response should have label")
        self.assertTrue("tabledef" in response.json, "response should have tabledef")
        self.assertTrue("help_url" in response.json, "response should have help_url")

        self.assertEqual(len(response.json["rows"]), 1, "Should have one result row")
        row = response.json["rows"][0]
        self.assertEqual(row["columns"][0],
                         "cmdf",
                         "Result row should have the right `name` value")

    def test_object_operation_not_available(self):
        """
        Test if the operation is rejected if there is no
        Web UI configuration.
        """
        json = {
            u'object_navigation_id': None,
            u'values': {
            }
        }
        with testcase.error_logging_disabled():
            # No operation at all
            response = self.c.post_json('/internal/uisupport/operation/class/rest_sub_no_python/CDB_Search/run',
                                        json, status=403)
            # Operation with disabled configuration
            response = self.c.post_json('/internal/uisupport/operation/class/rest_sub_no_python/CDB_Create/run',
                                        json, status=403)


class TestMultiObjectOperations(testcase.RollbackTestCase):

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

        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestMultiObjectOperations, self).setUp()

        self.created = [Foo.Create(name="cmdf", nr=1, nr_fl=2.4),
                        Foo.Create(name="cmdf2", nr=2, nr_fl=4.8)]

        app = Root()
        self.c = Client(app)

    def test_object_operation_CDBDelete(self):
        oids = [o.ID() for o in self.created]
        json = {
            u'object_navigation_id': oids,
            u'values': {
            }
        }
        with testcase.error_logging_disabled():
            self.c.post_json('/internal/uisupport/operation/class/rest_foo/CDB_Delete/run', json)

        for o in self.created:
            o.Reload()
            self.assertTrue(o.IsDeleted())


class TestRelshipOperations(testcase.RollbackTestCase):
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestRelshipOperations, self).setUp()
        self.c = Client(Root())
        self.parent = RelshipParent.Create(id=42, name="parent")
        self.child = RelshipChild.Create(child_id=4242, parent_id=self.parent.id, txt="child")

    def test_run_info(self):
        url = "/internal/uisupport/operation/relship/rest_rel_parent/%d/DD_Children/CDB_ShowObject/run" % self.parent.id
        json = {
            u'object_navigation_id': u'%d' % self.child.child_id
        }
        response = self.c.post_json(url, json).json
        self.assertIn("ui_link", response)
        self.assertEqual(response["ui_link"], "http://localhost/info/rel_child/4242")

    def test_run_create(self):
        """
        Test that the primary key of the relship parent is inserted into the operation attributes
        """
        url = "/internal/uisupport/operation/relship/rest_rel_parent/%d/DD_Children/CDB_Create/run" % self.parent.id
        json = {
            u'values': {
                u'child_id': 8765,
                u'txt': 'bla'
            }
        }
        response = self.c.post_json(url, json).json
        self.assertIn("ui_link", response)
        self.assertEqual(response["ui_link"], "http://localhost/info/rel_child/8765")
        self.assertIn("object", response)
        self.assertEqual(response["object"]["child_id"], 8765)
        self.assertEqual(response["object"]["parent_id"], 42)


class TestFileUploadOperations(testcase.RollbackTestCase):

    def setUp(self):
        try:
            from cs.restgenericfixture import Foo
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFileUploadOperations, self).setUp()

        self.created = Foo.Create(
            name="FileUploadTest",
            nr=1,
            nr_fl=2.4)

        app = Root()
        self.c = Client(app)

    def test_file_upload(self):
        oid = self.created.ID()
        import json
        from cs.web.components.ui_support.utils import WebFileUploadHelper
        with testcase.error_logging_disabled():
            response = self.c.post('/internal/uisupport/operation/class/rest_foo/CDB_Modify/run',
                                   upload_files=[
                                       (u'json', u'blob', json.dumps({"object_navigation_id": [oid], "values": {}}).encode("utf-8")),
                                       (u'file0', u'stringio', b'test stringio'),
                                       (u'file1', u'streamio', b'test streamio' * 100)])

        stream0 = WebFileUploadHelper.get_stream("stringio")
        self.assertEqual(stream0.readline(), b'test stringio', "String-io file different")
        stream1 = WebFileUploadHelper.get_stream("streamio")
        self.assertEqual(stream1.readline(), b'test streamio' * 100, "Stream-io file different")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
