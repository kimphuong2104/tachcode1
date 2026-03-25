#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import io

from cdb.objects import ByID
from cdb.objects.pdd import Sandbox
from cs.vp.bom import Item
from cs.vp.bomcreator.bomreader import BOMReader
import six


class ItemHierarchyBOMReader(BOMReader):
    """
    An example of a BOMReader that creates a hierarchy of items.
    The items are connected by their Assembly-Component relationship.

    Information about the hierarchy to create is read from the first
    primary file.

    (In this example, the item key is stored in the attribute "techdaten".
    Real implementations should find a more meaningful attribute for the key
    and make sure that there is a data base index on the attribute.)
    """
    def __init__(self, bom_context, factory, custom_state):
        self.doc_object_id = bom_context.object_id
        self.factory = factory
        self.top_item = Item.ByKeys(bom_context.teilenummer,
                                    bom_context.t_index)

        key2bom = {}  # tuple -> GeneratedBOM

        # create top bom
        topBom = factory.create_BOM()
        topKey = (self.doc_object_id,)
        key2bom[topKey] = topBom

        inputData = self.readFirstPrimaryFile()
        for line in inputData:
            attrs = line.split(";")
            self._createBomsRecursively(topKey, attrs, key2bom, indent=1)

        self.boms = []
        for key in sorted(six.iterkeys(key2bom)):
            self.boms.append(key2bom[key])

    def _createBomsRecursively(self, parentKey, attrs, key2bom, indent):
        """
        Recursively creates items and boms according to the values in attrs.

        :param parentKey:
        :param attrs: list of attribute values
        :param key2bom: dict
        :param indent: int visual indent
        """
        if len(attrs) > 0:
            first = attrs[0]
            rest = attrs[1:]
            key = parentKey + (first,)
            flatKey = ";".join(key)
            items = Item.KeywordQuery(techdaten=flatKey)
            if len(items) > 0:
                # item already exist
                item = items[0]
                if key in key2bom:
                    # BOM already exist
                    bom = key2bom[key]
                else:
                    bom = self.factory.create_BOM_for_assembly(item)
            else:
                # item and bom must be created
                bom = self.factory.create_assembly_and_BOM(benennung=first,
                                                           techdaten=flatKey,
                                                           t_kategorie="Baugruppe",
                                                           gebrauchsstand="aktiv",
                                                           mengeneinheit="Stk",
                                                           t_bereich="IT")
                item = bom.get_assembly()

            key2bom[key] = bom
            bom.set_visual_indent(indent)
            # add to parent bom
            parentBom = key2bom[parentKey]
            parentBom.create_and_add_entry(teilenummer=item.teilenummer,
                                           t_index=item.t_index)
            # create articles below us in the hierarchy
            self._createBomsRecursively(key, rest, key2bom, indent + 1)

    def readFirstPrimaryFile(self):
        """
        :return: list of string
        """
        result = []
        doc = ByID(self.doc_object_id)
        if len(doc.PrimaryFiles) > 0:
            f = doc.PrimaryFiles[0]
            ws = Sandbox()
            ws.checkout(f)
            with io.open(ws.pathname(f), encoding="utf-8") as fh:
                result = fh.readlines()
        return result
