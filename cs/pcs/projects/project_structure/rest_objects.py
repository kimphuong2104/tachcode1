# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Utilities for working with REST objects.

These are mostly redundant with implementations found in cs.web and the
platform, but are optimized for performance in batch mode.

This means that while implementation in cs.web and the platform usually only
work with ``cdb.objects.Object`` objects, these ones are designed to work on
``cdb.sqlapi.Record`` objects.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cs.pcs.projects.common.rest_objects import get_classname, get_rest_sysattrs


def rest_objects_by_oid(pcs_records, request, get_additional_data=None):
    """
    :param pcs_record: Table names and records representing objects.
    :type pcs_record: list of
        `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :param get_additional_data: Function to resolve additional values from
        one `pcs_record` and `request`.
    :type get_additional_data: func

    :returns: JSON-serializable rest objects indexed by `cdb_object_id`.
    :rtype: dict
    """
    return {
        pcs_record.record.cdb_object_id: pcs_record2rest_object(
            pcs_record,
            request,
            get_additional_data(pcs_record, request) if get_additional_data else {},
        )
        for pcs_record in pcs_records
    }


def rest_objects_by_restkey(pcs_records, request, get_additional_data=None):
    """
    :param pcs_record: Table names and records representing objects.
    :type pcs_record: list of
        `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :param get_additional_data: Function to resolve additional values from
        one `pcs_record` and `request`.
    :type get_additional_data: func

    :returns: JSON-serializable rest objects indexed by `system:navigation_id`.
    :rtype: dict
    """
    nav_id = "system:navigation_id"
    result = {}

    for pcs_record in pcs_records:
        rest_obj = pcs_record2rest_object(
            pcs_record,
            request,
            get_additional_data(pcs_record, request) if get_additional_data else {},
        )
        result[rest_obj[nav_id]] = rest_obj
    return result


def pcs_record2rest_object(pcs_record, request, kwargs):
    """
    :param pcs_record: Table name and record representing an object.
    :type pcs_record: `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :param request: The request sent from the frontend.
    :type request: ``morepath.Request``

    :param kwargs: Additional, pre-calculated key-value pairs.
    :type kwargs: dict

    :returns: JSON-serializable REST representation of ``pcs_record``.
    :rtype: dict
    """
    classname = get_classname(pcs_record.table_name)
    result = get_rest_sysattrs(pcs_record.record, classname, request)
    result.update(kwargs)
    return result
