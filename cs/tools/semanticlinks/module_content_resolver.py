#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module module_content_resolver

This is the documentation for the module_content_resolver module.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = ["LinkGraphCfgNode", "LinkMatrixCfgNode",
           "LinkMatrixRelationshipNode", "SemanticLinkTypeNode"]

from cdb.comparch import resolver_nodes


class LinkGraphCfgNode(resolver_nodes.Node):
    __type_mapping__ = "cdb_link_graph_cfg"


class LinkMatrixCfgNode(resolver_nodes.Node):
    __type_mapping__ = "cdb_link_matrix_cfg"

    def getReferenced(self):
        return ["RelationshipsConfigs"]


class LinkMatrixRelationshipNode(resolver_nodes.Node):
    __type_mapping__ = "cdb_link_matrix_rs"


class SemanticLinkTypeNode(resolver_nodes.Node):
    __type_mapping__ = "cdb_semantic_link_type"
    __opt_installer_entry_point__ = True


def register():
    # register node implementations for module content resolver
    node_impl = [LinkGraphCfgNode, LinkMatrixCfgNode,
                 LinkMatrixRelationshipNode, SemanticLinkTypeNode]
    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
