# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module test_items

This is the documentation for the test_items module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import datetime

from cdb import testcase, cdbuuid, ElementsError
from cdb.objects import operations
from cdb.platform.gui import Message
from cs.documents import Document

from cs.vp import products
from cs.vp.cad import Model
from cs.vp.items_documents import DocumentToPart

from cs.vp.tests.test_utils import (
    generate_item,
    generate_cad_document,
    generate_document,
    generate_rule,
    generate_predicate,
    generate_term)

ITEM_CATEGORY = "Baukasten"

# status numbers
REVIEW = 100
RELEASED = 200


def generateItem(**args):
    item_args = dict(
        benennung="Blech",
        t_kategorie=ITEM_CATEGORY,
        t_bereich="Engineering",
        mengeneinheit="qm",
        **args
    )
    return generate_item(**item_args)


def generate_product(**args):
    item_args = dict(
        code=cdbuuid.create_sortable_id()[:20],
        **args
    )
    return operations.operation(
        "CDB_Create",
        products.Product,
        **item_args
    )


class ItemTests(testcase.RollbackTestCase):

    def test_set_cdb_objektart(self):
        """The attribute cdb_objektart is automatically set when creating items not interactively"""
        item = generateItem()
        self.assertIsNotNone(item.cdb_objektart, "cdb_objektart is None")
        self.assertNotEqual(item.cdb_objektart, "", "cdb_objektart is empty")

    def test_clean_product2part_table(self):
        """Tests that the link from product2part is deleted when the item is deleted"""
        item = generateItem()
        product = generate_product()
        link = products.ProductPart.Create(
            product_object_id=product.cdb_object_id,
            teilenummer=item.teilenummer,
            t_index=item.t_index
        )
        self.assertIsNotNone(item)
        self.assertIsNotNone(product)
        self.assertIsNotNone(link)

        res = products.ProductPart.KeywordQuery(product_object_id=product.cdb_object_id)
        self.assertEqual(len(res), 1, "Link from product to part does not exists")

        operations.operation("CDB_Delete", item)

        res = products.ProductPart.KeywordQuery(product_object_id=product.cdb_object_id)
        self.assertEqual(len(res), 0, "Link from product to part not removed")

    def test_clean_product2part_table_only_correct_part(self):
        """Tests that the *correct* link from product2part is deleted when the item is deleted."""
        item = generateItem()
        item2 = generateItem()
        product = generate_product()
        link = products.ProductPart.Create(
            product_object_id=product.cdb_object_id,
            teilenummer=item.teilenummer,
            t_index=item.t_index
        )
        link2 = products.ProductPart.Create(
            product_object_id=product.cdb_object_id,
            teilenummer=item2.teilenummer,
            t_index=item2.t_index
        )
        self.assertIsNotNone(item)
        self.assertIsNotNone(item2)
        self.assertIsNotNone(product)
        self.assertIsNotNone(link)
        self.assertIsNotNone(link2)

        res = products.ProductPart.KeywordQuery(product_object_id=product.cdb_object_id)
        self.assertEqual(len(res), 2, "Link from product to part does not exists")

        operations.operation("CDB_Delete", item)

        res = products.ProductPart.KeywordQuery(product_object_id=product.cdb_object_id)
        self.assertEqual(len(res), 1, "Link from product to part not removed")
        link = res[0]
        self.assertEqual(link.teilenummer, item2.teilenummer)
        self.assertEqual(link.t_index, item2.t_index)

    def test_fail_validation_changed_ebom(self):
        # Prepare eBOMs with different teilenummern.
        eBom1 = generateItem(type_object_id="eBOM")
        eBom2 = generateItem(type_object_id="eBOM")

        # Prepare multiple indices of same mBOM.
        mBom = generateItem(type_object_id="mBOM", cdb_depends_on=eBom1.cdb_object_id)
        operations.operation("CDB_Index", mBom)

        # Changing eBOM of just one mBOM index should fail validation.
        expected_msg = Message.GetMessage("cdb_invalid_ebom_for_mbom", eBom1.teilenummer)
        with self.assertRaisesRegex(ElementsError, str(expected_msg)):
            operations.operation("CDB_Modify", mBom, cdb_depends_on=eBom2.cdb_object_id)

    def test_copy_resets_attributes(self):
        item = generateItem(t_ersatz_fuer='000000', t_ersatz_durch='000001')

        # Release item to fill t_pruefer / t_pruef_datum.
        item.ChangeState(REVIEW)
        item.ChangeState(RELEASED)

        copy = operations.operation('CDB_Copy', item, teilenummer='#')

        # Attributes copied implicitly (those specified above in generateItem(...)) should be reset by copy.
        self.assertEqual(copy.t_ersatz_fuer, '')
        self.assertEqual(copy.t_ersatz_durch, '')
        self.assertEqual(copy.t_pruefer, '')
        self.assertIsNone(copy.t_pruef_datum)

    def test_copy_keep_explicit_attribute_changes(self):
        item = generateItem(t_ersatz_fuer='000000', t_ersatz_durch='000001')

        # Release item to fill t_pruefer / t_pruef_datum.
        item.ChangeState(REVIEW)
        item.ChangeState(RELEASED)

        explicit_date = datetime.date.today() + datetime.timedelta(days=1)
        explicit_date = datetime.datetime(explicit_date.year, explicit_date.month, explicit_date.day, 0, 0)

        copy = operations.operation(
            'CDB_Copy',
            item,
            teilenummer='#',
            t_ersatz_fuer='100002', # use nonexisting part number to avoid side effects of setReplacementFor
            t_ersatz_durch='100003', # use nonexisting part number to avoid side effects of setReplacementFor
            t_pruefer='caddok',
            t_pruef_datum=explicit_date)

        # Explicit arguments specified in copy operation should be kept.
        self.assertEqual(copy.t_ersatz_fuer, '100002')
        self.assertEqual(copy.t_ersatz_durch, '100003')
        self.assertEqual(copy.t_pruefer, 'caddok')
        self.assertEqual(copy.t_pruef_datum, explicit_date)

    def test_copy_reset_explicit_unchanged_attribute(self):
        item = generateItem(t_ersatz_fuer='000000', t_ersatz_durch='000001')

        # Release item to fill t_pruefer / t_pruef_datum.
        item.ChangeState(REVIEW)
        item.ChangeState(RELEASED)

        copy = operations.operation(
            'CDB_Copy',
            item,
            teilenummer='#',
            t_ersatz_fuer=item.t_ersatz_fuer,
            t_ersatz_durch=item.t_ersatz_durch,
            t_pruefer=item.t_pruefer,
            t_pruef_datum=item.t_pruef_datum)

        # The current behavior resets these attributes even if specified explicitly in the copy operation if
        # the passed values are the same as in the source part.
        self.assertEqual(copy.t_ersatz_fuer, '')
        self.assertEqual(copy.t_ersatz_durch, '')
        self.assertEqual(copy.t_pruefer, '')
        self.assertIsNone(copy.t_pruef_datum)

    def test_get_preview_documents_no_docs(self):
        item = generateItem()
        self.assertEqual(item.get_preview_documents(), [])

    def test_get_preview_documents_no_rule(self):
        # No rule: should return only models on the item.

        item = generateItem()

        model_1 = generate_cad_document(item)
        model_2 = generate_cad_document(item)
        generate_document(item)

        preview_docs = item.get_preview_documents()

        self.assertEqual(len(preview_docs), 2)
        self.assertEqual(preview_docs[0].cdb_object_id, model_1.cdb_object_id)
        self.assertEqual(preview_docs[1].cdb_object_id, model_2.cdb_object_id)

    def test_get_preview_documents_rule_without_model(self):
        # Rule that specifies explicit class: should only return Documents of that class.

        item = generateItem()

        generate_cad_document(item)
        generate_cad_document(item)
        doc = generate_document(item)

        rule = generate_rule(name="Part Preview: Only Documents")
        generate_term(generate_predicate(rule, "cs.documents.Document"), "cdb_classname", "=", "document")

        preview_docs = item.get_preview_documents(rule)

        self.assertEqual(len(preview_docs), 1)
        self.assertEqual(preview_docs[0].cdb_object_id, doc.cdb_object_id)

    def test_get_preview_documents_prioritize_model(self):
        # Rule that specifies multiple classes, including model: Should return all documents matching any
        # class, but prioritize models.

        item = generateItem()

        generate_cad_document(item)
        generate_document(item)
        generate_cad_document(item)

        rule = generate_rule(name="Part Preview: Documents and Models")
        generate_term(generate_predicate(rule, "cs.documents.Document", predicate_name="doc_predicate"), "cdb_classname", "=", "document")
        generate_term(generate_predicate(rule, "cs.documents.Document", predicate_name="model_predicate"), "cdb_classname", "=", "model")

        preview_docs = item.get_preview_documents(rule)

        self.assertEqual(len(preview_docs), 3)
        self.assertIsInstance(preview_docs[0], Model)
        self.assertIsInstance(preview_docs[1], Model)
        self.assertIsInstance(preview_docs[2], Document)

    def test_get_preview_documents_recursively_from_master_item(self):
        item = generateItem()
        model = generate_cad_document(item)

        item_2 = generateItem(cdb_depends_on=item.cdb_object_id)
        item_3 = generateItem(cdb_depends_on=item_2.cdb_object_id)

        preview_docs = item_3.get_preview_documents()
        self.assertEqual(preview_docs[0].cdb_object_id, model.cdb_object_id)

    def test_get_preview_documents_with_recursion_false(self):
        item = generateItem()
        generate_cad_document(item)

        item_2 = generateItem(cdb_depends_on=item.cdb_object_id)
        item_3 = generateItem(cdb_depends_on=item_2.cdb_object_id)
        model = generate_cad_document(item_3)

        preview_docs = item_3.get_preview_documents(from_master_item=False)
        # Should be image from derived item (item_3), not the EngineeringView.
        self.assertEqual(preview_docs[0].cdb_object_id, model.cdb_object_id)

    def test_weak_documents_ignored_for_preview(self):
        """
        Test that weak document references are not evaluated as preview document candidates.
        """
        item = generateItem()

        # We let the model strongly relate to another item, but create a weak reference to above item.
        model = generate_cad_document(generateItem())

        operations.operation(
            "CDB_Create",
            DocumentToPart,
            teilenummer=item.teilenummer,
            t_index=item.t_index,
            z_nummer=model.z_nummer,
            z_index=model.z_index
        )

        # Documents that are only weakly related to the part should not be evaluated for the preview.
        self.assertEqual(item.get_preview_documents(), [])
