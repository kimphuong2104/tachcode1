# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import json

from webtest import TestApp as Client

from cdb import testcase

from cs.platform.web.root import Root

from cs.vp.items import Item
from cs.documents import Document


class TestInternalPreview(testcase.PlatformTestCase):
    def setUp(self):
        super(TestInternalPreview, self).setUp()

        self.client = Client(Root())
        self.item = Item.ByKeys(teilenummer="000061", t_index="")

    @classmethod
    def setUpClass(cls):
        super(TestInternalPreview, cls).setUpClass()

        from cs.threed.hoops.tests.utils import install_testdata
        install_testdata()

    def test_get_document(self):
        """ The API returns the CAD-document for a given part """
        url = "/internal/threed_preview/get_document"
        response = self.client.post(url, json.dumps({
            "cdb_object_id": self.item.cdb_object_id
        }))

        self.assertEqual(200, response.status_int)

        doc = Document.ByKeys(cdb_object_id=response.json).cdb_object_id
        self.assertTrue(doc is not None, "The response returned an invalid document")

        
