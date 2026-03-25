#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
# pylint: disable=too-many-instance-attributes

import hashlib
from builtins import str
from dataclasses import dataclass, field
from typing import Any, Callable, Self

from cs.variants import VariantSubPart
from cs.vp import items
from cs.vp.bom import AssemblyComponent, AssemblyComponentOccurrence


@dataclass
class StructureCompareData:
    """
    Hold all data regard to structure compare

    These class is used to transfer information's to the structure compare.
    Used for better separation in code
    """

    item_structure: list[Any] = field(default_factory=list)
    """
    The expected bom_item structure

    For detail see: cs.variants.api.reuse._get_first_level
    """

    occ_structure: dict[Any, Any] = field(default_factory=dict)
    """
    The expected occurrence structure

    For detail see: cs.variants.api.reuse._get_first_level
    """

    bom_item_attributes: list[str] = field(default_factory=list)
    """
    These are the attributes used for the bom_item

    Example:

    ['teilenummer', 't_index', 'position']
    """

    occurrence_only_attributes: list[str] = field(default_factory=list)
    """
    Occurrence only attributes used for compare

    Example:

    ['occurrence_id', 'assembly_path']
    """


KeyValue = Any
ListOfValues = list[Any]
Key = str
ListOfKeys = list[Key]
KeyValueStore = dict[Key, KeyValue]


class VariantBomNode:
    """
    Represents a node (bom_item) in the 100% variant bom
    """

    bom_item_keys = [
        "baugruppe",
        "b_index",
        "teilenummer",
        "t_index",
        # do not add menge to the keys at this point.
        # requires extra handling depending on whether the node has occurrences or not.
        # "menge",
    ]
    """
    All 'bom_item' keys are used for the checksum calculation and for the structure compare

    The attribute 'menge' is not included in this list. This attribute is added dynamically
    if necessary

    Important!: If the order is changed, the checksum is broken
    """

    item_keys = ["teilenummer", "t_index"]  # just for easier debugging

    assembly_keys = ["baugruppe", "b_index"]

    occurrence_keys = [
        "occurrence_id",
        "assembly_path",
    ]
    """
    All 'bom_item_occurrence' keys are used for the checksum calculation and for the structure compare

    Important!: If the order is changed, the checksum is broken
    """

    occurrence_blacklisted_keys = [
        "occurrence_id",
        "assembly_path",
        "cdb_object_id",
        "bompos_object_id",
    ]

    def __init__(self, value: items.Item | AssemblyComponent):
        """
        Creates a new variant bom node from the given `value`.
        Value can be either an Item (for the root node) or a AssemblyComponent
        """
        self.value: items.Item | AssemblyComponent = value
        """The object which is represented by this class"""
        self.parent: Self | None = None
        """The parent Node. None if this is the root node"""
        self.children: list[VariantBomNode] = []
        """List of children"""
        self.is_must_be_instantiated: bool = False
        self.has_sc_on_oc: bool = False
        self.ref_to_bom_item: AssemblyComponent | None = None
        self.reuse_children_lookup: dict[tuple[Any, ...], items.Item] = {}
        """Lookup for reuse; key = tuple of prim keys; value = item to reuse"""

        self.occurrences: list[AssemblyComponentOccurrence] = []
        """The filtered occurrences"""

        self.is_leaf: bool = True  # default True, set to false on reuse build

        self.has_occurrences: bool = False
        """Indicates if the maxbom bom_item has occurrences, no matter if filtered"""

        self.bom_items_to_delete: list[AssemblyComponent] = []
        """The items which must be deleted"""

        self.has_somewhere_deep_changed: bool = False

        self.compare_by_keys: Callable[
            [dict[str, Any], dict[str, Any]], bool
        ] = lambda lhs, rhs: all(lhs[key] == rhs[key] for key in self.bom_item_keys)

        self._checksum: str | None = None

    @property
    def bom_item_primary_key_values(self) -> KeyValueStore:
        """
        Return a dict with all values of the bom_item
        """
        return {each_key: self.value[each_key] for each_key in self.primary_keys}

    @property
    def primary_keys(self) -> ListOfKeys:
        """
        Return a list with primary keys from the value

        If the value is an Item then the item keys are returned
        If the value is a AssemblyComponent then the bom item keys are returned
        If neither an Item nor AssemblyComponent then an empty list is returned

        Note: "primary keys" does not mean the primary keys from the database.
        """
        if self.value is None:
            return []

        if isinstance(self.value, items.Item):
            return self.item_keys
        return self.bom_item_keys

    @property
    def is_no_old_existing(self) -> bool:
        return self.is_must_be_instantiated and self.ref_to_bom_item is None

    @property
    def is_original_needed(self) -> bool:
        return not self.is_must_be_instantiated and self.ref_to_bom_item is None

    def find_children_by_keys(self, keys: KeyValueStore) -> list[AssemblyComponent]:
        return [
            candidate
            for candidate in self.children
            if self.compare_by_keys(candidate.value, keys)
        ]

    def get_identification_keys(self) -> ListOfKeys:
        """
        Return the keys for identification (for reuse lookup and checksum)

        Adds attribute "menge" to the keys if node has no occurrences
        """
        keys = list(self.primary_keys)  # make a copy
        if not self.has_occurrences:
            keys.append("menge")
        return keys

    def get_identification_key_values(self) -> tuple[KeyValue, ...]:
        """Return the values as a list of tuples for identification (for reuse lookup)"""
        return tuple(self.value[key] for key in self.get_identification_keys())

    def remove_assembly_keys(self, list_with_keys: ListOfValues) -> ListOfValues:
        """Return a new list except all values defined in self.assembly_keys"""
        return [x for x in list_with_keys if x not in self.assembly_keys]

    @property
    def checksum(self) -> str:
        if self._checksum is None:
            list_of_checksums = self.calculate_checksum()
            self._checksum = hashlib.md5(  # nosec
                "".join(list_of_checksums).encode("utf-8")
            ).hexdigest()
        return self._checksum

    def calculate_checksum(self) -> list[str]:
        result_list = []

        for each_child_node in self.children:
            result_list.append(self._bom_item_to_string(each_child_node))
            for each_occ in each_child_node.occurrences:
                result_list.append(self._occ_to_string(each_occ))
            result_list.append(each_child_node.checksum)
        return result_list

    def _bom_item_to_string(self, variant_bom_node: Self) -> str:
        pkeys = list(variant_bom_node.get_identification_keys())
        return "".join([str(variant_bom_node.value[key]) for key in pkeys])

    def _occ_to_string(self, occ: AssemblyComponentOccurrence) -> str:
        return "".join([str(occ[key]) for key in self.occurrence_keys])

    def update_checksum(self, variability_model_id: str) -> None:
        """
        Update the checksum of this sub part

        Fixme: runs every inplace update - fix by load checksum while `_collect_cleanup_information`
         make a custom query for loading the `Components` including the checksum value
        """
        sub_part = VariantSubPart.ByKeys(
            instantiated_of_part_object_id=self.value.Item.cdb_object_id,
            part_object_id=self.ref_to_bom_item.Item.cdb_object_id,
            variability_model_id=variability_model_id,
        )
        if sub_part is not None and sub_part.structure_checksum != self.checksum:
            sub_part.Update(structure_checksum=self.checksum)

    def _get_key_values_for_structure_compare(
        self, child_node: Self, identification_keys: ListOfKeys
    ) -> tuple[KeyValue, ...]:
        """
        Return the key values for all children and the given keys

        Important note:
        Do not use the keys from the children. We must use the keys from the parent
        the keys from the children can be different (attribute "menge").
        Please see E065012.
        This is the reason why we get the identification keys as argument.
        """
        all_key_values = tuple(child_node.value[key] for key in identification_keys)

        if all_key_values in self.reuse_children_lookup:
            reuse_item = self.reuse_children_lookup[all_key_values]
            new_keys = []
            for each_pkname in identification_keys:
                if each_pkname == "teilenummer":
                    new_keys.append(reuse_item.teilenummer)

                elif each_pkname == "t_index":
                    new_keys.append(reuse_item.t_index)
                elif each_pkname in self.assembly_keys:
                    continue
                else:
                    new_keys.append(child_node.value[each_pkname])
            no_assembly_pkey_values = tuple(new_keys)

        else:
            # remove baugruppe and b_index from keys; not needed for structure compare
            no_assembly_pkey_values = tuple(
                child_node.value[x]
                for x in self.remove_assembly_keys(identification_keys)
            )
        return no_assembly_pkey_values

    def get_structure_for_compare(self) -> StructureCompareData:
        """Return the data for structure comparing"""
        structure_to_match = StructureCompareData()
        structure_to_match.bom_item_attributes = self.remove_assembly_keys(
            self.get_identification_keys()
        )

        structure_to_match.occurrence_only_attributes = list(self.occurrence_keys)

        for each_children_node in self.children:
            key_values = self._get_key_values_for_structure_compare(
                each_children_node, self.get_identification_keys()
            )

            structure_to_match.item_structure.append(key_values)

            # occ
            structure_to_match.occ_structure[key_values] = [
                tuple(y[x] for x in self.occurrence_keys)
                for y in each_children_node.occurrences
            ]
        return structure_to_match


def get_key_dict(for_bom_item: AssemblyComponent) -> KeyValueStore:
    """Return a key - value dict contains all the keys from VariantBomNode.bom_item_keys"""
    result = {
        each_key: for_bom_item[each_key] for each_key in VariantBomNode.bom_item_keys
    }
    return result
