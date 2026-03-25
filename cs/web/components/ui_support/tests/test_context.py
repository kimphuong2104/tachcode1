#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the context REST-API.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from cdb import testcase
from cs.platform.web.root import Root
from webtest import TestApp as Client

try:
    from cs.restgenericfixture import RelshipParent, RelshipChild
except ImportError:
    raise unittest.SkipTest("this test needs cs.restgenericfixture")


def _get_object_context(self):
    return [self, self]


class TestContextAPI(testcase.RollbackTestCase):
    """
    Tests for the context REST API.
    """

    def __init__(self, *args, **kwargs):
        super(TestContextAPI, self).__init__(*args, **kwargs)
        self.maxDiff = None

    def setUp(self):
        """
        Set up the test case
        """
        try:
            RelshipParent.GetObjectContext = _get_object_context
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestContextAPI, self).setUp()
        self.parent = RelshipParent.Create(id=1, name='parent')


    def test_valid_url(self):
        """
        We expect the result to be the same as "contextShould"
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/context/rest_rel_parent/1')
        json_data = response.json
        context_should = {
            'context': [
                {
                    'rest_link': 'http://localhost/api/v1/collection/rel_parent/1',
                    'system:description': 'parent',
                    'ui_link': 'http://localhost/info/rel_parent/1',
                    'system:icon_link': ''
                },
                {
                    'rest_link': 'http://localhost/api/v1/collection/rel_parent/1',
                    'system:description': 'parent',
                    'ui_link': 'http://localhost/info/rel_parent/1',
                    'system:icon_link': ''
                }
            ]
        }
        self.assertEqual(json_data, context_should)


    @testcase.without_error_logging
    def test_invalid_classname(self):
        """
        We expect a HTTPForbidden exception for a classname that does not exist
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/context/rest_context_wrong/1',
                         status=403)


    @testcase.without_error_logging
    def test_invalid_id(self):
        """
        We expect a HTTPForbidden exception for an id that does not exist
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/context/rest_rel_parent/5',
                         status=403)


    def test_missing_function_getobjectcontext(self):
        """
        We expect the result to be an array with only one element, which is equal to "contextShould"
        """
        c = Client(Root())
        try:
            del RelshipParent.GetObjectContext
        except Exception as e:
            print(e)
            raise unittest.SkipTest("deleting function is not working")
        response = c.get('/internal/uisupport/context/rest_rel_parent/1')
        context_should = {
            'context': [
                {
                    'rest_link': 'http://localhost/api/v1/collection/rel_parent/1',
                    'system:description': 'parent',
                    'ui_link': 'http://localhost/info/rel_parent/1',
                    'system:icon_link': ''
                }
            ]
        }
        json_data = response.json
        self.assertEqual(json_data, context_should)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
