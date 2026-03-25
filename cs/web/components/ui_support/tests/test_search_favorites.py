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
from cdb.testcase import RollbackTestCase
from cs.web.components.ui_support.search_favourites import SearchFavourite
from cs.web.components.ui_support.search_favourites import SearchFavouriteParam
from cs.web.components.ui_support.search_favourites import _LAST_OBJECTS_FAVOURITE_ID


class TestSearchFavorite(RollbackTestCase):

    def setUp(self):
        """
        Set up the test case
        """
        super(TestSearchFavorite, self).setUp()

        SearchFavouriteParam().Query().Delete()
        SearchFavourite.Query().Delete()

        def createFavourite(name, classname, params):
            sf = SearchFavourite.Create(
                name_de=name, classname=classname,
                subject_type='Person', subject_id='caddok')
            for p in params:
                SearchFavouriteParam.Create(
                    favourite_id=sf.cdb_object_id, attribute=p[0],
                    value=p[1], postion=p[2])
            return sf

        self.createdFavouriteRF = createFavourite(
            'a rest_foo search favourite', 'rest_foo',
            [['attr_rf', 'value_rf', 10], ['attr_rf1', 'value_rf1', 20]])

        self.createdFavouriteRF1 = createFavourite(
            'a second rest_foo search favourite', 'rest_foo',
            [['a1', 'v1', 10]])

        self.createdFavouriteP = createFavourite(
            'a cdb_person search favourite', 'cdb_person',
            [['test_attr_p', 'test_value_p', 10]])

        app = Root()
        self.c = Client(app)
        self.maxDiff = None

    def test_search_favorite_classname(self):
        response = self.c.get(u'/internal/uisupport/search_favourites/by_class/rest_foo')
        self.assertEqual(response.json['classDesignation'], 'REST-Test')
        self.assertEqual(response.json['classname'], 'rest_foo')

    def test_search_favorite_params(self):
        response = self.c.get(u'/internal/uisupport/search_favourites/by_class/rest_foo')
        found = False
        for fav in response.json['favourites']:
            if fav['cdb_object_id'] == self.createdFavouriteRF.cdb_object_id:
                self.assertEqual(
                    fav['params'],
                    [
                        {u'attribute': u'attr_rf', u'value': u'value_rf'},
                        {u'attribute': u'attr_rf1', u'value': u'value_rf1'}
                    ])
                found = True
        self.assertTrue(found, 'SearchFavourite with given params not found: %s' % self.createdFavouriteRF.name_de)

    def test_search_favorite_special_entries(self):
        response = self.c.get(u'/internal/uisupport/search_favourites/by_class/rest_complex')
        foundHistory = False
        for fav in response.json['favourites']:
            if fav['cdb_object_id'] == _LAST_OBJECTS_FAVOURITE_ID:
                foundHistory = True
        self.assertTrue(foundHistory, 'History-SearchFavourite not found')

    def test_search_favorite_all(self):
        foundRF = False
        foundRF1 = False
        foundP = False
        response = self.c.get(u'/internal/uisupport/search_favourites')
        for favClass in response.json:
            if favClass['classname'] == 'rest_foo':
                self.assertEqual(len(favClass['favourites']), 4,
                                 'Four rest_foo search favourite expected, found %s' % len(favClass['favourites']))
                for fav in favClass['favourites']:
                    if fav['cdb_object_id'] == self.createdFavouriteRF.cdb_object_id:
                        foundRF = len(fav['params']) == 2
                    if fav['cdb_object_id'] == self.createdFavouriteRF1.cdb_object_id:
                        foundRF1 = len(fav['params']) == 1
            if favClass['classname'] == 'cdb_person':
                self.assertEqual(len(favClass['favourites']), 3,
                                 'Three cdb_search search favourite expected, found %s' % len(favClass['favourites']))
                for fav in favClass['favourites']:
                    if fav['cdb_object_id'] == self.createdFavouriteP.cdb_object_id:
                        foundP = len(fav['params']) == 1
        self.assertTrue(foundRF and foundRF1, 'New created rest_foo SearchFavourite not found \n%s' % response.json)
        self.assertTrue(foundP, 'New created cdb_person SearchFavourite not found \n%s' % response.json)
