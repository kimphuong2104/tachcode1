#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the structre REST-API
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

from cdb import testcase
from cdb import util
from cs.platform.web.root import Root
from webtest import TestApp as Client


class TestStructure(testcase.RollbackTestCase):

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestStructure, self).setUp()
        self.parent = RelshipParent.Create(id=1, name='parent')
        self.children = [RelshipChild.Create(parent_id=self.parent.id, child_id=1, txt="One"),
                         RelshipChild.Create(parent_id=self.parent.id, child_id=2, txt="two")]

    @testcase.without_error_logging
    def test_structure_root_node(self):
        """
        Just check the values of the root node
        """
        app = Root()
        c = Client(app)
        response = c.get(u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure'
                         % self.parent.id)
        # The root node should contain a title
        json_data = response.json
        self.assertTrue("title" in json_data)
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        # We expect only the root node here
        self.assertEqual(1, len(nodes))
        node = nodes[0]
        self.assertTrue("icons" in node)
        self.assertTrue("label" in node)
        # The label has to be the object label
        self.assertEqual(self.parent.GetDescription(), node["label"])

        # Ensure we get a new root node each time we call get_root (E044613)
        # The label should change (in new versions of cs.restgenericfixture)
        self.parent.name = "New"
        response = c.get(u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure'
                         % self.parent.id)
        new_label = response.json["nodes"][0]["label"]
        self.assertEqual(self.parent.GetDescription(), new_label, "Root node seems to be cached (%s)" % new_label)

    @testcase.without_error_logging
    def test_structure_root_expand(self):
        """
        Test the expand url
        """
        app = Root()
        c = Client(app)
        response = c.get(u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure'
                         % self.parent.id)
        self.assertTrue("expand_url" in response.json["nodes"][0])
        expand_url = response.json["nodes"][0]["expand_url"]

        for clear_struct_cache in [False, True]:
            if clear_struct_cache:
                # Whitebox test - Clear the cache to check if an expand
                # url for an object works stateless
                from cs.web.components import structure
                structure.StructureCache().clear()

            expand_response = c.get(expand_url)

            nodes = expand_response.json["nodes"]
            # We expect only one folder node labeled with the ausgabe 'rest_rel_structure_folder'
            self.assertEqual(1, len(nodes))
            node = nodes[0]
            # The label has to be the object label
            self.assertEqual(util.get_label("rest_rel_structure_folder"), node["label"])

            # Either there is an url to navigate or the subnodes are part of the node
            if "expand_url" in node:
                expand_response = c.get(node["expand_url"])
                if expand_response:
                    subnodes = expand_response.json["nodes"]
            else:
                subnodes = node["subnodes"]
            self.assertEqual(len(self.children), len(subnodes))

    @testcase.without_error_logging
    def test_wrong_structure_root_node(self):
        """
        We expect a HTTPForbidden exception for a structure that does not exist
        """
        app = Root()
        c = Client(app)
        response = c.get(u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure_wrong' % self.parent.id,
                         status=403)

# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
