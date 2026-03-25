#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from webtest import TestApp as Client
from cdb import testcase
from cs.platform.web.root import Root


class TestOutletsAPI(testcase.PlatformTestCase):
    """
    Tests for the outlets REST API.
    """

    def setUp(self):
        """
        Set up the test case
        """
        try:
            import cs.webtest
        except RuntimeError:
            raise unittest.SkipTest("this test needs cs.webtest")
        super(TestOutletsAPI, self).setUp()

    def test_valid_url(self):
        """
        We expect the result with five libraries and one child
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/outlet/outlet_test/cswebtest_outlet_definition')
        json_data = response.json

        libaries = json_data.get("libraries")
        library_names = [r.get("library_name") for r in libaries]
        self.assertEquals(len(library_names), 5)
        self.assertTrue("cs-webtest-library" in library_names)
        self.assertTrue("cs-webtest-library2" in library_names)
        self.assertTrue("cs-webtest-library3" in library_names)
        self.assertTrue("cs-webtest-library4" in library_names)
        self.assertTrue("cs-webtest-library5" in library_names)

        children = json_data.get("children")
        self.assertTrue(len(children), 1)
        self.assertEquals(children[0].get("name"), "cs-webtest-HelloWorld")

        self.assertEquals(len(json_data.get("properties").get("__outlets")), 1)

    @testcase.without_error_logging
    def test_invalid_outlet_name(self):
        """
        We expect the result to be empty for an outlet_name that does not exist
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/outlet/rest_outlet_wrong/cswebtest_outlet_definition')
        json_data = response.json
        self.assertEquals(len(json_data.get("libraries")), 0)
        self.assertEquals(len(json_data.get("children")), 0)
        self.assertEquals(len(json_data.get("properties").get("__outlets")), 0)

    @testcase.without_error_logging
    def test_invalid_classname(self):
        """
        We expect a HTTPNotFound exception for a class_name that does not exist
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/outlet/outlet_test/wrong_class_name',
                         status=404)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
