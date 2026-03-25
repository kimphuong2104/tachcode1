#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from cs.variants import Variant
from cs.variants.api.constants_api import OBSOLETE_CHECKSUM_KEY
from cs.variants.api.instantiate_lookup import InstantiateLookup
from cs.vp import items


def test_variant_bom() -> None:
    maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
    assert maxbom is not None, "maxbom not found"
    variant = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
    )

    lookup = InstantiateLookup(maxbom, variant)
    lookup.build_variant_bom()

    root = lookup.variant_bom

    assert len(root.children) == 2

    t79 = root.children[0]
    t80 = root.children[1]

    assert t79.value.teilenummer == "9508579"
    assert t80.value.teilenummer == "9508580"

    assert len(t80.occurrences) == 1
    assert len(t79.occurrences) == 1

    t80.occurrences[0].occurrence_id = "VAR_TEST_REINSTANTIATE_PART_2_OC0"
    t79.occurrences[0].occurrence_id = "VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_OC0"


def test_must_be_instantiated() -> None:
    maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
    assert maxbom is not None, "maxbom not found"
    variant = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
    )
    lookup = InstantiateLookup(maxbom, variant)
    lookup.build_variant_bom()

    root = lookup.variant_bom
    assert root.is_must_be_instantiated

    t79 = root.children[0]
    t80 = root.children[1]

    # not really part of the test.
    # just to test if index 0 is the expected child
    assert t79.value.teilenummer == "9508579"
    assert t80.value.teilenummer == "9508580"

    assert t79.is_must_be_instantiated
    assert not t80.is_must_be_instantiated


def test_stop_build_bom_on_imprecise_pos() -> None:
    """
    Every bom_item is imprecise

    9508665@ - VAR_TEST_FULL_IMPRECISE Variant(1@e0bd9b6d-ed97-11ed-9892-f875a45b4131)
     +- 9508666@ - VAR_TEST_FULL_IMPRECISE_L1P0
        +- > VAR_TEST_FULL_IMPRECISE_L1P0_OCC0
        +- 9508667@ - VAR_TEST_FULL_IMPRECISE_L2P0
           +- > VAR_TEST_FULL_IMPRECISE_L2P0_OCC0
           +- 9508668@ - VAR_TEST_FULL_IMPRECISE_L3P0
              +- > VAR_TEST_FULL_IMPRECISE_L3P0_OCC0

    :return:
    """
    maxbom = items.Item.ByKeys(teilenummer="9508665", t_index="")
    assert maxbom is not None
    variant = Variant.ByKeys(
        variability_model_id="e0bd9b6d-ed97-11ed-9892-f875a45b4131", id="1"
    )

    lookup = InstantiateLookup(maxbom, variant)
    lookup.build_variant_bom()

    child9508666 = lookup.variant_bom.children[0]
    # no more children
    assert not child9508666.children
    # but occurrence present
    assert (
        child9508666.occurrences[0].occurrence_id == "VAR_TEST_FULL_IMPRECISE_L1P0_OCC0"
    )


def test_stop_build_bom_on_imprecise_pos_with_mixed_levels() -> None:
    """
    Mixed precise and imprecise across different levels

    9508669@ - VAR_TEST_MIXED_IMPRECISE_PRECISE
     +- 9508670@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L1P0        <- imprecise
     |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L1P0_OCC0
     |  +- 9508671@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P0
     |  |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P0_OCC0
     |  |  |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0_OCC0
     |  |  +- 9508673@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1
     |  |     +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1_OCC0
     |  +- 9508674@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P1
     |     +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P1_OCC0
     |     +- 9508675@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0
     |     |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0_OCC0
     |     +- 9508676@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1
     |        +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1_OCC0
     +- 9508677@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L1P1
        +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L1P1_OCC0
        +- 9508678@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P0
        |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P0_OCC0
        |  +- 9508679@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0
        |  |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0_OCC0
        |  +- 9508680@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1
        |     +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1_OCC0
        +- 9508681@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P1     <- imprecise
           +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P1_OCC0
           +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L2P1_OCC0
           +- 9508682@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0
           |  +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P0_OCC0
           +- 9508683@ - VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1
              +- > VAR_TEST_MIXED_IMPRECISE_PRECISE_L3P1_OCC0

    :return:
    """
    maxbom = items.Item.ByKeys(teilenummer="9508669", t_index="")
    assert maxbom is not None
    variant = Variant.ByKeys(
        variability_model_id="d0e236e1-edaa-11ed-b5eb-f875a45b4131", id="1"
    )
    assert variant is not None

    lookup = InstantiateLookup(maxbom, variant)
    lookup.build_variant_bom()
    assert len(lookup.variant_bom.children) == 2

    t9508670 = lookup.variant_bom.children[0]
    assert t9508670.value.teilenummer == "9508670"
    assert not t9508670.children  # no more children for imprecise pos

    t9508677 = lookup.variant_bom.children[1]
    assert t9508677.value.teilenummer == "9508677"

    assert len(t9508677.children) == 2

    t9508678 = t9508677.children[0]
    assert t9508678.value.teilenummer == "9508678"
    assert len(t9508678.children) == 2  # both children

    t9508681 = t9508677.children[1]
    assert t9508681.value.teilenummer == "9508681"
    assert not t9508681.children  # no more children for imprecise pos


def test_query_potential_sub_parts() -> None:
    def remove_magic(from_list):
        return [i for i in from_list if i.structure_checksum != OBSOLETE_CHECKSUM_KEY]

    maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
    assert maxbom is not None, "maxbom not found"
    variant = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
    )
    lookup = InstantiateLookup(maxbom, variant)

    result = lookup._query_potential_sub_parts(  # pylint: disable=W0212
        "non existing", "nothing"
    )  # pylint: disable=W0212

    assert len(result) == 0

    result = lookup._query_potential_sub_parts(  # pylint: disable=W0212
        "b1752105-a1d9-11eb-b94b-98fa9bf98f6d", "69f280630cf486971b887b513103b5bf"
    )

    assert len(result) == 3  # there are 2 with matching checksum and one with magic key
    filtered_result = remove_magic(result)
    assert len(filtered_result) == 2

    result = lookup._query_potential_sub_parts(  # pylint: disable=W0212
        "b1752105-a1d9-11eb-b94b-98fa9bf98f6d", "wrong_checksum"
    )

    assert len(result) == 1  # one with magic key
    # remove magic key
    filtered_result = remove_magic(result)
    assert len(filtered_result) == 0


@patch("cs.variants.api.instantiate_lookup.VariantSubPart.KeywordQuery")
def test_query_potential_sub_parts_sort_order(kwquery_mock: MagicMock) -> None:
    """obsolete must be at the end of the list (for performance)"""

    @dataclass
    class SubPartFake:
        structure_checksum: str

    kwquery_mock.return_value = [
        SubPartFake(OBSOLETE_CHECKSUM_KEY),
        SubPartFake("abc"),
        SubPartFake(OBSOLETE_CHECKSUM_KEY),
        SubPartFake("xxx"),
    ]
    maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
    assert maxbom is not None, "maxbom not found"
    variant = Variant.ByKeys(
        variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
    )
    lookup = InstantiateLookup(maxbom, variant)

    result = lookup._query_potential_sub_parts(  # pylint: disable=W0212
        "part", "checksum"
    )

    # It is only important that the two are obsolete at the end
    assert result[-1].structure_checksum == OBSOLETE_CHECKSUM_KEY
    assert result[-2].structure_checksum == OBSOLETE_CHECKSUM_KEY
