#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# This code is currently not used, because with the current SL of CDB (10.1.20)
# it is not possible to change the module assignment policy from "by class"
# to "by module id" (E031668).
# When the error will be fixed, this code can be used again. You just need to
# activate it in the setup.py


"""
Module module_content_resolver

This is the documentation for the module_content_resolver module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []


from cdb.comparch import resolver_nodes


class SystemTaskDefinitionNode(resolver_nodes.Node):
    __type_mapping__ = "cdbwf_system_task_definition"

    def getReferenced(self):
        return ["Parameters"]


class ParameterDefinitionNode(resolver_nodes.Node):
    __type_mapping__ = "cdbwf_parameter_definition"


def register():
    # register node implementations for module content resolver
    node_impl = [SystemTaskDefinitionNode, ParameterDefinitionNode]

    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
