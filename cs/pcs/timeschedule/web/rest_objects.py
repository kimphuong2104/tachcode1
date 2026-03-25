#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Utilities for working with REST objects.

These are mostly redundant with implementations found in cs.web and the
platform, but are optimized for performance in batch mode.

This means that while implementation in cs.web and the platform usually only
work with ``cdb.objects.Object`` objects, these ones are designed to work on
``cdb.sqlapi.Record`` objects (with the help of some hard-coded values in
plugins.)
"""

import logging

from cdb.lru_cache import lru_cache
from cdb.typeconversion import to_python_rep
from cdbwrapc import CDBClassDef, is_cdb_pq
from cs.platform.web.rest.generic.convert import dump

from cs.pcs.projects.common.rest_objects import CLASSNAME_CACHE_SIZE, get_rest_sysattrs
from cs.pcs.timeschedule.web.mapping import ColumnMapping

REST_WHITELIST = set(
    [
        "@context",
        "@id",
        "@type",
        "system:classname",
        "system:description",
        "system:icon_link",
        "system:navigation_id",
        "system:ui_link",
        "system:olc",  # Value added by cs.pcs after validation in the front-end
    ]
)
RELSHIP_FIELDS = [
    "rel_type",
    "minimal_gap",
    "violation",
    "pred_task_oid",
    "succ_task_oid",
    "cdb_project_id2",  # predecessor project id
    "task_id2",  # predecessor task id
    "cdb_project_id",  # successor project id
    "task_id",  # successor task id
]
UNSUPPORTED_SQL_TYPES = (
    "text",
    "mapped",
    "multilang",
    "virtual",
)


def get_rest_objects(plugins, column_group, record_tuples, request):
    """
    :param plugins: Plugins indexed by database table names.
    :type plugins: dict

    :param column_group: Column definitions group
    :type column_group: str

    :param record_tuples: Database table names and records representing each
        object to get rest objects for.
    :type record_tuples: list of tuple(str, cdb.sqlapi.Record)

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: JSON-serializable rest object.
    :rtype: list of dict
    """
    return [
        record2rest_object(plugins[relation], column_group, record, request)
        for relation, record in record_tuples
    ]


def get_sqltype(adef):
    """
    :param adef: Attribute definition to get the sqltype of.
    :type adef: cdbwrapc.CDBAttributeDef

    :returns: ``None`` if ``adef`` represents a long text or physical
        quantity. Otherwise one of ``cdb.sqlapi.SQL_CHAR``,
        ``cdb.sqlapi.SQL_DATE``, ``cdb.sqlapi.SQL_FLOAT``,
        ``cdb.sqlapi.SQL_INTEGER``.
    :rtype: int
    """

    for unsupported in UNSUPPORTED_SQL_TYPES:
        is_unsupported = getattr(adef, f"is_{unsupported}")
        if is_unsupported():
            logging.error(
                "'%s': cannot handle %s attribute '%s'",
                adef.getClassDef().getClassname(),
                unsupported,
                adef.getIdentifier(),
            )
            return None

    sqltype = adef.getSQLType()

    if is_cdb_pq(sqltype):
        logging.error(
            "'%s': cannot handle PQ '%s'",
            adef.getClassDef().getClassname(),
            adef.getIdentifier(),
        )
        return None

    return sqltype


@lru_cache(maxsize=CLASSNAME_CACHE_SIZE)
def get_attributes(plugin, column_group):
    """
    :param plugin: Plugin representing the class to get attribute information
        for.
    :type plugin: subclass of
        ``cs.pcs.timeschedule.web.plugins.TimeschedulePlugin``

    :returns: Attribute names and sqltypes. Attributes not required for the
        frontend (also see
        ``cs.pcs.timeschedule.web.mapping.ColumnMapping.GetFieldWhitelist``)
        or not configured as visible for the REST API are excluded.
    :rtype: list of tuple(str, int)

    .. note ::

        The result for up to n classnames is cached (where n is
        ``CLASSNAME_CACHE_SIZE``). To reset the cache, call
        ``get_attributes.cache_clear()``.

    :raises AttibuteError: if ``plugin`` is missing attribute ``classname`` or
        method ``GetRequiredFields``.
    """
    whitelist = ColumnMapping.GetFieldWhitelist(plugin, colgroup=column_group)

    cdef = CDBClassDef(plugin.classname)
    missing_attrs = set(whitelist)
    result = []

    for adef in cdef.getAttributeDefs():
        name = adef.getName()
        if name in whitelist and adef.rest_visible():
            sqltype = get_sqltype(adef)
            if sqltype is not None:
                result.append((name, sqltype))
                if name in missing_attrs:
                    missing_attrs.remove(name)

    if missing_attrs:
        logging.error(
            "'%s': missing attributes %s in mapping",
            plugin.classname,
            missing_attrs,
        )
    return result


def mapped_data(plugin, column_group, record, classname):
    """
    :param plugin: Plugin (and mapping) representing the class of ``record``.
    :type plugin: subclass of
        ``cs.pcs.timeschedule.web.plugins.TimeschedulePlugin``

    :param column_group: Column definitions group
    :type column_group: str

    :param record: Record representing an object.
    :type record: cdb.sqlapi.Record

    :param classname: Classname of object represented by record.
    :type classname: string

    :returns: JSON-serializable data of ``record`` (including only attributes
        configured as REST-visible and whitelisted by ``plugin``).
    :rtype: dict
    """
    data = {}

    for name, sqltype in get_attributes(plugin, column_group):
        try:
            data[name] = to_python_rep(
                sqltype,
                record[name],
            )
        except AttributeError:
            logging.exception(
                "field '%s' missing; plugin: '%s', record: %s", name, plugin, record
            )
            raise

    cdef = CDBClassDef(classname)
    result = dump(data, cdef)

    for field_name in plugin.GetNullableFields():
        if field_name in data and data[field_name] is None:
            result[field_name] = None

    return result


def record2rest_object(plugin, column_group, record, request):
    """
    :param plugin: Plugin (and mapping) representing the class of ``record``.
    :type plugin: subclass of
        ``cs.pcs.timeschedule.web.plugins.TimeschedulePlugin``

    :param column_group: Column definitions group
    :type column_group: str

    :param record: Record representing an object.
    :type record: cdb.sqlapi.Record

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: JSON-serializable REST representation of ``record``.
    :rtype: dict
    """

    # if record is of a subclass, its real classname is in cdb_classname
    real_classname = record.get("cdb_classname") or plugin.classname
    result = mapped_data(plugin, column_group, record, real_classname)

    subject = plugin.GetResponsible(record)
    if subject:
        result["subject_id"] = subject["subject_id"]
        result["subject_type"] = subject["subject_type"]

    result.update(get_rest_sysattrs(record, real_classname, request))
    result.update(
        {
            "system:description": plugin.GetDescription(record),
            "system:icon_link": plugin.GetObjectIcon(record),
        }
    )

    return result


def relships2json(relships):
    """
    :param relships: Task relationships to send to frontend
    :type relships: list, cdb.objects.ObjectCollection or RecordSet2

    :returns: JSON-serializable task relationships. Only fields whitelisted
        in ``RELSHIP_FIELDS`` are included.
    :rtype: list of dict

    :raises KeyError: if any relship is missing any field whitelisted in
        ``RELSHIP_FIELDS``.
    """
    return [{field: relship[field] for field in RELSHIP_FIELDS} for relship in relships]
