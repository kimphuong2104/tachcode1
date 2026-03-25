# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
"""
Module module_content_resolver

This is the documentation for the module_content_resolver module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id: module_content_resolver.py 132031 2015-10-05 11:44:50Z khi $"

# Exported objects
__all__ = []

from cdb.comparch import resolver_nodes


class ReqIFProfileNode(resolver_nodes.Node):
    __type_mapping__ = "cdbrqm_reqif_profile"
    __opt_installer_entry_point__ = True

    def getReferenced(self):
        return ["Entities", "AllAttributes", "RelationTypes"]


class ReqIFProfileEntityNode(resolver_nodes.Node):
    __type_mapping__ = "cdbrqm_reqif_profile_entities"
    __opt_installer_entry_point__ = False

    def getReferenced(self):
        return ["Attributes", "ClassificationClassAssignments"]


def register():
    # register node implementations for module content resolver
    node_impl = [ReqIFProfileNode, ReqIFProfileEntityNode]

    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
