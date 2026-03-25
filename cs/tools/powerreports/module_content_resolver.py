#!/usr/bin/env python
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module module_content_resolver

This is the documentation for the module_content_resolver module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []

from cdb.comparch import constants, resolver_nodes
from cdb.objects import ClassRegistry

PowerReports = constants.ContentDomain("PowerReports", "", "reports")


class XMLReportBaseNode(resolver_nodes.Node):
    __domain__ = PowerReports


class XMLReportNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_report"
    __opt_installer_entry_point__ = True

    def getReferenced(self):
        return [
            "Masks",
            "XMLSource",
            "ParametersForPublic",
            "GrantsToRoles",
            "Templates",
        ]


class XMLReportParameterNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_report_arg"

    @classmethod
    def getUnassignedObjects(cls):
        pycls = ClassRegistry().find(cls.__type_mapping__, generate=True)
        return pycls.Query(
            "(cdb_module_id='' or cdb_module_id is null) and persno = 'public'"
        )

    @classmethod
    def should_preset_module_id(cls, obj):
        return obj.persno == "public"


class XMLProviderParameterNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_provider_arg"


class XMLDataProviderNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_dataprovider"

    def getReferenced(self):
        return ["GrantsToRoles", "Parameters"]


class XMLReportGrantNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_report_grant"

    @classmethod
    def getUnassignedObjects(cls):
        pycls = ClassRegistry().find(cls.__type_mapping__, generate=True)
        return pycls.Query(
            "(cdb_module_id='' or cdb_module_id is null) "
            "and subject_type = 'Common Role'"
        )

    @classmethod
    def should_preset_module_id(cls, obj):
        return obj.subject_type == "Common Role"


class XMLProviderGrantNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_prov_grant"

    @classmethod
    def getUnassignedObjects(cls):
        pycls = ClassRegistry().find(cls.__type_mapping__, generate=True)
        return pycls.Query(
            "(cdb_module_id='' or cdb_module_id is null) "
            "and subject_type = 'Common Role'"
        )

    @classmethod
    def should_preset_module_id(cls, obj):
        return obj.subject_type == "Common Role"


class XMLSourceNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_source"
    __opt_installer_entry_point__ = True

    def getReferenced(self):
        return ["DataProviders"]


class XMLReportTemplateNode(XMLReportBaseNode):
    __type_mapping__ = "cdbxml_report_tmpl"


def register():
    # register content domain
    constants.ContentDomains.register_domain(PowerReports)

    # register node implementations for module content resolver
    node_impl = [
        XMLReportNode,
        XMLReportParameterNode,
        XMLProviderParameterNode,
        XMLDataProviderNode,
        XMLReportGrantNode,
        XMLProviderGrantNode,
        XMLSourceNode,
        XMLReportTemplateNode,
    ]
    for impl in node_impl:
        resolver_nodes.register_resolver_node(impl)
