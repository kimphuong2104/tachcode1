#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cdb import ue
from cs.variants import cad_integration
from cs.variants.cad_integration import (
    CADPlugin,
    find_plugins_for_maxbom,
    get_plugin,
    register_open_in_cad_plugin,
)


class PluginsResetContext:
    """reset and restore the global CAD_PLUGINS variable"""

    def __init__(self, initial_plugins: list[CADPlugin] | None = None):
        self.initial_plugins = initial_plugins
        self.original = None

    def __enter__(self):
        self.original = cad_integration.CAD_PLUGINS[:]
        if self.initial_plugins:
            cad_integration.CAD_PLUGINS = self.initial_plugins
        else:
            cad_integration.CAD_PLUGINS = []

    def __exit__(self, exc_type, exc_val, exc_tb):
        cad_integration.CAD_PLUGINS = self.original[:]


def test_register_plugin() -> None:
    with PluginsResetContext():
        register_open_in_cad_plugin("something", None)
        assert cad_integration.CAD_PLUGINS == [CADPlugin("something", None)]


def test_register_plugin_with_kwargs() -> None:
    with PluginsResetContext():
        register_open_in_cad_plugin("something", None, "label", blub="blab", thing=42)

        assert cad_integration.CAD_PLUGINS == [
            CADPlugin("something", None, "label", {"blub": "blab", "thing": 42})
        ]


@patch("cs.variants.cad_integration.get_label")
def test_cad_plugin_title_with_title(get_label_mock: MagicMock) -> None:
    """return the title if the title is given"""
    get_label_mock.return_value = "the_label"
    p = CADPlugin("x", None, "the_label")

    assert p.title == "the_label"
    assert get_label_mock.called


def test_cad_plugin_title_with_fallback() -> None:
    """fallback for title must return the erzeug_system"""
    p = CADPlugin("x", None)

    assert p.title == "x"


def test_get_plugin() -> None:
    initial_plugins = [
        CADPlugin("first_one", None),
        CADPlugin("second_one", None, "second_one"),
        CADPlugin("third_one", None),
        CADPlugin("second_one", None, "the second one again"),
    ]

    with PluginsResetContext(initial_plugins):
        p = get_plugin("does not exist")
        assert p is None

        p = get_plugin("second_one")
        assert p is not None
        assert p.erzeug_system == "second_one"

        # also find and return only the first match
        assert p.label == "second_one"


class MaxBomFake:
    def __init__(self, teilenummer="000000", t_index="", documents=None):
        self.teilenummer = teilenummer
        self.t_index = t_index
        self._documents = documents

    @property
    def Documents(self):
        return self._documents


def test_find_plugin_no_maxbom() -> None:
    """maxbom is None"""
    result = find_plugins_for_maxbom(None)
    assert not result


def test_find_plugin_no_erzeug_system() -> None:
    """no document with no erzeug_system"""

    class FakeErzeug:
        erzeug_system: list[Any] = []

    maxbom_fake = MaxBomFake("T1", "I2", FakeErzeug())

    with pytest.raises(ue.Exception) as ex:
        find_plugins_for_maxbom(maxbom_fake)
    assert "T1" in str(ex.value)
    assert "I2" in str(ex.value)


@patch("cs.variants.cad_integration.get_plugin")
def test_find_plugin(get_plugin_mock: MagicMock) -> None:
    def side_effect_func(arg):
        match arg:
            case "" | None:
                return None
            case _:
                return CADPlugin(arg, None)

    get_plugin_mock.side_effect = side_effect_func

    class FakeErzeug:
        erzeug_system: list[Any] = ["zeug1", None, "", "zeug2", "zeug1"]

    maxbom_fake = MaxBomFake("T1", "I2", FakeErzeug())

    result = find_plugins_for_maxbom(maxbom_fake)
    result = sorted(result, key=lambda x: x.erzeug_system)

    assert result == [CADPlugin("zeug1", None), CADPlugin("zeug2", None)]
