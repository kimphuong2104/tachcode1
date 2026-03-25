#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cs.variants.api.variant_bom_node import VariantBomNode

if TYPE_CHECKING:
    from cs.variants.items import AssemblyComponent, AssemblyComponentOccurrence


class InstantiateOptions:
    #  Additional attributes for bom item to update during reinstantiate
    #
    # Important!
    # Do not add primary keys or attribute 'menge'!
    #
    # These Attributes have a special meaning.
    #
    # For example:Attribute 'menge' is calculated automatically based on the occurrence and
    # is used in structure check for reuse
    # Adding this here will be result in a weird behaviour
    ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM: list[str] = []

    # Additional attributes for bom item occurrences to update during reinstantate
    #
    # Important!
    # Do not add primary keys
    ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE: list[str] = []

    @staticmethod
    def get_bom_item_attributes_to_update(
        bom_item: AssemblyComponent,
    ) -> dict[Any, Any]:
        """
        return a dict with all values of the bom_item to be updated
        :param bom_item: AssemblyComponent

        blacklisted attributes (pk-keys and menge) are filtered

        :return: dict with keys to update and the values from bom_item
        :rtype: dict
        """
        all_blacklisted_keys = list(VariantBomNode.bom_item_keys) + ["menge"]
        return {
            each_key: bom_item[each_key]
            for each_key in InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM
            if each_key not in all_blacklisted_keys
        }

    @staticmethod
    def get_bom_item_occurrences_attributes_to_update(
        bom_item_occurrence: AssemblyComponentOccurrence,
    ) -> dict[Any, Any]:
        """
        return a dict with all values of the bom_item_occurrence to be updated
        :param bom_item_occurrence: AssemblyComponentOccurrence
        :return: dict with keys to update the values from occurrence
        :rtype: dict
        """
        all_blacklisted_keys = VariantBomNode.occurrence_blacklisted_keys
        return {
            each_key: bom_item_occurrence[each_key]
            for each_key in InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE
            if each_key not in all_blacklisted_keys
        }
