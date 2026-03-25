#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
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
from urllib.parse import unquote

from cdb.cmsg import Cdbcmsg
from cdb.constants import kOperationShowObject
from cdb.lru_cache import lru_cache
from cdb.platform.mom.entities import Class
from cdbwrapc import CDBClassDef
from cs.platform.web.rest.generic.convert import dump_value
from cs.platform.web.rest.support import _REPLACEMENTS, rest_name_for_class_name

from cs.pcs.projects.helpers import is_cdbpc

# CLASSNAME_CACHE_SIZE shoud be > amount of classes used in application
# in our case, usually just projects and tasks
# but customers may include documents and parts, too
CLASSNAME_CACHE_SIZE = 5


def rest_key(record):
    """
    :param record: the record representing the object to get the rest key for.
    :type record: cdb.sqlapi.Record

    :returns: the object's rest key ("@"-delimited primary key values). Though
        not http-encoded, unsafe characters are replaced with safe ones.
    :rtype: str
    """
    res = []
    for k in record.thead.dbkeys():
        keyname = ""
        for c in str(dump_value(record[k])).encode("utf-8"):
            c = chr(c)
            keyname += _REPLACEMENTS[c]
        res.append(keyname)
    return "@".join(res)


@lru_cache(maxsize=CLASSNAME_CACHE_SIZE)
def get_classname(relation):
    """
    :param relation: Database table name to get classname for.
    :type relation: str

    :returns: Classname associated with given database table name. ``None``
        if classname cannot be determined.
    :rtype: str

    .. note ::

        The result for up to n database table names is cached (where n is
        ``CLASSNAME_CACHE_SIZE``). To reset the cache, call
        ``get_classname.cache_clear()``.

    """
    if relation:
        classdef = Class.ByRelation(relation)
        if classdef:
            return classdef.classname

    logging.error("could not determine classname for relation: %s", relation)
    return None


@lru_cache(maxsize=CLASSNAME_CACHE_SIZE)
def get_rest_sysattr_patterns(classname):
    """
    :param classname: Name of the class to get system attribute patterns for.
        These patterns contain placeholders to be replaced with values of a
        specific object.
    :type classname: str

    :returns: Patterns for system REST and JSON-LD attributes.
    :rtype: dict

    .. note ::

        The result for up to n classnames is cached (where n is
        ``CLASSNAME_CACHE_SIZE``). To reset the cache, call
        ``get_rest_sysattr_patterns.cache_clear()``.

    """
    if classname:
        restname = rest_name_for_class_name(classname)
        return {
            "@id": f"{{base}}/api/v1/collection/{restname}/{{restkey}}",
            "@context": f"{{base}}/api/v1/context/{classname}",
            "@type": f"{{base}}/api/v1/class/{classname}",
            "system:classname": classname,
            "system:navigation_id": "{restkey}",
            "system:ui_link": f"{{base}}/info/{restname}/{{restkey}}",
        }

    logging.error(
        "could not get REST system attribute patterns for classname: %s", classname
    )
    return None


def get_cdbpc_url(record, classname):
    """
    :param record: Record representing an object.
    :type record: cdb.sqlapi.Record

    :param classname: Classname of ``record``.
    :type classname: str

    :returns: Legacy "UI link", e.g. URL for operation "CDBShowObject".
    :rtype: str
    """
    msg = Cdbcmsg(classname, kOperationShowObject, True)
    cdef = CDBClassDef(classname)
    table_name = cdef.getPrimaryTable()

    for key in cdef.getKeyNames():
        msg.add_item(key, table_name, record[key])

    return msg.cdbwin_url()


def get_rest_sysattrs(record, classname, request):
    """
    :param record: Record representing an object.
    :type record: cdb.sqlapi.Record

    :param classname: Classname of ``record``.
    :type classname: str

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: System REST and JSON-LD attributes for given ``record``.
    :rtype: dict
    """
    patterns = get_rest_sysattr_patterns(classname)

    if not patterns:
        logging.error(
            "could not get REST system attributes for classname: %s", classname
        )
        return {}

    replacements = {
        "base": request.application_url,
        "restkey": rest_key(record),
    }

    if is_cdbpc():
        # request comes from cdbpc, not Web UI - generate legacy links
        patterns["system:ui_link"] = get_cdbpc_url(record, classname)

    return {k: unquote(v.format(**replacements)) for k, v in patterns.items()}


def get_restlinks_in_batch(record_tuples, request):
    """
    :param record_tuples: Database table names and records representing each
        object to get links for.
    :type record_tuples: list of tuple(str, cdb.sqlapi.Record)

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: REST "@id" links indexed by cdb_object_ids.
    :rtype: dict

    :raises ValueError: if determining any link fails.
    """
    try:
        return {
            record.cdb_object_id: unquote(
                get_rest_sysattr_patterns(get_classname(relation),)["@id"].format(
                    base=request.application_url,
                    restkey=rest_key(record),
                )
            )
            for relation, record in record_tuples
        }
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        msg = f"cannot get links: '{record_tuples}', '{request}'"
        logging.exception(msg)
        raise ValueError(msg) from exc


def get_project_id_in_batch(record_tuples, request):
    """
    :param record_tuples: Database table names and records representing each
        object to get links for.
    :type record_tuples: list of tuple(str, cdb.sqlapi.Record)

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: Dict for cdb_project_id.
    :rtype: dict

    :raises ValueError: if determining any link fails.
    """
    try:
        return {
            record.cdb_object_id: record.cdb_project_id
            for relation, record in record_tuples
            if hasattr(record, "cdb_object_id") and hasattr(record, "cdb_project_id")
        }
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        msg = f"cannot get project id: '{record_tuples}', '{request}'"
        logging.exception(msg)
        raise ValueError(msg) from exc


def get_restkeys_in_batch(record_tuples):
    """
    :param record_tuples: Database table names and records representing each
        object to get rest keys for.
    :type record_tuples: list of tuple(str, cdb.sqlapi.Record)

    :returns: REST keys indexed by cdb_object_ids.
    :rtype: dict

    :raises ValueError: if determining any rest keys fails.
    """
    try:
        return {
            record.cdb_object_id: rest_key(record) for relation, record in record_tuples
        }
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        msg = f"cannot get rest keys: '{record_tuples}'"
        logging.exception(msg)
        raise ValueError(msg) from exc


def get_oid_from_node_id(node_id):
    """
    :param node_id: id of the node.
    :type str

    :returns: object id of the object contained in the node.
    :rtype: str
    """
    return node_id.split("@")[0]
