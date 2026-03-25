# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import cs.vp.items.tests as common
from cs.vp.cad.tests import generateDocumentReference

from cdb import testcase
from cdb import sqlapi

from cs.vp.cad.search import CadDocumentStructureSearch
from cs.vp.cad.search import DocumentAttributeAccessor

from cs.vp.cad import Model


class TestDocumentStructureSearch(testcase.RollbackTestCase):
    def setUp(self):
        super(TestDocumentStructureSearch, self).setUp()

        self.context_document = common.generateCADDocument(common.generateItem())
        self.parent1_document = common.generateCADDocument(common.generateItem())
        self.parent2_document = common.generateCADDocument(common.generateItem())
        self.parent3_document = common.generateCADDocument(common.generateItem())

        self.child1_document = common.generateCADDocument(common.generateItem())
        self.child2_document = common.generateCADDocument(common.generateItem())

        generateDocumentReference(self.context_document, self.parent1_document, "p1")
        generateDocumentReference(self.context_document, self.parent2_document, "p2")
        generateDocumentReference(self.context_document, self.parent3_document, "p3")

        generateDocumentReference(self.parent2_document, self.child1_document, "c1")
        generateDocumentReference(self.parent2_document, self.child2_document, "c2")


    def test_get_single_search_result(self):
        """ Will return the single search result when searched """
        search_string = self.child1_document.z_nummer[3:]
        s = CadDocumentStructureSearch(self.context_document, search_string)

        results = s.get_results()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 3)

        model = results[0][-1]
        self.assertTrue(search_string in model.GetDescription())


    def test_search_result_order(self):
        """ Will return the search result in the correct order when searched """
        s = CadDocumentStructureSearch(self.context_document)

        results = s.get_results()

        expected_order = [
            self.context_document,
            self.parent1_document,
            self.parent2_document,
            self.child1_document,
            self.child2_document,
            self.parent3_document,
        ]

        self.assertEqual(len(results), 6)

        for i in range(6):
            self.assertTrue(results[i][-1]["cdb_object_id"] == expected_order[i].cdb_object_id,
                "Expected (%s / %s) to be at index %s but found (%s / %s)." % (
                    results[i][-1]["z_nummer"], results[i][-1]["z_index"], i,
                    expected_order[i].z_nummer, expected_order[i].z_index
                ))

    def test_attribute_accessor_with_base_attr_types_on_table_rec(self):
        rec = sqlapi.RecordSet2("zeichnung", "z_nummer='%s'" % self.context_document.z_nummer)[0]
        acc = DocumentAttributeAccessor(rec, ignore_errors=False)
        for attr in Model.GetFieldNames():
            acc[attr]

    def test_attribute_accessor_with_all_attr_types_on_view_rec(self):
        rec = sqlapi.RecordSet2("zeichnung_v", "z_nummer='%s'" %  self.context_document.z_nummer)[0]
        acc = DocumentAttributeAccessor(rec, ignore_errors=False)
        for attr in Model.GetFieldNames(any):
            acc[attr]
