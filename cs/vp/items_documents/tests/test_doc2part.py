# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc
from cdb import constants
from cdb.objects.operations import operation, rship_operation
from cdb.platform.mom import SimpleArgument
from cdb.testcase import RollbackTestCase

from cs.documents import Document
from cs.vp import items
from cs.vp.cad import Model
from cs.vp.items_documents import DocumentToPart


class TestDocumentToPart(RollbackTestCase):

    def _create_document(self, title, part=None):
        create_args = {
            "titel": title,
            "z_categ1": "142",
            "z_categ2": "153"
        }
        if part:
            create_args["teilenummer"] = part.teilenummer
            create_args["t_index"] = part.t_index
        doc = operation(
            constants.kOperationNew,
            Document,
            **create_args
        )
        self.assertIsNotNone(doc, 'document could not be created!')
        return doc

    def _create_model(self, title, part=None):
        create_args = {
            "titel": title,
            "z_categ1": "142",
            "z_categ2": "153"
        }
        if part:
            create_args["teilenummer"] = part.teilenummer
            create_args["t_index"] = part.t_index
        doc = operation(
            constants.kOperationNew,
            Model,
            **create_args
        )
        self.assertIsNotNone(doc, 'model could not be created!')
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

    def _create_reference(self, doc, part, kind=DocumentToPart.KIND_WEAK):
        create_args = {
            "z_nummer": doc.z_nummer,
            "z_index": doc.z_index,
            "teilenummer": part.teilenummer,
            "t_index": part.t_index,
            "kind": kind
        }
        reference = operation(
            constants.kOperationNew,
            DocumentToPart,
            **create_args
        )
        self.assertIsNotNone(doc, 'reference could not be created!')
        return reference

    def test_create_document_without_part(self):
        doc = self._create_document("doc without part")
        references = DocumentToPart.KeywordQuery(z_nummer=doc.z_nummer, z_index=doc.z_index)
        self.assertEqual(0, len(references))

    def test_create_document_with_part(self):
        strong_part = self._create_part()
        doc = self._create_document("doc with part", strong_part)
        self.assertEqual(strong_part.teilenummer, doc.teilenummer)
        self.assertEqual(strong_part.t_index, doc.t_index)
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(strong_part.teilenummer, references[0].teilenummer)
        self.assertEqual(strong_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_STRONG, references[0].kind)

    def test_create_from_relationship(self):
        strong_and_relship_part = self._create_part()
        create_args = {
            "teilenummer": strong_and_relship_part.teilenummer,
            "t_index": strong_and_relship_part.t_index,
            "titel": "create from relship",
            "z_categ1": "142",
            "z_categ2": "153"
        }
        doc_from_relship = rship_operation(
            cdbwrapc.RelshipContext(strong_and_relship_part.ToObjectHandle(), "Documents"),
            constants.kOperationNew,
            Document,
            target_args=create_args
        )
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc_from_relship.z_nummer, z_index=doc_from_relship.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(strong_and_relship_part.teilenummer, references[0].teilenummer)
        self.assertEqual(strong_and_relship_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_STRONG, references[0].kind)

    def test_create_from_relationship_without_part(self):
        relship_part = self._create_part()
        create_args = {
            "titel": "create from relship",
            "z_categ1": "142",
            "z_categ2": "153"
        }
        doc_from_relship = rship_operation(
            cdbwrapc.RelshipContext(relship_part.ToObjectHandle(), "Documents"),
            constants.kOperationNew,
            Document,
            target_args=create_args
        )
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc_from_relship.z_nummer, z_index=doc_from_relship.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(relship_part.teilenummer, references[0].teilenummer)
        self.assertEqual(relship_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_WEAK, references[0].kind)

    def test_create_from_relationship_with_different_part(self):
        strong_part = self._create_part()
        relship_part = self._create_part()
        create_args = {
            "teilenummer": strong_part.teilenummer,
            "t_index": strong_part.t_index,
            "titel": "create from relship",
            "z_categ1": "142",
            "z_categ2": "153"
        }
        doc_from_relship = rship_operation(
            cdbwrapc.RelshipContext(relship_part.ToObjectHandle(), "Documents"),
            constants.kOperationNew,
            Document,
            target_args=create_args
        )
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc_from_relship.z_nummer, z_index=doc_from_relship.z_index
        )
        self.assertEqual(2, len(references))
        for reference in references:
            if DocumentToPart.KIND_STRONG == reference.kind:
                self.assertEqual(strong_part.teilenummer, reference.teilenummer)
                self.assertEqual(strong_part.t_index, reference.t_index)
            elif DocumentToPart.KIND_WEAK == reference.kind:
                self.assertEqual(relship_part.teilenummer, reference.teilenummer)
                self.assertEqual(relship_part.t_index, reference.t_index)
            else:
                self.fail("Unexpected reference kind: " + reference.kind)

    def test_delete_document_without_part(self):
        doc = self._create_document("doc without part")
        operation(constants.kOperationDelete, doc)
        references = DocumentToPart.KeywordQuery(z_nummer=doc.z_nummer, z_index=doc.z_index)
        self.assertEqual(0, len(references))

    def test_delete_document_with_part(self):
        part = self._create_part()
        doc = self._create_document("doc with part", part)
        operation(constants.kOperationDelete, doc)
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(0, len(references))

    def test_delete_document_with_weak_references(self):
        doc = self._create_document("doc without part")
        weak_part = self._create_part()
        self._create_reference(doc, weak_part)
        operation(constants.kOperationDelete, doc)
        references = DocumentToPart.KeywordQuery(z_nummer=doc.z_nummer, z_index=doc.z_index)
        self.assertEqual(0, len(references))

    def test_delete_document_with_both_references(self):
        strong_part = self._create_part()
        doc = self._create_document("doc without part", strong_part)
        weak_part = self._create_part()
        self._create_reference(doc, weak_part)
        operation(constants.kOperationDelete, doc)
        references = DocumentToPart.KeywordQuery(z_nummer=doc.z_nummer, z_index=doc.z_index)
        self.assertEqual(0, len(references))

    def test_add_part_to_document(self):
        doc = self._create_document("doc without part")
        strong_part = self._create_part()

        update_args = {
            "teilenummer": strong_part.teilenummer,
            "t_index": strong_part.t_index
        }
        operation(
            constants.kOperationModify,
            doc,
            **update_args
        )
        references = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(strong_part.teilenummer, references[0].teilenummer)
        self.assertEqual(strong_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_STRONG, references[0].kind)

    def test_change_part_of_document(self):
        old_strong_part = self._create_part()
        doc = self._create_document("doc with part", old_strong_part)

        new_strong_part = self._create_part()
        update_args = {
            "teilenummer": new_strong_part.teilenummer,
            "t_index": new_strong_part.t_index
        }
        operation(
            constants.kOperationModify,
            doc,
            **update_args
        )

        references = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(new_strong_part.teilenummer, references[0].teilenummer)
        self.assertEqual(new_strong_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_STRONG, references[0].kind)

    def test_change_part_of_document_with_existing_weak_reference(self):
        doc = self._create_document("doc without part")
        weak_part = self._create_part()
        self._create_reference(doc, weak_part)

        update_args = {
            "teilenummer": weak_part.teilenummer,
            "t_index": weak_part.t_index
        }
        operation(
            constants.kOperationModify,
            doc,
            **update_args
        )

        references = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(1, len(references))
        self.assertEqual(weak_part.teilenummer, references[0].teilenummer)
        self.assertEqual(weak_part.t_index, references[0].t_index)
        self.assertEqual(DocumentToPart.KIND_STRONG, references[0].kind)

    def test_copy_document_without_part(self):
        doc_src = self._create_document("src doc without part")

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc_src, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        copy_args = {
        }
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            **copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(0, len(references_copy))

    def test_copy_document_with_same_part(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc_src, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        copy_args = {
        }
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            **copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(1, len(references_copy))
        self.assertEqual(references_copy[0].kind, DocumentToPart.KIND_STRONG)
        self.assertEqual(references_copy[0].teilenummer, strong_part.teilenummer)

    def test_copy_document_with_new_part(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc_src, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        copy_strong_part = self._create_part()
        copy_args = {
            "teilenummer": copy_strong_part.teilenummer,
            "t_index": copy_strong_part.t_index
        }
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            **copy_args
        )

        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(1, len(references_copy))
        self.assertEqual(references_copy[0].kind, DocumentToPart.KIND_STRONG)
        self.assertEqual(references_copy[0].teilenummer, copy_strong_part.teilenummer)
        self.assertEqual(references_copy[0].t_index, copy_strong_part.t_index)

    def test_copy_document_with_removed_part(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc_src, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        copy_args = {
            "teilenummer": "",
            "t_index": ""
        }
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            **copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(0, len(references_copy))

    def test_copy_from_strong_relationship(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)
        copy_args = {
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(strong_part.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(1, len(references_copy))
        self.assertEqual(references_copy[0].kind, DocumentToPart.KIND_STRONG)
        self.assertEqual(references_copy[0].teilenummer, strong_part.teilenummer)
        self.assertEqual(references_copy[0].t_index, strong_part.t_index)

    def test_copy_from_strong_relationship_with_removed_part(self):
        strong_part_src = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part_src)
        copy_args = {
            "teilenummer": "",
            "t_index": ""
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(strong_part_src.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(1, len(references_copy))
        self.assertEqual(references_copy[0].kind, DocumentToPart.KIND_WEAK)
        self.assertEqual(references_copy[0].teilenummer, strong_part_src.teilenummer)
        self.assertEqual(references_copy[0].t_index, strong_part_src.t_index)

    def test_copy_from_strong_relationship_with_changed_part(self):
        strong_part_src = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part_src)
        strong_part_copy = self._create_part()
        copy_args = {
            "teilenummer": strong_part_copy.teilenummer,
            "t_index": strong_part_copy.t_index
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(strong_part_src.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        for reference in references_copy:
            if DocumentToPart.KIND_STRONG == reference.kind:
                self.assertEqual(strong_part_copy.teilenummer, reference.teilenummer)
                self.assertEqual(strong_part_copy.t_index, reference.t_index)
            elif DocumentToPart.KIND_WEAK == reference.kind:
                self.assertEqual(strong_part_src.teilenummer, reference.teilenummer)
                self.assertEqual(strong_part_src.t_index, reference.t_index)
            else:
                self.fail("Unexpected reference kind: " + reference.kind)

    def test_copy_from_weak_relationship(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)
        weak_part = self._create_part()
        self._create_reference(doc_src, weak_part)
        copy_args = {
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(weak_part.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        for reference in references_copy:
            if DocumentToPart.KIND_STRONG == reference.kind:
                self.assertEqual(strong_part.teilenummer, reference.teilenummer)
                self.assertEqual(strong_part.t_index, reference.t_index)
            elif DocumentToPart.KIND_WEAK == reference.kind:
                self.assertEqual(weak_part.teilenummer, reference.teilenummer)
                self.assertEqual(weak_part.t_index, reference.t_index)
            else:
                self.fail("Unexpected reference kind: " + reference.kind)

    def test_copy_from_weak_relationship_with_removed_part(self):
        strong_part = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part)
        weak_part = self._create_part()
        self._create_reference(doc_src, weak_part)
        copy_args = {
            "teilenummer": "",
            "t_index": ""
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(weak_part.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        self.assertEqual(1, len(references_copy))
        self.assertEqual(references_copy[0].kind, DocumentToPart.KIND_WEAK)
        self.assertEqual(references_copy[0].teilenummer, weak_part.teilenummer)
        self.assertEqual(references_copy[0].t_index, weak_part.t_index)

    def test_copy_from_weak_relationship_with_changed_part(self):
        strong_part_src = self._create_part()
        doc_src = self._create_document("src doc with part", strong_part_src)
        weak_part = self._create_part()
        self._create_reference(doc_src, weak_part)
        strong_part_copy = self._create_part()
        copy_args = {
            "teilenummer": strong_part_copy.teilenummer,
            "t_index": strong_part_copy.t_index
        }
        doc_copy = rship_operation(
            cdbwrapc.RelshipContext(weak_part.ToObjectHandle(), "Documents"),
            constants.kOperationCopy,
            doc_src,
            target_args=copy_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_copy.z_nummer, z_index=doc_copy.z_index
        )
        for reference in references_copy:
            if DocumentToPart.KIND_STRONG == reference.kind:
                self.assertEqual(strong_part_copy.teilenummer, reference.teilenummer)
                self.assertEqual(strong_part_copy.t_index, reference.t_index)
            elif DocumentToPart.KIND_WEAK == reference.kind:
                self.assertEqual(weak_part.teilenummer, reference.teilenummer)
                self.assertEqual(weak_part.t_index, reference.t_index)
            else:
                self.fail("Unexpected reference kind: " + reference.kind)

    def test_delete_part_from_document(self):
        strong_part = self._create_part()
        doc = self._create_document("doc without part", strong_part)

        update_args = {
            "teilenummer": "",
            "t_index": ""
        }
        operation(
            constants.kOperationModify,
            doc,
            **update_args
        )

        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc.z_nummer, z_index=doc.z_index
        )
        self.assertEqual(0, len(references_copy))

    def test_index_document(self):
        strong_part = self._create_part()
        doc = self._create_document("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        index_args = {
        }
        doc_index = operation(
            constants.kOperationIndex,
            doc,
            **index_args
        )
        references_copy = DocumentToPart.KeywordQuery(
            z_nummer=doc_index.z_nummer, z_index=doc_index.z_index
        )
        self.assertEqual(1 + len(weak_parts), len(references_copy))
        for reference in references_copy:
            part = weak_parts.get(reference.teilenummer)
            if part:
                self.assertEqual(reference.kind, DocumentToPart.KIND_WEAK)
            else:
                self.assertEqual(reference.kind, DocumentToPart.KIND_STRONG)
                self.assertEqual(reference.teilenummer, strong_part.teilenummer)

    def test_index_model_with_new_part_index(self):
        strong_part = self._create_part()
        doc = self._create_model("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        index_args = [SimpleArgument("cdb::argument.create_part_index", 1)]
        doc_index = operation(
            constants.kOperationIndex,
            doc,
            index_args
        )
        references_index = DocumentToPart.KeywordQuery(
            z_nummer=doc_index.z_nummer, z_index=doc_index.z_index
        )
        self.assertEqual(1 + len(weak_parts), len(references_index))
        for reference in references_index:
            part = weak_parts.get(reference.teilenummer)
            if part:
                self.assertEqual(reference.kind, DocumentToPart.KIND_WEAK)
            else:
                self.assertEqual(reference.kind, DocumentToPart.KIND_STRONG)
                self.assertEqual(reference.teilenummer, strong_part.teilenummer)
                self.assertNotEqual(reference.t_index, strong_part.t_index)

    def test_index_model_with_highest_part_index(self):
        strong_part = self._create_part()
        doc = self._create_model("src doc with part", strong_part)

        weak_parts = {}
        for _ in range(2):
            weak_part = self._create_part()
            self._create_reference(doc, weak_part)
            weak_parts[weak_part.teilenummer] = weak_part

        index_args = []
        strong_part_index = operation(
            constants.kOperationIndex,
            strong_part,
            index_args
        )

        index_args = [SimpleArgument("cdb::argument.max_part_index", 1)]
        doc_index = operation(
            constants.kOperationIndex,
            doc,
            index_args
        )
        references_index = DocumentToPart.KeywordQuery(
            z_nummer=doc_index.z_nummer, z_index=doc_index.z_index
        )
        self.assertEqual(1 + len(weak_parts), len(references_index))
        for reference in references_index:
            part = weak_parts.get(reference.teilenummer)
            if part:
                self.assertEqual(reference.kind, DocumentToPart.KIND_WEAK)
                self.assertEqual(reference.teilenummer, part.teilenummer)
                self.assertEqual(reference.t_index, part.t_index)
            else:
                self.assertEqual(reference.kind, DocumentToPart.KIND_STRONG)
                self.assertEqual(reference.teilenummer, strong_part_index.teilenummer)
                self.assertEqual(reference.t_index, strong_part_index.t_index)

    def test_python_relship_document(self):
        strong_part = self._create_part()
        doc = self._create_document("doc with part", strong_part)
        weak_part = self._create_part()
        self._create_reference(doc, weak_part)

        expected_ref_parts = set([strong_part.teilenummer, weak_part.teilenummer])
        found_ref_parts = set()
        for doc2part in doc.ItemReferences:
            found_ref_parts.add(doc2part.teilenummer)

        self.assertSetEqual(expected_ref_parts, found_ref_parts)

    def test_python_relship_item(self):
        part = self._create_part()
        doc_1 = self._create_document("doc with part", part)
        doc_2 = self._create_document("doc with part")
        self._create_reference(doc_2, part)

        expected_doc_parts = set([doc_1.z_nummer, doc_2.z_nummer])
        found_doc_parts = set()
        for doc2part in part.DocumentReferences:
            found_doc_parts.add(doc2part.z_nummer)

        self.assertSetEqual(expected_doc_parts, found_doc_parts)
