#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

import functools
import logging
from collections import defaultdict

from cdb import ElementsError, kernel, sqlapi
from cdb import util as cdbutil
from cdbwrapc import CDBClassDef
from cs.platform.web.rest.generic.convert import dump
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common import partition

SQL_CHUNKSIZE = 990


def _get_classinfo(getter, param):
    try:
        cldef = getter(param)
    except ElementsError as exc:
        logging.exception("_get_classinfo")
        raise HTTPBadRequest from exc

    if not cldef:
        logging.error("cannot find class def for %s(%s)", getter, param)
        raise HTTPBadRequest

    table = cldef.getPrimaryTable()
    return cldef, table


def get_classinfo(classname):
    """
    :param classname: Classname to get info for
    :type classname: str

    :returns: 2-tuple (class definition, primary database table)
    :rtype: (CDBClassDef, str)

    :raises webob.exc.HTTPBadRequest: if CDBClassDef cannot be found.
    """
    return _get_classinfo(CDBClassDef, classname)


def get_classinfo_REST(restname):
    """
    :param restname: REST name to get info for
    :type restname: str

    :returns: 2-tuple (class definition, primary database table)
    :rtype: (CDBClassDef, str)

    :raises webob.exc.HTTPBadRequest: if CDBClassDef cannot be found.
    """
    return _get_classinfo(CDBClassDef.findByRESTName, restname)


def _build_literal(table_info, name, value):
    op = "="
    if value is None:
        op = " IS "
    return f"{name}{op}{sqlapi.make_literal(table_info, name, value)}"


def _get_single_sql_condition(table_info, keynames, values):
    if len(keynames) != len(values):
        logging.exception(
            "_get_single_sql_condition: "
            "length of keys and values does not match, %s, %s",
            keynames,
            values,
        )
        raise IndexError
    return " AND ".join(
        [
            _build_literal(table_info, name, value)
            for name, value in zip(keynames, values)
        ]
    )


def get_sql_condition(table, keynames, rest_keys):
    """
    :param table: Database table name
    :type table: str

    :param keynames: Ordered names of primary keys
    :type keynames: list of str

    :param rest_keys: Ordered values of primary keys
    :type rest_keys: list of str

    :returns: SQL where condition.
        If either `keynames` or `rest_keys` are empty, "1=2" is returned.
    :rtype: str
    """
    if not (keynames and rest_keys):
        return "1=2"

    tinfo = cdbutil.tables[table]
    all_conditions = [
        _get_single_sql_condition(tinfo, keynames, rest_key) for rest_key in rest_keys
    ]
    conditions = [
        f"({') OR ('.join(chunk)})"
        for chunk in partition(all_conditions, SQL_CHUNKSIZE)
    ]
    return f"({') OR ('.join(conditions)})"


def get_rest_key(record, keynames):
    """
    :param record: Record to get REST key for
    :type record: cdb.sqlapi.Record

    :param keynames: Ordered names of primary keys
    :type keynames: list of str

    :returns: REST key for given `record`
    :rtype: str

    .. note ::

        This implementation is functionally identical to
        `cs.platform.web.rest.support.rest_key`, but works with a
        `cdb.sqlapi.Record` instead of a `cdb.objects.Object`.

    """
    from cs.platform.web.rest.generic import convert
    from cs.platform.web.rest.support import _REPLACEMENTS

    result = []

    for k in keynames:
        keyname = ""
        for c in str(convert.dump_value(record[k])).encode("utf-8"):
            c = chr(c)
            keyname += _REPLACEMENTS[c]
        result.append(keyname)

    return "@".join(result)


def filter_dict(record, fields, cldef):
    """
    :param record: Record to get REST key for
    :type record: cdb.sqlapi.Record

    :param fields: Field names to include in result
    :type fields: list of str

    :param cldef: Class definition to type values for
    :type cldef: cdbwrapc.CDBClassDef

    :returns: Record values in `fields` indexed by field names
        and typed as expected by attribute definitions of `cldef`
    :rtype: dict

    :raises KeyError: if any field is missing in `record`.
    """
    filtered = {field: record[field] for field in fields}
    return dump(filtered, cldef)


def _merge_results(valtype, updater, *results):
    merged = defaultdict(valtype)

    for result in results:
        for key in result:
            updater(merged, result, key)

    return merged


def merge_results_dict(*results):
    """
    :param results: Dicts to merge
    :type results: list of dict

    :returns: Merged dict of dicts. Nested dicts are updated, not replaced.
    :rtype: dict

    .. rubric :: Example

    .. code-block :: python

        a = {
            "foo": {"a": "A"},
            "bar": {"a": "A"},
        }
        b = {
            "foo": {"b": "B"},
            "baz": {"b": "B"},
        }
        merge_results_dict(a, b)
        expected = {
            "foo": {"a": "A", "b": "B"},
            "bar": {"a": "A"},
            "baz": {"b": "B"},
        }
    """

    def updater(merged, result, key):
        merged[key].update(result[key])

    return _merge_results(dict, updater, *results)


def merge_results_str(*results):
    """
    :param results: Dicts to merge
    :type results: list of dict

    :returns: Merged dict of str. String values are concatenated.
    :rtype: dict

    .. rubric :: Example

    .. code-block :: python

        a = {
            "foo": "a",
            "bar": "a",
        }
        b = {
            "foo": "b",
            "baz": "b",
        }
        merge_results_dict(a, b)
        expected = {
            "foo": "ab",
            "bar": "a",
            "baz": "b",
        }
    """

    def updater(merged, result, key):
        merged[key] += result[key]

    return _merge_results(str, updater, *results)


def get_mapped_referers(classname, names):
    """
    :param classname: Classname to get referers for
    :type classname: str

    :param names: Names of mapped attributes to get referers for.
    :type names: list of str

    :returns: Referers of mapped attributes for given `rest_name`,
        indexed by `names`.
        Non-existing mapped attributes will be omitted.
    :rtype: dict
    """
    mapped_attrs = kernel.MappedAttributes(classname)
    return {
        mapped_attr.getName(): mapped_attr.getReferer()
        for mapped_attr in mapped_attrs
        if mapped_attr.getName() in names
    }


def _get_mapped_attr(mapped_attrs, referers, record, name):
    source_attr = referers.get(name, None)

    if not source_attr:
        logging.error(
            "get_mapped_attrs no referer found: '%s' (%s)",
            name,
            referers,
        )
        raise HTTPBadRequest

    source_value = record.get(source_attr, None)

    if source_value is None:
        return ""

    return mapped_attrs.getValue(name, source_value)


def get_mapped_attrs(classname, record, referers, names):
    mapped_attrs = kernel.MappedAttributes(classname)

    return {
        name: _get_mapped_attr(mapped_attrs, referers, record, name) for name in names
    }


def get_oids_from_json(request):
    """
    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: cdb_object_ids extracted from request's JSON payload.
    :rtype: list

    :raises KeyError: if request's JSON payload does not include the key
        "objectIDs".
    :raises webob.exc.HTTPBadRequest: if "objectIDs" value in request's JSON
        payload is not a list.
    """
    object_ids = request.json["objectIDs"]

    if not isinstance(object_ids, list):
        logging.error("malformed 'object_ids': %s", object_ids)
        raise HTTPBadRequest

    return object_ids


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
