# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import json

from webtest import TestApp as Client

from cdb import testcase

from cs.platform.web.root import Root

from cs.documents import Document

from cs.vp.items import Item

from cs.threed.hoops.tests import utils


class TestSearch(testcase.PlatformTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSearch, cls).setUpClass()

        utils.install_testdata()

    def setUp(self):
        self.root_part = Item.ByKeys(teilenummer='000061', t_index='')
        self.root_doc = Document.ByKeys(z_nummer='000061-1', z_index='')
        self.client = Client(Root())

        super(TestSearch, self).setUp()

    def _get_internal_url(self, context, view_name, param=None):
        if param:
            return '/internal/cs.threed.hoops.web.tree/search/%s/%s?%s' % (context.cdb_object_id, view_name, param)
        return '/internal/cs.threed.hoops.web.tree/search/%s/%s' % (context.cdb_object_id, view_name)  

    def test_get_unreleased_parts(self):
        url = self._get_internal_url(self.root_part, 'unreleased_parts')
        response = self.client.post(url, json.dumps({}))

        self.assertTrue('objects' in response.json)
        self.assertEqual(len(response.json['objects']), 5)

        draft_status = None
        for status_result in response.json['objects']:
            if status_result['statusName'] == 'Entwurf':
                draft_status = status_result
        self.assertIsNotNone(draft_status)
        self.assertEqual(len(draft_status['tableResults']), 21)

    def test_search_parts_by_text(self):
        search_string = 'condition=30'
        url = self._get_internal_url(self.root_part, 'text', search_string)
        response = self.client.post(url, json.dumps({}))

        self.assertTrue('tableResults' in response.json)
        self.assertEqual(len(response.json['tableResults']), 4)

    def test_search_documents_by_text(self):
        search_string = 'condition=neigung'
        url = self._get_internal_url(self.root_doc, 'text', search_string)
        response = self.client.post(url, json.dumps({}))

        self.assertTrue('paths' in response.json)
        self.assertEqual(len(response.json['paths']), 9)