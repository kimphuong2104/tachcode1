#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

import logging

import six

from cdb.cad import getMaxIndex
from cdb import sqlapi
from cdb.objects import ByID

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator import msg
from cs.wsm.bom.wsmbomreader import WSMBOMReader, get_appinfo_tree, filename_of_record
from cs.wsm.srvappinfoitems import BOMPosition, BOMClass


class CADBomInfoBOMReaderBase(WSMBOMReader):
    """
    Abstract base class for BOMReaders that generate the BOM from the BOM section
    of Workspaces file information (.appinfo file).
    Makes sure that appinfo bom info is available.
    """

    def __init__(self, bom_context, factory, _custom_state):
        WSMBOMReader.__init__(self, bom_context, factory, _custom_state)
        self.log(
            "started on document %s, for part %s-%s"
            % (bom_context.object_id, bom_context.teilenummer, bom_context.t_index)
        )
        self.init_ok = False
        self.factory = factory
        self._context = bom_context
        self._bom = factory.create_BOM()
        self.boms = [self._bom]
        self.referenced_docs = []
        self._hints = self._bom.user_hints

        if self.anchor_file is None:
            return

        appinfo_tree = get_appinfo_tree(self.anchor_file, self.workspace, self._hints)
        if appinfo_tree is None:
            return

        # this is the appinfo BOM for the main article, delivered
        # by CAD integrations which support only a single BOM per file;
        # we provide it in "bom_info" for backwards compatibility
        main_bom_info = appinfo_tree.getBOM()
        if main_bom_info is not None:
            self.bom_info = main_bom_info
            self.bom_infos = [main_bom_info]
        else:
            self.bom_info = None
            self.bom_infos = []

        # these are the appinfo BOMs delivered by CAD integrations which
        # support multiple BOMs
        extra_boms = appinfo_tree.getBOMs()
        if extra_boms is not None:
            bomInfos = extra_boms.getBOMs()
            bomInfosWithPart = [
                (bomInfo, self.get_assembly_from_bom(bomInfo, produce_hint=False))
                for bomInfo in bomInfos
            ]
            useAnonBomForMainAsm = self._anonymousBomCanBeAssigned(bomInfosWithPart)

            for bom_info, item in bomInfosWithPart:
                if item is None:
                    if useAnonBomForMainAsm:
                        item = self._bom._assembly
                    else:
                        # add warning message:
                        self.get_assembly_from_bom(bom_info, produce_hint=True)
                        continue
                # is it the main file?
                if item == self._bom._assembly:
                    if self.bom_info is None:
                        self.bom_info = bom_info
                        self.bom_infos.insert(0, bom_info)
                    continue
                # otherwise add another BOM
                bom = factory.create_BOM_for_assembly(item)
                self.boms.append(bom)
                self.bom_infos.append(bom_info)

        # if there is no BOM info for the document article, remove the original
        # main bom
        if self.bom_info is None and len(self.bom_infos) > 0:
            self.boms = self.boms[1:]

        if len(self.bom_infos) == 0:
            self._hints.append(
                msg("WSM_BOM_no_bominfo") % filename_of_record(self.anchor_file)
            )
        else:
            self.init_ok = True

    def get_part_from_position(self, position, produce_hint=True):
        """
        Extracts part information from a BOMInfo Position.

        :Parameters:
          - `position`: :class:`cs.wsm.srvappinfoitems.BOMPosition`
        """
        assert isinstance(position, BOMPosition)
        return self._get_part_from_partno_partversion(position, produce_hint)

    def get_assembly_from_bom(self, bom, produce_hint=True):
        """
        Extracts assembly information from a BOMClass.

        :Parameters:
          - `position`: :class:`cs.wsm.srvappinfoitems.BOMClass`
        """
        assert isinstance(bom, BOMClass)
        return self._get_part_from_partno_partversion(bom, produce_hint)

    def sort_key(self, entry):
        """
        Override this method if you need customized sorting of entries.
        The value returned by this method must be suitable as the ``key``
        argument of Python's ``sorted`` function.

        This is useful when position numbers are assigned automatically
        and the order of elements in the XML is not quite right.

        :Parameters:
          - `entry`: :class:`BOMEntry``
        """
        raise NotImplementedError

    def _get_part_from_partno_partversion(self, item, produce_hint):
        """
        Extracts part information from an AppinfoItem.
        The item must have getPartNumber/getPartVersion methods.
        """
        teilenummer = item.getPartNumber()
        t_index = item.getPartVersion()
        if teilenummer is None or teilenummer == "":
            if produce_hint:
                self._hints.append(msg("WSM_BOM_no_part_specified"))
            return None

        if t_index is None:  # version not given -> get highest index from db
            t_index = getMaxIndex(teilenummer, "teile_stamm")

        item = Item.ByKeys(teilenummer, t_index)
        if item is None:
            self._hints.append(msg("WSM_BOM_part_not_found") % (teilenummer, t_index))
        return item

    def sanity_check(self, attrs, user_hints):
        """Checks and adjust some critical attributes."""
        # menge
        try:
            menge = float(attrs["menge"])
        except Exception:
            user_hints.append(
                msg("WSM_BOM_quantity_format") % six.text_type(attrs["menge"])
            )
            menge = 0.0
        attrs["menge"] = menge
        # position
        cadPos = None
        posNumber = attrs.get("position", None)
        if posNumber is not None:
            try:
                cadPos = int(posNumber)
            except Exception:
                pass
            if cadPos is None:
                user_hints.append(
                    msg("WSM_BOM_position_format") % six.text_type(posNumber)
                )
                del attrs["position"]  # will get a generated position later
            else:
                attrs["position"] = cadPos

    def map_from_BOMInfo(self, position, teilenummer, t_index):
        """Creates a dict of attributes from the information
        in a `BOMInfo` position.

        `teilenummer` and `t_index` are passed as arguments because different
        users of this method may use different ways to extract the part
        from `position`.

        :Parameters:
          - `position`: :class:`cs.wsm.srvappinfoitems.BOMPosition`
          - `teilenummer`: String
          - `t_index`: String

        """
        attrs = dict()
        attrs["teilenummer"] = teilenummer
        attrs["t_index"] = t_index

        # 'menge'(quantity) and 'position'(posno) are always mapped.
        # They are converted to the right type later
        # and have special handling in case of missing or wrong values.
        attrs["menge"] = position.getQuantity()
        attrs["position"] = position.getPosNumber()

        # map additional attributes

        # create property dict to avoid repeated linear search
        prop_dict = dict((p.getItemName(), p) for p in position.getProperties())

        converters = {
            sqlapi.SQL_CHAR: lambda x: x,
            sqlapi.SQL_FLOAT: convert_float,
            sqlapi.SQL_INTEGER: convert_int,
        }

        mapping = self.factory.get_attribute_mapping()
        for cdb_name, cad_name, is_property in mapping:
            val = None
            if is_property:
                prop = prop_dict.get(cad_name)
                if prop is not None:
                    val = prop.getValue()
            else:
                val = position.findAttributeByName(cad_name)
            if val is None:
                logging.error(u"Appinfo value for '%s' not found.", cad_name)
            else:
                attrs[cdb_name] = val  # store unmodified value for use in UEs

                field_descr = AssemblyComponent.GetFieldByName(cdb_name)
                if field_descr is None:
                    logging.error(
                        u"Cannot find field descriptor for CDB attribute '%s' not found.",
                        cdb_name,
                    )
                    continue
                converter = converters.get(field_descr.type)
                if converter is None:
                    logging.error(
                        u"Can't convert to type '%s' of CDB attribute '%s'.",
                        field_descr.type,
                        cdb_name,
                    )
                    continue

                try:
                    val = converter(val)
                    attrs[cdb_name] = val
                except (ValueError, TypeError):
                    logging.error(
                        u"Appinfo value for '%s' has an unexpected format.", cad_name
                    )

        return attrs

    def _anonymousBomCanBeAssigned(self, bomInfosWithPart):
        """
        Check whether we can use an anonymous BOM as the BOM of the main assembly.

        :param bomInfosWithPart: Iterable of pairs (BOMClass (appinfo elements), item)
        :returns bool
        """
        if self.bom_info is not None:
            # main asm already has a BOM assigned
            return False

        numBomInfosWithoutPart = 0
        numBomInfosForMainAsm = 0
        for _bomInfo, part in bomInfosWithPart:
            if part is None:
                numBomInfosWithoutPart += 1
            if part == self._bom._assembly:
                numBomInfosForMainAsm += 1

        return numBomInfosWithoutPart == 1 and numBomInfosForMainAsm == 0


class CADBomInfoReader(CADBomInfoBOMReaderBase):
    """
    A BOMReader that generates the BOM from the BOM section
    of Workspaces file information (.appinfo file).

    This class does not consider CAD references.
    """

    def __init__(self, bom_context, factory, custom_state):
        CADBomInfoBOMReaderBase.__init__(self, bom_context, factory, custom_state)
        if not self.init_ok:
            return

        for bom, bom_info in zip(self.boms, self.bom_infos):
            # first only create entries
            entries = []
            for position in bom_info.getPositions():
                item = self.get_part_from_position(position)
                if item is None:
                    continue

                if self.ignore_component_item(item, self._hints):
                    continue

                attrs = self.map_from_BOMInfo(position, item.teilenummer, item.t_index)

                if not self.adjust_and_filter(attrs):
                    self.log("Entry filtered by custom method.")
                    continue

                self.sanity_check(attrs, self._hints)

                self.log(
                    "Adding entry for part %s-%s." % (item.teilenummer, item.t_index)
                )
                entry = bom.create_entry(**attrs)
                entries.append(entry)

            # optionally sort entries
            try:
                sortedEntries = sorted(entries, key=self.sort_key)
                entries = sortedEntries
            except NotImplementedError:
                pass  # ok, no sorting wanted

            # now add to BOM
            for entry in entries:
                bom.add_entry(entry)


class CADBomInfoReaderWithReferences(CADBomInfoReader):
    """
    A BOMReader that generates the BOM from the BOM section
    of Workspaces file information (.appinfo file).

    In contrast to :class:`CADBomInfoReader`, this class uses a position's
    CAD reference to find out the referenced part if the position does not
    have a part number or has an empty part number.
    """

    def __init__(self, bom_context, factory, custom_state):
        self.references_fetched = False
        CADBomInfoReader.__init__(self, bom_context, factory, custom_state)

    def get_part_from_position(self, position, produce_hint=True):
        self._ensure_references_fetched()

        item = CADBomInfoReader.get_part_from_position(
            self, position, produce_hint=False
        )
        if item is None:
            if position.getPartNumber():  # the part was specified, but not found
                return None

            item = self._get_part_from_cad_reference(
                position.getCadReference(),
                want_assembly=False,
                produce_hint=produce_hint,
            )
        return item

    def get_assembly_from_bom(self, bom, produce_hint=True):
        self._ensure_references_fetched()

        item = CADBomInfoReader.get_assembly_from_bom(self, bom, produce_hint=False)
        if item is None:
            if bom.getPartNumber():  # the part was specified, but not found
                return None

            item = self._get_part_from_cad_reference(
                bom.getCadReference(), want_assembly=True, produce_hint=produce_hint
            )
        return item

    def _get_part_from_cad_reference(self, cad_ref, want_assembly, produce_hint):
        if cad_ref is None:
            if produce_hint:
                self._hints.append(msg("WSM_BOM_neither_part_nor_reference"))
            return None

        ref_path = cad_ref.getPath()
        ref_record = self.workspace.getFileRecord(ref_path)
        if ref_record is None:
            obj = ByID(self._context.object_id)
            desc = obj.GetDescription()
            self._hints.append(msg("WSM_BOM_not_in_workspace") % (ref_path, desc))
            return None

        if not ref_record.getObject().isPrimary():
            self._hints.append(msg("WSM_BOM_not_a_primary_file") % ref_path)
            return None

        ref_id = ref_record.getObject().cdbf_object_id
        ref_doc = self.get_referenced_doc(ref_id, self._hints)
        if ref_doc is None:
            return None
        variant_id = cad_ref.getVariantId()
        variant_name = cad_ref.getVariantName()
        if want_assembly:
            item = self.get_assembly_from_document(ref_doc, variant_id, self._hints)
        else:
            if self.ignore_component_document(ref_doc, self._hints):
                return None

            try:  # this only works with cs.bomcreator >= 15.2.1 SL 19
                item = self.get_part_from_document(
                    ref_doc, variant_id, self._hints, variant_name
                )
            except TypeError:
                item = self.get_part_from_document(ref_doc, variant_id, self._hints)
        return item

    def _ensure_references_fetched(self):
        if not self.references_fetched:
            self.refresh_workspace_with_references(self.workspace, self._hints)
            self.references_fetched = True


def convert_float(x):
    if not x:
        return sqlapi.NULL
    return float(x)


def convert_int(x):
    if not x:
        return sqlapi.NULL
    return int(x)
