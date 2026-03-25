#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
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
__revision__ = "$Id: module_content_resolver.py 198563 2019-07-12 07:11:33Z tst $"

from cdb.comparch import resolver_nodes
from cdb.objects import ClassRegistry


class PageConfigNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_page_config"

    def getReferenced(self):
        return ["Label",
                "Owners"]


class PluginNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_plugin"

    def getReferenced(self):
        return ["Configurations"]


class PluginConfigNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_plugin_config"

    def getReferenced(self):
        return ["Libraries"]


class DialogHookConfigNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_dialog_hook"

    def getReferenced(self):
        return ["HookFunction"]


class OutletDescriptionNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_outlet_description"

    def getReferenced(self):
        return ["Definitions"]


class OutletDefinitionNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_outlet_definition"

    def getReferenced(self):
        return ["Positions"]


class OutletPositionNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_outlet_position"

    def getReferenced(self):
        return ["Owners", "Child", "Label", "Icon"]


class OutletPositionOwnerNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_outlet_position_owner"


class OutletChildNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_outlet_child"

    def getReferenced(self):
        return ["Label", "Icon"]


class DisplayContextNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_display_context"

    def getReferenced(self):
        return ["Configurations"]


class DisplayConfigurationNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_display_configuration"


class SearchFavouriteNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_search_favourites"

    @classmethod
    def getUnassignedObjects(cls):
        pycls = ClassRegistry().find(cls.__type_mapping__, generate=True)
        return pycls.Query("(cdb_module_id='' or cdb_module_id is null) "
                           "and subject_type = 'Common Role'")

    @classmethod
    def should_preset_module_id(cls, obj):
        return (obj.subject_type == "Common Role")

    def getReferenced(self):
        return ["Params"]


class SearchFavouriteParamNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_search_fav_params"

    @classmethod
    def getUnassignedObjects(cls):
        """
        We do not want the search params to be undefined. The warning for
        a unassigned favourite is enough.
        """
        return []


class DashboardNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_dashboard"

    @classmethod
    def getUnassignedObjects(cls):
        pycls = ClassRegistry().find(cls.__type_mapping__, generate=True)
        return pycls.Query("(cdb_module_id='' or cdb_module_id is null) "
                           "and subject_type = 'Common Role'")

    def getReferenced(self):
        return ["Items"]


class DashboardItemNode(resolver_nodes.Node):
    __type_mapping__ = "csweb_dashboard_item"

    @classmethod
    def getUnassignedObjects(cls):
        return []

def register():
    node_impl = [DialogHookConfigNode,
                 PageConfigNode,
                 PluginNode,
                 PluginConfigNode,
                 OutletDescriptionNode,
                 OutletDefinitionNode,
                 OutletPositionNode,
                 OutletPositionOwnerNode,
                 OutletChildNode,
                 DisplayContextNode,
                 DisplayConfigurationNode,
                 SearchFavouriteNode,
                 SearchFavouriteParamNode,
                 DashboardNode,
                 DashboardItemNode]

    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
