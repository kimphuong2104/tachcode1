#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from copy import deepcopy

from cs.variants.api import reinstantiate_parts
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.maxbom_deep_wide_constants import (
    t9508629,
    t9508632_t_index,
    t9508632_teilenummer,
    t9508633_keys,
)
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.variants.api.tests.test_helpers import switch_reuse
from cs.vp.bom import AssemblyComponent, Item


class SwitchImpreciseInVariantPart(ReuseTestCase):
    def test_from_precise_to_imprecise(self) -> None:
        """
        Switching from precise to imprecise for 9508633 in variant part and reinstantiate

        After reinstantiate the `is_imprecise` attribute are still `True` in variant part

        """
        part_to_reinstantiate = Item.KeywordQuery(
            **maxbom_deep_wide_constants.t9508629_keys
        )[0]
        self.assert_subassembly_structure(t9508629, part_to_reinstantiate)

        bom_item = AssemblyComponent.KeywordQuery(
            **t9508633_keys
            | {
                "baugruppe": t9508632_teilenummer,
                "b_index": t9508632_t_index,
            }
        )[0]
        assert bom_item is not None
        bom_item.is_imprecise = True
        bom_item.Reload()

        expected_structure = deepcopy(t9508629)

        def add_imprecise(item: SubassemblyStructure) -> None:
            _is_imprecise = 0
            if item.item_keys["teilenummer"] == "9508633":
                _is_imprecise = 1
            item.bom_item_keys["is_imprecise"] = _is_imprecise

        expected_structure.update_with_fn(add_imprecise)

        with switch_reuse(to=False):
            reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)
            self.assert_subassembly_structure(expected_structure, part_to_reinstantiate)
