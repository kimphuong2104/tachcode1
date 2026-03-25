#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cs.variants.api.instantiate_lookup import InstantiateLookup, helpers
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.vp import items


class TestInstantiateLookupReuse(ReuseTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = self._reuse_enabled

    def setUp(self):
        super().setUp()
        self._reuse_enabled = helpers.REUSE_ENABLED
        helpers.REUSE_ENABLED = True

    def test_build_reuse(self):
        """
        9508596@a - VAR_TEST_MAXBOM_DEEP Variant(2@1771fe02-f5e3-11eb-923d-f875a45b4131)
         +- 9508597@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1
            +- 9508598@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2
               +- 9508599@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3
                  +- 9508600@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4
                     +- 9508601@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5
                        +- 9508602@ - VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5

        expected reuse item
            9508614@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1
             +- 9508615@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2
                +- 9508616@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3
                   +- 9508617@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4
                      +- 9508618@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5
                         +- 9508602@ - VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5

        :return:
        """
        lookup = InstantiateLookup(self.maxbom_deep, self.var2)
        lookup.build_variant_bom()
        lookup.build_reuse()

        variant_bom = lookup.variant_bom

        expected_reuse_item = items.Item.ByKeys(teilenummer="9508614", t_index="")
        expected_reuse_keys = variant_bom.children[0].get_identification_key_values()
        self.assertIsNotNone(expected_reuse_item)

        self.assertTrue(expected_reuse_keys in variant_bom.reuse_children_lookup)
        self.assertEqual(
            variant_bom.reuse_children_lookup[expected_reuse_keys].cdb_object_id,
            expected_reuse_item.cdb_object_id,
        )
