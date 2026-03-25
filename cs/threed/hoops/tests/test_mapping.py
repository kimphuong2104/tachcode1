# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Unit tests for the model mapping
"""

import os

from cdb import testcase
from cdb import constants
from cdb.objects import operations

from cs.threed.hoops.mapping import DocumentFileMapper, PartDocumentMapper
from cs.documents import Document

from cs.vp.bom import Item, AssemblyComponent


class TestDocumentFileMapping(testcase.PlatformTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDocumentFileMapping, cls).setUpClass()

        from cs.threed.hoops.tests.utils import install_testdata
        install_testdata()

    def setUp(self):
        self.context_document = Document.ByKeys(z_nummer="000061-1", z_index="")

        self.filenames_top_down = [
            "000061-1-.CATProduct",
            "000068-1-.CATProduct",
            "000065-1-.CATPart"
        ]

        self.documents_top_down = [
            self.context_document,
            Document.ByKeys(z_nummer="000068-1", z_index=""),
            Document.ByKeys(z_nummer="000065-1", z_index="")
        ]

        super(TestDocumentFileMapping, self).setUp()

    def test_find_documents_for_exchange_ids(self):
        """
        Mapping from filenames to documents works
        """
        mapper = DocumentFileMapper(self.context_document)

        result = mapper.get_document_path_for_filenames(self.filenames_top_down)

        self.assertEqual(len(result), 3, "the resulting list should have length 3")

        for i, (expected, received) in enumerate(zip(self.documents_top_down, result)):
            self.assertEqual(expected.ID(), received.ID(), "expected element %d of the list "
                                                           "to be equal, but is wasn't" % i)

    def test_find_documents_for_filenames_with_duplicate_filenames(self):
        """
        Mapping from filenames to documents works for globally non unique file names
        """
        filenames = self.filenames_top_down
        filenames.append("000066-1-.CATPart")

        mapper = DocumentFileMapper(self.context_document)
        result = mapper.get_document_path_for_filenames(filenames)
        self.assertEqual(len(result), 4, "the resulting list should have length 4")

        documents = self.documents_top_down
        documents.append(Document.ByKeys(z_nummer="000066-1", z_index=""))
        for i, (expected, received) in enumerate(zip(documents, result)):
            self.assertEqual(expected.ID(), received.ID(), "expected element %d of the list "
                                                           "to be equal, but is wasn't" % i)

    def test_find_filenames_for_documents(self):
        """
        Mapping from documents to filenames works
        """
        mapper = DocumentFileMapper(self.context_document)

        result = mapper.get_filename_paths_for_document_paths([self.documents_top_down])[0]
        self.assertListEqual(self.filenames_top_down, result)


    def test_find_files_for_different_solid_works_extensions(self):
        """
        Mapping from filenames to documents with alternative solid workds extensions works
        """
        docs_by_file = {
            "EGMC000205-1.sldasm": Document.ByKeys(z_nummer="9508446-1", z_index=""),
            "EGMC000160-1.sldasm": Document.ByKeys(z_nummer="9508395-1", z_index=""),
            "EGMC000157-1.sldasm": Document.ByKeys(z_nummer="9508386-1", z_index=""),
            "EGMC000156-1.sldprt": Document.ByKeys(z_nummer="9508407-1", z_index=""),
            }

        mapper = DocumentFileMapper(list(docs_by_file.values())[0])

        result = mapper.get_document_path_for_filenames(docs_by_file.keys())

        self.assertEqual(len(result), 4, "the resulting list should have length 4")
        for i, (expected, received) in enumerate(zip(docs_by_file.values(), result)):
            self.assertEqual(expected.ID(), received.ID(), "expected element %d of the list "
                                                           "to be equal, but is wasn't" % i)


class TestPartDocumentMapping(testcase.RollbackTestCase):
    def setUp(self):
        super(TestPartDocumentMapping, self).setUp()

        self.bom_item_occurrence1 = None
        self.bom_item_occurrence2 = None

        try:
            from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence
            # for some reason the bom item occurrences have to be created first
            self.bom_item_occurrence1 = operations.operation(
                constants.kOperationNew,
                AssemblyComponentOccurrence,
                occurrence_id="000065-1.1",
                reference_path="000065-1-.CATProduct",
                assembly_path="000068-1-.CATProduct",
                bompos_object_id="9272396e-331a-11ec-8e65-ac675dd11acc",
                relative_transformation="4.34282531123647e-16 -1.10525763698619e-16 1.0 0.0 -0.268851001259338 0.963181778856853 2.2321369501078e-16 0.0 -0.963181778856853 -0.268851001259338 3.88578058618805e-16 0.0 -59.3194251848828 2100.00000000004 1015.0 1.0"
            )

            self.bom_item_occurrence2 = operations.operation(
                constants.kOperationNew,
                AssemblyComponentOccurrence,
                occurrence_id="000065-1.2",
                reference_path="000065-1-.CATProduct",
                assembly_path="000068-1-.CATProduct",
                bompos_object_id="9272396e-331a-11ec-8e65-ac675dd11acc",
                relative_transformation="3.70550924170356e-16 -1.77476996327318e-16 1.0 0.0 -0.177900173283307 0.984048539628899 2.40567052673817e-16 0.0 -0.984048539628899 -0.177900173283307 3.33066907387547e-16 0.0 993.047352234761 1149.99443658468 1015.0 1.0"
            )
        except:
            pass

        self.addtl_bom_item = operations.operation(
            constants.kOperationNew,
            AssemblyComponent,
            baugruppe="000068",
            b_index="",
            teilenummer="000065",
            t_index="",
            variante="",
            position=30,
            auswahlmenge=0.0,
            is_imprecise=0,
        )

        self.context_part = Item.ByKeys(teilenummer="000061", t_index="")

        self.documents_top_down = [
            Document.ByKeys(z_nummer="000061-1", z_index=""),
            Document.ByKeys(z_nummer="000068-1", z_index=""),
            Document.ByKeys(z_nummer="000065-1", z_index="")
        ]

        self.parts_top_down = [
            self.context_part,
            Item.ByKeys(teilenummer="000068", t_index=""),
            Item.ByKeys(teilenummer="000065", t_index="")
        ]

        self.filenames_top_down = [
            "000061-1-.CATProduct",
            "000068-1-.CATProduct",
            "000065-1-.CATPart"
        ]

        self.bom_items_top_down = [
            AssemblyComponent.ByKeys(
                baugruppe="000061",
                b_index="",
                teilenummer="000068",
                t_index="",
                variante="",
                position=30,
            ),
            AssemblyComponent.ByKeys(
                baugruppe="000068",
                b_index="",
                teilenummer="000065",
                t_index="",
                variante="",
                position=50,
            )
        ]

        self.model_transformations = [
            "4.342825311236475e-16 -1.105257636986187e-16 1 0 -0.2688510012593379 0.9631817788568531 2.2321369501078e-16 0 -0.9631817788568531 -0.2688510012593379 3.885780586188049e-16 0 -59.31942518488277 2100.000000000038 1014.9999999999998 1",
            "3.70550924170356e-16 -1.77476996327318e-16 1.0 0.0 -0.177900173283307 0.984048539628899 2.40567052673817e-16 0.0 -0.984048539628899 -0.177900173283307 3.33066907387547e-16 0.0 993.047352234761 1149.99443658468 1015.0 1.0",
            None # root item trafo
        ]


    def test_find_bom_items_for_filenames(self):
        self.bom_items_top_down.append(self.addtl_bom_item)

        mapper = PartDocumentMapper(self.context_part)
        result = mapper.get_bom_item_path_for_filenames(self.filenames_top_down)

        self.assertTrue(all([entry in self.bom_items_top_down for entry in result]))

    def test_find_bom_items_for_filenames_with_multiple_occurrences(self):
        if not self.bom_item_occurrence1 or not self.bom_item_occurrence2:
            assert False, "No occurrences found. This might be because BomCreator is not available."
        mapper = PartDocumentMapper(self.context_part)
        result = mapper.get_bom_item_path_for_filenames(self.filenames_top_down, self.model_transformations)

        self.assertListEqual(result, self.bom_items_top_down)

    def test_find_filenames_for_bom_items(self):
        mapper = PartDocumentMapper(self.context_part)
        result = mapper.get_filename_path_for_bom_items(self.bom_items_top_down)

        self.assertListEqual(self.filenames_top_down, result)
