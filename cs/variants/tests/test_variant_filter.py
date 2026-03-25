#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import constants
from cdb.objects import operations
from cs.classification.api import get_classification
from cs.variants import api
from cs.variants.api.filter import PropertiesBasedVariantFilter
from cs.variants.selection_condition import (
    get_expression_dd_field_length,
    map_expression_to_correct_attribute,
)
from cs.variants.tests import common


def make_expression_long(expression):
    result = expression

    while len(result) < get_expression_dd_field_length():
        result += " and True"

    return result


class TestVariantFilter(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp(with_occurrences=with_occurrences)

        variability_model_prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        variability_model_prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        variant_classification = {
            variability_model_prop1: common.get_text_property_entry(
                variability_model_prop1, "VALUE1"
            ),
            variability_model_prop2: common.get_text_property_entry(
                variability_model_prop2, "VALUE1"
            ),
        }
        self.variant = api.save_variant(self.variability_model, variant_classification)

    def set_invalid_selection_condition(self):
        self.update_selection_condition_expression(
            "CS_VARIANTS_TEST_CLASS_%s != 'VALUE1' or CS_VARIANTS_TEST_CLASS_%s != 'VALUE1'"
            % (self.prop1, self.prop2)
        )

    def set_valid_selection_condition_long(self):
        long_expression = make_expression_long(
            self.selection_condition.get_expression()
        )
        self.update_selection_condition_expression(long_expression)

    def set_invalid_selection_condition_long(self):
        long_expression = make_expression_long(
            "CS_VARIANTS_TEST_CLASS_%s != 'VALUE1' or CS_VARIANTS_TEST_CLASS_%s != 'VALUE1'"
            % (self.prop1, self.prop2)
        )
        self.update_selection_condition_expression(long_expression)

    def update_selection_condition_expression(self, expression):
        operations.operation(
            constants.kOperationModify,
            self.selection_condition,
            **map_expression_to_correct_attribute(expression)
        )

    def test_variant_filter_short_true(self):
        variant_filter = self.variant.make_variant_filter()
        self.assertTrue(variant_filter.eval_bom_item(self.comp))

    def test_variant_filter_short_false(self):
        self.set_invalid_selection_condition()

        variant_filter = self.variant.make_variant_filter()
        self.assertFalse(variant_filter.eval_bom_item(self.comp))

    def test_variant_filter_long_true(self):
        self.set_valid_selection_condition_long()

        variant_filter = self.variant.make_variant_filter()
        self.assertTrue(variant_filter.eval_bom_item(self.comp))

    def test_variant_filter_long_false(self):
        self.set_invalid_selection_condition_long()

        variant_filter = self.variant.make_variant_filter()
        self.assertFalse(variant_filter.eval_bom_item(self.comp))

    def test_unsaved_variant_filter_short_true(self):
        # Need normalized floats so no narrow
        properties = get_classification(self.variant, narrowed=False)["properties"]

        variant_filter = PropertiesBasedVariantFilter(
            self.variability_model.cdb_object_id, properties
        )
        self.assertTrue(variant_filter.eval_bom_item(self.comp))

    def test_unsaved_variant_filter_short_false(self):
        self.set_invalid_selection_condition()

        # Need normalized floats so no narrow
        properties = get_classification(self.variant, narrowed=False)["properties"]

        variant_filter = PropertiesBasedVariantFilter(
            self.variability_model.cdb_object_id, properties
        )
        self.assertFalse(variant_filter.eval_bom_item(self.comp))

    def test_unsaved_variant_filter_long_true(self):
        self.set_valid_selection_condition_long()

        # Need normalized floats so no narrow
        properties = get_classification(self.variant, narrowed=False)["properties"]

        variant_filter = PropertiesBasedVariantFilter(
            self.variability_model.cdb_object_id, properties
        )
        self.assertTrue(variant_filter.eval_bom_item(self.comp))

    def test_unsaved_variant_filter_long_false(self):
        self.set_invalid_selection_condition_long()

        # Need normalized floats so no narrow
        properties = get_classification(self.variant, narrowed=False)["properties"]

        variant_filter = PropertiesBasedVariantFilter(
            self.variability_model.cdb_object_id, properties
        )
        self.assertFalse(variant_filter.eval_bom_item(self.comp))
