# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb.testcase import RollbackTestCase

from cs.vp.items import Item
from cs.vp.tests import test_utils as util


class TestItemImagePreview(RollbackTestCase):
    def setUp(self):
        super(TestItemImagePreview, self).setUp()

        self.item = util.generate_item()

    def get_image_preview_file(self, item=None):
        requested_item = self.item if item is None else item
        return Item.search_image_preview_file(requested_item.get_preview_documents())

    def test_when_no_models_then_no_preview(self):

        image_file = self.item.get_image_preview_file()
        self.assertIsNone(image_file)

    def test_when_no_files_then_no_preview(self):
        util.generate_cad_document(self.item)

        image_file = self.item.get_image_preview_file()
        self.assertIsNone(image_file)

    def test_when_only_unsupported_files_then_no_preview(self):
        model = util.generate_cad_document(self.item)
        util.generate_file(model, "Acrobat")

        image_file = self.item.get_image_preview_file()
        self.assertIsNone(image_file)

    def test_skip_unsupported_files_within_model(self):
        model = util.generate_cad_document(self.item)
        util.generate_file(model, "Acrobat")
        preview_file = util.generate_file(model, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

    def test_skip_unsupported_files_across_models(self):
        model = util.generate_cad_document(self.item)
        util.generate_file(model, "Acrobat")

        model2 = util.generate_cad_document(self.item)
        preview_file = util.generate_file(model2, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

    def test_skip_models_without_files(self):
        util.generate_cad_document(self.item)
        util.generate_cad_document(self.item)
        model = util.generate_cad_document(self.item)
        preview_file = util.generate_file(model, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

    def test_preview_only_first_supported_file(self):
        model_1 = util.generate_cad_document(self.item)
        util.generate_file(model_1, "Acrobat")

        model_2 = util.generate_cad_document(self.item)
        util.generate_file(model_2, "Acrobat")
        preview_file = util.generate_file(model_2, "PNG")

        model_3 = util.generate_cad_document(self.item)
        util.generate_file(model_3, "JPG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

    def test_preview_image_by_priority(self):
        # Prioritize derived/associated over others.
        item = util.generate_item()
        model = util.generate_cad_document(item)
        util.generate_file(model, "PNG")
        primary_file = util.generate_primary_file(model, "PNG")
        preview_file = util.generate_derived_file(model, primary_file, "PNG")

        image_file = item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

        item = util.generate_item()
        model = util.generate_cad_document(item)
        # There does not necessarily need to be a primary file.
        parent_file = util.generate_file(model, "PNG")
        preview_file = util.generate_derived_file(model, parent_file, "PNG")

        image_file = item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

        item = util.generate_item()
        model = util.generate_cad_document(item)
        util.generate_file(model, "PNG")
        util.generate_primary_file(model, "PNG")
        preview_file = util.generate_associated_file(model, primary_file, "PNG")

        image_file = item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

        # Prioritize primary over non-derived/non-associated.
        item = util.generate_item()
        model = util.generate_cad_document(item)
        util.generate_file(model, "PNG")
        preview_file = util.generate_primary_file(model, "PNG")
        util.generate_file(model, "PNG")
        # Second primary should be skipped.
        util.generate_primary_file(model, "PNG")

        image_file = item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, preview_file)

    def test_get_derived_across_docs(self):
        model_with_regular = util.generate_cad_document(self.item)
        util.generate_file(model_with_regular, "PNG")

        model_with_primary = util.generate_cad_document(self.item)
        util.generate_primary_file(model_with_primary, "PNG")

        model_with_derived = util.generate_cad_document(self.item)
        primary_file = util.generate_primary_file(model_with_derived, "PNG")
        derived_file = util.generate_derived_file(model_with_derived, primary_file, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, derived_file)

    def test_get_associated_across_docs(self):
        model_with_regular = util.generate_cad_document(self.item)
        util.generate_file(model_with_regular, "PNG")

        model_with_primary = util.generate_cad_document(self.item)
        util.generate_primary_file(model_with_primary, "PNG")

        model_with_associated = util.generate_cad_document(self.item)
        primary_file = util.generate_primary_file(model_with_associated, "PNG")
        associated_file = util.generate_associated_file(model_with_associated, primary_file, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, associated_file)

    def test_get_primary_across_docs(self):
        model_with_regular = util.generate_cad_document(self.item)
        util.generate_file(model_with_regular, "PNG")

        model_with_primary = util.generate_cad_document(self.item)
        primary_file = util.generate_primary_file(model_with_primary, "PNG")

        image_file = self.item.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, primary_file)

    def test_when_derived_then_recurse(self):
        model = util.generate_cad_document(self.item)
        image = util.generate_file(model, "PNG")

        item2 = util.generate_item(cdb_depends_on=self.item.cdb_object_id)

        # Since item2 depends on self.item, it should take the preview from self.item.
        image_file = item2.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, image)

        # Same test as above but makes sure get_image_preview_file() passes 'from_master_item=True'.
        image_file = item2.get_image_preview_file()
        self.assertEqual(image_file.cdb_object_id, image)

    def test_preview_and_thumbnail_are_same(self):
        # No preview, no thumbnail.
        thumbnail = self.item.GetThumbnailFile()
        self.assertIsNone(thumbnail)

        model = util.generate_cad_document(self.item)
        image = util.generate_file(model, "PNG")
        thumbnail = self.item.GetThumbnailFile()

        self.assertEqual(thumbnail.cdb_object_id, image)

        # Preview changes -> thumbnail changes.
        primary_image = util.generate_primary_file(model, "PNG")
        derived_image = util.generate_derived_file(model, primary_image, "PNG")
        model.Reload()
        thumbnail = self.item.GetThumbnailFile()

        self.assertEqual(thumbnail.cdb_object_id, derived_image)
