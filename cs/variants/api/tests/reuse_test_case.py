#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cs.variants import VariabilityModel, Variant
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.variants.api.tests.reinstantiate_test_case import (
    ReinstantiateTestCase as ReTeCase,
)
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst
from cs.vp import items


class ReuseTestCase(BaseTestCase):
    maxbom_deep_wide_keys = maxbom_deep_wide_constants.t9508619_keys

    variability_model_id = (
        "39a54ecc-2401-11eb-9218-24418cdf379c"  # VAR_TEST_REINSTANTIATE
    )

    variability_model_id_multi = (
        "1771fe02-f5e3-11eb-923d-f875a45b4131"  # VAR_TEST_REINSTANTIATE_MULTI
    )

    b_t9508597_9508596_a = "7672801d-f5e3-11eb-923d-f875a45b4131"
    b_t9508614_9508613 = "6b5033dc-f6a5-11eb-923d-f875a45b4131"
    b_t9508608_9508607 = "64fa6076-f6a5-11eb-923d-f875a45b4131"
    b_t9508609_9508608 = "64fa6073-f6a5-11eb-923d-f875a45b4131"

    t9508608_id = "64fa6062-f6a5-11eb-923d-f875a45b4131"
    t9508614_id = "6b5033bb-f6a5-11eb-923d-f875a45b4131"

    maxbom_deep_without_index_keys = {"teilenummer": "9508596", "t_index": ""}

    maxbom_deep_keys = {"teilenummer": "9508596", "t_index": "a"}
    t9508618_keys = {"teilenummer": "9508618", "t_index": ""}
    t9508617_keys = {"teilenummer": "9508617", "t_index": ""}
    t9508616_keys = {"teilenummer": "9508616", "t_index": ""}
    t9508615_keys = {"teilenummer": "9508615", "t_index": ""}
    t9508614_keys = {"teilenummer": "9508614", "t_index": ""}
    t9508613_keys = {"teilenummer": "9508613", "t_index": ""}

    t9508618 = Subst(
        t9508618_keys,
        children=[ReTeCase.maxbom_deep_part_level5],
        occurrence_keys=[ReTeCase.maxbom_deep_subassembly_level5_occurrence1_keys],
    )
    t9508617 = Subst(
        t9508617_keys,
        children=[t9508618],
        occurrence_keys=[
            ReTeCase.maxbom_deep_subassembly_level4_occurrence1_keys,
            ReTeCase.maxbom_deep_subassembly_level4_occurrence2_keys,
        ],
    )
    t9508616 = Subst(
        t9508616_keys,
        children=[t9508617],
        occurrence_keys=[ReTeCase.maxbom_deep_subassembly_level3_occurrence1_keys],
    )
    t9508615 = Subst(
        t9508615_keys,
        children=[t9508616],
        occurrence_keys=[
            ReTeCase.maxbom_deep_subassembly_level2_occurrence1_keys,
            ReTeCase.maxbom_deep_subassembly_level2_occurrence2_keys,
        ],
    )
    t9508614 = Subst(
        t9508614_keys,
        children=[t9508615],
        occurrence_keys=[ReTeCase.maxbom_deep_subassembly_level1_occurrence1_keys],
    )
    t9508613 = Subst(t9508613_keys, children=[t9508614])

    expected_maxbom_deep_structure = Subst(
        maxbom_deep_keys,
        children=[ReTeCase.maxbom_deep_subassembly_level1],
    )

    _variability_model_multi = None

    @property
    def variability_model_multi(self):
        if self._variability_model_multi is None:
            self._variability_model_multi = VariabilityModel.ByKeys(
                cdb_object_id=self.variability_model_id_multi
            )

        return self._variability_model_multi

    _var1_normal = None

    @property
    def var1_normal(self):
        if self._var1_normal is None:
            self._var1_normal = Variant.ByKeys(
                variability_model_id=self.variability_model_id, id=1
            )

        return self._var1_normal

    _var1 = None

    @property
    def var1(self):
        if self._var1 is None:
            self._var1 = Variant.ByKeys(
                variability_model_id=self.variability_model_id_multi, id=1
            )

        return self._var1

    _var2 = None

    @property
    def var2(self):
        if self._var2 is None:
            self._var2 = Variant.ByKeys(
                variability_model_id=self.variability_model_id_multi, id=2
            )

        return self._var2

    _maxbom_deep = None

    @property
    def maxbom_deep(self):
        """
        9508596@a - VAR_TEST_MAXBOM_DEEP
         +- 9508597@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1
            +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1_OC1
            +- 9508598@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2
               +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2
               +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1
               +- 9508599@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3
                  +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3_OC1
                  +- 9508600@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4
                     +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC2
                     +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC1
                     +- 9508601@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5
                        +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5_OC1
                        +- 9508602@ - VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5
                           +- > VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC1
                           +- > VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC2

        :return:
        """
        if self._maxbom_deep is None:
            self._maxbom_deep = items.Item.ByKeys(**self.maxbom_deep_keys)

        return self._maxbom_deep

    _maxbom_deep_without_index = None

    @property
    def maxbom_deep_without_index(self):
        """
        9508596@ - VAR_TEST_MAXBOM_DEEP
         +- 9508597@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1
            +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL1_OC1
            +- 9508598@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2
               +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2
               +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1
               +- 9508599@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3
                  +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL3_OC1
                  +- 9508600@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4
                     +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC2
                     +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL4_OC1
                     +- 9508601@ - VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5
                        +- > VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL5_OC1
                        +- 9508602@ - VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5
                           +- > VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC1
                           +- > VAR_TEST_MAXBOM_DEEP_BOM_ITEM_LEVEL5_OC2

        :return:
        """
        if self._maxbom_deep_without_index is None:
            self._maxbom_deep_without_index = items.Item.ByKeys(
                **self.maxbom_deep_without_index_keys
            )

        return self._maxbom_deep_without_index

    _maxbom_deep_wide = None

    @property
    def maxbom_deep_wide(self):
        """
        9508619@ - VAR_TEST_MAXBOM_DEEP_WIDE
         +- 9508620@ - VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1
            +- > VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0
            +- 9508621@ - VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1
               +- > VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0
               +- 9508622@ - VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1
                  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0
                  +- 9508623@ - VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1
                     +- > VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0
                     +- 9508624@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1
                     |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_OC0
                     |  +- 9508626@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1
                     |     +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P1_I1_OC0
                     +- 9508625@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2
                        +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0
                        +- 9508627@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1
                        |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0
                        +- 9508628@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2
                           +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1
                           +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0

        :return:
        """
        if self._maxbom_deep_wide is None:
            self._maxbom_deep_wide = items.Item.ByKeys(**self.maxbom_deep_wide_keys)

        return self._maxbom_deep_wide
