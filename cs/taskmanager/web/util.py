#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import functools
import logging
import re

from cdb import sqlapi
from cdb.objects import ByID
from cs.platform.web.rest.support import (
    decode_key_component,
    get_object_from_rest_name,
    rest_key,
    rest_name,
)
from cs.platform.web.root import get_v1
from cs.platform.web.root.main import _get_dummy_request

REST_ID_CLASS = re.compile(r"^.*/api/v1/class/(?P<classname>[a-z_]+)(/.*)?$")
REST_ID_OBJECT = re.compile(
    r"^.*/api/v1/collection/(?P<restname>[A-Za-z_]+)/(?P<keys>.+)$"
)


def _convert_rest_id(pattern, rest_id):
    """
    :param pattern: Pattern to match against `rest_id`
    :type pattern: Regular expression pattern

    :param rest_id: Rest URL ("@id")
    :type rest_id: str

    :returns: `groupdict` of the pattern match (or empty dict)
    :rtype dict:
    """
    if rest_id:
        match = pattern.match(rest_id)
        if match:
            return match.groupdict()

    return {}


def get_classname_from_rest_id(type_rest_id):
    """
    :param type_rest_id: REST URL ("@id") of a class/type definition
    :type type_rest_id: str

    :returns: Classname extracted from `type_rest_id`
    :rtype: str
    """
    values = _convert_rest_id(REST_ID_CLASS, type_rest_id)
    return values.get("classname")


def _get_uuid(rest_name, rest_keys):
    """
    :param rest_name: REST (class-) name
    :type rest_name: str

    :param rest_keys: REST keys (primary keys separated by "@")
    :type rest_keys: str

    :returns: UUID of the object identified by `rest_name` and `rest_keys`
        (`None` if object is not found or not readable)
    :rtype: str
    """
    if rest_name and rest_keys:
        obj = get_object_from_rest_name(rest_name, rest_keys)
        if obj:
            return obj.cdb_object_id
    logging.error(
        "could not identify object: rest name '%s', keys '%s'",
        rest_name,
        rest_keys,
    )
    return None


def _decode_pkeys(rest_key):
    """
    :param rest_key: REST key as encoded by the platform
    :type rest_key: str

    :returns: utf-8-encoded primary keys, components still separated by "@"
    :rtype: unicode
    """
    raw_keys = sqlapi.quote(rest_key)
    if raw_keys:
        result = decode_key_component(raw_keys)
        return result
    return None


def get_uuid_from_rest_id(rest_id):
    """
    :param rest_id: REST URL ("@id") of an object
    :type rest_id: str

    :returns: UUID of the object represented by `rest_id`
    :rtype: str

    .. note ::

        Read access is checked; if denied, return value will be `None`
    """
    values = _convert_rest_id(REST_ID_OBJECT, rest_id)
    pkeys = _decode_pkeys(values.get("keys"))
    if pkeys:
        return _get_uuid(values.get("restname"), pkeys)
    return None


def get_pkeys_from_rest_id(rest_id):
    """
    :param rest_id: REST URL ("@id") of an object
    :type rest_id: str

    :returns: utf-8-encoded primary keys, components still separated by "@"
    :rtype: unicode
    """
    values = _convert_rest_id(REST_ID_OBJECT, rest_id)
    result = _decode_pkeys(values.get("keys"))
    return result


def get_collection_app(request):
    """
    :param request: The request sent by the frontend
    :type request: morepath.Request

    :returns: The mounted "collection" app
    :rtype: cs.platform.web.rest.app.CollectionApp
    """
    if request is None:
        request = _get_dummy_request()
    return get_v1(request).child("collection")


def get_rest_object(obj, collection_app, request):
    """
    :param obj: Object to get REST representation of.
        Should have the attribute "@cs_tasks_class" injected.
    :type obj: cdb.objects.Object

    :param collection_app: The mounted "collection" app
    :type collection_app: cs.platform.web.rest.app.CollectionApp

    :param request: The request sent by the frontend
    :type request: morepath.Request

    :returns: JSON-serializable REST representation of `obj`
        (minimal "relship-target" view)
    :rtype: dict

    .. note ::

        In addition to the regular REST representation, for objects with
        lifecycles, the key "system:status" is added to contain information
        about the object's current status as returned by
        `cs.platform.web.rest.generic.model.Workflow`:

        .. code-block :: json

            {
                "status": 0,
                "color": "#F8F8F8",
                "label": "New",
            }
    """
    if not obj:
        return None

    if request is None:
        request = _get_dummy_request()

    result = request.view(
        obj,
        app=collection_app,
        # use relship-target over default view, because
        # resolving relships is _expensive_
        # this also resolves long texts
        name="relship-target",
    )

    result["@cs_tasks_class"] = getattr(obj, "@cs_tasks_class", None)
    return result


def get_rest_key_from_key(key):
    from cs.platform.web.rest.generic import convert
    from cs.platform.web.rest.support import _REPLACEMENTS

    keyname = ""
    for c in convert.dump_value(key):
        keyname += _REPLACEMENTS[c]
    return keyname


def get_rest_id_from_uuid(uuid, request):
    obj = ByID(uuid)
    if obj and obj.CheckAccess("read"):
        return get_object_rest_id(obj, request)
    return None


def get_object_rest_id(obj, request):
    result = "{}/api/v1/collection/{}/{}".format(
        request.application_url,
        rest_name(obj),
        rest_key(obj),
    )
    return result


def get_object_ui_link(obj, request):
    result = "{}/info/{}/{}".format(
        request.application_url,
        rest_name(obj),
        rest_key(obj),
    )
    return result


def get_class_rest_id(classname, request):
    result = "{}/api/v1/class/{}".format(
        request.application_url,
        classname,
    )
    return result


def partition(values, chunksize):
    """
    Generator that yields sublists of `values` of max. `chunksize` items each

    :param values: List to partition (must support `len` and slicing)
    :type values: list

    :param chunksize: Maximum size of each chunk
    :type chunksize: int

    :raises ValueError: if `chunksize` is not an int greater than 1
    """
    if not (isinstance(chunksize, int) and chunksize > 1):
        raise ValueError("chunksize must be a positive integer")

    range_func = range

    for index in range_func(0, len(values), chunksize):
        yield values[index : index + chunksize]


def format_in_condition(col_name, values, max_inlist_value=1000):
    """
    :param col_name: Name of the column to generate an "in" clause for
    :type col_name: string

    :param values: Values to use in "in" clause
    :type values: list - will break if a set is used

    :returns: "or"-joined SQL "in" clauses including ``values`` in batches of
        up to 1000 each to respect DBMS-specific limits (ORA: 1K, MS SQL 10K).
        NOTE: If values is empty "1=0" is returned, so no value should be
              returned for the SQL statement.
    :rtype: string
    """

    def _convert(values):
        return "{} IN ({})".format(
            col_name, ",".join([sqlapi.make_literals(v) for v in values])
        )

    if not values:
        return "1=0"

    conditions = [_convert(chunk) for chunk in partition(values, max_inlist_value)]
    return " OR ".join(conditions)


def get_grouped_data(table, condition, *group_attrs, **kwargs):
    """
    :param table: Table name to query for data
    :type table: str

    :param condition: SQL WHERE clause (without "WHERE", see
        `cdb.sqlapi.RecordSet2` constructor for valid conditions)
    :type condition: str

    :param kwargs: dict of keyword arguments.
            Note: Only keyword argument transform_func is recognized, which is
                  transformation function applied to single record
    :type kwargs: dict

    :param group_attrs: Attribute names to group `records` by
    :type group_attrs: tuple of str

    :returns: Lists of `cdb.sqlapi.Record` objects
        indexed by their shared values of `group_attrs`.
    :rtype: dict

    :raises ValueError: if no attributes for grouping are given
    """
    records = sqlapi.RecordSet2(table, condition, access="read")
    transform_func = kwargs.get("transform_func")

    if not group_attrs:
        raise ValueError("No grouping attributes given")

    result = {}

    def traverse(root, key):
        return root.setdefault(key, {})

    for record in records:
        keys = [record[attr] for attr in group_attrs]
        last_key = keys[-1]
        # construct nested dict path
        parent = functools.reduce(traverse, keys[:-1], result)
        # make sure leaf is a list and add the record
        parent.setdefault(last_key, [])
        parent[last_key].append(transform_func(record) if transform_func else record)

    return result
