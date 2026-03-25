# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cs.web.components.base.main import SettingDict

from cs.vp.bom.web.filter import add_group_component_for_filter_plugin, COMPONENT_NAME


def test_add_group_component_for_filter_plugin() -> None:
    app_setup = SettingDict()
    group_component_1 = "group_component_1"
    group_component_2 = "group_component_2"

    plugin_discriminator_1 = "plugin_discriminator_1"
    plugin_discriminator_2 = "plugin_discriminator_2"
    plugin_discriminator_3 = "plugin_discriminator_3"

    add_group_component_for_filter_plugin(
        app_setup, group_component_1, plugin_discriminator_1
    )
    add_group_component_for_filter_plugin(
        app_setup, group_component_2, plugin_discriminator_2
    )
    add_group_component_for_filter_plugin(
        app_setup, group_component_1, plugin_discriminator_3
    )

    key = "groupComponentForFilterPlugins"
    group_component_for_filter_plugins = app_setup[COMPONENT_NAME][key]

    assert (
        group_component_for_filter_plugins[plugin_discriminator_1]
        == group_component_1
    )
    assert (
        group_component_for_filter_plugins[plugin_discriminator_2]
        == group_component_2
    )
    assert (
        group_component_for_filter_plugins[plugin_discriminator_3]
        == group_component_1
    )
