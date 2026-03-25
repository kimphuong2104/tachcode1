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
from cs.web.components.ui_support.object_search import SearchModel


class TestObjectSearch(RollbackTestCase):

    def setUp(self):
        """
        Set up the test case
        """
        super(TestObjectSearch, self).setUp()

        app = Root()
        self.c = Client(app)

    def _getResponseEntry(self, response, classname, key):
        for entry in response.json['classes']:
            if entry['classname'] == classname:
                return entry[key]
        return None

    def test_objectsearch(self):
        response = self.c.get(u'/internal/uisupport/object_search_allowed_classes')
        self.assertEqual(self._getResponseEntry(response, 'cdb_person', 'rest'), 'person')
        self.assertEqual(self._getResponseEntry(response, 'angestellter', 'rest'), 'person')
        self.assertIn('angestellter', self._getResponseEntry(response, 'cdb_person', 'subClasses'))

    def test_objectsearch_exclude_class(self):
        response = self.c.get(u'/internal/uisupport/object_search_allowed_classes', {'exclude_classes': 'angestellter'})
        self.assertEqual(self._getResponseEntry(response, 'cdb_person', 'rest'), 'person')
        self.assertEqual(self._getResponseEntry(response, 'angestellter', 'rest'), None)
        self.assertNotIn('angestellter', self._getResponseEntry(response, 'cdb_person', 'subClasses'))

    def test_objectsearch_exclude_classes(self):
        response = self.c.get(u'/internal/uisupport/object_search_allowed_classes', {'exclude_classes': 'angestellter,cdb_person'})
        self.assertEqual(self._getResponseEntry(response, 'cdb_person', 'rest'), None)
        self.assertEqual(self._getResponseEntry(response, 'angestellter', 'rest'), None)

    def test_objectsearch_SearchModel(self):
        indexed_classes = SearchModel._get_indexed_classnames()
        self.assertIn('angestellter', indexed_classes)
        self.assertIn('cdb_person', indexed_classes)
        self.assertIn('cdb_organization', indexed_classes)
