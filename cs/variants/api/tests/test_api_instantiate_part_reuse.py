#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import constants
from cdb.objects.operations import operation
from cs.variants.api import helpers, instantiate_part
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst
from cs.vp.items import Item


class TestApiInstantiatePartReuse(ReuseTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = False

    def setUp(self):
        super().setUp()
        helpers.REUSE_ENABLED = True

    def test_deep_reuse(self):
        result = instantiate_part(self.var2, self.maxbom_deep)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[self.t9508614],
        )

        self.assertRelationshipToMaxBOM(result, self.maxbom_deep, self.var2)
        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )

    def test_deep_wide_instantiate_v1_again(self):
        result = instantiate_part(self.var1, self.maxbom_deep_wide)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assertRelationshipToMaxBOM(result, self.maxbom_deep_wide, self.var1)
        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )

    def test_deep_wide_instantiate_v2(self):
        # Note: we must delete testdata
        to_delete = [
            "9508636",
            "9508637",
            "9508638",
            "9508639",
            "9508640",
            "9508641",
            "9508642",
        ]
        for each in to_delete:
            i = Item.ByKeys(teilenummer=each, t_index="")
            self.assertIsNotNone(i, msg="item to delete not found: {}".format(each))
            operation(constants.kOperationDelete, i)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        def get_new_subst():
            return Subst({"teilenummer": check_teilenummer, "t_index": ""})

        result = instantiate_part(self.var2, self.maxbom_deep_wide)

        l1 = get_new_subst()
        l2 = get_new_subst()
        l3 = get_new_subst()
        l4 = get_new_subst()
        l5a = get_new_subst()
        l5b = get_new_subst()

        l1.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys
        )
        l2.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys
        )
        l3.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys
        )
        l4.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys
        )
        l5a.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0_keys
        )
        l5b.occurrence_keys.append(
            maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys
        )

        l1.children.append(l2)
        l2.children.append(l3)
        l3.children.append(l4)
        l4.children.append(l5a)
        l4.children.append(l5b)
        l5a.children.append(maxbom_deep_wide_constants.t9508626)
        l5b.children.append(maxbom_deep_wide_constants.t9508627)
        l5b.children.append(maxbom_deep_wide_constants.t9508628_v2)

        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[l1],
        )

        self.assertRelationshipToMaxBOM(result, self.maxbom_deep_wide, self.var2)
        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )

    def test_instantiate_v2_again(self):
        result = instantiate_part(self.var2, self.maxbom_deep_wide)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[maxbom_deep_wide_constants.t9508637],
        )

        self.assertRelationshipToMaxBOM(result, self.maxbom_deep_wide, self.var2)
        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )
