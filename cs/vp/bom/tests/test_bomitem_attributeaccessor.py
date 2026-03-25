# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb.testcase import RollbackTestCase
from cs.vp.items.tests import generateItem
import cs.vp.bom.tests as common

from cs.vp.bom import search
from cs.vp.bom import AssemblyComponent
from cdb import sqlapi


class TestBOMItemAttributeAccessor(RollbackTestCase):

    def setUp(self):
        super(TestBOMItemAttributeAccessor, self).setUp()
        self.assembly = generateItem()
        self.part = generateItem()
        self.bom_item = common.generateComponent(baugruppe=self.assembly.teilenummer,
                                                 teilenummer=self.part.teilenummer)

    def test_base_attr_types_on_table_rec(self):
        rec = sqlapi.RecordSet2("einzelteile", "baugruppe='%s'" % self.assembly.teilenummer)[0]
        acc = search.BomItemAttributeAccessor(rec, None, ignore_errors=False)
        for attr in AssemblyComponent.GetFieldNames():
            acc[attr]

    def test_all_attr_types_on_view_rec(self):
        rec = sqlapi.RecordSet2("einzelteile_v", "baugruppe='%s'" % self.assembly.teilenummer)[0]
        acc = search.BomItemAttributeAccessor(rec, None, ignore_errors=False)
        for attr in AssemblyComponent.GetFieldNames(any):
            acc[attr]

    def test_joined_attr_types_on_two_table_recs(self):
        bom_item_rec = sqlapi.RecordSet2("einzelteile", "baugruppe='%s'" % self.assembly.teilenummer)[0]
        part_rec = sqlapi.RecordSet2("teile_stamm", "teilenummer='%s'" % self.part.teilenummer)[0]
        acc = search.BomItemAttributeAccessor(bom_item_rec, part_rec, ignore_errors=False)
        fields = ['t_kategorie', # simple joined attr
                  'i18n_b_benennung', # joined multi language attr
                  ]
        for attr in fields:
            acc[attr]

    def test_chained_joined_attr(self):
        bom_item_rec = sqlapi.RecordSet2("einzelteile", "baugruppe='%s'" % self.assembly.teilenummer)[0]
        part_rec = sqlapi.RecordSet2("part_v", "teilenummer='%s'" % self.part.teilenummer)[0]
        acc = search.BomItemAttributeAccessor(bom_item_rec, part_rec, ignore_errors=False)
        fields = ['assembly_status_name']
        for attr in fields:
            acc[attr]
