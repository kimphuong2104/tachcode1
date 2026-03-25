# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Support to refresh structure nodes.
"""

from __future__ import absolute_import
import json

from cs.web.components.structure import StructureCache

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class StructureRefreshModel(object):
    """
    Morepath model to refresh structure nodes.
    """

    def __init__(self, root_object, structure_name):
        """
        Initializes the structure `structure_name` to be refreshed,
        starting with the specified `root_object`.
        """
        self.root_object = root_object
        self.structure_name = structure_name

    def get_refresh_information(self, nodes):
        """
        Returns a dictionary containing the updated nodes.
        """

        def _update_node_content(_node, _content):
            if _node is not None:
                if _content is not None:
                    _node['content']['label'] = _content['label']
                    _node['content']['icons'] = _content['icons']
                    return _node
                else:
                    _node['remove'] = True
                    return _node

        result = []
        for node in nodes:
            rest_structure = StructureCache().get_structure(self.structure_name,
                                                            self.root_object,
                                                            False)
            content = rest_structure.refresh_node(
                json.loads(node['content']['rest_node_id'])
            )
            refreshed_node = _update_node_content(node, content)
            if refreshed_node:
                result = result + [refreshed_node]

        return {'nodes': result}
