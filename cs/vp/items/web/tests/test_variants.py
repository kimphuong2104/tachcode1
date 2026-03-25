# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module test_variants

This is the documentation for the test_variants module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import unittest

from cdb.testcase import RollbackTestCase, error_logging_disabled

from webtest import TestApp as Client

from cs.platform.web.root import Root
from cs.vp import products
from cs.vp import variants


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

        self.rest_key = "9502657@"

        product = products.Product.ByKeys(
            cdb_object_id="b637b76e-ca74-11e5-8bc0-cc3d8239ce24")
        if not product:
            raise Exception(
                "Cannot find test data. Fixture package cs.vptests required.")
        self.product = product

        app = Root()
        self.c = Client(app)

    def test_filter_bom(self):
        "Calling BOM/filtered with valid product_object_id and variant_id should return the filtered bom"

        variant = variants.ProductVariant.CreateVariant(
            {
                51: 65,  # AB = AB2
                52: 77  # AA = AA1
            },
            product_object_id=self.product.cdb_object_id
        )

        response = self.c.get(
            '/api/v1/collection/part/%s/relship/BOM/filtered' % self.rest_key,
            {
                "product_object_id": self.product.cdb_object_id,
                "variant_id": variant.id
            }
        )

        targets = response.json.get("targets")
        self.assertEqual(len(targets), 3)
        self.assertEqual(
            set([target.get("teilenummer") for target in targets]),
            set(["9502658", "9502659", "9502660"])
        )

    def test_filter_bom_without_params(self):
        "Calling BOM/filtered without product_object_id and variant_id should return the filtered bom"

        response = self.c.get(
            '/api/v1/collection/part/%s/relship/BOM/filtered' % self.rest_key
        )
        targets = response.json.get("targets")
        self.assertEqual(len(targets), 6)

    def test_filter_bom_invalid(self):
        "Calling BOM/filtered with invalid product_object_id and variant_id should produce a 404 error"

        with error_logging_disabled():
            response = self.c.get(
                '/api/v1/collection/part/%s/relship/BOM/filtered' % self.rest_key,
                {
                    "product_object_id": "invalid",
                    "variant_id": "lala"
                },
                expect_errors=True
            )
        self.assertEqual(response.status_code, 404)
