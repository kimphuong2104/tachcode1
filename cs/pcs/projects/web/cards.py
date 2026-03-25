#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

from cs.pcs.projects.common.cards import add_card


def setup_project_default_card(model, request, app_setup):
    """
    Adds the serialized mask configuration for class "cdbpcs_project" and
    ``DisplayConfiguration`` "table_card" to ``app_setup``.

    :param model: The application's main model (unused).
    :type model:

    :param request: The request sent from the frontend (unused).
    :type request: morepath.Request

    :param app_setup: The application setup object.
    :type app_setup: cs.web.components.base.main.SettingDict

    .. note ::

        Every page, outlet or application intending to use "cards" has to load
        the appropriate configuration somehow.
        Putting them into ``app_setup`` is the recommended pattern.

    """
    add_card(app_setup, "cdbpcs_project", "table_card")
