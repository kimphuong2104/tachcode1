# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com

from cdb.testcase import RollbackTestCase

from cs.vp.tests import test_utils as util
from cs.vp.cad.file_type_list import FileTypeList

from cs.vp.bom.web.preview.internal import AvailableViewers


class Test2DPreview(RollbackTestCase):

    def setUp(self):
        super(Test2DPreview, self).setUp()
        self.item = util.generate_item()
        self.viewers = AvailableViewers(self.item)

    def test_initialize_viewers(self):
        self.assertEqual(self.viewers.item.cdb_object_id, self.item.cdb_object_id)

    def test_initialize_viewers_by_id(self):
        viewers = AvailableViewers(self.item.cdb_object_id)

        self.assertEqual(viewers.item.cdb_object_id, self.item.cdb_object_id)

    def test_no_documents(self):
        pdfs, imgs = self.viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 0)
        self.assertEqual(len(imgs), 0)

    def test_one_document(self):
        model = util.generate_cad_document(self.item)
        pdf = util.generate_file(model, "Acrobat")
        img_1 = util.generate_file(model, "PNG")
        img_2 = util.generate_file(model, "JPG")

        pdfs, imgs = self.viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0].cdb_object_id, pdf)
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0].cdb_object_id, img_1)
        self.assertEqual(imgs[1].cdb_object_id, img_2)

    def test_multiple_documents(self):
        model_1 = util.generate_cad_document(self.item)
        pdf = util.generate_file(model_1, "Acrobat")

        model_2 = util.generate_cad_document(self.item)
        img_1 = util.generate_file(model_2, "PNG")

        model_3 = util.generate_cad_document(self.item)
        img_2 = util.generate_file(model_3, "JPG")

        pdfs, imgs = self.viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0].cdb_object_id, pdf)
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0].cdb_object_id, img_1)
        self.assertEqual(imgs[1].cdb_object_id, img_2)

    def test_allow_specific_file_types(self):
        model = util.generate_cad_document(self.item)
        util.generate_file(model, "Acrobat")
        util.generate_file(model, "PNG")
        util.generate_file(model, "JPG")

        viewers = AvailableViewers(self.item, allowed_file_types=FileTypeList("Acrobat"))

        pdfs, imgs = viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 1)
        self.assertEqual(len(imgs), 0)

        viewers = AvailableViewers(self.item, allowed_file_types=FileTypeList("PNG"))

        pdfs, imgs = viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 0)
        self.assertEqual(len(imgs), 1)

        # Empty FileTypeList -> All types are forbidden.
        viewers = AvailableViewers(self.item, allowed_file_types=FileTypeList())

        pdfs, imgs = viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 0)
        self.assertEqual(len(imgs), 0)

    def test_forward_document_selection_rule(self):
        model = util.generate_cad_document(self.item)
        util.generate_file(model, "Acrobat")
        doc = util.generate_document(self.item)
        doc_pdf = util.generate_file(doc, "Acrobat")

        rule = util.generate_rule(name="Part 2D Preview: Only Documents")
        predicate = util.generate_predicate(rule, "cs.documents.Document")
        util.generate_term(predicate, "cdb_classname", "=", "document")

        viewers = AvailableViewers(self.item, document_selection_rule=rule)

        pdfs, imgs = viewers.get_2d_preview_files()

        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0].cdb_object_id, doc_pdf)
        self.assertEqual(len(imgs), 0)
