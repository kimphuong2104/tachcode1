# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Collections of methods for efficiently querying a product structure.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections
import logging
from typing import Any

from cdb import sqlapi
from cdb import typeconversion
from cdb import util
from cdbwrapc import CDBClassDef

from cs.vp import bom
from cs.vp import items
from cs.vp.bom import AssemblyComponent
from cs.vp.bom.bomqueries_plugins import ComponentJoinPlugin
from cs.vp.bom.enhancement import FlatBomEnhancement
from cs.vp.bom.enhancement.plugin import AbstractPlugin
from cs.vp.utils import chunk


LOG = logging.getLogger(__name__)


# Exported objects
__all__ = [
    "flat_bom",
    "flat_bom_dict",
    "get_path_sort_key",
    "get_sort_key"
]


aliased_bom_item_attributes = {
    "t_index": "t_index_as_saved"
}


default_part_attributes = [
    "baugruppenart",
    "cdb_depends_on",
    "materialnr_erp",
    "site_object_id",
    "t_index",
    "type_object_id",
]


aliased_part_attributes = {
    "cdb_classname": "item_cdb_classname",
    "cdb_object_id": "item_object_id",
    "ce_valid_from": "item_ce_valid_from",
    "ce_valid_to": "item_ce_valid_to"
}


JOINED_ATTRIBUTE_MAPPING = None
JOINED_MULTILANG_ATTRIBUTES = None


def get_joined_attribute_mapping():
    # FIXME: currently only "Component" join is supported. add support for other joines.
    global JOINED_ATTRIBUTE_MAPPING
    global JOINED_MULTILANG_ATTRIBUTES
    if JOINED_ATTRIBUTE_MAPPING is None:
        JOINED_ATTRIBUTE_MAPPING = {}
        JOINED_MULTILANG_ATTRIBUTES = []
        joined_component_attributes = CDBClassDef("einzelteile").getJoinedAttributeDefs(
            include_multilang=True, join_name="Component"
        )
        for joined_attr in joined_component_attributes:
            joined_attribute_def = joined_attr.getJoinedAttributeDef()
            if (
                not joined_attribute_def.is_mapped(include_multilang=True) and
                not joined_attribute_def.is_joined(include_multilang=True) and
                not joined_attribute_def.is_virtual()
            ):
                if joined_attr.is_multilang():
                    # language neutral attribute without representation in db-table
                    JOINED_MULTILANG_ATTRIBUTES.append(joined_attr.getName())
                else:
                    # attributes with column in db-table
                    JOINED_ATTRIBUTE_MAPPING[joined_attr.getName()] = joined_attribute_def.getName()

    return JOINED_ATTRIBUTE_MAPPING


MULTILANG_ATTRIBUTE_NAMES = None


def get_multilang_attribute_names():
    global MULTILANG_ATTRIBUTE_NAMES
    if MULTILANG_ATTRIBUTE_NAMES is None:
        get_joined_attribute_mapping()
        MULTILANG_ATTRIBUTE_NAMES = list(JOINED_MULTILANG_ATTRIBUTES)
        for attr_def in CDBClassDef("einzelteile").getMultiLangAttributeDefs():
            if (
                not attr_def.is_mapped(include_multilang=True) and
                not attr_def.is_joined(include_multilang=True) and
                not attr_def.is_virtual()
            ):
                # add only own multilang attributes of bom_item
                MULTILANG_ATTRIBUTE_NAMES.append(attr_def.getName())
    return MULTILANG_ATTRIBUTE_NAMES


BOM_ITEM_VIEW_ALIAS = "bom_item_view"
VIRTUAL_ATTRIBUTES: frozenset[str] | None = None


def get_virtual_attribute_names() -> frozenset[str]:
    global VIRTUAL_ATTRIBUTES
    if VIRTUAL_ATTRIBUTES:
        return VIRTUAL_ATTRIBUTES

    virtual_attributes = CDBClassDef("bom_item").getVirtualAttributeDefs()
    VIRTUAL_ATTRIBUTES = frozenset(attribute.getName() for attribute in virtual_attributes)
    return VIRTUAL_ATTRIBUTES


def _get_flat_bom_query(
    where_condition: str,
    bom_item_attributes_select: str,
    part_attributes_select: str,
    bom_enhancement: FlatBomEnhancement
):

    bom_enhancement_select_statement = bom_enhancement.get_bom_item_select_stmt_extension()
    bom_enhancement_sql_join_statement = bom_enhancement.get_sql_join_stmt_extension()
    bom_enhancement_where_part_statement = bom_enhancement.get_part_where_stmt_extension()
    bom_enhancement_where_bom_item_statement = bom_enhancement.get_bom_item_where_stmt_extension()
    bom_enhancement_where_statement = "({0}) AND ({1})".format(
        bom_enhancement_where_part_statement,
        bom_enhancement_where_bom_item_statement
    )
    if VIRTUAL_ATTRIBUTES:
        # E075051: Join einzelteile_v view so we can SELECT virtual attributes.
        bom_item_view_join_statement = f"""
            LEFT OUTER JOIN einzelteile_v {BOM_ITEM_VIEW_ALIAS} ON
                {AbstractPlugin.BOM_ITEM_TABLE_ALIAS}.cdb_object_id = {BOM_ITEM_VIEW_ALIAS}.cdb_object_id
        """
    else:
        bom_item_view_join_statement = ""

    return """
            SELECT {bom_item_attrs},
                {part_attrs}
                {bom_enhancement_select_statement}
            FROM einzelteile {bom_item_table_alias}
            INNER JOIN teile_stamm assembly ON 
                {bom_item_table_alias}.baugruppe=assembly.teilenummer AND 
                {bom_item_table_alias}.b_index=assembly.t_index
            {bom_item_view_join_statement}
            {bom_enhancement_sql_join_statement}
            WHERE {where_condition} AND {bom_enhancement_where_statement}
        """.format(
        where_condition=where_condition,
        bom_item_attrs=bom_item_attributes_select,
        part_table_alias=AbstractPlugin.COMPONENT_TABLE_ALIAS,
        part_attrs=part_attributes_select,
        bom_item_table_alias=AbstractPlugin.BOM_ITEM_TABLE_ALIAS,
        bom_enhancement_select_statement=bom_enhancement_select_statement,
        bom_enhancement_sql_join_statement=bom_enhancement_sql_join_statement,
        bom_enhancement_where_statement=bom_enhancement_where_statement,
        bom_item_view_join_statement=bom_item_view_join_statement
    )


def _get_select_statements(part_attributes):
    bom_keys = [fd.name for fd in bom.AssemblyComponent.GetTableKeys()]
    bom_item_attributes_select = ""
    for col_name in bom_keys:
        if col_name not in aliased_bom_item_attributes:
            if bom_item_attributes_select:
                bom_item_attributes_select = f"{bom_item_attributes_select}, {AbstractPlugin.BOM_ITEM_TABLE_ALIAS}.{col_name}"
            else:
                bom_item_attributes_select = f"{AbstractPlugin.BOM_ITEM_TABLE_ALIAS}.{col_name}"
    for col_name, alias_name in aliased_bom_item_attributes.items():
        if col_name in bom_keys:
            bom_item_attributes_select = f"{bom_item_attributes_select}, {AbstractPlugin.BOM_ITEM_TABLE_ALIAS}.{col_name} as {alias_name}"
    for col_name in get_virtual_attribute_names():
        # E075051: Ensure virtual attributes are SELECTed into the resulting record.
        bom_item_attributes_select = f"{bom_item_attributes_select}, {BOM_ITEM_VIEW_ALIAS}.{col_name}"

    component_attributes = []
    component_attributes.extend(default_part_attributes)
    part_keys = [fd.name for fd in items.Item.GetTableKeys()]
    component_attributes.extend([
        attr for attr in part_attributes
        if attr in part_keys and attr not in bom_keys and attr not in component_attributes
    ])
    part_attributes_select = ", ".join(
        [f"{AbstractPlugin.COMPONENT_TABLE_ALIAS}.{name}" for name in component_attributes])
    for bom_item_col_name, sql_select_name in get_joined_attribute_mapping().items():
        if bom_item_col_name not in component_attributes:
            part_attributes_select = f"{part_attributes_select}, {AbstractPlugin.COMPONENT_TABLE_ALIAS}.{sql_select_name} as {bom_item_col_name}"
    for col_name, alias_name in aliased_part_attributes.items():
        if col_name in part_keys:
            part_attributes_select = f"{part_attributes_select}, {AbstractPlugin.COMPONENT_TABLE_ALIAS}.{col_name} as {alias_name}"

    return bom_item_attributes_select, part_attributes_select


def flat_bom(*roots, **kwargs):
    """
    Return a RecordSet of all the bom positions present in the product
    structure of one of the roots. Computes the result efficiently
    making only one database query per bom level.

    If you want to filter or general enhance the flat_bom results see :ref:`enhancement_api`.

    :param positional arguments: instances of cs.vp.items.Item of which the flat boms
        have to be computed
    :type positional arguments: cs.vp.items.Item

    :keyword bom_enhancement: Used to enhance bom functionality. This includes filter with different plugins
        and extension to add extra data
    :type bom_enhancement: cs.vp.bom.enhancement.FlatBomEnhancement

    :keyword part_attributes: Attributes from the relation teile_stamm, which have
        to be joined in the result.

    :keyword levels: the levels for the flat_bom (default: -1 for all levels).
    :type levels: int

    :keyword sort_func: optional sort func for bom_items (default: None).
    :type sort: func

    :returns: a record set containing all the bom position in the product
        structure of one of the given roots
    :rtype: list[cdb.sqlapi.Record]
    """
    if (
            "variant_filter" in kwargs
            or "bomfilter" in kwargs
            or "bomfilter_func" in kwargs
            or "bomfilter_function" in kwargs
            or "additional_condition" in kwargs
            or "searched_item" in kwargs
    ):
        raise Exception(
            'The arguments ["variant_filter", "bomfilter", "bomfilter_func", "bomfilter_function",'
            + '"additional_condition", "searched_item", "bom_predicates_attr"] '
            + 'are not longer supported. Please use "bom_enhancement" or apply your filter on the result.'
        )

    bom_enhancement: FlatBomEnhancement = kwargs.get("bom_enhancement") or FlatBomEnhancement()
    if ComponentJoinPlugin not in bom_enhancement:
        bom_enhancement.add(ComponentJoinPlugin("as_saved"))

    bom_item_attributes_select, part_attributes_select = _get_select_statements(
        kwargs.get("part_attributes", [])
    )

    def query_bom_level(assembly_ids, max_level=-1, level=1, already_queried_assembly_oids=None):
        if already_queried_assembly_oids is None:
            already_queried_assembly_oids = set(assembly_ids)
        result = []
        next_level_assemblies = []
        for root_ids_chunk in chunk(assembly_ids, 30000):
            root_condition = str(items.Item.cdb_object_id.one_of(*root_ids_chunk)).replace(
                "cdb_object_id", "assembly.cdb_object_id"
            )
            query = _get_flat_bom_query(
                root_condition,
                bom_item_attributes_select,
                part_attributes_select,
                bom_enhancement
            )
            level_result = sqlapi.RecordSet2(table="einzelteile", sql=query)
            level_result = filter_by_read_access(level_result)
            for bom_position in level_result:
                result.append(bom_position)
                if bom_enhancement.resolve_bom_item_children(bom_position):
                    component_object_id = bom_position.item_object_id
                    if component_object_id not in already_queried_assembly_oids:
                       already_queried_assembly_oids.add(component_object_id)
                       next_level_assemblies.append(component_object_id)
        if bom_enhancement is not None:
            result = bom_enhancement.filter_bom_item_records(result)
        if next_level_assemblies and (-1 == max_level or level < max_level):
            result.extend(
                query_bom_level(
                    next_level_assemblies,
                    max_level,level+1,
                    already_queried_assembly_oids
                )
            )
        return result

    flat_bom = query_bom_level(
        [root.cdb_object_id for root in roots],
        kwargs.get("levels", -1)
    )
    sort_func = kwargs.get("sort_func", None)
    if sort_func:
        flat_bom = sorted(flat_bom, key=sort_func)
    return flat_bom


def bom_item_records(*bom_item_ids, **kwargs):
    """
    Return a RecordSet of all the bom positions for the given cdb_object_ids. The records are the same as
    for flat_bom.

    If you want to filter or general enhance the flat_bom results see :ref:`enhancement_api`.

    :param positional arguments: cdb_object_ids of bom_item to get the records for
    :type positional arguments: string

    :keyword bom_enhancement: Used to enhance bom functionality. This includes filter with different plugins
        and extension to add extra data
    :type bom_enhancement: cs.vp.bom.enhancement.FlatBomEnhancement

    :keyword part_attributes: Attributes from the relation teile_stamm, which have
        to be joined in the result.

    :returns: a record set containing all the bom positions for the given bom_item_ids
    :rtype: sqlapi.RecordSet2
    """

    bom_enhancement: FlatBomEnhancement = kwargs.get("bom_enhancement") or FlatBomEnhancement()
    if ComponentJoinPlugin not in bom_enhancement:
        bom_enhancement.add(ComponentJoinPlugin("as_saved"))

    bom_item_attributes_select, part_attributes_select = _get_select_statements(
        kwargs.get("part_attributes", [])
    )

    where_condition = str(AssemblyComponent.cdb_object_id.one_of(*bom_item_ids)).replace(
        "cdb_object_id", f"{AbstractPlugin.BOM_ITEM_TABLE_ALIAS}.cdb_object_id"
    )
    query = _get_flat_bom_query(
        where_condition,
        bom_item_attributes_select,
        part_attributes_select,
        bom_enhancement
    )
    return sqlapi.RecordSet2(table="einzelteile", sql=query)


def bom_item_record_dict(*bom_item_ids: list[str], **kwargs) -> dict[str, sqlapi.Record]:
    """
    Same as bom_item_records but returns a dictionary.
    The keys are of the BOM item's cdb_object_id and the value is the Record of the given BOM item.
    """
    records = bom_item_records(*bom_item_ids, **kwargs)
    result = {}
    for record in records:
        result[record['cdb_object_id']] = record
    return result


def flat_bom_dict(*roots, **kwargs):
    """
    Same as flat_bom but returns a dictionary.
    The keys are of the form (teilenummer, t_index) and the values are
    the children of the given item in the product structure.
    """
    components = flat_bom(*roots, **kwargs)
    result = collections.defaultdict(list)
    for comp in components:
        result[(comp.baugruppe, comp.b_index)].append(comp)
    return result


def get_path_sort_key(bom_component_path: list[Any]) -> list[tuple]:
    """
    Creates a sort key for an entire BOM component path. A path sort key is a list of sort key tuples returned
    by :meth:`bomqueries.get_sort_key`.

    :param bom_component_path: List that represents a BOM component path.

    :return: List of ints that represents a sorting key created by the BOM components' positions.
    """
    return [get_sort_key(comp) for comp in bom_component_path]


def get_sort_key(bom_component: Any) -> tuple | None:
    """
    Creates a sorting key for a BOM item or record. The key is a tuple consisting of the position, teilenummer
    and cdb_cdate of the object. If the object does not have a 'position' (e.g. when used for a BOM's root
    item), -inf is used instead.

    :param bom_component: The BOM component (BOM item, record or dict) to create the sort key for.

    :return: Key that can be used to sort a list of BOM item records.
    """

    if bom_component is None:
        return None

    # Get values from dicts, Records, AssemblyComponent and Item the same way.
    def get_or_fallback(attribute, fallback):
        try:
            attribute_value = bom_component[attribute]
            return attribute_value if attribute_value is not None else fallback
        except (AttributeError, KeyError):
            return fallback

    position: int | float = get_or_fallback('position', float('-inf'))
    component_no: str = get_or_fallback('teilenummer', '')
    creation_date: str = get_or_fallback('cdb_cdate', '')

    return position, component_no, creation_date


# -- utils --------------------------------------------------------------------


_bom_item_acc_is_active = None


def bom_item_acc_is_active():
    global _bom_item_acc_is_active
    if _bom_item_acc_is_active is None:
        rset = sqlapi.RecordSet2("cdb_auth_cl_cfg", "relation='einzelteile'")
        _bom_item_acc_is_active = len(rset) != 0
    return _bom_item_acc_is_active


def filter_by_read_access(bom_item_rset):
    if not bom_item_acc_is_active():
        return bom_item_rset

    result = []
    ac = util.ACAccessSystem("einzelteile")
    for rec in bom_item_rset:
        if ac.check(list(rec), [typeconversion.to_untyped_c_api(val) for val in rec.values()], "read"):
            result.append(rec)
    return result
