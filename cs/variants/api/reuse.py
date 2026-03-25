# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from typing import Any, Optional

from cdb import sqlapi
from cs.variants.api.variant_bom_node import StructureCompareData
from cs.vp.bom import AssemblyComponentOccurrence
from cs.vp.items import Item

CdbObjectId = str


def compare_structure(
    structure_to_match: StructureCompareData,
    item_object_ids_to_check: list[CdbObjectId],
) -> Optional[Item]:
    """
    compares the structure

    Notes:
        - item_object_ids_to_check defines the order to check the items
        - object_ids with without existing items are skipped

    :param structure_to_match: the structure data
    :param item_object_ids_to_check: list of object_ids of items
    :return: the first Item that matches or None if nothing matches
    """
    items_to_check = Item.KeywordQuery(cdb_object_id=item_object_ids_to_check)

    def find_item(object_id: CdbObjectId) -> Item | None:
        result = [item for item in items_to_check if item.cdb_object_id == object_id]
        if result:
            return result[0]
        return None

    def check_occ(each_keys_tuple: tuple[Any, ...]) -> bool:
        right_occ = item_structure.get(each_keys_tuple, [])
        left_occ = structure_to_match.occ_structure.get(each_keys_tuple, [])

        return set(left_occ) == set(right_occ)

    for each_item_object_id in item_object_ids_to_check:
        each_item = find_item(each_item_object_id)
        if each_item is None:
            # skip this item because it does not exist
            continue

        item_structure = _get_first_level(
            each_item,
            structure_to_match.bom_item_attributes,
            structure_to_match.occurrence_only_attributes,
        )

        # compare
        if set(structure_to_match.item_structure) == set(item_structure.keys()) and all(
            check_occ(x) for x in structure_to_match.occ_structure
        ):
            return each_item

    return None


def _get_first_level(
    item: Item, bom_item_attributes: list[Any], occurrence_only_attributes: list[Any]
) -> dict[tuple[Any, ...], list[tuple[Any, ...]]]:
    """
    return the first level of bom_items with occurrences

    this will return a dict containing the `bom_item_attributes` as tuple
    of the first level of children and a list of `occurrence_attributes`

    .. code-block:: pycon
        >>> from cs.variants.api import reuse
        >>> reuse._get_first_level(
        ...     item,
        ...     ["teilenummer", "t_index", "position"],
        ...     ["occurrence_id"],
        ... )
        {
            ("9508581", "", 40L):
                [
                    ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC0",),
                    ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC1",)
                ],
            ("9508579", "", 30L):
                [
                    ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_OC0",)
                ],
            ("9508576", "", 10L):
                [
                    ("VAR_TEST_REINSTANTIATE_PART_1_OC0",)
                ],
            ("9508580", "", 20L):
                [
                    ("VAR_TEST_REINSTANTIATE_PART_2_OC0",),
                    ("VAR_TEST_REINSTANTIATE_PART_2_OC1",)
                ]
        }
        >>>

    * bom_item_attributes must be the same as used for lookup index

    :param item: the item
    :param bom_item_attributes: list of keys for bom_item to retrieve
    :param occurrence_only_attributes: list of occurrence specific keys to retrieve
    """
    data: dict[tuple[Any, ...], list[tuple[Any, ...]]] = {}

    sqlstmt = (
        "SELECT * FROM einzelteile "
        "WHERE baugruppe='{baugruppe}' AND b_index='{b_index}'"
    )
    sqlstmt = sqlstmt.format(baugruppe=item.teilenummer, b_index=item.t_index)

    result_query = sqlapi.RecordSet2("einzelteile", sql=sqlstmt)

    if not result_query:
        return data

    bompos_ids = [each_record["cdb_object_id"] for each_record in result_query]
    condition = AssemblyComponentOccurrence.bompos_object_id.one_of(*bompos_ids)
    result_occ = sqlapi.RecordSet2("bom_item_occurrence", condition)

    for each_record in result_query:
        tuple_of_keys = tuple(each_record[key] for key in bom_item_attributes)

        data[tuple_of_keys] = [
            tuple(each_occ[key] for key in occurrence_only_attributes)
            for each_occ in result_occ
            if each_occ["bompos_object_id"] == each_record["cdb_object_id"]
        ]

    return data
