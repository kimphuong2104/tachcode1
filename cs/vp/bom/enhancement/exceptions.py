# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
from __future__ import annotations
from typing import TYPE_CHECKING, TypeAlias, Union

from cs.vp.bom.enhancement.plugin import AbstractPlugin


if TYPE_CHECKING:
    # make mypy happy
    from cs.vp.bom.enhancement import FlatBomRestEnhancement, FlatBomEnhancement


AnyEnhancementType = Union["FlatBomEnhancement", "FlatBomRestEnhancement"]


def create_msg(
    plugin: AbstractPlugin,
    method_name: str,
    enhancement: AnyEnhancementType,
    original_msg: str
) -> str:
    msg = f"The enhancement plugin '{plugin.__class__.__name__}' raised an error. "
    msg += f"This was happened during '{method_name}' in {enhancement}. "
    msg += f"Original error msg: '{original_msg}'."
    return msg


class EnhancementPluginError(Exception):
    """Error object if a plugin raises any error during runtime

    Prints a human-understandable error message

    """
    def __init__(
        self,
        plugin: AbstractPlugin,
        method_name: str,
        enhancement: AnyEnhancementType,
        original_msg: str
    ):
        super().__init__(create_msg(plugin, method_name, enhancement, original_msg))
        self.plugin = plugin
        """The plugin who raises the error"""
        self.enhancement = enhancement
        """The enhancement object"""
        self.method_name = method_name
        """The method from the enhancement which was called"""
        self.original_msg = original_msg
        """The original error msg from the plugin"""
