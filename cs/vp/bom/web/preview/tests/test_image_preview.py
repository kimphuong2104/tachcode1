# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from webob.exc import HTTPNotFound, HTTPBadRequest

from cdb.testcase import RollbackTestCase

from cs.vp.products import Product
from cs.vp.bom.web.preview.internal import ImagePreview
from cs.vp.tests import test_utils


class TestImagePreview(RollbackTestCase):

    def setUp(self):
        super(TestImagePreview, self).setUp()
        self.item = test_utils.generate_item()

    def test_object_not_found_throws_error(self):
        with self.assertRaises(HTTPNotFound):
            ImagePreview("ABCDE")

    def test_part_no_file(self):
        preview = ImagePreview(self.item.cdb_object_id)

        self.assertEqual(preview.requested_object_id, self.item.cdb_object_id)
        self.assertIsNone(preview.image_preview_file)

    def test_part_with_image_file(self):
        model = test_utils.generate_cad_document(self.item)
        image_file = test_utils.generate_file(model, "PNG")
        preview = ImagePreview(self.item.cdb_object_id)

        self.assertEqual(preview.requested_object_id, self.item.cdb_object_id)
        self.assertEqual(preview.image_preview_file.cdb_object_id, image_file)

    def test_document_no_file(self):
        doc = test_utils.generate_document(self.item)
        preview = ImagePreview(doc.cdb_object_id)

        self.assertEqual(preview.requested_object_id, doc.cdb_object_id)
        self.assertIsNone(preview.image_preview_file)

    def test_document_with_single_image_file(self):
        doc = test_utils.generate_document(self.item)
        image_file = test_utils.generate_file(doc, "PNG")
        preview = ImagePreview(doc.cdb_object_id)

        self.assertEqual(preview.requested_object_id, doc.cdb_object_id)
        self.assertEqual(preview.image_preview_file.cdb_object_id, image_file)

    def test_document_with_multiple_image_files(self):
        doc = test_utils.generate_document(self.item)
        image_file = test_utils.generate_file(doc, "PNG")
        test_utils.generate_file(doc, "JPG")
        test_utils.generate_file(doc, "PNG")
        preview = ImagePreview(doc.cdb_object_id)

        self.assertEqual(preview.requested_object_id, doc.cdb_object_id)
        self.assertEqual(preview.image_preview_file.cdb_object_id, image_file)

    def test_model_no_file(self):
        model = test_utils.generate_cad_document(self.item)
        preview = ImagePreview(model.cdb_object_id)

        self.assertEqual(preview.requested_object_id, model.cdb_object_id)
        self.assertIsNone(preview.image_preview_file)

    def test_model_with_single_image_file(self):
        model = test_utils.generate_cad_document(self.item)
        image_file = test_utils.generate_file(model, "PNG")
        preview = ImagePreview(model.cdb_object_id)

        self.assertEqual(preview.requested_object_id, model.cdb_object_id)
        self.assertEqual(preview.image_preview_file.cdb_object_id, image_file)

    def test_model_with_multiple_image_files(self):
        model = test_utils.generate_cad_document(self.item)
        image_file = test_utils.generate_file(model, "PNG")
        test_utils.generate_file(model, "JPG")
        test_utils.generate_file(model, "PNG")
        preview = ImagePreview(model.cdb_object_id)

        self.assertEqual(preview.requested_object_id, model.cdb_object_id)
        self.assertEqual(preview.image_preview_file.cdb_object_id, image_file)

    def test_invalid_object_class_throws_bad_request(self):
        product = Product.Query()[0]

        # Product is neither item nor model/document, so should throw the exception.
        with self.assertRaises(HTTPBadRequest):
            ImagePreview(product.cdb_object_id)
