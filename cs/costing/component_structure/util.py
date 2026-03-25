#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import copy

from cdb import sqlapi
from cdb import ddl
from cdb import util
from cdb.lru_cache import lru_cache
from cdbwrapc import CDBClassDef, CDBAttributeDefMultiLang

from cs.pcs.projects.project_structure.util import _get_oid_query_str
from cs.pcs.projects.project_structure.util import _get_oids_by_relation
from cs.pcs.projects.project_structure.util import get_flat_structure
from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.projects.project_structure.util import PCS_RECORD
from cs.pcs.projects.project_structure.util import DTAG_PATTERN
from cs.pcs.projects.project_structure.rest_objects import pcs_record2rest_object
from cs.pcs.projects.project_structure.query_patterns import get_query_pattern
from cs.pcs.projects.common import partition

from cs.costing.component_structure import query_patterns

def resolve_component_structure(root_oid, get_row_and_node,
                                request):
    """
    :param root_oid: The `cdb_object_id` of the root project to resolve.
    :type root_oid: str

    :param get_row_and_node: The function to construct a single row and
        node entry for parameters
        `(row_number, oid, rest_link, collapsed)`.
    :type get_row_and_node: function

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: 4-tuple of pcs records, rows, flat tree nodes and levels.
    :rtype: tuple
    """
    cost_records, cost_levels = resolve_structure(root_oid, "cdbpco_calculation")
    pcs_records = convert_records(cost_records)
    rows, flat_nodes, levels = get_flat_structure(
        cost_levels,
        pcs_records,
        get_row_and_node,
        request,
    )
    return pcs_records, rows, flat_nodes, levels


def resolve_structure(root_oid, root_table_name, offset=0):
    """
    :param root_oid: `cdb_object_id` of the root object to resolve.
    :type root_oid: str

    :param root_table_name: Database table name of the root object.
    :type root_table_name: str

    :returns: tuple of database records and resolved structure nodes.
        If no structure could be resolved,
        structure nodes only contain a list with just the root node record.
    :rtype: list of `database records`,
            list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`
    :raises TypeError: if root_oid is not a string
    .. note ::

        Please note that tasks with position ``NULL`` are unsupported and
        considered corrupted data.
        Their existence will break the expected sorting order.

    """
    pattern = "structure"
    query_pattern = get_query_pattern(pattern, query_patterns.load_query_pattern)
    if query_pattern:
        comp_attrs = get_component_attributes()
        query_str = query_pattern.format(
            oid=root_oid,
            comp_fields="a."+",a.".join(comp_attrs),
            child_fields="child_comp."+",child_comp.".join(comp_attrs),
            calc_fields="null as "+", null as ".join(comp_attrs),
            fields=",".join(comp_attrs)
        )
        cost_records = sqlapi.RecordSet2(sql=query_str)
    else:
        try:
            # only get root record
            q = "SELECT cdb_object_id, name, name AS ml_name_en,'' AS comp_object_id, '' AS quantity, " \
                "'' AS cdb_classname, 0 AS cloned, 0 as llevel, {table_name} as table_name FROM {table_name} " \
                "WHERE {where_clause}".format(table_name=root_table_name, where_clause=_get_oid_query_str([root_oid]))
            cost_records = sqlapi.RecordSet2(sql=q)
        except TypeError:
            raise ValueError("non-string oid value: {}".format(root_oid))

    pcs_levels = [
        PCS_LEVEL(
            record.cdb_object_id,
            record.table_name,
            int(record.llevel),
        )
        for record in cost_records
    ]
    return cost_records, pcs_levels


def convert_records(cost_records):
    """
    :param cost_records: db records to parse into correct format.
    :type cost_records: list of db records

    :returns: parsed db records
    :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`
    :raises KeyError: if db records do not have field 'table_name'
    """
    pcs_records = []
    for rec in cost_records:
        try:
            rec.thead.tname = "cdbpco_component"
            pcs_records.append(PCS_RECORD(rec.table_name, rec))
        except KeyError:
            raise ValueError("provided record does not have required field 'table_name'")
    return pcs_records

# copied and adjusted from cs.pcs.common
def format_in_condition(query, values, max_inlist_value=1000):
    """
    :param query: query to generate an "in" clause for
    :type query: string

    :param values: Values to use in "in" clause
    :type values: list - will break if a set is used

    :returns: "or"-joined SQL "in" clauses including ``values`` in batches of
        up to 1000 each to respect DBMS-specific limits (ORA: 1K, MS SQL 10K).
        NOTE: If values is empty "1=0" is returned, so no value should be
              returned for the SQL statement.
    :rtype: string
    """
    def _convert(query, values):
        return query.format(
            ",".join([
                sqlapi.make_literals(v)
                for v in values
            ])
        )

    if len(values) == 0:
        return "1=0"
    else:
        conditions = [
            _convert(query, chunk)
            for chunk in partition(values, max_inlist_value)
        ]
    return " OR ".join(conditions)


def filter_oid_with_read_access(oids):
    try:
        query_str = format_in_condition("id in ({})", oids)
    except TypeError:
        raise ValueError("non-string oid value: '{}'".format(oids))

    return [
        rec.id
        for rec in sqlapi.RecordSet2("cdb_object", query_str, access="read")
    ]


def resolve_records(pcs_levels):
    # NOTE: It is assumed, that oids in pcs_level already have been checked for read access
    oids_by_relation = _get_oids_by_relation(pcs_levels)

    result = []
    component_field_str = "c." + ",c.".join(get_component_attributes())
    # Prepared query for joined attributes from cdbpco_component as well as cdbpco_comp2component
    q = "SELECT 'cdbpco_comp2component' as table_name, c.name, c.ml_name_en, c.cdb_classname, c.cloned, "\
        "c2c.cdb_object_id, c2c.quantity, c2c.comp_object_id, %s FROM cdbpco_comp2component c2c "\
        "JOIN cdbpco_component_v c ON c2c.comp_object_id=c.cdb_object_id WHERE c2c.cdb_object_id IN ({})" % component_field_str
    for relation, oids in oids_by_relation:

        try:
            query_str = format_in_condition(q, oids)
        except TypeError:
            raise ValueError("non-string oid value: '{}'".format(oids))

        for rec in sqlapi.RecordSet2(sql=query_str):
            rec.thead.tname = "cdbpco_component"
            result += [
                PCS_RECORD(relation, rec)
            ]

    return result


# copied and adjusted from cs.pcs.projects.project_structure.rest_objects
def rest_objects_by_restkey(pcs_records, mapping_oids, request, get_additional_data=None):
    """
    :param pcs_record: Table names and records representing objects.
    :type pcs_record: list of
        `cs.pcs.projects.project_structure.util.PCS_RECORD`

    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :param mapping_oids: Mapping of `cdb_object_ids` to costing structure
                         specific `cdb_object_ids` combined with occurence
    :type mapping_oids: dict

    :param get_additional_data: Function to resolve additional values from
        one `pcs_record` and `request`.
    :type get_additional_data: func

    :returns: JSON-serializable rest objects indexed by cdb_object_ids`
              combined with occurence.
    :rtype: dict
    """
    result = {}

    for pcs_record in pcs_records:
        rest_obj = pcs_record2rest_object(
            pcs_record,
            request,
            get_additional_data(pcs_record, request)
            if get_additional_data else {},
        )
        oid = pcs_record.record.cdb_object_id
        for oid_occ in mapping_oids[oid]:
            result[oid_occ] = rest_obj
    return result


@lru_cache()
def get_component_attributes():
    cdef = CDBClassDef("cdbpco_component")
    field_list = []
    multilang_fields = []
    for mattr_def in cdef.getMultiLangAttributeDefs():
        name = mattr_def.getName()
        multilang_fields.append(name)
    for attr_def in cdef.getAttributeDefs():
        name = attr_def.getName()
        if not (attr_def.is_text() or attr_def.is_mapped(include_multilang=True) or name in multilang_fields):
            if name in ["cdb_object_id", "quantity", "cloned",
                        "calc_object_id", "name", "ml_name_en",
                        "cdb_classname", "parent_object_id"]:
                continue
            field_list.append(name)
    return field_list


def validate_dtag(classname, label, failsafe=True):
    """
    validate fields in description tag labels

    :param classname: Name of the class.
    :type classname: str

    :param label: label to get the fields from.
    :type label: str

    :param failsafe: if True invalid field placeholders will be replaced with "<field_name>", else an error is raised
    :type failsafe: bool

    :returns: the label in the current language and the fields required for placeholders.
    If failsafe is True, placeholders for invalid fields are replaced with static strings "<field_name>".
    :rtype: tuple of (label, fields)

    :raises ErrorMessage: if failsafe is False and the label contains any placeholders for invalid fields.
    """
    cdef = CDBClassDef(classname)
    table = ddl.Table(cdef.getPrimaryTable())
    relation = cdef.getRelation()
    view = None
    if relation != table:
        view = ddl.View(cdef.getRelation())
        view_column_names = view.getColumnNames()
    fields = DTAG_PATTERN.findall(label)
    missing = []
    for field in fields:
        if view:
            if not field in view_column_names:
                missing.append(field)
        else:
            if not table.hasColumn(field):
                missing.append(field)
    if missing:
        if failsafe:
            new_label = None
            for m in missing:
                new_label = label.replace("{" + m + "}", "<" + m + ">") if new_label is None else new_label.replace(
                    "{" + m + "}", "<" + m + ">")
                fields.remove(m)
            return new_label, fields
        else:
            raise util.ErrorMessage(
                "cdbpcs_project_structure_dtag_invalid", ", ".join(missing))
    return label, fields