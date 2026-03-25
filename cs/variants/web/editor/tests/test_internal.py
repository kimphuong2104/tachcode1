#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from webtest import AppError
from webtest import TestApp as Client

from cs.platform.web.rest.support import get_restlink
from cs.platform.web.root import Root
from cs.variants.tests import common


class TestVariantEditorInternal(common.VariantsTestCase):
    def make_request(self, include_product=False, include_variability_model=False):
        c = Client(Root())
        params = {}

        if include_product:
            params["productRestLink"] = get_restlink(self.product)

        if include_variability_model:
            params["variabilityModelRestLink"] = get_restlink(self.variability_model)

        response = c.post_json(
            "/internal/variant_manager/setup_information/",
            params,
        )
        return response.json

    def assert_result(self, result):
        self.assertTrue("product" in result)
        self.assertIsInstance(result["product"], str)
        self.assertTrue("variability_models" in result)
        self.assertIsInstance(result["variability_models"], list)
        self.assertTrue("variability_model_variants_ids" in result)
        self.assertIsInstance(result["variability_model_variants_ids"], list)
        self.assertTrue("variability_model_maxboms" in result)
        self.assertIsInstance(result["variability_model_maxboms"], dict)
        self.assertTrue("classnames" in result)
        self.assertIsInstance(result["classnames"], dict)
        self.assertTrue("rest_objects" in result)
        self.assertIsInstance(result["rest_objects"], list)
        self.assertTrue("property_definitions" in result)
        self.assertIsInstance(result["property_definitions"], dict)
        self.assertTrue("initial_table_limit" in result)
        self.assertIsInstance(result["initial_table_limit"], int)
        self.assertTrue("limit_increment" in result)
        self.assertIsInstance(result["limit_increment"], int)
        self.assertTrue("initial_applied_filter_data" in result)
        self.assertIsInstance(result["initial_applied_filter_data"], dict)

        self.assertEqual(1, len(result["variability_models"]))
        self.assertIn(get_restlink(self.product), result["product"])

    def test_fetch_variant_manager_setup_information_no_include(self):
        with self.assertRaises(AppError):
            self.make_request()

    def test_fetch_variant_manager_setup_information_only_product(self):
        result = self.make_request(include_product=True)
        self.assert_result(result)

    def test_fetch_variant_manager_setup_information_only_variability_model(self):
        result = self.make_request(include_variability_model=True)
        self.assert_result(result)

    def test_fetch_variant_manager_setup_information_both_includes(self):
        result = self.make_request(include_product=True, include_variability_model=True)
        self.assert_result(result)
