# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase

from cs.documents import Document
from cs.vp import items

from cs.vp.items_documents import DocumentToPart
from cs.vp.items_documents.scripts.create_doc2part import create_doc2part


class TestCreateDocumentToPart(RollbackTestCase):

    def _create_document(self, title, part=None):
        create_args = {
            "titel": title,
            "z_nummer": Document.makeNumber(None),
            "z_index": "",
            "z_categ1": "142",
            "z_categ2": "153"
        }
        if part:
            create_args["teilenummer"] = part.teilenummer
            create_args["t_index"] = part.t_index
        doc = Document.Create(**create_args)
        self.assertIsNotNone(doc, 'document could not be created!')
        return doc

    def _create_part(self):
        item_args = dict(
            benennung="Blech",
            t_kategorie="Baukasten",
            t_bereich="Engineering",
            mengeneinheit="qm"
        )
        part = operation(
            constants.kOperationNew,
            items.Item,
            **item_args
        )
        self.assertIsNotNone(part, 'part could not be created!')
        return part

    def test_create_document2part(self):
        part = self._create_part()
        doc_1 = self._create_document("TestDoc 1", part)
        doc_2 = self._create_document("TestDoc 2", part)
        doc2part_created = create_doc2part()
        self.assertTrue(doc2part_created >= 2)
        for doc in [doc_1, doc_2]:
            doc2parts = DocumentToPart.KeywordQuery(
                z_nummer=doc.z_nummer, z_index=doc.z_index, teilenummer=doc.teilenummer, t_index=doc.t_index
            )
            self.assertEqual(1, len(doc2parts))
            self.assertEqual(DocumentToPart.KIND_STRONG, doc2parts[0].kind)



