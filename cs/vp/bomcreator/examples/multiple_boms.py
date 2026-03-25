#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from cs.vp.bom import Item
from cs.vp.bomcreator.bomreader import BOMReader


class MultipleBOMReader(BOMReader):
    """
    An example of a BOMReader that create more than one BOM.
    """
    def __init__(self, bom_context, factory, custom_state):
        self._createTestData()

        # create the main bom for the main assembly (taken from the CAD document)
        self._bom = factory.create_BOM()
        self._bom.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index, menge=1.0)

        # create another BOM for our test assembly
        bom2 = factory.create_BOM_for_assembly(self.assembly2)
        bom2.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index, menge=1.0)

        # return both BOMs as a list
        self.boms = [self._bom, bom2]

    def _createTestData(self):
        part_teilenummer = "multiple_bom_reader_part"
        self.part = Item.ByKeys(teilenummer=part_teilenummer, t_index="")
        if self.part is None:
            self.part = Item.Create(benennung="testpart", teilenummer=part_teilenummer, t_index="", mengeneinheit="Stk")

        assembly_teilenummer = "multiple_bom_reader_assembly"
        self.assembly2 = Item.ByKeys(teilenummer=assembly_teilenummer, t_index="")
        if self.assembly2 is None:
            self.assembly2 = Item.Create(benennung="testasm", teilenummer=assembly_teilenummer, t_index="", mengeneinheit="Stk")
