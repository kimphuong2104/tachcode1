#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.structure.plugins.util import resolve_including_timeframe
from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin


class PersonPlugin(TimeSchedulePlugin):
    table_name = "angestellter"
    table_view = "cdb_person_v"
    classname = "cdb_person"
    catalog_name = "cdbpcs_angest_sbrows"
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
        return resolve_including_timeframe("person", root_oid, request)
