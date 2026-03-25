# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import unittest
import urllib.parse
from webtest import TestApp as Client

from cs.platform.web.root import Root

from cs.vp.utils import parse_url_query_args


class TestLegacyPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lbom_oid = "lbom123"
        cls.rbom_oid = "rbom123"
        cls.variability_model_oid = "var_model123"
        cls.product_object_id = "product123"
        cls.variant_id = "123"
        cls.site_oid = "site123"
        cls.site_oid2 = "site2123"
        cls.signature = "signature123"

        cls.bommanager_base_legacy_url = "/bommanager/{lbom_oid}".format(lbom_oid=cls.lbom_oid)

    def get_bommanager_legacy_url(self, query_args):
        url = self.bommanager_base_legacy_url
        if len(query_args) > 0:
            url += "/" + \
               "/".join(["/".join(item) for item in query_args.items()])

        return url

    def get_request_for_legacy_url(self, expect_errors=False, **query_args):
        c = Client(Root())
        return c.get(self.get_bommanager_legacy_url(query_args), expect_errors=expect_errors)

    def check_with_query_args(self, **query_args):
        expected_query_args = {each_key: each_value for each_key, each_value in query_args.items()}

        response = self.get_request_for_legacy_url(**query_args)
        location = response.headers['location']

        parsed_url_query_args = parse_url_query_args(location)

        self.assertEqual(self.bommanager_base_legacy_url, urllib.parse.urlparse(location).path)
        self.assertDictEqual(expected_query_args, parsed_url_query_args)

    def test_redirect_legacy_full_path(self):
        self.check_with_query_args(
            rbom=self.rbom_oid,
            variability_model=self.variability_model_oid,
            variant=self.variant_id,
            site=self.site_oid,
            site2=self.site_oid2,
            signature=self.signature
        )

    def test_redirect_legacy_mixed_path(self):
        self.check_with_query_args(
            rbom=self.rbom_oid,
            variability_model=self.variability_model_oid,
            site=self.site_oid
        )

    def test_redirect_legacy_rbom_path(self):
        self.check_with_query_args(
            rbom=self.rbom_oid,
        )

    def test_redirect_legacy_variability_model_path(self):
        self.check_with_query_args(
            variability_model=self.variability_model_oid,
        )

    def test_redirect_legacy_product_path(self):
        self.check_with_query_args(
            product=self.product_object_id,
        )

    def test_redirect_legacy_variant_path(self):
        self.check_with_query_args(
            variant=self.variant_id,
        )

    def test_redirect_legacy_site_path(self):
        self.check_with_query_args(
            site=self.site_oid,
        )

    def test_redirect_legacy_site2_path(self):
        self.check_with_query_args(
            site2=self.site_oid2
        )

    def test_redirect_legacy_signature_path(self):
        self.check_with_query_args(
            signature=self.signature
        )

    def test_redirect_legacy_empty_path(self):
        response = self.get_request_for_legacy_url(
            expect_errors=True
        )

        self.assertEqual(404, response.status_int)

    def test_redirect_legacy_with_not_valid_path_elements(self):
        response = self.get_request_for_legacy_url(
            rbom=self.rbom_oid,
            variability_model=self.variability_model_oid,
            variant=self.variant_id,
            site=self.site_oid,
            site2=self.site_oid2,
            signature=self.signature,
            blub="blub123",
            expect_errors=True
        )

        self.assertEqual(404, response.status_int)

    def test_redirect_legacy_with_not_valid_path_element(self):
        response = self.get_request_for_legacy_url(
            blub="blub123",
            expect_errors=True
        )

        self.assertEqual(404, response.status_int)
