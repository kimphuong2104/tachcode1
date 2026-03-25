# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.vp.variants import tests

from cdb.testcase import RollbackTestCase
from cs.vp import variants


class TestVariantInfoText(RollbackTestCase):
    def setUp(self):
        super(TestVariantInfoText, self).setUp()

        # prevent bug where the id is 0
        variants.properties.EnumDefinition.NewID()
        variants.properties.EnumDefinition.NewID()

        product = tests.generateProductWithEnumValues(product_code="TEST_INFO_STRING_2")
        self.variant = tests.generateVariantForProduct(product)

    def test_get_info_text(self):
        """A variant will have the correct info text generated"""
        expected = '{Test property alphanumeric}=Hello world, {Test property numeric}=42, {Test property boolean} \u2610'
        self.assertEqual(self.variant.getInfoText(lang="en"), expected)
