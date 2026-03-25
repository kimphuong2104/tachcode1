# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from webtest import TestApp as Client
from cs.platform.web.root import Root
from cdb.testcase import PlatformTestCase, RollbackTestCase, without_error_logging
from cs.web.components.favorites.model import Favorite


class TestFavorite(RollbackTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    def setUp(self):
        """
        Set up the test case
        """
        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestFavorite, self).setUp()

        Favorite.Query().Delete()

        self.created = Favorite.Create(
            title='A favorite',
            frontend_url='/2',
            icon_url='/icon',
            cdb_cpersno='caddok',
            ref_object_id='')

        self.created_rest = Favorite.Create(
            title='A favorite with rest name and id',
            frontend_url='/2',
            icon_url='/icon',
            rest_name='person',
            rest_id='caddok',
            cdb_cpersno='caddok',
            ref_object_id='')

        self.created_notmine = Favorite.Create(
            title='Not my favorite',
            frontend_url='/2',
            icon_url='/icon',
            rest_name='person',
            rest_id='caddok',
            cdb_cpersno='someone_else')

        app = Root()
        self.c = Client(app)

    def test_favorite_GET_rest(self):
        oid = self.created_rest.ID()
        response = self.c.get(u'/internal/favorites/%s' % oid)
        self.assertEqual(
            response.json,
            {
                u'@id': u'http://localhost/internal/favorites/%s' % oid,
                u'classname': u'angestellter',
                u'frontend_url': u'/2',
                u'title': u'A favorite with rest name and id',
                u'icon_url': u'/icon',
                u'rest_url': u'http://localhost/api/v1/collection/person/caddok',
                u'rootclass': u'cdb_person',
                u'rest_name': u'person',
                u'ref_object_id': u''
            })

    @without_error_logging
    def test_favorite_GET_notmine(self):
        oid = self.created_notmine.ID()
        self.c.get(u'/internal/favorites/%s' % oid, status=404)

    def test_favorite_PUT(self):
        oid = self.created_rest.ID()
        json = {
            u'@id': u'http://localhost/internal/favorites/%s' % oid,
            u'title': u'Changed title'
        }
        response = self.c.put_json(u'/internal/favorites/%s' % oid, json)
        self.assertEqual(
            response.json,
            {
                u'@id': u'http://localhost/internal/favorites/%s' % oid,
                u'classname': u'angestellter',
                u'frontend_url': u'/2',
                u'title': u'Changed title',
                u'icon_url': u'/icon',
                u'rest_url': u'http://localhost/api/v1/collection/person/caddok',
                u'rootclass': u'cdb_person',
                u'rest_name': u'person',
                u'ref_object_id': u''
            })
        response = self.c.get(u'/internal/favorites/%s' % oid)
        self.assertEqual(
            response.json,
            {
                u'@id': u'http://localhost/internal/favorites/%s' % oid,
                u'classname': u'angestellter',
                u'frontend_url': u'/2',
                u'title': u'Changed title',
                u'icon_url': u'/icon',
                u'rest_url': u'http://localhost/api/v1/collection/person/caddok',
                u'rootclass': u'cdb_person',
                u'rest_name': u'person',
                u'ref_object_id': u''
            })

    def test_favorite_DELETE(self):
        oid = self.created.ID()
        response = self.c.delete(u'/internal/favorites/%s' % oid)
        self.assertEqual(
            response.json,
            {})
        oid = self.created_rest.ID()
        response = self.c.delete(u'/internal/favorites/%s' % oid)
        self.assertEqual(
            response.json,
            {})
        response = self.c.get(u'/internal/favorites')
        self.assertEqual(
            response.json,
            {
                u'@id': u'http://localhost/internal/favorites',
                u'favorites': []
            }
        )

    def test_favorite_collection_GET(self):
        oid = self.created.ID()
        oid_rest = self.created_rest.ID()
        response = self.c.get(u'/internal/favorites')
        favorite_id = 'http://localhost/internal/favorites/%s' % oid
        favorite_rest_id = 'http://localhost/internal/favorites/%s' % oid_rest
        self.assertEqual(
            response.json,
            {
                u'@id': u'http://localhost/internal/favorites',
                u'favorites': [
                    {
                        u'@id': favorite_rest_id,
                        u'classname': u'angestellter',
                        u'frontend_url': u'/2',
                        u'title': u'A favorite with rest name and id',
                        u'icon_url': u'/icon',
                        u'rest_url': u'http://localhost/api/v1/collection/person/caddok',
                        u'rootclass': u'cdb_person',
                        u'rest_name': u'person',
                        u'ref_object_id': u''
                    }
                ]
            }
        )

    def test_favorite_collection_POST(self):
        response = self.c.post_json(u'/internal/favorites', {
            'title': 'A favorite with rest name and id',
            'frontend_url': '/info/person/user.public',
            'icon_url': '/icon',
            'rest_name': 'person',
            'rest_id': 'user.public',
            'classname': 'angestellter',
            'cdb_cpersno': 'caddok',
            'ref_object_id': ''
        })
        json = response.json.copy()
        json.pop('@id')
        self.assertEqual(
            json,
            {
                u'classname': u'angestellter',
                u'frontend_url': u'/info/person/user.public',
                u'title': u'A favorite with rest name and id',
                u'icon_url': u'/icon',
                u'rest_url': u'http://localhost/api/v1/collection/person/user.public',
                u'rootclass': u'cdb_person',
                u'rest_name': u'person',
                u'ref_object_id': u''
            }
        )


class TestFavoriteNoDuplicate(PlatformTestCase):

    def setUp(self):
        super(TestFavoriteNoDuplicate, self).setUp()
        app = Root()
        self.c = Client(app)

    def tearDown(self):
        Favorite.Query().Delete()
        super(TestFavoriteNoDuplicate, self).tearDown()

    def test_favorite_collection_POST_duplicate(self):
        """Make sure an object is inserted only once as a favorite
        """
        fav_data = {
            'title': 'Duplicate',
            'frontend_url': '/info/person/user.public',
            'icon_url': '/icon',
            'rest_name': 'person',
            'rest_id': 'user.public',
            'classname': 'angestellter'
        }
        response = self.c.post_json(u'/internal/favorites', fav_data)
        fav_id = response.json.pop('@id')
        # insert the same favorite again, and check that we get back the one
        # created above
        response = self.c.post_json(u'/internal/favorites', fav_data)
        self.assertEqual(response.json.pop('@id'), fav_id)
