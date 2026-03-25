#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
"""
Module to update checksums for test data
"""
import logging

from cs.variants import Variant, VariantSubPart
from cs.variants.api.instantiate_lookup import InstantiateLookup
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.variant_bom_node import VariantBomNode
from cs.vp.bom import Item

LOG = logging.getLogger(__name__)

mapping_t9508614 = {
    "9508597": {
        "teilenummer": "9508614",
        "part_object_id": "6b5033bb-f6a5-11eb-923d-f875a45b4131",
        "instantiated_of_part_object_id": "ae11f303-ca9a-11eb-b955-98fa9bf98f6d",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508598": {
        "teilenummer": "9508615",
        "part_object_id": "6b5033bf-f6a5-11eb-923d-f875a45b4131",
        "instantiated_of_part_object_id": "ae11f309-ca9a-11eb-b955-98fa9bf98f6d",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508599": {
        "teilenummer": "9508616",
        "part_object_id": "6b5033c3-f6a5-11eb-923d-f875a45b4131",
        "instantiated_of_part_object_id": "ae11f30f-ca9a-11eb-b955-98fa9bf98f6d",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508600": {
        "teilenummer": "9508617",
        "part_object_id": "6b5033c7-f6a5-11eb-923d-f875a45b4131",
        "instantiated_of_part_object_id": "ae11f315-ca9a-11eb-b955-98fa9bf98f6d",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508601": {
        "teilenummer": "9508618",
        "part_object_id": "6b5033cb-f6a5-11eb-923d-f875a45b4131",
        "instantiated_of_part_object_id": "ae11f31b-ca9a-11eb-b955-98fa9bf98f6d",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
}

mapping_t9508630 = {
    "9508620": {
        "teilenummer": "9508630",
        "part_object_id": "edc325ca-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354d5-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508621": {
        "teilenummer": "9508631",
        "part_object_id": "edc325cc-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354dd-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508622": {
        "teilenummer": "9508632",
        "part_object_id": "edc325ce-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354e3-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508623": {
        "teilenummer": "9508633",
        "part_object_id": "edc325d0-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354e9-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508624": {
        "teilenummer": "9508634",
        "part_object_id": "edc325d2-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354ef-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508625": {
        "teilenummer": "9508635",
        "part_object_id": "edc325d6-fc37-11eb-923e-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354f5-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
}

mapping_t9508637 = {
    "9508620": {
        "teilenummer": "9508637",
        "part_object_id": "e727d273-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354d5-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508621": {
        "teilenummer": "9508638",
        "part_object_id": "e727d277-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354dd-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508622": {
        "teilenummer": "9508639",
        "part_object_id": "e727d27b-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354e3-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508623": {
        "teilenummer": "9508640",
        "part_object_id": "e727d27f-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354e9-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508624": {
        "teilenummer": "9508641",
        "part_object_id": "e727d283-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354ef-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
    "9508625": {
        "teilenummer": "9508642",
        "part_object_id": "e727d28b-fe67-11eb-9240-f875a45b4131",
        "instantiated_of_part_object_id": "8f2354f5-fc0a-11eb-923e-f875a45b4131",
        "variability_model_id": ReuseTestCase.variability_model_id_multi,
    },
}


def _update(current_node: VariantBomNode, mapping: dict[str, dict[str, str]]) -> None:
    """runs recursive for every bom node"""
    for each_child in current_node.children:
        each_child_teilenummer = each_child.bom_item_primary_key_values["teilenummer"]
        if each_child_teilenummer in mapping:
            sub_part = VariantSubPart.ByKeys(**mapping[each_child_teilenummer])
            assert sub_part is not None
            sub_part.Update(structure_checksum=each_child.checksum)
            LOG.debug("update %s", mapping[each_child_teilenummer])

        _update(each_child, mapping)


def update(
    maxbom_keys: dict[str, str],
    variability_model_id: str,
    variant_id: int,
    mapping: dict[str, dict[str, str]],
) -> None:
    maxbom = Item.ByKeys(**maxbom_keys)

    variant = Variant.ByKeys(variability_model_id=variability_model_id, id=variant_id)

    lookup = InstantiateLookup(maxbom, variant)
    lookup.build_variant_bom()
    lookup.build_reuse()

    _update(lookup.variant_bom, mapping)


if __name__ == "__main__":
    update(
        ReuseTestCase.maxbom_deep_keys,
        ReuseTestCase.variability_model_id_multi,
        2,
        mapping_t9508614,
    )
    update(
        ReuseTestCase.maxbom_deep_wide_keys,
        ReuseTestCase.variability_model_id_multi,
        1,
        mapping_t9508630,
    )
    update(
        ReuseTestCase.maxbom_deep_wide_keys,
        ReuseTestCase.variability_model_id_multi,
        2,
        mapping_t9508637,
    )
