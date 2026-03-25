# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import collections

from webtest import TestApp as Client

from cdb.validationkit import run_with_roles
from cs.platform.web.root import Root
from cs.variants.tests import common


class TestInternalVariantById(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp()

        self.props = collections.OrderedDict(
            [
                (self.prop1, "VALUE1"),
                (self.prop2, "VALUE2"),
            ]
        )

        self.variant = common.generate_variant(self.variability_model, self.props)

    def test_fetch_existing_variant_by_id(self):
        c = Client(Root())
        response = c.get(
            "/internal/variant_filter/variant_by_id/"
            "{variant_id}/variability_model/{variability_model_id}".format(
                variant_id=self.variant.id,
                variability_model_id=self.variability_model.cdb_object_id,
            )
        )

        self.assertEqual(200, response.status_int)
        self.assertEqual(self.variant.id, response.json["object"]["id"])

        prop1_found = False
        prop2_found = False
        for each_key, each_value in response.json["classification"].items():
            if each_key.endswith(self.prop1):
                self.assertEqual(self.props[self.prop1], each_value[0]["value"])
                prop1_found = True
            if each_key.endswith(self.prop2):
                self.assertEqual(self.props[self.prop2], each_value[0]["value"])
                prop2_found = True

        self.assertTrue(prop1_found)
        self.assertTrue(prop2_found)

    def test_fetch_non_existing_variant_by_id(self):
        c = Client(Root())
        response = c.get(
            "/internal/variant_filter/variant_by_id/"
            "{variant_id}/variability_model/{variability_model_id}".format(
                variant_id=self.variant.id + 1,
                variability_model_id=self.variability_model.cdb_object_id,
            ),
            expect_errors=True,
        )

        self.assertEqual(404, response.status_int)


class TestInternalSelectionConditionByKeys(common.VariantsTestCase):
    def setUp(self, with_occurrences=True):
        super().setUp(with_occurrences=with_occurrences)

        self.props = collections.OrderedDict(
            [
                (self.prop1, "VALUE1"),
                (self.prop2, "VALUE2"),
            ]
        )

        self.variant = common.generate_variant(self.variability_model, self.props)

    @run_with_roles(["public", "Engineering"])
    def make_request(self):
        c = Client(Root())
        response = c.get(
            "/internal/selection_condition/by_keys",
            params={
                "variability_model_id": self.variability_model.cdb_object_id,
                "ref_object_id": self.occurrence1.cdb_object_id,
            },
        )

        return response.json["object"], response.json["permission"]

    def test_with_permission(self):
        result_object, result_permission = self.make_request()

        self.assertEqual(
            self.selection_condition_occurrence1.cdb_object_id,
            result_object["cdb_object_id"],
        )
        self.assertTrue(result_permission)

    def test_without_permission(self):
        self.comp.Item.ChangeState(200)
        self.subassembly.ChangeState(200)
        self.maxbom.ChangeState(200)

        result_object, result_permission = self.make_request()

        self.assertEqual(
            self.selection_condition_occurrence1.cdb_object_id,
            result_object["cdb_object_id"],
        )
        self.assertFalse(result_permission)
