#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Tests for the REST API to the Enterprise Search
"""

from __future__ import absolute_import
__revision__ = "$Id$"
__revision__ = "$Id: test_api.py 205766 2020-01-08 10:16:33Z yzh $"

import time
import unittest
import logging
import os
import requests

from cdb import testcase
from cdbwrapc import getSysKey


WAIT_INTERVALS = [0.1, 0.5, 1.0, 5.0]


def repeat(fn):
    if not fn():
        for i in WAIT_INTERVALS:
            time.sleep(i)
            if fn():
                break


class TestESAPI(unittest.TestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    port = 0
    host = ""
    proto = ""

    @classmethod
    def setUpClass(cls):
        logging.getLogger("requests").setLevel(logging.WARNING)
        svc = testcase.require_service("cdb.uberserver.services.apache.Apache")
        cls.host = svc.hostname
        cls.port = svc.port

        if int(getSysKey('ssl_mode')) > 0:
            cls.proto = "https"
        else:
            cls.proto = "http"
        cls.session = requests.session()
        cls.session.auth = ('caddok', os.environ.get('INSTANCE_ADMINPWD', ''))
        logged_in = cls.session.get(cls.get_qualified_url(""))
        if logged_in.status_code == 401:
            raise unittest.SkipTest("Login failed: caddok without password")

    @classmethod
    def tearDownClass(cls):
        cls.session.get(cls.get_qualified_url("server/__quit__"))
        cls.session.close()

    @classmethod
    def get_qualified_url(cls, path):
        return "%s://%s:%d/%s" % (cls.proto, cls.host, cls.port, path)

    def test_basic(self):
        search_url = self.get_qualified_url("internal/search/fulltext?searchtext=xxxxx")
        response = self.session.get(search_url)

        def _test():
            if response.status_code == 500:
                return False

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(list(data), ['result'])
            result = data['result']
            self.assertIn('dateFilters', result)
            self.assertIn('facetInfo', result)
            self.assertIn('result', result)
            self.assertIn('settings', result)
            self.assertDictContainsSubset({u'classname': [u''],
                                        u'df': u'',
                                        u'obsolete': 0,
                                        u'page': 1,
                                        u'query': u'xxxxx',
                                        u'sortDate': 0},
                                        result['settings'])
            return True

        repeat(_test)

    def test_paging(self):
        try:
            from cs.documents import Document
            if len(Document.Query("titel like 'Sitz%'")) < 20:
                raise unittest.SkipTest("Skipped because not enough data for 2 pages")
        except ImportError:
            raise unittest.SkipTest("Skipped because the test needs cs.documents")
        search_url = self.get_qualified_url("internal/search/fulltext?searchtext=sitz*")
        response = self.session.get(search_url)
        self.assertEqual(response.status_code, 200)
        settings = response.json()['result']['settings']
        next_page_url = "%s&r=%s&page=%s" % (search_url, settings['r'], settings['page'])
        response = self.session.get(next_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset({u'classname': [u''],
                                       u'df': u'',
                                       u'obsolete': 0,
                                       u'page': 2,
                                       u'query': u'sitz*',
                                       u'r': settings['r'],
                                       u'sortDate': 0},
                                      response.json()['result']['settings'])
