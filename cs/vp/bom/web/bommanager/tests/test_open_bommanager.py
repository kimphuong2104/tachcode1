# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


from cdb.testcase import RollbackTestCase
from cdb import util

import cs.vp.bom.tests as common
from cs.vp import bom
from cs.vp.bom.web import bommanager

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class TestOpenBOMManager(RollbackTestCase):

    def setUp(self):
        super(TestOpenBOMManager, self).setUp()
        util.PersonalSettings().invalidate()
        bommanager.set_active_bom_type_setting('mBOM')
        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 0
        bom._n_bom_types = None

    def tearDown(self):
        super(TestOpenBOMManager, self).tearDown()
        bommanager.set_active_bom_type_setting('mBOM')
        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 0

    def test_open_ebom(self):
        """The operation called on an ebom without mboms will open the bom manager only on the ebom"""
        ebom = common.generateItem()
        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_one_mbom_of_active_type(self):
        """The operation called on an ebom with just one mbom and mbom as active bom type will open the bom manager for the mbom"""
        ebom = common.generateItem()
        mbom = ebom.generate_mbom()

        bommanager.set_active_bom_type_setting("mBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("mBOM"),
                         "mBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertEqual(rbom, mbom, "The mbom was not opened on the right")

    def test_open_ebom_with_one_mbom_of_not_active_type(self):
        """The operation called on an ebom with just one mbom and sbom as active bom type will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_mbom()

        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        bommanager.set_active_bom_type_setting("sBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("sBOM"),
                         "sBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_multiple_mboms_of_active_type(self):
        """The operation called on an ebom with more than one mbom and mbom as active bom type will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_mbom()
        ebom.generate_mbom()

        bommanager.set_active_bom_type_setting("mBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("mBOM"),
                         "mBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_multiple_mboms_of_active_type_and_one_sbom(self):
        """The operation called on an ebom with more than one mbom and mbom as active bom type and one sbom will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_mbom()
        ebom.generate_mbom()
        ebom.generate_sbom()

        bommanager.set_active_bom_type_setting("mBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("mBOM"),
                         "mBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_one_sbom_of_active_type(self):
        """The operation called on an ebom with just one sbom and sbom as active bom type will open the bom manager for the sbom"""
        ebom = common.generateItem()
        sbom = ebom.generate_sbom()

        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        bommanager.set_active_bom_type_setting("sBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("sBOM"),
                         "sBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertEqual(rbom, sbom, "The sbom was not opened on the right")

    def test_open_ebom_with_one_sbom_of_not_active_type(self):
        """The operation called on an ebom with just one sbom and mbom as active bom type will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_sbom()

        bommanager.set_active_bom_type_setting("mBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("mBOM"),
                         "mBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_multiple_sboms_of_active_type(self):
        """The operation called on an ebom with more than one sbom and sbom as active bom type will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_sbom()
        ebom.generate_sbom()

        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        bommanager.set_active_bom_type_setting("sBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("sBOM"),
                         "sBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")

    def test_open_ebom_with_multiple_sboms_of_active_type_and_one_mbom(self):
        """The operation called on an ebom with more than one sbom and sbom as active bom type and one mbom will open the bom manager just for the ebom"""
        ebom = common.generateItem()
        ebom.generate_sbom()
        ebom.generate_sbom()
        ebom.generate_mbom()

        bom.BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        bommanager.set_active_bom_type_setting("sBOM")

        lbom, rbom = bommanager.get_boms(ebom)

        self.assertEqual(bommanager.get_active_bomtype(), bom.BomType.GetBomTypeForCode("sBOM"),
                         "sBOM is not the active bom type")
        self.assertEqual(lbom, ebom, "The ebom was not opened on the left")
        self.assertIsNone(rbom, "Found an unexpected bom on the right")
