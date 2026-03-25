# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cs.web.components.base.main import SettingDict

COMPONENT_NAME = "cs-vp-bom-web-filter"
VERSION = "15.8.0"


def add_group_component_for_filter_plugin(
    app_setup: SettingDict, group_component: str, plugin_discriminator: str
):
    """
    Adds a group component for a filter plugin discriminator.
    Can be called multiple times with the same group component,
    which will add every given plugin discriminator to this group component.

    :param app_setup: app_setup from cs.web
    :param group_component: name of the registered group component
    :param plugin_discriminator: discriminator of the plugin which should be placed under parent component
    """
    if COMPONENT_NAME not in app_setup:
        app_setup[COMPONENT_NAME] = {}

    key = "groupComponentForFilterPlugins"
    if key not in app_setup[COMPONENT_NAME]:
        app_setup[COMPONENT_NAME][key] = {}

    app_setup[COMPONENT_NAME][key][plugin_discriminator] = group_component
