# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module test_options

This is the documentation for the test_options module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import unittest

from cdb.testcase import RollbackTestCase
from cs.vp import products
from cs.vp import variants
from cs.vp.variants import varianttableadapters
from cs.vp.variants import filter as vpfilter

# SQL> SELECT cdb_object_id, code, name_de FROM cdbvp_product
# cdb_object_id                       |code                |name_de             |
# ------------------------------------+--------------------+--------------------+
# b637b76e-ca74-11e5-8bc0-cc3d8239ce24|TEST                |                    |
#
#
# SQL> SELECT id, name_de FROM cdbvp_property where product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# id|name_de|
# --+-------+
# 52|AA     |
# 50|A      |
# 51|AB     |
# 54|B      |
# 55|C      |
#
#
# SQL> select p.id, p.name_de, ed.value, ed.value_txt_de from cdbvp_enum_def ed INNER JOIN cdbvp_property p ON p.id=ed.id AND p.product_object_id=ed.product_object_id where p.product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# id|name_de|value|value_txt_de|
# --+-------+-----+------------+
# 52|AA     |73   |AA1         |
# 52|AA     |75   |AA2         |
# 52|AA     |77   |AA3         |
# 51|AB     |63   |AB1         |
# 51|AB     |65   |AB2         |
#
#
# SQL> select constraint_text_de from cdbvp_constraint where product_object_id='b637b76e-ca74-11e5-8bc0-cc3d8239ce24'
# constraint_text_de|
# ------------------+
# !AB IF (C)        |


class TestObject(RollbackTestCase):

    def setUp(self):
        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        super(TestObject, self).setUp()

        product = products.Product.ByKeys(
            cdb_object_id="b637b76e-ca74-11e5-8bc0-cc3d8239ce24")
        if not product:
            raise Exception(
                "Cannot find test data. Fixture package cs.vptests required.")
        self.product = product

    def test_variant_invalid(self):
        """ A variant which doesn't satisfy a constraint should have the status 'invalid' """
        raise unittest.SkipTest("Feature is not supported anymore")

        variant = variants.ProductVariant.CreateVariant(
            {
                50: True,  # A
                51: 63,  # AB = AB1
                52: 77,  # AA = AA3
                54: False,  # !B
                55: True,  # C
                362: 1,  # B1
                363: 0,  # B2
            },
            product_object_id=self.product.cdb_object_id
        )
        self.assertEqual(
            variant.solver_status,
            varianttableadapters.SyncStatus.invalid.value
        )

    def test_variant_valid(self):
        """ A variant which satisfies all constraints should have the status 'ok' """
        raise unittest.SkipTest("Feature is not supported anymore")

        variant = variants.ProductVariant.CreateVariant(
            {
                50: True,  # A
                51: 63,  # AB = AB1
                52: 73,  # AA = AA1
                54: False,  # !B
                55: False,  # C
                362: 1,  # B1
                363: 0,  # B2
            },
            product_object_id=self.product.cdb_object_id
        )
        self.assertEqual(
            variant.solver_status,
            varianttableadapters.SyncStatus.ok.value
        )

    def _generate_filter_bom(self, position, props, result):
        variant = variants.ProductVariant.CreateVariant(
            props,
            product_object_id=self.product.cdb_object_id
        )
        bom_filter = vpfilter.VariantBOMFilter(
            self.product.cdb_object_id, variant.id)

        maxbom = self.product.MaxBoms[0]
        component = maxbom.ComponentsByPosition[position][0]

        self.assertEqual(
            bom_filter.eval(
                baugruppe=component.baugruppe,
                b_index=component.b_index,
                teilenummer=component.teilenummer,
                t_index=component.t_index,
                variante=component.variante,
                position=component.position
            ),
            result
        )

    def test_filter_value_option(self):
        """ A value should filter a bom option

            If we have a bom predicate of type 'Option' and a variant with
            a property value, the bom predicate should evaluate to True.
        """
        self._generate_filter_bom(2, {51: 63}, True)  # AB = AB1

    def test_filter_option_value(self):
        """ An option should not filter a bom value

            If we have a bom predicate of type 'value' and a variant with
            an option, the bom predicate should evaluate to False.
        """
        self._generate_filter_bom(5, {51: True}, False)  # AB
