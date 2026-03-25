# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import six
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from datetime import datetime, timedelta
from six.moves.urllib.parse import urlsplit, parse_qs
from webtest import TestApp as Client

from cdb.testcase import RollbackTestCase, error_logging_disabled
from cdb.objects.org import Person
from cs.platform.web.root import Root
from cs.web.components.history import get_history_entries_per_class
from cs.web.components.history.model import HistoryItem
from cs.web.components.history import get_history_size


class TestHistory(RollbackTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    def setUp(self):
        """
        Set up the test case
        """
        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestHistory, self).setUp()

        HistoryItem.Query().Delete()

        self.created = HistoryItem.Create(
            cdb_cpersno='caddok',
            rest_name='person',
            rest_id='caddok',
            cdb_cdate=datetime(2011, 1, 1),
            ref_object_id='123'
        )

        # this is not tested directly, but we don't expect it
        # to show up in our tests.
        self.created_notmine = HistoryItem.Create(
            cdb_cpersno='someone_else',
            rest_name='person',
            rest_id='caddok',
            cdb_cdate=datetime(2011, 1, 1),
            ref_object_id='456'
        )

        app = Root()
        self.c = Client(app)

    def test_history_collection_GET(self):
        caddok = Person.ByKeys('caddok')
        response = self.c.get(u'/internal/history')
        query_dict = parse_qs(urlsplit(response.json['@id'])[3], True)
        self.assertEqual(query_dict['amount'][0], u'%s' % get_history_size())
        self.assertEqual(
            response.json['history_items'],
            [
                {
                    u'classname': u'angestellter',
                    u'frontend_url': u'http://localhost/info/person/caddok',
                    u'title': caddok.GetDescription(),
                    u'icon_url': caddok.GetObjectIcon(),
                    u'ref_object_id': u'123',
                    u'rootclass': u'cdb_person',
                    u'timestamp': u'2011-01-01T00:00:00',
                    u'rest_url': u'http://localhost/api/v1/collection/person/caddok'
                }
            ]

        )

    def test_history_collection_POST(self):
        caddok = Person.ByKeys('caddok')
        params = {
            'classname': 'cdb_person',
            'rest_id': 'caddok'
        }
        self.c.post_json(u'/internal/history', params)
        response = self.c.get(u'/internal/history', params)
        json = response.json['history_items'][0].copy()
        json.pop('timestamp')
        self.assertEqual(
            json,
            {
                u'classname': u'angestellter',
                u'frontend_url': u'http://localhost/info/person/caddok',
                u'title': caddok.GetDescription(),
                u'icon_url': caddok.GetObjectIcon(),
                u'ref_object_id': u'123',
                u'rest_url': u'http://localhost/api/v1/collection/person/caddok',
                u'rootclass': u'cdb_person',
            }
        )

    def test_history_collection_GET_by_classname(self):
        response = self.c.get(u'/internal/history?classname=cdb_person')
        self.assertEqual(len(response.json['history_items']), 1)
        response = self.c.get(u'/internal/history?classname=cdb_organization')
        self.assertEqual(len(response.json['history_items']), 0)

    def test_history_collection_amount(self):
        response = self.c.get(u'/internal/history?classname=cdb_person&amount=9999')
        # smoke test to check that amount basically doesn't crash
        self.assertEqual(len(response.json['history_items']), 1)

    def test_history_collection_max_entries(self):
        NUM_ENTRIES = get_history_entries_per_class() + 2
        # Create a lot of entries, bypassing the mechanism for keeping the number
        # per class <= get_history_entries_per_class. Attention: Don't check the number
        # of entries returned from GET, because entries for non-existing objects
        # get filterd out!
        HistoryItem.Query().Delete()
        for i in six.moves.range(NUM_ENTRIES):
            HistoryItem.Create(cdb_cpersno='caddok',
                               rest_name='person',
                               rest_id='dummy_%d' % i,
                               cdb_cdate=datetime.utcnow() - timedelta(minutes=i))
        cnt = len(HistoryItem.KeywordQuery(cdb_cpersno='caddok', rest_name='person'))
        self.assertEqual(cnt, NUM_ENTRIES)
        # post a new entry, and check that the history gets truncated, and the
        # new entry is in front
        params = {
            'classname': 'cdb_person',
            'rest_id': 'caddok'
        }
        self.c.post_json(u'/internal/history', params)
        response = self.c.get(u'/internal/history', params)
        self.assertEqual(response.json['history_items'][0]['frontend_url'],
                         u'http://localhost/info/person/caddok')
        cnt = len(HistoryItem.KeywordQuery(cdb_cpersno='caddok', rest_name='person'))
        self.assertEqual(cnt, get_history_entries_per_class())

    def test_history_as_table(self):
        response = self.c.get(u'/internal/history?classname=cdb_person&as_table')
        json = response.json
        self.assertIn('tabledef', json)

    def test_history_as_table_no_classname(self):
        with error_logging_disabled():
            response = self.c.get(u'/internal/history?as_table', status=400)
            self.assertEqual(response.status, '400 Bad Request')
