#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.structure.plugins.util import resolve_including_timeframe
from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin


class PoolAssignmentPlugin(TimeSchedulePlugin):
    table_name = "cdbpcs_pool_assignment"
    table_view = "cdbpcs_pool_assignment_v"
    classname = "cdbpcs_pool_assignment"
    allow_pinning = True
    catalog_name = "cdbpcs_resource_assignment"
    description_pattern = "{}: {}"
    description_attrs = (
        "pool_oid",
        # "pool_name",
        "resource_oid",
        # "resource_name",
    )
    required = {"pool_oid"}

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set(cls.description_attrs),
            cls.required,
        )

    @classmethod
    def GetDescription(cls, record):
        return cls.description_pattern.format(
            record["pool_name"],
            record["resource_name"],
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        return resolve_including_timeframe("pool_assign", root_oid, request)
