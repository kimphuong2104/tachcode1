#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module Content Resolver - helps cdbpkg assign module IDs based on structured
data
"""

from cdb.comparch.resolver_nodes import Node, register_resolver_node

__all__ = [
    "DashboardDefaultNode",
]


class DashboardDefaultNode(Node):
    __type_mapping__ = "cs_objdashboard_default"

    def getReferenced(self):
        return ["ConfigEntries"]


def register():
    for _ in __all__:
        try:
            register_resolver_node(DashboardDefaultNode)
        except TypeError:
            pass
