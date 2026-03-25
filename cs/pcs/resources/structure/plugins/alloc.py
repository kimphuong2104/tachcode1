#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.projects.project_structure.util import resolve_query
from cs.pcs.resources.structure.plugins.ctes import (
    get_query_pattern,
    load_query_pattern,
)
from cs.pcs.timeschedule.web.plugins import TimeSchedulePlugin


class AllocationPlugin(TimeSchedulePlugin):
    table_name = "cdbpcs_prj_alloc"
    table_view = "cdbpcs_prj_alloc_v"
    classname = "cdbpcs_prj_alloc"
    catalog_name = "cdbpcs_alloc"
    olc_attr = "<see GetObjectKind>"
    task_id = "task_id"
    description_pattern = "{} h | {} | {}"
    description_attrs = (
        "hours",
        "pool_oid",
        "resource_oid",
    )
    subject_id_attr = "task_subject_id"
    subject_type_attr = "task_subject_type"

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set([cls.task_id]),
            set(cls.description_attrs),
        )

    @classmethod
    def GetObjectKind(cls, record):
        """
        This class neither has a dedicated object kind field
        nor a class hierarchy, so it's always the class name
        """
        return cls.classname

    @classmethod
    def GetDescription(cls, record):
        return cls.description_pattern.format(
            record["hours"],
            record["joined_pool_name"],
            record["joined_resource_name"],
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        query_pattern = get_query_pattern("alloc", load_query_pattern)
        query_str = query_pattern.format(oid=root_oid)
        return resolve_query(query_str)
