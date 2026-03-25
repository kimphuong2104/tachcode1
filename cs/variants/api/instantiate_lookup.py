# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import logging
from operator import attrgetter
from typing import Any

from cdb.sqlapi import Record
from cs.variants import VariantSubPart
from cs.variants.api import helpers
from cs.variants.api.constants_api import OBSOLETE_CHECKSUM_KEY
from cs.variants.api.filter import BomPredicatesAttrFlatBomPlugin, VariantFilter
from cs.variants.api.instantiate import get_instantiated_of
from cs.variants.api.reuse import compare_structure
from cs.variants.api.variant_bom_node import VariantBomNode, get_key_dict
from cs.vp import items
from cs.vp.bom import AssemblyComponent, bomqueries
from cs.vp.bom.enhancement import FlatBomEnhancement
from cs.vp.bom.enhancement.plugin import AbstractPlugin

LOG = logging.getLogger(__name__)


class AssemblyImprecisePlugin(AbstractPlugin):
    """only load bom_items where the assembly is not imprecise"""

    def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
        return bom_item_record.is_imprecise == 0


class InstantiateLookup:
    """
    hold all information regard to (re)instantiate
    """

    def __init__(self, maxbom, variant):
        self.maxbom = maxbom
        self.variant = variant
        self.variant_bom: VariantBomNode = None
        self.reinstantiate_lookup = {}

        self.variant_filter = VariantFilter(variant)

        from cs.variants.api import VariantsClassification

        variant_classification = VariantsClassification(
            class_codes=self.variant_filter.classification["assigned_classes"]
        )
        self.variant_driven_props = (
            variant_classification.get_variant_driving_properties()
        )

    def build_reuse(self):
        """
        build all information needed for reuse

        In order for this method to work, method `build_variant_bom`
        must have been run first.
        """
        self._build_reuse(self.variant_bom)

    def build_variant_bom(self):
        """builds the complete variant bom"""
        flat_bom_dict = self._get_flat_bom_with_occurrence()

        self.variant_bom = VariantBomNode(self.maxbom)
        self._build_variant_bom(self.variant_bom, flat_bom_dict)

    def collect_modifications(self, part_to_reinstantiate):
        """
        collect the information to clean up the instantiated part

        This method must run after the build for reuse

        :return:
        """
        all_nodes = [(self.variant_bom, part_to_reinstantiate)]
        while all_nodes:
            variant_bom_node, current_children_instance = all_nodes.pop()
            self._collect_cleanup_information(
                variant_bom_node, current_children_instance
            )
            for each_variant_bom_node in variant_bom_node.children:
                self._collect_modifications(each_variant_bom_node, all_nodes)

    def _collect_modifications(self, each_variant_bom_node, all_nodes_ref):
        if each_variant_bom_node.is_no_old_existing:
            # make it new or reuse an existing
            # the old one is from maxbom
            # or added after instantiated (maybe from different rule or manually)
            self._bubble_up_has_somewhere_deep_changed(each_variant_bom_node)

        elif each_variant_bom_node.is_original_needed:
            # switch back to the original from maxbom
            self._bubble_up_has_somewhere_deep_changed(each_variant_bom_node)

        else:
            # if we enabled reuse then we have to check for changes on occurrences
            if helpers.is_reuse_enabled() and not self._compare_occ(
                each_variant_bom_node
            ):
                self._bubble_up_has_somewhere_deep_changed(each_variant_bom_node)

            if each_variant_bom_node.is_must_be_instantiated:
                all_nodes_ref.append(
                    (
                        each_variant_bom_node,
                        each_variant_bom_node.ref_to_bom_item.Item,
                    )
                )

    def _compare_occ(self, variant_bom_node):
        """
        compares the occurrences from the node with the occurrences from the ref_to_bom_item

        if maxbom has no occurrences then the attribute 'menge' is compared

        :param variant_bom_node: the node
        :type variant_bom_node: VariantBomNode
        :return: True if there are equal, False if not equal
        """
        # if there are no occurrences we must compare the 'menge'. E073446
        if not variant_bom_node.has_occurrences:
            return (
                variant_bom_node.ref_to_bom_item.menge != variant_bom_node.value.menge
            )

        prim_keys = variant_bom_node.occurrence_keys
        all_occ_from_instance = [
            tuple(each_occ[key] for key in prim_keys)
            for each_occ in variant_bom_node.ref_to_bom_item.Occurrences
        ]

        all_occ_from_node = [
            tuple(each_occ[key] for key in prim_keys)
            for each_occ in variant_bom_node.occurrences
        ]

        return set(all_occ_from_instance) == set(all_occ_from_node)

    def _bubble_up_has_somewhere_deep_changed(self, variant_bom_node):
        if not helpers.is_reuse_enabled():
            # we do not need this information without reuse
            return

        all_nodes = list([variant_bom_node])

        while all_nodes:
            current_node = all_nodes.pop()
            if current_node.has_somewhere_deep_changed:
                return

            current_node.has_somewhere_deep_changed = True

            if current_node.parent is not None:
                all_nodes.append(current_node.parent)

    def _collect_cleanup_information(self, variant_bom_node, instance):
        """
        collect cleanup information about the instance

        logic for reinstantiate: if a component is not in variant_bom
         - if it isn't an instance, delete it
         - if it's an instance, but its maxbom is not in the variant bom, delete it
         - if it's an instance, but its maxbom is not in self.is_must_be_instantiated, delete it
         - otherwise reinstantiate it

        :param variant_bom_node: the node
        :type variant_bom_node: cs.variants.api.variant_bom_node.VariantBomNode
        :param instance: the instance to clean up
        :type instance: cs.vp.items.Item
        :return:
        """
        for each_instance_bom_item in instance.Components:
            keys = dict(
                get_key_dict(each_instance_bom_item),
                baugruppe=variant_bom_node.value.teilenummer,
                b_index=variant_bom_node.value.t_index,
            )
            bom_items_found = variant_bom_node.find_children_by_keys(keys)

            if len(bom_items_found) == 1:
                # found original from maxbom
                if bom_items_found[0].is_must_be_instantiated:
                    # now has a selection condition
                    self._mark_bom_item_to_delete(
                        variant_bom_node, each_instance_bom_item
                    )
                else:
                    bom_items_found[0].ref_to_bom_item = each_instance_bom_item
                continue

            if not bom_items_found:
                # Not able to find bom_item in maxbom. So it could be possible:
                #    - no more existent -> delete
                #    - could be a subassembly that was instantiated
                #       -> check instantiated of
                #       -> store as ref
                copy_of_id = get_instantiated_of(
                    self.variant.variability_model_id,
                    each_instance_bom_item.Item.cdb_object_id,
                )
                res = [
                    x
                    for x in variant_bom_node.children
                    if x.value.Item.cdb_object_id == copy_of_id
                ]
                variant_part_node = res[0] if len(res) == 1 else None
                if variant_part_node is None:
                    # manual added
                    # no longer exists in maxbom
                    self._mark_bom_item_to_delete(
                        variant_bom_node, each_instance_bom_item
                    )

                else:
                    # previously instantiated
                    if variant_part_node.is_must_be_instantiated:
                        variant_part_node.ref_to_bom_item = each_instance_bom_item
                    else:
                        self._mark_bom_item_to_delete(
                            variant_bom_node, each_instance_bom_item
                        )

                    variant_part_node.old_instantiated = True

                continue
            raise Exception(  # pylint: disable=broad-exception-raised
                # todo: address to broad exception
                "Found more than one bom_items in maxbom for keys {0}. result: {1}".format(
                    keys, bom_items_found
                )
            )

    def _mark_bom_item_to_delete(self, variant_bom_node, bom_item):
        variant_bom_node.bom_items_to_delete.append(bom_item)
        self._bubble_up_has_somewhere_deep_changed(variant_bom_node)

    def _query_potential_sub_parts(
        self, part_object_id: str, checksum: str
    ) -> list[VariantSubPart]:
        """
        Return a list of sub_parts with matching checksum

        The result is sorted by checksum.
        This ensures that all magic keys are at the end of the list.
        This guarantees that the real checksum object is tested first

        Returns a list of VariantSubPart
        """
        result = VariantSubPart.KeywordQuery(
            instantiated_of_part_object_id=part_object_id,
            variability_model_id=self.variant.variability_model_id,
            structure_checksum=[checksum, OBSOLETE_CHECKSUM_KEY],
        )
        # logging
        found_obs = [
            obs for obs in result if obs.structure_checksum == OBSOLETE_CHECKSUM_KEY
        ]
        if found_obs:
            LOG.info(
                "found '%s' potential sub parts with marked as '%s' "
                "(instantiated_of_part_object_id=%s, variability_model_id=%s",
                len(found_obs),
                OBSOLETE_CHECKSUM_KEY,
                part_object_id,
                self.variant.variability_model_id,
            )
        # make sure all the magic keys are at the end of the list
        return sorted(
            result, key=lambda v: v.structure_checksum == OBSOLETE_CHECKSUM_KEY
        )

    def _build_reuse(self, initial_node):
        to_resolve = list(initial_node.children)
        all_childs = []

        # go deep to the leaves before run logic.
        while to_resolve:
            current_node = to_resolve.pop()

            if current_node.is_leaf:
                continue

            all_childs.append(current_node)
            to_resolve.extend(current_node.children)

        while all_childs:
            current_node = all_childs.pop()
            if current_node.parent is None:
                continue

            # query by checksum
            potential_sub_parts = self._query_potential_sub_parts(
                current_node.value.Item.cdb_object_id, current_node.checksum
            )

            if not potential_sub_parts:
                continue

            structure_to_match = current_node.get_structure_for_compare()
            found_item = compare_structure(
                structure_to_match,
                [x.part_object_id for x in potential_sub_parts],
            )
            if found_item:
                # update checksum if magic key
                # we have to find it in the list of potential_sub_parts
                sub_part = next(
                    (
                        x
                        for x in potential_sub_parts
                        if x.instantiated_of_part_object_id
                        == current_node.value.Item.cdb_object_id
                        and x.variability_model_id == self.variant.variability_model_id
                        and x.part_object_id == found_item.cdb_object_id
                    ),
                    None,
                )
                if sub_part is None:
                    # ops, there is a major error!
                    raise ValueError(
                        "sub_part is None. This means the structure check founds an item but the"
                        "found item is not in the list of 'potential_sub_parts'."
                        "Possible problem could be the condition are not correct to find the"
                        "matching sub_part inside the 'potential_sub_parts' list"
                    )
                if sub_part.structure_checksum == OBSOLETE_CHECKSUM_KEY:
                    LOG.info(
                        "updated already instantiated part '%s@%s' marked as '%s' with new checksum",
                        found_item.teilenummer,
                        found_item.t_index,
                        OBSOLETE_CHECKSUM_KEY,
                    )
                    sub_part.Update(structure_checksum=current_node.checksum)

                current_node.parent.reuse_children_lookup[
                    current_node.get_identification_key_values()
                ] = found_item

    def _set_must_be_instantiated_up(self, start_node):
        all_nodes = list([start_node])
        while all_nodes:
            current_node = all_nodes.pop()

            current_node.is_must_be_instantiated = True
            if current_node.parent is not None:
                all_nodes.append(current_node.parent)

    def _build_variant_bom(self, init_variant_bom_node, flat_bom_dict):
        all_nodes = list([init_variant_bom_node])

        while all_nodes:
            variant_bom_node = all_nodes.pop()
            for bom_record in flat_bom_dict[
                (variant_bom_node.value.teilenummer, variant_bom_node.value.t_index)
            ]:
                # `is_leaf` must be set regardless of whether children are filtered or not.
                # Otherwise, if all the children are filtered the node is seen as leaf.
                # In that case reuse would not find it
                variant_bom_node.is_leaf = False

                if self.variant_filter.eval_bom_item(bom_record):
                    ac = AssemblyComponent.FromRecords([bom_record])[0]
                    cnode = VariantBomNode(ac)
                    cnode.parent = variant_bom_node
                    variant_bom_node.children.append(cnode)
                    cnode.has_sc_on_oc = bom_record["has_sc_on_oc"] == 1
                    if bom_record[
                        "has_sc_on_oc"
                    ] == 1 or self.variant_filter.has_selection_condition(bom_record):
                        self._set_must_be_instantiated_up(cnode.parent)

                    # reuse
                    self._load_occurrences(cnode)

                    all_nodes.append(cnode)
                else:
                    self._set_must_be_instantiated_up(variant_bom_node)

    def _get_flat_bom_with_occurrence(self) -> dict[tuple[str, str], list[Any]]:
        """return a flat_bom_dict with the occurrence `has_sc_on_oc` flag"""
        part_attributes = [fd.name for fd in items.Item.GetTableKeys()]

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(BomPredicatesAttrFlatBomPlugin())
        bom_enhancement.add(AssemblyImprecisePlugin())

        # we need the complete unfiltered bom, because otherwise self.is_must_be_instantiated
        # will be incomplete
        # The flat_bom must be sorted according to the same keys and order as used for the checksum.
        flat_bom = bomqueries.flat_bom_dict(
            self.maxbom,
            part_attributes=part_attributes,
            bom_enhancement=bom_enhancement,
            sort_func=attrgetter(*VariantBomNode.bom_item_keys),
        )
        return flat_bom  # type: ignore

    def _load_occurrences(self, variant_bom_node: VariantBomNode) -> None:
        """
        load the occurrences for one bom_item, eval it with the variant_filter
        and store it in the `variant_bom_node`

        :param variant_bom_node:
        :return:
        """
        # parent is None = root, root has no occurrences
        if variant_bom_node.parent is None:
            return

        # FIXME: optimize sql roundtrips
        old_bom_item_occurrences = variant_bom_node.value.Occurrences.Execute()
        if not old_bom_item_occurrences:
            return
        variant_bom_node.has_occurrences = True

        # sorting the occurrences is important!
        # if the order is not stable then the checksum does not match
        for occurrence in sorted(
            old_bom_item_occurrences,
            key=attrgetter(*variant_bom_node.occurrence_keys),
        ):
            if (
                variant_bom_node.has_sc_on_oc
                # eval_bom_item will also work with occurrence because it just needs a cdb_object_id
                and not self.variant_filter.eval_bom_item(occurrence)
            ):
                continue

            variant_bom_node.occurrences.append(occurrence)
