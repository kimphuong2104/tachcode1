#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from contextlib import contextmanager

from cdb import testcase
from cs.classification.api import compare_classification, get_classification
from cs.variants import Variant
from cs.variants.api import helpers
from cs.vp import items


class TestCopyVariantClassification(testcase.RollbackTestCase):
    def test_copy(self):
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")

        attrs = {"teilenummer": items.Item.MakeItemNumber(), "t_index": ""}
        instance = maxbom.Copy(**attrs)
        self.assertIsNotNone(instance, "instance not created")
        current_cls = get_classification(instance)
        self.assertListEqual(current_cls["assigned_classes"], [])

        helpers.copy_variant_classification(variant, instance)
        instance.Reload()

        cls_compare = compare_classification(variant, instance)
        self.assertTrue(cls_compare["classification_is_equal"])


class TestGetPartUsage(testcase.RollbackTestCase):
    def test_no_part(self):
        result = helpers.count_part_used_in_bom_items("blub", "")
        self.assertEqual(result, 0)

    def test_no_reuse(self):
        result = helpers.count_part_used_in_bom_items("9508622", "")
        self.assertEqual(result, 1)

    def test_multiple(self):
        result = helpers.count_part_used_in_bom_items("9508576", "")
        self.assertEqual(result, 7)

    def test_with_imprecise(self):
        """
        Same assembly with mixed imprecise and index

        Query for 9508686@a for usage must return 2
            -> one precise with index a
            -> one imprecise without index

        9508684@ - VAR_TEST_PART_REUSE_IMPRECISE
         +- 9508685@ - VAR_TEST_PART_REUSE_IMPRECISE_L1P0
         |  +- 9508686@a - VAR_TEST_PART_REUSE_IMPRECISE_L2P0   <- Index a, precise
         |  |  +- 9508687@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P0
         |  |  +- 9508688@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P1
         |  +- 9508686@b - VAR_TEST_PART_REUSE_IMPRECISE_L2P0   <- Index b, precise
         |  |  +- 9508687@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P0
         |  |  +- 9508688@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P1
         +- 9508692@ - VAR_TEST_PART_REUSE_IMPRECISE_L1P1
            +- 9508686@ - VAR_TEST_PART_REUSE_IMPRECISE_L2P0     <- No index, imprecise
            |  +- 9508687@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P0
            |  +- 9508688@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P1
            +- 9508696@ - VAR_TEST_PART_REUSE_IMPRECISE_L2P1
               +- 9508697@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P0
               +- 9508698@ - VAR_TEST_PART_REUSE_IMPRECISE_L3P1
        :return:
        """
        result = helpers.count_part_used_in_bom_items("9508686", "a")
        self.assertEqual(result, 2)


@contextmanager
def switch_reuse(to: bool = True) -> None:
    """contextmanager to enable or disable reuse"""
    original_value = helpers.REUSE_ENABLED
    try:
        helpers.REUSE_ENABLED = to
        yield
    finally:
        helpers.REUSE_ENABLED = original_value
