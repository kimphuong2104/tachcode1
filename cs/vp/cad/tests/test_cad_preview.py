# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.testcase import RollbackTestCase

from cs.vp.tests import test_utils as util

# Exported objects
__all__ = []


class TestCadPreview(RollbackTestCase):
    def setUp(self):
        super(TestCadPreview, self).setUp()
        self.item = util.generate_item()
        self.doc = util.generate_cad_document(self.item)

    def test_get_primary_pdf__empty_document(self):
        self.assertListEqual([], self.doc.get_2d_preview_pdfs())

    def test_get_supported_preview_image__empty_document(self):
        self.assertListEqual([], self.doc.get_2d_supported_preview_images())
    
    def test_get_primary_pdf__only_one_pdf(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        gen_file = util.generate_derived_file(self.doc, primary_file_id, "Acrobat")
        self.doc.Reload()

        found = self.doc.get_2d_preview_pdfs()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)

    def test_get_supported_preview_image__only_one_png(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        gen_file = util.generate_derived_file(self.doc, primary_file_id, "PNG")
        self.doc.Reload()

        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)

    def test_get_supported_preview_image__only_one_jpg(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        gen_file = util.generate_derived_file(self.doc, primary_file_id, "JPG")
        self.doc.Reload()

        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)

    def test_get_supported_preview_image__only_one_jpeg(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        gen_file = util.generate_derived_file(self.doc, primary_file_id, "JPEG")
        self.doc.Reload()

        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)

    def test_get_supported_preview_image__belongs_to__only_one_png(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        gen_file = util.generate_associated_file(self.doc, primary_file_id, "PNG", "Testfile")
        self.doc.Reload()

        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)
        self.assertEqual(found[0].cdbf_name, "Testfile")

    def test_get_supported_preview_image__pdf_and_png(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        util.generate_derived_file(self.doc, primary_file_id, "Acrobat")
        gen_file = util.generate_derived_file(self.doc, primary_file_id,"PNG")
        self.doc.Reload()
        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found))
        self.assertEqual(gen_file, found[0].cdb_object_id)

    def test_get_supported_preview_image__multiple_images(self):
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        util.generate_derived_file(self.doc, primary_file_id, "PNG")
        util.generate_derived_file(self.doc, primary_file_id, "JPG")
        util.generate_derived_file(self.doc, primary_file_id, "JPEG")
        util.generate_derived_file(self.doc, primary_file_id, "PNG")
        self.doc.Reload()
        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(4, len(found))

    def test_get_supported_preview_image__wrong_type(self):
        
        primary_file_id = util.generate_primary_file(self.doc, "CatiaV5:Prod")
        util.generate_derived_file(self.doc, primary_file_id, "PNGG")

        self.doc.Reload()
        found = self.doc.get_2d_supported_preview_images()

        self.assertEqual(0, len(found))

    def test_get_supported_preview_image__sorting_order(self):
        file_1 = util.generate_file(self.doc, "JPEG")
        primary_file_id = util.generate_primary_file(self.doc, "PNG")
        associated_file_id = util.generate_associated_file(self.doc, primary_file_id, "JPEG")
        derived_file_id = util.generate_derived_file(self.doc, primary_file_id, "JPEG")
        primary_file_2_id = util.generate_primary_file(self.doc, "PNG")

        self.doc.Reload()
        found = self.doc.get_2d_supported_preview_images()
        found_ids = [f.cdb_object_id for f in found]

        self.assertEqual(5, len(found))
        self.assertListEqual(
            [
                associated_file_id,
                derived_file_id,
                primary_file_id,
                primary_file_2_id,
                file_1
            ],
            found_ids)

    def test_get_supported_preview__no_primary_or_derived(self):
        util.generate_file(self.doc, "Acrobat")
        util.generate_file(self.doc, "PNG")
        util.generate_file(self.doc, "JPG")
        util.generate_file(self.doc, "JPGG")

        self.doc.Reload()

        found_pdf = self.doc.get_2d_preview_pdfs()
        found_images = self.doc.get_2d_supported_preview_images()

        self.assertEqual(1, len(found_pdf))
        self.assertEqual(2, len(found_images))

    def test_3d_preview__not_available(self):
        self.assertFalse(self.doc.is_3d_preview_available())

    def test_3d_preview__available(self):
        util.generate_file(self.doc, "Hoops:SCZ")

        self.doc.Reload()

        self.assertTrue(self.doc.is_3d_preview_available())

    def test_preview_and_thumbnail_are_same(self):
        # No preview, no thumbnail.
        self.assertIsNone(self.doc.GetThumbnailFile())

        image = util.generate_file(self.doc, "PNG")
        self.doc.Reload()

        self.assertEqual(self.doc.GetThumbnailFile(), self.doc.get_2d_supported_preview_images()[0])
        self.assertEqual(self.doc.GetThumbnailFile().cdb_object_id, image)

        # Preview changes -> thumbnail changes.
        primary_image = util.generate_primary_file(self.doc, "PNG")
        self.doc.Reload()

        self.assertEqual(self.doc.GetThumbnailFile(), self.doc.get_2d_supported_preview_images()[0])
        self.assertEqual(self.doc.GetThumbnailFile().cdb_object_id, primary_image)
