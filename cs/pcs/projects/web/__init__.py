#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

import os

from cdb import auth, rte, sig, util
from cs.platform.web import static

APP = "cs-pcs-projects-web"
VERSION = "15.1.0"


def get_app_url_patterns(request):
    from cs.pcs.projects.web import rest_app
    from cs.pcs.projects.web.rest_app import milestones, project_structure

    links = {}

    for module in [rest_app, milestones, project_structure]:
        links.update(module.get_app_url_patterns(request))

    return links


def setup_settings(model, request, app_setup):
    """
    Adds project default settings to `app_setup`.

    :param model: The application's main model (not used).

    :param request: The morepath request (used for link generation).

    :param app_setup: The application setup object.
    :type app_setup: cs.web.components.base.main.SettingDict
    """
    app_setup.merge_in(
        ["pcs-table-default-settings"],
        {
            "thumbnails": int(
                util.PersonalSettings().getValueOrDefaultForUser(
                    "cs.pcs.table.project.thumbnails", "", auth.persno, ""
                )
            ),
        },
    )


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)
