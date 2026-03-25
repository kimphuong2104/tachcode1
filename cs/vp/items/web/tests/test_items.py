# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
import urllib.parse

from webtest import TestApp as Client

from cs.platform.web.root import Root

from cdb import sig
from cdb.testcase import RollbackTestCase, error_logging_disabled

from cs.vp.items import Item

class TestObject(RollbackTestCase):

    def setUp(self):
        """
        Set up the test case
        """
        super(TestObject, self).setUp()

        self.created = Item.Create(
            teilenummer="000009",
            t_index="",
            benennung="test",
            t_kategorie="Einzelteil",
            gebrauchsstand="aktiv",
            t_bereich="IT",
            mengeneinheit="Stk",
            cdb_obsolete=0,
            item_maturity=10,
            cdb_status_txt='Draft',
            st_gewicht=0.0,
            cdb_objektart='part_ERP',
            materialnr_erp="000009",
            status=0,
            cdb_mpersno="caddok",
            cdb_mdate="05.12.2014 16:49:58",
            cdb_cpersno="caddok",
            cdb_cdate="05.12.2014 16:49:58"
        )

        app = Root()
        self.c = Client(app)

    def test_item_GET(self):
        oid = self.created.teilenummer
        response = self.c.get('/api/v1/collection/part/%s' % oid)
        self.assertEqual(response.json["benennung"], "test")

    def test_item_GET_invalid(self):
        oid = "invalid"
        with error_logging_disabled():
            response = self.c.get('/api/v1/collection/part/%s' % oid,
                                  expect_errors=True)
        self.assertEqual(response.status_code, 404)

    def test_versions_GET(self):
        oid = self.created.teilenummer
        response = self.c.get('/api/v1/collection/part/%s/versions' % oid)
        self.assertEqual(len(response.json), 1)
        self.assertEqual(list(map(urllib.parse.unquote, response.json[0]["relship:versions"])),
                         ['http://localhost/api/v1/collection/part/000009@'])
        self.assertEqual(response.json[0]["cdb_status_txt"], "Draft")
        link = response.json[0]["@id"]
        response = self.c.get(link)
        self.assertEqual(response.json["t_index"], "")

    def test_versions_PUT(self):
        try:
            @sig.connect(Item, "index", "post")
            def index_post(_, ctx):
                self.assertTrue(ctx.uses_restapi)

            oid = self.created.teilenummer
            response = self.c.put_json('/api/v1/collection/part/%s/versions' % oid, {})
            self.assertEqual(len(response.json), 2)
            self.assertEqual(list(map(urllib.parse.unquote, response.json[0]["relship:versions"])),
                             ['http://localhost/api/v1/collection/part/000009@',
                              'http://localhost/api/v1/collection/part/000009@a'])
            link = response.json[1]["@id"]
            response = self.c.get(link)
            self.assertEqual(response.json["t_index"], "a")
        finally:
            sig.disconnect(index_post)

    def test_versions_PUT_content(self):
        try:
            @sig.connect(Item, "index", "post")
            def index_post(_, ctx):
                self.assertTrue(ctx.uses_restapi)
            json = {
                'cdb::argument.t_index_neu': 'b'
            }
            oid = self.created.teilenummer
            response = self.c.put_json('/api/v1/collection/part/%s/versions' % oid, json)
            self.assertEqual(len(response.json), 2)
            self.assertEqual(list(map(urllib.parse.unquote, response.json[0]["relship:versions"])),
                             ['http://localhost/api/v1/collection/part/000009@',
                              'http://localhost/api/v1/collection/part/000009@b'])
            link = response.json[1]["@id"]
            response = self.c.get(link)
            self.assertEqual(response.json["t_index"], "b")
        finally:
            sig.disconnect(index_post)

    def test_class_GET(self):
        oid = self.created.teilenummer
        response = self.c.get('/api/v1/collection/part/%s/class' % oid)
        # FIXME: create and use sample classification
        self.assertEqual(response.json['class'], None)

    def test_classify_PUT(self):
        raise unittest.SkipTest("This test needs to setup the required item class'")
        oid = self.created.teilenummer
        json = {
            "teile_stamm.sachgruppe": "Schraube",
            "teile_stamm.sachgruppe/schraube/schraube.l": "2.34",
            "teile_stamm.sachgruppe/schraube/schraube.dm": "4.56"
        }
        response = self.c.put_json('/api/v1/collection/part/%s/class' % oid, json)
        self.assertEqual(response.json['class'], "Schraube")
        self.assertEqual(response.json['properties']['dm']['value'], 4.56)
        self.assertEqual(response.json['properties']['l']['value'], 2.34)
