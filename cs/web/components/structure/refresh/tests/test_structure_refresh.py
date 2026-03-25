#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the structure refresh
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
import json

from cdb import testcase
from cdb import sqlapi
from cs.platform.web.root import Root
from webtest import TestApp as Client


class TestStructureRefresh(testcase.RollbackTestCase):

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestStructureRefresh, self).setUp()
        self.parent = RelshipParent.Create(id=1, name='parent')
        self.children = [RelshipChild.Create(parent_id=self.parent.id, child_id=1, txt="One"),
                         RelshipChild.Create(parent_id=self.parent.id, child_id=2, txt="two")]
        app = Root()
        c = Client(app)
        response = c.get(
            u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure'
            % self.parent.id)
        json_data = response.json
        self.root_node_new_label = "parent"
        self.node_1_new_label = "Child: 1: One"
        self.node_2_new_label = "Child: 2: two"
        parent = json_data['nodes'][0]
        child = parent['subnodes'][0]
        self.root_node = {
            "content": {
                "label": "",
                "rest_node_id": parent['rest_node_id'],
                "parent_node": None
            }
        }
        self.node_1 = {
            "content": {
                "label": "",
                "rest_node_id": child['subnodes'][0]['rest_node_id'],
                "parent_node": {
                    "label": "",
                    "rest_node_id": child['rest_node_id'],
                    "parent_node": {
                        "label": "",
                        "rest_node_id": parent['rest_node_id']
                    }
                }
            }
        }
        self.node_2 = {
            "content": {
                "label": "",
                "rest_node_id": child['subnodes'][1]['rest_node_id'],
                "parent_node": {
                    "label": "",
                    "rest_node_id": child['rest_node_id']
                }
            }
        }

    @testcase.without_error_logging
    def test_structure_refresh_node(self):
        """
        We expect the node to be refreshed
        """
        app = Root()
        c = Client(app)
        url = u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure' \
              u'/refresh_node' % self.parent.id
        params = json.dumps({
            "nodes": [self.node_1]
        })
        response = c.post(url, params=params)
        json_data = response.json
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        self.assertEqual(1, len(nodes))
        node = nodes[0]
        node_content = node["content"]
        self.assertTrue("icons" in node_content)
        self.assertTrue("label" in node_content)
        self.assertTrue(node_content["label"] == self.node_1_new_label)

    @testcase.without_error_logging
    def test_structure_refresh_root_node(self):
        """
        We expect the root node to be refreshed
        """
        app = Root()
        c = Client(app)
        url = u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure' \
              u'/refresh_node' % self.parent.id
        params = json.dumps({
            "nodes": [self.root_node]
        })
        response = c.post(url, params=params)
        json_data = response.json
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        self.assertEqual(1, len(nodes))
        node = nodes[0]
        node_content = node["content"]
        self.assertTrue("icons" in node_content)
        self.assertTrue("label" in node_content)
        self.assertTrue(node_content["label"] == self.root_node_new_label)

    @testcase.without_error_logging
    def test_structure_refresh_two_nodes(self):
        """
        We expect the two nodes to be refreshed
        """
        app = Root()
        c = Client(app)
        url = u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure' \
              u'/refresh_node' % self.parent.id
        params = json.dumps({
            "nodes": [self.node_1, self.node_2]
        })
        response = c.post(url, params=params)
        json_data = response.json
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        self.assertEqual(2, len(nodes))
        node_1 = nodes[0]
        node_2 = nodes[1]
        self.assertTrue("icons" in node_1["content"])
        self.assertTrue("label" in node_1["content"])
        self.assertTrue(node_1["content"]["label"] == self.node_1_new_label)
        self.assertTrue("icons" in node_2["content"])
        self.assertTrue("label" in node_2["content"])
        self.assertTrue(node_2["content"]["label"] == self.node_2_new_label)

    @testcase.without_error_logging
    def test_structure_remove_one_node(self):
        """
        We expect the node to contain the key 'remove'.
        """
        app = Root()
        c = Client(app)
        url = u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure' \
              u'/refresh_node' % self.parent.id
        sqlapi.SQLexecute("DELETE FROM rest_rel_child WHERE child_id = %d" % (
            self.children[0].child_id))
        params = json.dumps({
            "nodes": [self.node_1]
        })
        response = c.post(url, params=params)
        json_data = response.json
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        self.assertEqual(1, len(nodes))
        self.assertTrue("remove" in nodes[0])

    @testcase.without_error_logging
    def test_structure_empty_nodes(self):
        """
        We expect no nodes to be returned
        """
        app = Root()
        c = Client(app)
        url = u'http://localhost/api/v1/collection/rel_parent/%s/structure/rest_rel_structure' \
              u'/refresh_node' % self.parent.id
        params = json.dumps({
            "nodes": []
        })
        response = c.post(url, params=params)
        json_data = response.json
        self.assertTrue("nodes" in json_data)
        nodes = json_data["nodes"]
        self.assertEqual(0, len(nodes))

    @testcase.without_error_logging
    def test_wrong_structure(self):
        """
        We expect a HTTPForbidden exception for a structure that does not exist
        """
        app = Root()
        c = Client(app)
        params = json.dumps({
            "nodes": [self.node_1]
        })
        c.post(u'http://localhost/api/v1/collection/rel_parent/%s/structure'
               u'/rest_rel_structure_wrong/refresh_node' % self.parent.id,
               params=params, status=403)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
