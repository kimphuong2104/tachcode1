#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Test for Relship metadata API
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import pkg_resources
import unittest
from webtest import TestApp as Client
from cs.platform.web.root import Root
from cdb import testcase


class TestRelships(testcase.RollbackTestCase):

    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        self.c = Client(Root())

        # NEVER!!! raise after initializing the transaction context of
        # RollbackTestCase
        super(TestRelships, self).setUp()

    def test_1_n(self):
        response = self.c.get('/api/v1/class/rest_rel_parent/relships')
        json = response.json
        self.assertEqual(json, {u'DD_Children': {u'hide': False,
                                                 u'name': u'rest_rel_parent2child',
                                                 u'icon_url': u'',
                                                 u'is_one_on_one': False,
                                                 u'label': u'Children',
                                                 u'pos': 10,
                                                 u'reference_classname': u'rest_rel_child',
                                                 u'link_classname': u'rest_rel_child',
                                                 u'show_in_mask': True,
                                                 u'available_in_ui': True}})

    def test_1_1(self):
        response = self.c.get('/api/v1/class/rest_rel_child/relships')
        json = response.json
        self.assertEqual(json, {u'DD_Parent': {u'hide': False,
                                               u'name': u'rest_rel_child2parent',
                                               u'icon_url': u'',
                                               u'is_one_on_one': True,
                                               u'label': u'Parent',
                                               u'pos': 10,
                                               u'reference_classname': u'rest_rel_parent',
                                               u'link_classname': u'rest_rel_child',
                                               u'show_in_mask': True,
                                               u'available_in_ui': True}})

    def test_n_m(self):
        response = self.c.get('/api/v1/class/fixture_nm_parent/relships')
        json = response.json
        self.assertEqual(sorted(json.keys()),
                         ['Children', 'ChildrenMultiLink', 'ChildrenRO', 'FolderContent'])

        self.assertEqual(json['Children'], {u'hide': False,
                                            u'name': u'fixture_nm_aggregation_deep',
                                            u'icon_url': u'',
                                            u'is_one_on_one': False,
                                            u'label': u'Aggregierte Objekte',
                                            u'pos': 20,
                                            u'reference_classname': u'fixture_nm_target',
                                            u'link_classname': u'fixture_nm_link_class',
                                            u'show_in_mask': True,
                                            u'available_in_ui': True})
        self.assertEqual(json['ChildrenMultiLink'], {u'hide': False,
                                            u'name': u'fixture_nm_readomultilink',
                                            u'icon_url': u'',
                                            u'is_one_on_one': False,
                                            u'label': u'NM-Multilink',
                                            u'pos': 10,
                                            u'reference_classname': u'fixture_nm_target',
                                            u'link_classname': u'fixture_nm_multilink_class',
                                            u'show_in_mask': True,
                                            u'available_in_ui': True})
        self.assertEqual(json['FolderContent'], {u'hide': False,
                                                 u'name': u'fixture_nm_folder',
                                                 u'icon_url': u'',
                                                 u'is_one_on_one': False,
                                                 u'label': u'Ordnerinhalt',
                                                 u'pos': 30,
                                                 u'reference_classname': u'cdbfolder_content',
                                                 u'link_classname': u'cdbfolder_content',
                                                 u'show_in_mask': True,
                                                 u'available_in_ui': False})
        self.assertEqual(json['ChildrenRO'], {u'hide': False,
                                              u'name': u'fixture_nm_readonly',
                                              u'icon_url': u'',
                                              u'is_one_on_one': False,
                                              u'label': u'Readonly NM',
                                              u'pos': 40,
                                              u'reference_classname': u'fixture_nm_target',
                                              u'link_classname': u'fixture_nm_link_class',
                                              u'show_in_mask': True,
                                              u'available_in_ui': True})
