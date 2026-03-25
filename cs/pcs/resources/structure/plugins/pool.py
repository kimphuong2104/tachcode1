#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.structure.plugins.util import resolve_including_timeframe
from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin


class PoolPlugin(TimeSchedulePlugin):
    table_name = "cdbpcs_resource_pool"
    classname = "cdbpcs_resource_pool"
    catalog_name = "pcs_resource_pool"
    allow_pinning = True
    description_pattern = "{}"
    description_attrs = ("name",)
    required = {"parent_oid"}

    @classmethod
    def GetDescription(cls, record):
        return record.name

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set(cls.description_attrs),
            cls.required,
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        return resolve_including_timeframe("pool", root_oid, request)
