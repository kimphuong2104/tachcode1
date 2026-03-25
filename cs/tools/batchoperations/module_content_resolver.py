#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


from __future__ import absolute_import
__revision__ = "$Id$"


# Exported objects
__all__ = []

from cdb.comparch import resolver_nodes
from cdb.comparch import constants

BatchOperations = constants.ContentDomain("BatchOperations", "", "batch_ops")


class BatchOperationBaseNode(resolver_nodes.Node):
    __domain__ = BatchOperations


class TypeDefinitionNode(BatchOperationBaseNode):
    __type_mapping__ = "cdbbop_typedef"
    __opt_installer_entry_point__ = True

    def getReferenced(self):
        return ["Operations"]


class OperationDefinitionNode(BatchOperationBaseNode):
    __type_mapping__ = "cdbbop_opdef"
    __opt_installer_entry_point__ = False


def register():
    # register content domain
    constants.ContentDomains.register_domain(BatchOperations)

    # register node implementations for module content resolver
    node_impl = [TypeDefinitionNode, OperationDefinitionNode]
    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
