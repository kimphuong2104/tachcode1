# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from mock import MagicMock, patch

from cdb import ue
from cs.classification.validation import ClassificationValidator
from cs.variants.items import _instantiate_part_now
from cs.variants.tests import common

# IMPORTANT #
# This import does not work here:
# from cs.variants.items import _instantiate_part_now
# If this import is here then tests from other test files will not work anymore. Reason unknown.


def get_context_mock(max_bom_id=None):
    ctx_mock = MagicMock()
    ctx_mock.dialog.max_bom_id = max_bom_id
    return ctx_mock


class TestVariantInstantiate(common.VariantsTestCaseWithFloat):
    def setUp(self):
        super().setUp()

        comp = self.maxbom.Components[0]
        expression = "CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'" % self.prop1
        common.generate_selection_condition(self.variability_model, comp, expression)

        self.variant = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )
        self.variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE3",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )
        self.variant3 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE4",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )
        self.variant4 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE5",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )
        # Reset caches in cs.classification
        ClassificationValidator.reload_all()

    def test_no_bom_id(self):
        ctx_mock = get_context_mock({})

        with self.assertRaises(ue.Exception) as assert_raises:
            _instantiate_part_now([], ctx_mock)

        self.assertIn("Maximalstückliste", str(assert_raises.exception))

    def test_no_maxbom(self):
        ctx_mock = get_context_mock(1)

        with self.assertRaises(ue.Exception) as assert_raises:
            _instantiate_part_now([], ctx_mock)

        self.assertIn("Maximalstückliste", str(assert_raises.exception))

    @patch("cs.variants.items.instantiate_part")
    def test_one_variant_valid_variant(self, mock_instantiate):
        ctx_mock = get_context_mock(self.maxbom.cdb_object_id)
        mock_instantiate.return_value = True

        _instantiate_part_now([self.variant], ctx_mock)

        mock_instantiate.assert_called_once()

    @patch("cs.variants.items.instantiate_part")
    def test_multiple_variants_valid_variants(self, mock_instantiate):
        ctx_mock = get_context_mock(self.maxbom.cdb_object_id)
        mock_instantiate.return_value = True

        _instantiate_part_now([self.variant, self.variant2], ctx_mock)

        self.assertTrue(mock_instantiate.call_count == 2)

    @patch("cs.variants.api.check_classification_attributes")
    @patch("cs.variants.api.build_instance")
    def test_one_variant_with_invalid_classification(self, build_instance, mock_check):
        ctx_mock = get_context_mock(self.maxbom.cdb_object_id)
        mock_check.return_value = False
        build_instance.return_value = True

        with self.assertRaises(ue.Exception) as assert_raises:
            _instantiate_part_now([self.variant], ctx_mock)

        self.assertIn("Merkmale", str(assert_raises.exception))

        mock_check.assert_called_once()
        build_instance.assert_not_called()

    @patch("cs.variants.api.check_classification_attributes")
    @patch("cs.variants.api.make_root_instance")
    def test_multiple_variants_with_all_invalid_classification(
        self, make_root_instance, mock_check
    ):
        """
        we expect to find all variant description in result expection message
        :param make_root_instance:
        :param mock_check:
        :return:
        """
        ctx_mock = get_context_mock(self.maxbom.cdb_object_id)
        mock_check.return_value = False
        make_root_instance.return_value = True

        with self.assertRaises(ue.Exception) as assert_raises:
            _instantiate_part_now([self.variant, self.variant2], ctx_mock)

        self.assertIn(self.variant.GetDescription(), str(assert_raises.exception))
        self.assertIn(self.variant2.GetDescription(), str(assert_raises.exception))

        self.assertTrue(mock_check.call_count == 2)
        make_root_instance.assert_not_called()

    @patch("cs.variants.api.check_classification_attributes")
    @patch("cs.variants.api.make_root_instance")
    def test_multiple_variants_with_one_invalid_classification(
        self, make_root_instance, mock_check
    ):
        ctx_mock = get_context_mock(self.maxbom.cdb_object_id)
        mock_check.return_value = True
        make_root_instance.side_effect = [
            True,
            Exception("variant2"),
            True,
            Exception("variant4"),
        ]
        with self.assertRaises(ue.Exception) as assert_raises:
            _instantiate_part_now(
                [self.variant, self.variant2, self.variant3, self.variant4], ctx_mock
            )

        self.assertIn(self.variant2.GetDescription(), str(assert_raises.exception))
        self.assertIn(self.variant4.GetDescription(), str(assert_raises.exception))

        self.assertTrue(mock_check.call_count == 4)
        self.assertTrue(make_root_instance.call_count == 4)
