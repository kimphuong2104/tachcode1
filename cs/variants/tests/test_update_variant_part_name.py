#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import testcase
from cs.variants import Variant
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.vp import items


class UpdateVariantPartNameTests(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.maxbom = items.Item.ByKeys(**maxbom_deep_wide_constants.t9508619_keys)
        self.variant = Variant.ByKeys(
            variability_model_id="1771fe02-f5e3-11eb-923d-f875a45b4131", id="1"
        )

    def test_variant_name_in_benennung2(self):
        """the name of the variant must be saved in benennung2"""
        self.assertIsNone(self.maxbom.benennung2)
        expected_variant_name = "my extreme awesome variant"
        self.variant.name = expected_variant_name

        self.maxbom.update_variant_part_name(self.variant)

        self.assertEqual(self.maxbom.benennung2, expected_variant_name)

    def test_to_long_variant_name_are_shortened(self):
        """name too long must be cut off"""
        self.assertIsNone(self.maxbom.benennung2)
        expected_variant_name = "dbTHu6wCf0MTqUmr2kV9FGvaysutjENhrumTIFOF1234"
        expected_variant_name_result = "dbTHu6wCf0MTqUmr2kV9FGvaysutjENhrumTIFOF"
        self.variant.name = expected_variant_name

        self.maxbom.update_variant_part_name(self.variant)

        self.assertEqual(self.maxbom.benennung2, expected_variant_name_result)

    def test_instance_must_have_correct_prefix(self):
        """the name of the new instance must have the correct prefix"""
        expected_maxbom_name_de = "MAXBOM_DE"
        expected_maxbom_name_en = "MAXBOM_EN"
        self.maxbom.SetLocalizedValue("i18n_benennung", "de", expected_maxbom_name_de)
        self.maxbom.SetLocalizedValue("i18n_benennung", "en", expected_maxbom_name_en)

        expected_name_de = "Var{0}-{1}".format(self.variant.id, expected_maxbom_name_de)
        expected_name_en = "Var{0}-{1}".format(self.variant.id, expected_maxbom_name_en)

        self.maxbom.update_variant_part_name(self.variant)

        self.assertEqual(
            self.maxbom.GetLocalizedValue("i18n_benennung", "de"), expected_name_de
        )
        self.assertEqual(
            self.maxbom.GetLocalizedValue("i18n_benennung", "en"), expected_name_en
        )

    def test_long_name_are_shortened(self):
        """name too long must be cut off"""
        expected_maxbom_name_de = "dbTHu6wCf0MTqUmr2kV9FGvaysutjENhrumTIFOF"
        expected_maxbom_name_de_result = "dbTHu6wCf0MTqUmr2kV9FGvaysutjENhrum"
        self.maxbom.SetLocalizedValue("i18n_benennung", "de", expected_maxbom_name_de)
        expected_name_de = "Var{0}-{1}".format(
            self.variant.id, expected_maxbom_name_de_result
        )

        self.maxbom.update_variant_part_name(self.variant)

        self.assertEqual(
            self.maxbom.GetLocalizedValue("i18n_benennung", "de"), expected_name_de
        )
