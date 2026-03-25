#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from dataclasses import dataclass
from typing import Callable

from cdb import ue
from cdb.sqlapi import Record
from cs.variants.api.filter import (
    BomPredicatesAttrFlatBomPlugin,
    CsVariantsFilterContextPlugin,
)
from cs.vp.bom import AssemblyComponentOccurrence
from cs.vp.bom.enhancement import FlatBomEnhancement
from cs.vp.bom.enhancement.plugin import AbstractPlugin


class InVariantPlugin(AbstractPlugin):
    def __init__(
        self, variant_filter_context_plugin: CsVariantsFilterContextPlugin
    ) -> None:
        self.variant_filter_context_plugin = variant_filter_context_plugin

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        for each in bom_item_records:
            each.in_variant = (
                self.variant_filter_context_plugin.variant_filter.eval_bom_item(each)
            )

        return bom_item_records


@dataclass
class OccurrenceWalkGeneratorResult:
    """
    Represents one result yielded by OccurrenceWalkGenerator.walk()

    - path: the occurrence path (list of strings)
            eg.: '["modular unit with pressure reservoir.1", "modular unit base assembly.1"]'
            the order is from top to down!
    - active: true if the path is not filtered, False otherwise
    - bom_item: the bom_item record (from flat_bom)
    - occurrence_obj: the occurrence obj if bom_item has an occurrence, default=None

    """

    path: tuple[str, ...]
    active: bool
    bom_item: Record
    occurrence_obj: AssemblyComponentOccurrence = None


MissingOccurrenceCallbackType = Callable[[Record, str], None]


class OccurrenceWalkGenerator:
    """
    Generator to iterate over all occurrences in a maxbom

    This is part of the API to open a variant in an CAD system through the workspace

    """

    def __init__(
        self, maxbom, variant_filter_plugin: CsVariantsFilterContextPlugin
    ) -> None:
        self.maxbom = maxbom
        self.variant_filter_plugin = variant_filter_plugin
        self.bom_enhancement = FlatBomEnhancement()
        self.bom_enhancement.add(InVariantPlugin(variant_filter_plugin))
        self.bom_enhancement.add(BomPredicatesAttrFlatBomPlugin())
        self._handle_missing_occurrence_callback: MissingOccurrenceCallbackType = (
            self._handle_missing_occurrence_callback_default
        )

    def set_handle_missing_occurrence_callback(
        self, callback: MissingOccurrenceCallbackType
    ) -> None:
        """
        Callback to be called if a bom_item has no occurrence information

        The callback will be called immediately if a bom_node has
            - no occurrences
            - and the occurrence attribute from the bom_node himself is empty (None)

        The callback receives the following arguments:
            - bom_item: the bom_item (as a record from flat_bom)
            - path: tuple with the current occurrence path (the current bom_node excluded)

        :param callback: the callback
        :return:
        """
        self._handle_missing_occurrence_callback = callback

    def add_bom_filter_plugin(self, plugin: AbstractPlugin) -> None:
        """
        Add a plugin to the bom filter plugins

        This plugin is added to the bom filter plugins to filter the flat_bom

        Example of usage:

        .. code-block:: python

            from cs.vp.bom.bomqueries_filter import BomFilterPlugin


            class CADSourceBomFilterPlugin(BomFilterPlugin):
                def __init__(self, cad_source):
                    self.cad_source = cad_source

                def get_bom_item_where_stmt_extension(self, bom_item_table_alias):
                    return "{0}.cadsource = '{1}'".format(bom_item_table_alias, self.cad_source)


            bom_filter_plugin = CADSourceBomFilterPlugin(self.cad_source)
            self.add_bom_filter_plugin(bom_filter_plugin)

        """
        self.bom_enhancement.add(plugin)

    def walk(self):
        """
        Yield a `cs.variants.api.occurrence_walk_generator.OccurrenceWalkGeneratorResult` object
        for every occurrence in the maxbom

        This method does not filter the maxbom like the cs.variants does, but mark an occurrence as filtered

        If a bom_item has no occurrences and the bom_items attribute `occurence_id` is None,
        then the `set_handle_missing_occurrence_callback` is called if given,
        otherwise an ue.Exception is raised
        :return:
        """
        flat_bom_dict = self._flat_bom_dict()
        for each in self._walk(self.maxbom, flat_bom_dict):
            yield each

    def _walk(self, bom_node, flat_bom_dict, path=(), parent_in=True):
        bom_items = flat_bom_dict[(bom_node.teilenummer, bom_node.t_index)]
        for each_bom_item in bom_items:
            is_in = each_bom_item.in_variant and parent_in

            all_occurrences = self._load_occurrences(each_bom_item)

            if not all_occurrences:
                # we have no occurrence for this bom_item.
                # in this case we expect the bom_item has the correct occurrence_id
                for each in self._walk_bom_item(
                    each_bom_item, flat_bom_dict, path, is_in
                ):
                    yield each

            else:
                for each in self._walk_with_occurrences(
                    each_bom_item, flat_bom_dict, path, is_in, all_occurrences
                ):
                    yield each

    def _walk_bom_item(self, bom_item, flat_bom_dict, path, is_in):
        if bom_item.occurence_id is None:
            self._handle_missing_occurrence_callback(bom_item, path)

        new_path = path + (bom_item.occurence_id,)
        result_item = OccurrenceWalkGeneratorResult(new_path, is_in, bom_item)
        yield result_item

        for result in self._walk(bom_item, flat_bom_dict, new_path, is_in):
            yield result

    def _walk_with_occurrences(self, bom_item, flat_bom_dict, path, is_in, occurrences):
        for each_occ in occurrences:
            new_path = path + (each_occ.occurrence_id,)
            result_item = OccurrenceWalkGeneratorResult(
                new_path, is_in and each_occ.in_variant, bom_item, each_occ
            )
            yield result_item

            for result in self._walk(bom_item, flat_bom_dict, new_path, is_in):
                yield result

    @staticmethod
    def _handle_missing_occurrence_callback_default(bom_item: Record, path: str):
        """default implementation for missing occurrence"""
        raise ue.Exception(
            "cs_variants_no_occ_id", bom_item.teilenummer, bom_item.t_index
        )

    def _flat_bom_dict(self):
        from cs.vp.bom.bomqueries import flat_bom_dict

        return flat_bom_dict(
            self.maxbom,
            bom_enhancement=self.bom_enhancement,
        )

    def _load_occurrences(self, bom_node_record):
        bom_item_occurrences = AssemblyComponentOccurrence.KeywordQuery(
            bompos_object_id=bom_node_record.cdb_object_id,
        )

        for occurrence in bom_item_occurrences:
            occurrence.in_variant = not (
                bom_node_record.has_sc_on_oc
                and not self.variant_filter_plugin.variant_filter.eval_bom_item(
                    occurrence
                )
            )

        return bom_item_occurrences
