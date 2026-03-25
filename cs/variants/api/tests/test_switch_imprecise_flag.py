#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

"""
Test for imprecise changes (from and to imprecise)

Product: SWITCH_IMPRECISE

MaxBOM:

9508699@ - : VAR_TEST_SWITCH_IMPRECISE
 +- 9508700@ - 10: VAR_TEST_SWITCH_IMPRECISE_L1P0       <-- imprecise=False
    +- > VAR_TEST_SWITCH_IMPRECISE_L1P0_OCC0
    +- 9508701@ - 10: VAR_TEST_SWITCH_IMPRECISE_L2P0    <-- sc '== "VALUE2"'
       +- > VAR_TEST_SWITCH_IMPRECISE_L2P0_OCC0


Variability Model (VAR_TEST_REINSTANTIATE_MULTI): d6cbc26e-f3d6-11ed-9763-f875a45b4131
Variant: 1 / VAR_TEST_TEXT="VALUE1", VAR_TEST_FLOAT=2.0
Variant: 2 / VAR_TEST_TEXT="VALUE2", VAR_TEST_FLOAT=2.0


Variant part for variant 1:

9508702@ - Var1-VAR_TEST_SWITCH_IMPRECISE
 +- 9508703@ - VAR_TEST_SWITCH_IMPRECISE_L1P0           <-- imprecise=False
    +- > VAR_TEST_SWITCH_IMPRECISE_L1P0_OCC0


Variant part for variant 2:

9508704@ - : Var2-VAR_TEST_SWITCH_IMPRECISE
 +- 9508705@ - 10: VAR_TEST_SWITCH_IMPRECISE_L1P0       <-- imprecise=False
    +- > VAR_TEST_SWITCH_IMPRECISE_L1P0_OCC0
    +- 9508701@ - 10: VAR_TEST_SWITCH_IMPRECISE_L2P0
       +- > VAR_TEST_SWITCH_IMPRECISE_L2P0_OCC0

"""

from cs.variants import Variant
from cs.variants.api import instantiate_part, reinstantiate_parts
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst
from cs.variants.api.tests.test_helpers import switch_reuse
from cs.vp.bom import AssemblyComponent, Item

t9508699_teilenummer = "9508699"
t9508699_t_index = ""
t9508699_item_object_id = "5f2ce0aa-f3d6-11ed-9d6a-f875a45b4131"
t9508699_keys = {"teilenummer": "9508699", "t_index": ""}
t9508700_teilenummer = "9508700"
t9508700_t_index = ""
t9508700_bom_item_object_id = "5f932d36-f3d6-11ed-bf0a-f875a45b4131"
t9508700_keys = {"teilenummer": "9508700", "t_index": ""}
t9508701_teilenummer = "9508701"
t9508701_t_index = ""
t9508701_keys = {"teilenummer": "9508701", "t_index": ""}
t9508701 = Subst(
    t9508701_keys,
    children=[],
)

t9508700 = Subst(
    t9508700_keys,
    children=[t9508701],
)

t9508699 = Subst(
    t9508699_keys,
    children=[t9508700],
)


t9508702_teilenummer = "9508702"
t9508702_t_index = ""
t9508702_keys = {"teilenummer": "9508702", "t_index": ""}
t9508703_teilenummer = "9508703"
t9508703_t_index = ""
t9508703_keys = {"teilenummer": "9508703", "t_index": ""}
t9508703 = Subst(
    t9508703_keys,
    children=[],
)

t9508702 = Subst(
    t9508702_keys,
    children=[t9508703],
)

t9508704_teilenummer = "9508704"
t9508704_t_index = ""
t9508704_keys = {"teilenummer": "9508704", "t_index": ""}
t9508705_teilenummer = "9508705"
t9508705_t_index = ""
t9508705_keys = {"teilenummer": "9508705", "t_index": ""}

t9508705 = Subst(
    t9508705_keys,
    children=[t9508701],
)

t9508704 = Subst(
    t9508704_keys,
    children=[t9508705],
)


class SwitchImpreciseTests(BaseTestCase):
    def test_l1_switch_to_imprecise_and_reinstantiate(self) -> None:
        """
        enable imprecise for 9508700 and disable reuse

        This will switch back to the subassembly from the maxbom.
        Only the Attribute `is_imprecise` on 9508700 is different.

        """
        part_to_reinstantiate = Item.KeywordQuery(**t9508702_keys)[0]
        self.assert_subassembly_structure(t9508702, part_to_reinstantiate)

        maxbom = Item.KeywordQuery(**t9508699_keys)[0]
        self.assert_subassembly_structure(t9508699, maxbom)

        _t9508700 = AssemblyComponent.KeywordQuery(**t9508700_keys)[0]
        assert _t9508700 is not None
        assert not _t9508700.is_imprecise

        _t9508700.is_imprecise = True
        _t9508700.Reload()

        with switch_reuse(to=False):
            reinstantiate_parts([part_to_reinstantiate], maxbom)
            expected_result = Subst(
                {
                    "teilenummer": part_to_reinstantiate.teilenummer,
                    "t_index": part_to_reinstantiate.t_index,
                },
                children=[t9508700],
            )

            self.assert_subassembly_structure(expected_result, part_to_reinstantiate)
            bom_item = AssemblyComponent.KeywordQuery(
                **t9508700_keys
                | {
                    "baugruppe": t9508702_teilenummer,
                    "b_index": t9508702_t_index,
                }
            )[0]
            assert bom_item is not None
            assert bom_item.is_imprecise

    def test_l1_switch_to_imprecise_and_reinstantiate_v2(self) -> None:
        """
        enable imprecise for 9508700 and disable reuse with variant 2

        This will switch back to the subassembly from the maxbom.
        This test differs insofar as the existing structure is the same as from the maxbom.
        To understand see sc on 9508701

        """
        part_to_reinstantiate = Item.KeywordQuery(**t9508704_keys)[0]
        self.assert_subassembly_structure(t9508704, part_to_reinstantiate)

        maxbom = Item.KeywordQuery(**t9508699_keys)[0]
        self.assert_subassembly_structure(t9508699, maxbom)

        _t9508700 = AssemblyComponent.KeywordQuery(**t9508700_keys)[0]
        assert _t9508700 is not None
        assert not _t9508700.is_imprecise

        _t9508700.is_imprecise = True
        _t9508700.Reload()

        with switch_reuse(to=False):
            reinstantiate_parts([part_to_reinstantiate], maxbom)
            expected_result = Subst(
                {
                    "teilenummer": part_to_reinstantiate.teilenummer,
                    "t_index": part_to_reinstantiate.t_index,
                },
                children=[t9508700],
            )

            self.assert_subassembly_structure(expected_result, part_to_reinstantiate)
            bom_item = AssemblyComponent.KeywordQuery(
                **t9508700_keys
                | {
                    "baugruppe": t9508704_teilenummer,
                    "b_index": t9508704_t_index,
                }
            )[0]
            assert bom_item is not None
            assert bom_item.is_imprecise

    def test_l1_switch_to_imprecise_and_instantiate_with_reuse(self) -> None:
        """
        enable imprecise for 9508700 and enabled reuse with variant 1

        This will switch back to the subassembly from the maxbom.
        Only the Attribute `is_imprecise` on 9508700 is different.

        """
        maxbom = Item.ByKeys(cdb_object_id=t9508699_item_object_id)
        self.assert_subassembly_structure(t9508699, maxbom)

        _t9508700 = AssemblyComponent.ByKeys(cdb_object_id=t9508700_bom_item_object_id)
        assert _t9508700 is not None
        assert not _t9508700.is_imprecise

        _t9508700.is_imprecise = True
        _t9508700.Reload()

        variant = Variant.ByKeys(
            variability_model_id="d6cbc26e-f3d6-11ed-9763-f875a45b4131", id="1"
        )
        assert variant is not None

        with switch_reuse(to=True):
            instantiation = instantiate_part(variant, maxbom)

            expected_result = Subst(
                {
                    "teilenummer": instantiation.teilenummer,
                    "t_index": instantiation.t_index,
                },
                children=[t9508700],
            )
            self.assert_subassembly_structure(expected_result, instantiation)
            bom_item = AssemblyComponent.KeywordQuery(
                **t9508700_keys
                | {
                    "baugruppe": instantiation.teilenummer,
                    "b_index": instantiation.t_index,
                }
            )[0]
            assert bom_item is not None
            assert bom_item.is_imprecise

    def test_l1_switch_to_imprecise_and_instantiate_with_reuse_v2(self) -> None:
        """
        enable imprecise for 9508700 and enabled reuse with variant 2

        Reuse doesn't matter. This will switch back to the subassembly from the maxbom.

        This test differs insofar as the potentially reusable structure is the same as from the maxbom.

        """
        maxbom = Item.ByKeys(cdb_object_id=t9508699_item_object_id)
        self.assert_subassembly_structure(t9508699, maxbom)

        _t9508700 = AssemblyComponent.ByKeys(cdb_object_id=t9508700_bom_item_object_id)
        assert _t9508700 is not None
        assert not _t9508700.is_imprecise

        _t9508700.is_imprecise = True
        _t9508700.Reload()

        variant = Variant.ByKeys(
            variability_model_id="d6cbc26e-f3d6-11ed-9763-f875a45b4131", id="2"
        )
        assert variant is not None

        with switch_reuse(to=True):
            instantiation = instantiate_part(variant, maxbom)

            expected_result = Subst(
                {
                    "teilenummer": instantiation.teilenummer,
                    "t_index": instantiation.t_index,
                },
                children=[t9508700],
            )
            self.assert_subassembly_structure(expected_result, instantiation)
            bom_item = AssemblyComponent.KeywordQuery(
                **t9508700_keys
                | {
                    "baugruppe": instantiation.teilenummer,
                    "b_index": instantiation.t_index,
                }
            )[0]
            assert bom_item is not None
            assert bom_item.is_imprecise
