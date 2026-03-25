#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cdb import ue
from cs.variants import Variant
from cs.variants.api.occurrence_walk_generator import OccurrenceWalkGenerator
from cs.variants.cad_integration import CADPlugin
from cs.variants.tests.test_cad_integration import PluginsResetContext


@patch("cs.variants.items.Item.ByKeys")
def test_get_max_bom_item_from_context_with_maxbom_id(by_keys_mock: MagicMock) -> None:
    by_keys_mock.return_value = "The item"

    class Fake:
        pass

    dialog = Fake()
    setattr(dialog, "max_bom_id", 123)
    ctx = Fake()
    setattr(ctx, "dialog", dialog)
    var = Variant.ByKeys(
        variability_model_id="3cccd84d-d61d-11e9-85d2-082e5f0d3665", id="1"
    )
    assert var is not None

    result = var._get_max_bom_item(ctx)  # pylint: disable=protected-access

    by_keys_mock.assert_called_with(cdb_object_id=123)

    assert result == "The item"


@patch("cs.variants.items.Item.ByKeys")
def test_get_max_bom_item_from_context_without_maxbom_id(
    by_keys_mock: MagicMock,
) -> None:
    class Fake:
        pass

    dialog = Fake()
    ctx = Fake()
    setattr(ctx, "dialog", dialog)
    var = Variant.ByKeys(
        variability_model_id="3cccd84d-d61d-11e9-85d2-082e5f0d3665", id="1"
    )
    assert var is not None
    result = var._get_max_bom_item(ctx)  # pylint: disable=protected-access

    by_keys_mock.assert_not_called()
    assert result is None


class FakeContext:
    def __init__(self):
        self.data = {}
        self.dialog_skipped = False
        self.readonly = {}
        self.dialog = {}

    def set(self, key, value):
        self.data[key] = value

    def skip_dialog(self):
        self.dialog_skipped = True

    def set_readonly(self, key):
        self.readonly[key] = True


@dataclass
class FakePlugin:
    erzeug_system: str = "zeug"
    title: str = "The Title"
    callback: Any = None


@patch("cs.variants.Variant._get_max_bom_item")
@patch("cs.variants.cad_integration.find_plugins_for_maxbom")
def test_operation_open_in_cad_unsaved_pre_mask_with_plugin(
    find_plugin_mock: MagicMock, get_max_bom_mock: MagicMock
) -> None:
    """if exactly one cad plugin found then the dialog must be skipped"""
    get_max_bom_mock.return_value = None

    find_plugin_mock.return_value = [FakePlugin()]

    ctx = FakeContext()

    with PluginsResetContext([CADPlugin("something", None)]):
        Variant.on_cs_variants_open_in_cad_unsaved_pre_mask(ctx)

    assert ctx.dialog_skipped
    assert ctx.data["plugin_selected_erzeug_system"] == "zeug"
    assert ctx.data["plugin_selection"] == "The Title"


@patch("cs.variants.Variant._get_max_bom_item")
@patch("cs.variants.cad_integration.find_plugins_for_maxbom")
def test_operation_open_in_cad_unsaved_pre_mask_with_multiple_plugin(
    find_plugin_mock: MagicMock, get_max_bom_mock: MagicMock
) -> None:
    """if more than one cad plugin found"""
    get_max_bom_mock.return_value = None

    find_plugin_mock.return_value = [FakePlugin(), FakePlugin()]

    ctx = FakeContext()

    with PluginsResetContext([CADPlugin("something", None)]):
        Variant.on_cs_variants_open_in_cad_unsaved_pre_mask(ctx)

    assert not ctx.dialog_skipped
    assert ctx.readonly["variability_model_id"]
    assert ctx.readonly["max_bom_id"]


def test_operation_open_in_cad_unsaved_pre_mask_no_plugin_registered() -> None:
    """if there is no cad plugin registered"""
    with PluginsResetContext():
        with pytest.raises(ue.Exception) as ex:
            Variant.on_cs_variants_open_in_cad_unsaved_pre_mask(None)

    expected_label = "cs_variants_cad_plugin_no_plugin_registered"
    assert ex.value.msg.getLabel() == expected_label


@patch("cs.variants.Variant._get_max_bom_item")
@patch("cs.variants.cad_integration.get_plugin")
def test_operation_open_in_cad_unsaved_now_plugin_callback(
    get_plugin_mock: MagicMock, get_max_bom_mock: MagicMock
) -> None:
    """the callback from the selected plugin must be called"""
    get_max_bom_mock.return_value = None
    the_callback = MagicMock()
    get_plugin_mock.return_value = FakePlugin(callback=the_callback)

    ctx = FakeContext()
    ctx.dialog["variability_model_id"] = "123"
    ctx.dialog["params_list"] = '[{"x": 1}]'  # must be json loadable
    ctx.dialog["plugin_selected_erzeug_system"] = "catia"

    Variant.on_cs_variants_open_in_cad_unsaved_now(ctx)

    assert the_callback.call_args.args[0] == "zeug"
    assert the_callback.call_args.args[2] == ctx
    assert isinstance(the_callback.call_args.args[1], OccurrenceWalkGenerator)


@patch("cs.variants.cad_integration.get_plugin")
def test_operation_open_in_cad_unsaved_now_no_plugin(
    get_plugin_mock: MagicMock,
) -> None:
    """no plugin with the selected erzeug_system found"""
    get_plugin_mock.return_value = None

    ctx = FakeContext()
    ctx.dialog["plugin_selected_erzeug_system"] = "des_zeug"

    with PluginsResetContext():
        with pytest.raises(ue.Exception) as ex:
            Variant.on_cs_variants_open_in_cad_unsaved_now(ctx)

    expected_label = "cs_variant_cad_plugin_not_found"
    assert ex.value.msg.getLabel() == expected_label


def test_operation_open_in_cad_pre_mask_no_plugin_registered() -> None:
    """if there is no cad plugin registered"""
    var = Variant()
    with PluginsResetContext():
        with pytest.raises(ue.Exception) as ex:
            var.on_cs_variants_open_in_cad_pre_mask(None)

    expected_label = "cs_variants_cad_plugin_no_plugin_registered"
    assert ex.value.msg.getLabel() == expected_label


@patch("cs.variants.cad_integration.find_plugins_for_maxbom")
@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_pre_mask_no_plugin_found(
    get_max_bom_mock: MagicMock, find_plugin_mock: MagicMock
) -> None:
    """if no plugin for the selected maxbom is found"""

    @dataclass
    class MaxBomFake:
        teilenummer: str = "00"
        t_index: str = ""

    get_max_bom_mock.return_value = MaxBomFake()
    find_plugin_mock.return_value = None
    var = Variant()

    with PluginsResetContext([CADPlugin("zeug", None)]):
        with pytest.raises(ue.Exception) as ex:
            var.on_cs_variants_open_in_cad_pre_mask(None)

    expected_label = "cs_variants_cad_plugin_no_plugin_for_maxbom"
    assert ex.value.msg.getLabel() == expected_label


@patch("cs.variants.cad_integration.find_plugins_for_maxbom")
@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_pre_mask_exactly_one_plugin_found(
    get_max_bom_mock: MagicMock, find_plugin_mock: MagicMock
) -> None:
    """if exactly one plugin found skip the dialog"""
    get_max_bom_mock.return_value = {}  # doesn't matter what
    find_plugin_mock.return_value = [FakePlugin()]
    ctx = FakeContext()
    var = Variant()

    with PluginsResetContext([CADPlugin("zeug", None)]):
        var.on_cs_variants_open_in_cad_pre_mask(ctx)

    assert ctx.dialog_skipped
    assert ctx.data["plugin_selected_erzeug_system"] == "zeug"
    assert ctx.data["plugin_selection"] == "The Title"


@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_pre_mask_no_maxbom(get_max_bom_mock: MagicMock) -> None:
    """if no maxbom is found"""
    get_max_bom_mock.return_value = None
    ctx = FakeContext()
    var = Variant()

    with PluginsResetContext([CADPlugin("zeug", None)]):
        var.on_cs_variants_open_in_cad_pre_mask(ctx)

    assert not ctx.dialog_skipped
    assert ctx.readonly["variability_model_id"]


@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_now_no_maxbom(get_max_bom_mock: MagicMock) -> None:
    """if no maxbom is found"""
    get_max_bom_mock.return_value = None
    var = Variant()

    with PluginsResetContext([CADPlugin("zeug", None)]):
        with pytest.raises(ue.Exception) as ex:
            var.on_cs_variants_open_in_cad_now(None)

    expected_label = "cs_variants_select_maxbom"
    assert ex.value.msg.getLabel() == expected_label


@patch("cs.variants.cad_integration.get_plugin")
@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_now_no_plugin(
    get_max_bom_mock: MagicMock, get_plugin_mock: MagicMock
) -> None:
    """if no plugin for erzeug_system is found"""
    get_max_bom_mock.return_value = {}  # doesnt matter
    get_plugin_mock.return_value = None
    ctx = FakeContext()
    ctx.dialog["plugin_selected_erzeug_system"] = "something"
    var = Variant()

    with PluginsResetContext([CADPlugin("zeug", None)]):
        with pytest.raises(ue.Exception) as ex:
            var.on_cs_variants_open_in_cad_now(ctx)

    expected_label = "cs_variant_cad_plugin_not_found"
    assert ex.value.msg.getLabel() == expected_label


@patch("cs.variants.cad_integration.get_plugin")
@patch("cs.variants.Variant._get_max_bom_item")
def test_operation_open_in_cad_now(
    get_max_bom_mock: MagicMock, get_plugin_mock: MagicMock
) -> None:
    """callback from plugin must be called"""
    get_max_bom_mock.return_value = {}  # doesnt matter
    the_callback = MagicMock()
    get_plugin_mock.return_value = FakePlugin(callback=the_callback)
    ctx = FakeContext()
    ctx.dialog["plugin_selected_erzeug_system"] = "something"
    var = Variant()
    var.variability_model_id = "123"

    var.on_cs_variants_open_in_cad_now(ctx)

    assert the_callback.call_args.args[0] == "zeug"
    assert the_callback.call_args.args[2] == ctx
    assert isinstance(the_callback.call_args.args[1], OccurrenceWalkGenerator)
