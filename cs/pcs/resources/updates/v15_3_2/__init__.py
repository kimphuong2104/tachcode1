#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdbwrapc import CDBClassDef


def get_classes_and_tables(base_classnames):
    """
    Generator yielding tuples (classname, table_name)
    for each classname in `base_classnames` and their subclasses
    (in any level)
    """
    for base_classname in base_classnames:
        base_class = CDBClassDef(base_classname)
        table = base_class.getPrimaryTable()
        yield base_classname, table
        for sub_classname in base_class.getSubClassNames(True):
            yield sub_classname, table


class RemoveOrphanedResourceScheduleObjects(object):
    """
    In the past, when object were deleted, that were pinned in a resource schedule,
    the reference for the object in the resource schedule content table was not
    always deleted This script removes all of these orphaned references.
    """

    __base_classes__ = [  # possible base classes for content entries
        "cdbpcs_resource_schedule",
        "cdbpcs_prj_demand",
        "cdbpcs_prj_alloc",
        "cdbpcs_resource_pool",
        "cdbpcs_pool_assignment",
        "cdb_organization",
        "cdb_person",
    ]
    __delete_pattern__ = """FROM cdbpcs_rs_content
        WHERE cdb_content_classname = '{classname}'
        AND NOT EXISTS (
            SELECT 1 FROM {table}
            WHERE {table}.cdb_object_id = cdbpcs_rs_content.content_oid
        )"""

    def run(self):
        """
        For each entry in cdbpcs_rs_content (i.e. pinned objects in resource schedules)
        it is checked if content_oid is equal to cdb_object_id in either db table
        of these classes:
        [ResourceSchedule, ResourceDemand, ResourceAssignment, ResourcePool,
        ResourcePoolAssignmentPerson, Organisation, Person]
        If not, the entry is orphaned and will be deleted.
        """
        for classname, table in get_classes_and_tables(self.__base_classes__):
            sqlapi.SQLdelete(
                self.__delete_pattern__.format(
                    classname=classname,
                    table=table,
                )
            )


pre = [RemoveOrphanedResourceScheduleObjects]
post = []
