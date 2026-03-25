# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi
from cdb import util

SQL_MAX_CHUNK_SIZE = 1000
MONOLITHIC_FILETYPES = [
    "PRC",
    "STEP",
    "JT",
]

def chunks(elements, max_size=SQL_MAX_CHUNK_SIZE):
    elements_list = list(elements) if elements is not None else []
    for i in range(0, len(elements_list), max_size):
        yield elements_list[i:i + max_size]


def variant_name(variant):
    name = variant.name
    if not name:

        try:
            # InfoTxt does not exist for cs.variants variants
            variant_infotxt_fallback_language = util.get_prop("vifl")
            name = variant.InfoTxt[variant_infotxt_fallback_language]
        except AttributeError:
            return "%s" % variant.id

    return "%s: %s" % (variant.id, name)


def isclose(a, b, rel_tol=1e-06, abs_tol=1e-06):
    return abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def __get_mapped_attr_name(attr, attr_mapping=None):
    if attr_mapping is None or attr not in attr_mapping:
        return attr
    return attr_mapping[attr]


def __make_pk_statement(objects, primary_keys, attr_mapping=None):
    number_types = (int, float)

    def _getattr(o, name):
        if isinstance(o, dict):
            return o.get(name)
        # CDB Object
        return getattr(o, name)

    def _get_format_str(val):
        if isinstance(val, int):
            return "%s=%d"
        if isinstance(val, float):
            return "%s=%f"
        return "%s='%s'"

    def _quote(val):
        if isinstance(val, number_types):
            return val
        return sqlapi.quote(val)

    result = []
    for obj in objects:
        pk_values = []
        for attr in primary_keys:
            val = _getattr(obj, attr)
            format_str = _get_format_str(val)
            quoted_val = _quote(val)
            pk_values.append(
                format_str % (__get_mapped_attr_name(attr, attr_mapping), quoted_val)
            )
        pk_statement = " AND ".join(pk_values)
        result.append("(%s)" % pk_statement)

    return " OR ".join(result)


def make_item_pk_statement(objects, attr_mapping=None):
    return __make_pk_statement(objects, primary_keys=['teilenummer', 't_index'], attr_mapping=attr_mapping)


def get_occurrences_for_bom_item_ids(ids):
    try:
        from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence
        return AssemblyComponentOccurrence.KeywordQuery(bompos_object_id=ids)
    except:
        return []