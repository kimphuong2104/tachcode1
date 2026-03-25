#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

from cdb.cad import getCADConfValue, isTrue
from cdb.objects import ByID

from cs.vp.cad import CADVariant
from cs.wsm.virtualworkspace import FilenameNotUnique

from cs.vp.bomcreator import msg
from cs.vp.bomcreator.bom import OccurrenceInfo
from cs.vp.bomcreator.bomreader import make_recursive_reader_type, ResultOrder
from cs.wsm.bom.wsmbomreader import WSMBOMReader, filename_of_record
from cs.wsm.bom.wsmbomreader import get_appinfo_tree

import os
import six


class ComponentStructureBOMReader(WSMBOMReader):
    """
    A BOM reader that traverses the tree of occurrences
    and adds a BOM position for every directly referenced document.

    To find the correct part of a referenced document, it typically uses
    `teilenummer`, `t_index`, but also respects CAD variants if
    a variant id is given in a CAD reference.
    """

    follow_variants_only_on_toplevel = True

    def __init__(self, bom_context, factory, custom_state):
        WSMBOMReader.__init__(self, bom_context, factory, custom_state)
        self.log(
            "started on document %s, for part %s-%s"
            % (bom_context.object_id, bom_context.teilenummer, bom_context.t_index)
        )
        self._factory = factory
        self._context = bom_context
        self.boms = []
        self.referenced_docs = []
        self.referenced_variant_ids = []

        self.use_occurrence_quantities = isTrue(
            getCADConfValue(u"STL Use Occurrence Quantities", bom_context.cadsource)
        )

        if self.anchor_file is None:
            self.boms = [factory.create_BOM()]
        else:
            # we need referenced documents:
            doc = ByID(bom_context.object_id)
            workspace_refreshed = False

            # first, find out which variants we are interested in
            is_top_level = custom_state.get("current_depth", 1) == 1
            if not self.follow_variants_only_on_toplevel or is_top_level:
                variants = self.get_variants_with_assigned_assembly(doc)
                create_bom_from_non_variant, variants = self.filter_variants(
                    doc, variants, bom_context.global_user_hints
                )
                if create_bom_from_non_variant:
                    variants.insert(0, None)
            else:
                variants = [bom_context.variant_id]

            for variant_id in variants:
                if not variant_id:
                    bom = factory.create_BOM()
                else:
                    assembly = self.get_assembly_from_document(
                        doc,
                        variant_id,
                        bom_context.global_user_hints,
                        ignore_singleton_variant=not is_top_level,
                    )
                    if assembly is None:
                        continue
                    bom = factory.create_BOM_for_assembly(assembly)
                    bom.variantId = variant_id
                self.boms.append(bom)
                if not workspace_refreshed:
                    self.refresh_workspace_with_references(
                        self.workspace, bom.user_hints
                    )
                    workspace_refreshed = True

                for ref_info in self.walk_component_structure(
                    self.anchor_file, bom.user_hints, variant_id=variant_id
                ):
                    (doc_id, occ_variant_id, occurrence) = ref_info
                    self.log(
                        "Processing reference: doc %s, variant %s"
                        % (doc_id, occ_variant_id)
                    )
                    item_doc = self.get_referenced_doc(doc_id, bom.user_hints)
                    if item_doc is None:
                        continue

                    self.process_component(bom, item_doc, occurrence)

    def walk_component_structure(self, assembly_rec, user_hints, variant_id=None):
        """Recursively walks through the given assembly's occurrence structure.
        Yields the object id of every document
        which contains a referenced anchor file.
        """
        assembly_filename = filename_of_record(assembly_rec)
        assembly_obj_id = assembly_rec.getObject().cdbf_object_id
        self.log("Walking through assembly %s" % assembly_obj_id)
        appinfo_tree = get_appinfo_tree(assembly_rec, self.workspace, user_hints)
        if appinfo_tree is None:
            self.log(
                "Assembly ignored because it does not have appinfo"
                " or the appinfo is currently not available"
            )
            return

        occurrences = self.get_sorted_occurrences_from_appinfo(appinfo_tree, variant_id)
        self.log("Found %d occurrences." % len(occurrences))

        for occurrence in occurrences:
            self.log(u"Occurrence %s" % occurrence.getItemName())
            if self.ignore_occurrence(occurrence):
                self.log("Occurrence %s ignored for BOM." % occurrence.getName())
                continue
            cad_ref = occurrence.getCadReference()
            if cad_ref is None:
                self.log("Occurrence does not have a CAD reference.")
                continue
            occ_filename = os.path.normpath(cad_ref.getPath())
            occ_variant_id = cad_ref.getVariantId()
            if occ_variant_id is not None:
                occ_variant_id = occ_variant_id.strip()
            occ_variant_name = cad_ref.getVariantName()
            if occ_variant_name is not None:
                occ_variant_name = occ_variant_name.strip()
            self.log(u"Occurrence filename: %s" % occ_filename)
            assembly_dir = assembly_rec.getDirectory()
            try:
                referenced_rec = self.workspace.getFileRecord(
                    occ_filename, assembly_dir, throwIfNotUnique=True
                )
                if referenced_rec is None:
                    obj = ByID(self._context.object_id)
                    desc = obj.GetDescription()
                    user_hints.append(
                        msg("WSM_BOM_not_in_workspace") % (occ_filename, desc)
                    )
                    continue
            except FilenameNotUnique as e:
                obj = ByID(self._context.object_id)
                desc = obj.GetDescription()
                user_hints.append(
                    msg("WSM_BOM_filename_not_unique")
                    % (occ_filename, desc, ", ".join(e.docs))
                )
                continue

            ref_obj_id = referenced_rec.getObject().cdbf_object_id
            # are we still in the same document?
            if ref_obj_id == assembly_obj_id:
                # recurse into structure
                for result in self.walk_component_structure(
                    referenced_rec, user_hints, variant_id=occ_variant_id
                ):
                    yield result
            else:
                if referenced_rec.getObject().isPrimary():
                    quantity = 1
                    if self.use_occurrence_quantities:
                        quantity = occurrence.getQuantity()
                        if quantity is None:
                            quantity = 1
                    for _ in six.moves.range(quantity):
                        for result in self._yield_occurrence(
                            ref_obj_id,
                            occurrence,
                            occ_filename,
                            assembly_filename,
                            occ_variant_id,
                            occ_variant_name,
                        ):
                            yield result
                else:
                    user_hints.append(msg("WSM_BOM_not_a_primary_file") % occ_filename)

    def _yield_occurrence(
        self,
        ref_obj_id,
        occurrence,
        occ_filename,
        assembly_filename,
        occ_variant_id,
        occ_variant_name,
    ):
        occ_id = occurrence.getItemName()
        # TECHDEBT: supporting different versions of cs.bomcreator
        try:
            tmatrix = ""
            matrix_object = occurrence.getTMatrix()
            if matrix_object:
                tmatrix = matrix_object.getMatrixAsString()
            try:
                occ_info = OccurrenceInfo(
                    occ_id,
                    occ_filename,
                    assembly_filename,
                    occ_variant_id,
                    tmatrix,
                    occ_variant_name,
                )
            except (TypeError, AttributeError):
                # for versions without occ_variant_name in occurrence info
                occ_info = OccurrenceInfo(
                    occ_id, occ_filename, assembly_filename, occ_variant_id, tmatrix
                )
        except (TypeError, AttributeError):
            # for versions without tmatrix in occurrence info
            occ_info = OccurrenceInfo(
                occ_id, occ_filename, assembly_filename, occ_variant_id
            )

        yield (ref_obj_id, occ_variant_id, occ_info)

    def get_sorted_occurrences_from_appinfo(self, appinfo_tree, variant_id):
        occurrences = None
        if variant_id:
            variants = appinfo_tree.getVariants()
            variant = None
            for var in variants:
                if var.getItemName().strip() == variant_id:
                    variant = var
                    break
            if variant:
                occurrences = variant.getOccurrences()
            else:
                self.log(
                    "Could not find occurrence structure of variant %s. "
                    "Using main occurrence structure instead." % variant_id
                )

        if occurrences is None:
            occurrences = appinfo_tree.getOccurrences()

        # iterate through SORTED occurrences such that
        # new bom entries are generated in a meaningful order

        def getSortVal(occ):
            try:
                return int(occ.getSortValue())
            except (TypeError, ValueError):
                self.log(
                    "Invalid value for sort value of occurrence '%s': %s"
                    % (occ.getItemName(), occ.getSortValue())
                )
                return 0

        occurrences.sort(key=getSortVal)
        return occurrences

    def ignore_occurrence(self, occurrence):
        """
        Allows to ignore an occurrence based on the appinfo content.
        By default, ignores occurrences which are not "bom-relevant".

        :Parameters:

          - `occurrence`: :class:`cs.wsm.srvappinfoitems.Occurrence`

        :Returns bool
        """
        return not occurrence.isBomRelevant()

    def add_component_attributes(self, part, doc, attributes):
        """
        Allows to extract attribute values from a component part or a document
        and add it to the bom position.

        `attributes` is a dictionary of `bom_item` attribute values
        which can be manipulated like a normal dict.

        This method is called before `adjust_and_filter`.

        :Parameters:

          - `part`: :class:`cs.vp.items.Item`
          - `doc`: :class:`cs.documents.Document`
        """
        pass

    def filter_variants(self, doc, variants, user_hints):
        """
        This method allows to filter for which variants of a document a BOM is created.
        The input contains only the variants which have an item assigned.

        By default, the method filters variants with duplicate items and creates a warning
        in this case.

        This method returns a pair:
           The first element is a boolean: Should a BOM be created from the non-variant structure?
           The other element is a list of variant ids.

        :Parameters:

          - `doc`: :class:`cs.documents.Document' the document representing the component
          - `variants`: list of ids of variants with assigned item
          - 'user_hints': :class:`cs.vp.bomcreator.bom.UserHintList'

        :Returns (bool, filtered list of variant ids)
        """
        item_to_variant = {}
        result = []
        doc_item_key = (self._context.teilenummer, self._context.t_index)
        for variant_id in variants:
            variant = CADVariant.ByKeys(
                z_nummer=doc.z_nummer, z_index=doc.z_index, variant_id=variant_id
            )
            if variant and variant.teilenummer:
                item_key = (variant.teilenummer, variant.t_index)
                if item_key in item_to_variant:
                    # the item was already assigned to a different variant
                    # => ignore this variant and show a warning
                    user_hints.append(
                        msg("WSM_BOM_item_assigned_to_different_variant")
                        % (
                            variant_id,
                            doc.z_nummer,
                            doc.z_index,
                            variant.teilenummer,
                            variant.t_index,
                            item_to_variant[item_key],
                        )
                    )
                elif item_key == doc_item_key:
                    # the item was already assigned to the document
                    # => ignore this variant and show a warning
                    user_hints.append(
                        msg("WSM_BOM_item_assigned_to_document")
                        % (
                            variant_id,
                            doc.z_nummer,
                            doc.z_index,
                            variant.teilenummer,
                            variant.t_index,
                        )
                    )
                else:
                    item_to_variant[item_key] = variant_id
                    result.append(variant_id)

        return True, result

    def process_component(self, bom, component_doc, occurrence):
        """
        Analyze a component and add a BOM position for the component.

        Can be overridden to extend the functionality or to suppress
        certain components in ways not covered by the methods
        `ignore_occurrence`, `ignore_component_item`, or `ignore_component_document`.

        :Parameters:

          - `bom`: :class:`cs.vp.bomcreator.bom.GeneratedBOM' the BOM that is currently constructed
          - `component_doc`: :class:`cs.documents.Document' the document representing the component
          - `occurrence`: :class:`cs.vp.bomcreator.bom.OccurrenceInfo`
        """
        if self.ignore_component_document(component_doc, bom.user_hints):
            return

        self.referenced_docs.append(component_doc.cdb_object_id)
        occ_variant_id = occurrence.occurrence_variant_id
        self.referenced_variant_ids.append(occ_variant_id)

        self.add_bom_position(bom, component_doc, occ_variant_id, occurrence)

    def add_bom_position(self, bom, item_doc, variant_id, occurrence):
        """Adds a BOM position for the part identified
        by the given document."""

        try:
            # also take into account variant name (for old variant ids)
            # this only works with cs.bomcreator >= 15.2.1 SL 19
            variant_name = occurrence.occurrence_variant_name
            part = self.get_part_from_document(
                item_doc, variant_id, bom.user_hints, variant_name
            )
        except (TypeError, AttributeError):
            part = self.get_part_from_document(item_doc, variant_id, bom.user_hints)
        if part is None:
            return None

        if self.ignore_component_item(part, bom.user_hints):
            return None

        if part is not None:
            # now really create the new entry
            self.log(
                "Adding BOM position for part %s-%s." % (part.teilenummer, part.t_index)
            )
            new_entry = bom.create_entry(
                teilenummer=part.teilenummer,
                t_index=part.t_index,
                menge=1.0,
                occurence_id=occurrence.occurrence_id,
            )

            self.add_component_attributes(part, item_doc, new_entry.attrs)

            if not self.adjust_and_filter(new_entry.attrs):
                self.log("Entry filtered by custom method.")
                return
            # create again; parts of the key may have changed
            new_entry = bom.create_entry(**new_entry.attrs)

            new_entry.add_occurrence(occurrence)
            bom.add_entry(new_entry)

    def get_variants_with_assigned_assembly(self, doc):
        variant_ids = []
        for cad_variant in doc.CADVariants:
            if cad_variant.teilenummer:
                variant_ids.append(cad_variant.variant_id)
        return variant_ids


RecursiveBOMReader = make_recursive_reader_type(
    ComponentStructureBOMReader, ResultOrder.BreadthFirst
)
"""Like :class:`ComponentStructureBOMReader`, but additionally creates
BOMs for all referenced sub-assemblies. The type of BOM reader used for the
sub-assemblies depends on their cad source."""


class ComponentStructureIgnoreSuppressedBOMReader(ComponentStructureBOMReader):
    """
    Like :class:`ComponentStructureBOMReader`, but ignores suppressed occurrences.
    """

    def ignore_occurrence(self, occurrence):
        return not occurrence.isBomRelevant() or occurrence.isSuppressed()


RecursiveIgnoreSuppressedBOMReader = make_recursive_reader_type(
    ComponentStructureIgnoreSuppressedBOMReader, ResultOrder.BreadthFirst
)
"""Like :class:`ComponentStructureIgnoreSuppressedBOMReader`, but additionally creates
BOMs for all referenced sub-assemblies. The type of BOM reader used for the
sub-assemblies depends on their cad source."""


class ComponentStructureAllVariantsBOMReader(ComponentStructureBOMReader):
    """
    Like parent class, but always considers all variants of an assembly,
    independently of traversal depth.
    """

    follow_variants_only_on_toplevel = False


RecursiveAllVariantsBOMReader = make_recursive_reader_type(
    ComponentStructureAllVariantsBOMReader, ResultOrder.BreadthFirst
)
"""Derives a 150% structure of the given assembly,
i.e. creates BOMs for all variants of all assemblies in the structure."""
