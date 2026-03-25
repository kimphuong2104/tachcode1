#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Module module_content_resolver

This is the documentation for the module_content_resolver module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []


from cdb.comparch import resolver_nodes


class QCDefinitionNode(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_definition"
    __opt_installer_entry_point__ = True

    def getReferenced(self):
        return ["Associations"]


class QCClassAssociationNode(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_def2class"

    def getReferenced(self):
        result = ["ORule",
                  "ComputationRule"]
        from cs.metrics.qualitycharacteristics import KKZClassAssociation, OKZClassAssociation
        if isinstance(self.obj, OKZClassAssociation):
            result.append("ChildConfigurations")
            result.append("ParentConfigurations")
        elif isinstance(self.obj, KKZClassAssociation):
            result.append("GroupingAttributes")
        else:
            raise NotImplementedError("{} is not supported as QCClassAssociationNode".format(str(type(self.obj))))
        return result


class QCComputationRuleNode(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_computation_rule"


class QCUnitTypeNode(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_unit_type"
    __opt_installer_entry_point__ = True


class QCUnitNode(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_unit"
    __opt_installer_entry_point__ = True


class QCParents(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_parents"

    def getReferenced(self):
        return ["ORule"]


class QCChildren(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_children"

    def getReferenced(self):
        return ["ORule"]


class QCGroupingAttribute(resolver_nodes.Node):
    __type_mapping__ = "cdbqc_grouping_attribute"


def register():
    # register node implementations for module content resolver
    node_impl = [QCDefinitionNode, QCClassAssociationNode, QCComputationRuleNode, QCUnitTypeNode,
                 QCUnitNode, QCParents, QCChildren, QCGroupingAttribute]

    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
