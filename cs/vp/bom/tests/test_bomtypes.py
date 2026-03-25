# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the bom types
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.testcase import RollbackTestCase, max_sql

from cdb import constants, ElementsError
from cdb.objects import operations

from cs.vp.bom import BomType


class TestActivatedBomTypes(RollbackTestCase):
    def test_sbom_deactivated(self):
        """ The sBOM BOM Type is present but disabled """
        sbom_bom_type = BomType.GetBomTypeForCode(code="sBOM")
        self.assertIsNotNone(sbom_bom_type)
        self.assertEqual(sbom_bom_type.is_enabled, 0)

    def test_defaults_enabled(self):
        """ The default BOM Types must be enabled """
        ebom = BomType.GetBomTypeForCode(code="eBOM")
        mbom = BomType.GetBomTypeForCode(code="mBOM")

        self.assertIsNotNone(ebom)
        self.assertIsNotNone(mbom)
        self.assertEqual(mbom.is_enabled, 1)
        self.assertEqual(ebom.is_enabled, 1)

    def test_defaults_disable(self):
        """ The default BOM Types cannot be disabled """
        for bom_type_code in ["eBOM", "mBOM"]:
            bom_type = BomType.GetBomTypeForCode(code=bom_type_code)
            self.assertIsNotNone(bom_type)
            self.assertEqual(bom_type.is_enabled, 1)
            with self.assertRaisesRegex(
                ElementsError,
                "Der Stücklistentyp {} kann nicht deaktiviert werden.".format(bom_type_code)
            ):
                operations.operation(
                    constants.kOperationModify,
                    bom_type,
                    is_enabled=0
                )

    def test_ebom_identity(self):
        """ The eBOM BOM Type has the correct cdb_object_id """
        ebom = BomType.GetBomTypeForCode(code="eBOM")
        self.assertEqual(ebom.cdb_object_id, "af664278-1938-11eb-9e9d-10e7c6454cd1")

    def test_bom_types_caches(self):
        """ BOM Types are being queried only once and cached """
        sbom = BomType.GetBomTypeForCode(code="sBOM")

        with max_sql(0):
            for _ in range(10):
                other = BomType.GetBomTypeForCode(code="sBOM")
                self.assertEqual(sbom, other)


