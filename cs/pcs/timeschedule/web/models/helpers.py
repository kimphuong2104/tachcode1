#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import namedtuple
from itertools import groupby
from operator import itemgetter

import isodate
from cdb import sqlapi, typeconversion
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common import format_in_condition

PCS_OID = namedtuple("pcs_oid", ["cdb_object_id", "table_name"])


def is_milestone(obj):
    return getattr(obj, "milestone", 0)


def get_date(dictionary, key, is_iso=True):
    """
    :param dictionary: a dictionary.
    :type dictionary: dict

    :param key: the JSON key to get data from ``dictionary`` for.
    :type key: str

    :param is_iso: If ``True``, the JSON value is expected to be ISO 8601.
        Else, it is expected to be in CE legacy format.
    :type is_iso: bool

    :returns: the date in ``dictionary[key]``.
    :rtype: datetime.date

    :raises webob.exc.HTTPBadRequest: if the key is missing in ``dictionary``
        or contains an invalid value.
    """

    def raise_bad_request():
        logging.error(
            "invalid key '%s' in request dictionary: %s",
            key,
            dictionary,
        )
        raise HTTPBadRequest

    if not (isinstance(dictionary, dict) and isinstance(key, str)):
        raise_bad_request()

    try:
        date_str = dictionary[key]
    except KeyError:
        raise_bad_request()

    if not date_str:
        return None

    if is_iso:
        try:
            return isodate.parse_date(date_str)
        except (isodate.ISO8601Error, TypeError):
            logging.exception("tried to convert ISO date '%s' from %s", key, dictionary)
            raise_bad_request()
    else:
        try:
            dt = typeconversion.from_legacy_date_format(date_str)
            return dt.date()
        except ValueError:
            logging.exception(
                "tried to convert legacy date '%s' from %s", key, dictionary
            )
            raise_bad_request()


def get_oid_query_str(oids, attr=None):
    """
    :param oids: List of cdb_object_id values.
    :type oids: list

    :param attr: Attribute name to use (defaults to "cdb_object_id").
    :type attr: str

    :returns: SQL WHERE clause for given values, e.g.
        ``"cdb_object_id IN ('a', 'b', 'c')"``.
    :rtype: str

    :raises TypeError: if ``oids`` is not iterable or any cdb_object_id is
        neither ``None`` nor a ``str``.
    """
    if attr is None:
        attr = "cdb_object_id"

    return format_in_condition(attr, oids)


def get_pcs_oids(oids):
    """
    :param oids: cdb_object_ids to get database table names for.
    :type oids: list of str

    :returns: cdb_object_ids and their respective database table names.
    :rtype: list of `PCS_OID`
    """
    rset = sqlapi.RecordSet2("cdb_object", get_oid_query_str(oids, "id"))
    return [PCS_OID(record.id, record.relation) for record in rset]


def get_oids_by_relation(pcs_oids):
    """
    :param pcs_oids: cdb_object_ids and database table names of objects.
    :type pcs_oids: list of `PCS_OID`

    :returns: list of cdb_object_ids grouped by database table names
    :rtype: list of tuple(str, list)

    :raises ValueError: if
        - `pcs_oids` or one of its values is not iterable,
        - any value contains less than 2 value.
    """
    oids_by_relation = []
    try:
        sorted_oids = sorted(pcs_oids, key=itemgetter(1))
    except TypeError as exc:
        raise ValueError(
            f"value (or one of its values) is not iterable: '{pcs_oids}'"
        ) from exc
    except IndexError as exc:
        raise ValueError(
            f"each value must contain at least 2 values: '{pcs_oids}'"
        ) from exc

    for relation, oids in groupby(sorted_oids, itemgetter(1)):
        oids_by_relation.append((relation, [o[0] for o in oids]))

    return oids_by_relation


def get_node(row_number, expanded, node_id):
    return {
        "id": node_id,
        "rowNumber": row_number,
        "expanded": expanded,
        "children": [],
    }
