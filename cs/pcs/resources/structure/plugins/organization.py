#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.structure.plugins.util import resolve_including_timeframe
from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin


class OrganizationPlugin(TimeSchedulePlugin):
    table_name = "cdb_org"
    table_view = "cdb_organization_v"
    classname = "cdb_organization"
    catalog_name = "cdb_organization"
    description_pattern = "{}"
    description_attrs = ("name",)

    @classmethod
    def GetDescription(cls, record):
        return record.name

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set(cls.description_attrs),
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        return resolve_including_timeframe("organization", root_oid, request)
