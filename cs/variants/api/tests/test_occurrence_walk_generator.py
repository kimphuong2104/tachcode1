#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import pytest

from cdb import ue
from cs.variants.api.filter import (
    CsVariantsFilterContextPlugin,
    CsVariantsVariabilityModelContextPlugin,
)
from cs.variants.api.occurrence_walk_generator import OccurrenceWalkGenerator
from cs.vp import items


def test_walk_generator() -> None:
    maxbom = items.Item.ByKeys(teilenummer="9508517", t_index="")  # platform

    var_model_context = CsVariantsVariabilityModelContextPlugin(
        "3cccd84d-d61d-11e9-85d2-082e5f0d3665"
    )
    variant_filter_plugin = CsVariantsFilterContextPlugin(var_model_context, 1)
    walk_generator = OccurrenceWalkGenerator(maxbom, variant_filter_plugin)

    result_list = list(walk_generator.walk())

    assert len(result_list) == 3553, "we are expecting 3553 occurrences"

    def list_contains(path: tuple[str, ...]) -> bool:
        for each in result_list:
            if each.path == path:
                return True
        return False

    assert list_contains(("modular unit with pressure reservoir.1",))
    assert list_contains(
        (
            "modular unit with pressure reservoir.1",
            "modular unit base assembly.1",
        )
    )
    assert list_contains(
        (
            "modular unit with pressure reservoir.1",
            "modular unit base assembly.1",
            "frame assembly.1",
        )
    )
    assert list_contains(
        (
            "modular unit with pressure reservoir.1",
            "modular unit base assembly.1",
            "frame assembly.1",
            "post.1",
        )
    )
    assert list_contains(
        (
            "modular unit with pressure reservoir.1",
            "modular unit base assembly.1",
            "frame assembly.1",
            "post.2",
        )
    )


def test_without_occurrences_missing_id_no_callback() -> None:
    maxbom = items.Item.ByKeys(
        teilenummer="9508651", t_index=""
    )  # VAR_TEST_MAXBOM_MULTI_REUSE
    var_model_context = CsVariantsVariabilityModelContextPlugin(
        "39a54ecc-2401-11eb-9218-24418cdf379c"
    )
    variant_filter_plugin = CsVariantsFilterContextPlugin(var_model_context, 1)
    walk_generator = OccurrenceWalkGenerator(maxbom, variant_filter_plugin)

    gen = walk_generator.walk()
    with pytest.raises(ue.Exception):
        next(gen)


def test_without_occurrences_missing_id_with_callback() -> None:
    def my_callback(bom_item, path):
        raise KeyError(bom_item.teilenummer)

    maxbom = items.Item.ByKeys(
        teilenummer="9508651", t_index=""
    )  # VAR_TEST_MAXBOM_MULTI_REUSE

    var_model_context = CsVariantsVariabilityModelContextPlugin(
        "39a54ecc-2401-11eb-9218-24418cdf379c"
    )
    variant_filter_plugin = CsVariantsFilterContextPlugin(var_model_context, 1)
    walk_generator = OccurrenceWalkGenerator(maxbom, variant_filter_plugin)

    walk_generator.set_handle_missing_occurrence_callback(my_callback)
    gen = walk_generator.walk()
    with pytest.raises(KeyError) as ex:
        next(gen)

    assert ex.value.args[0] == "9508652"
