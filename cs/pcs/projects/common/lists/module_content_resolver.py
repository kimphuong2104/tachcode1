#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module Content Resolver - helps cdbpkg assign module IDs based on structured
data
"""


from cdb.comparch import resolver_nodes

__all__ = []


class ListConfigurationNode(resolver_nodes.Node):
    __type_mapping__ = "cs_list_config"

    def getReferenced(self):
        return ["ListDataProviderReference"]


class ListConfig2DataProviderNode(resolver_nodes.Node):
    __type_mapping__ = "list_cfg2data_provider"

    def getReferenced(self):
        return ["ListDataProvider"]


class ListDataProviderNode(resolver_nodes.Node):
    __type_mapping__ = "cs_list_dataprovider"

    def getReferenced(self):
        return ["ListItemConfig"]


class ListItemConfigurationsNode(resolver_nodes.Node):
    __type_mapping__ = "cs_list_item_config"

    def getReferenced(self):
        return ["AllListItemConfigEntries"]


class ListItemEntriesNode(resolver_nodes.Node):
    __type_mapping__ = "cs_list_item_cfg_entry"


def register():
    # register node implementations for module content resolver
    node_impl = [
        ListConfigurationNode,
        ListConfig2DataProviderNode,
        ListDataProviderNode,
        ListItemConfigurationsNode,
        ListItemEntriesNode,
    ]

    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
