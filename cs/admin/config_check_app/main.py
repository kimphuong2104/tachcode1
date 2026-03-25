# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
Web app to start a configuration check and render the results
"""

from __future__ import absolute_import

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte
from cdb import sig

from cdb.comparch.modules import Module
from cdb.comparch.packages import Package
from cs.platform.web import static
from cs.platform.web.root import Internal
from cs.web.components.base.main import BaseApp, BaseModel


class ConfigCheckApp(BaseApp):

    def update_app_setup(self, app_setup, model, request):
        super(ConfigCheckApp, self).update_app_setup(app_setup, model, request)
        app_setup.merge_in(["links", "cs-admin"], {
            "config_check_api": "/internal/cs-admin/config-check-api"
        })


@Internal.mount(app=ConfigCheckApp, path="/cs-admin/config-check")
def _mount_app():
    return ConfigCheckApp()


@ConfigCheckApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Configuration Check"


@ConfigCheckApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-admin-config_check_app", "0.0.1")
    return "cs-admin-config_check_app-MainComponent"


@ConfigCheckApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-admin-config_check_app", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-admin-config_check_app.js")
    lib.add_file("cs-admin-config_check_app.js.map")
    static.Registry().add(lib)


@sig.connect(Module, list, "cdb_module_show_configcheck", "now")
def _module_configcheck(objects, ctx):
    qs = "&".join("modules[]=%s" % obj.module_id for obj in objects)
    ctx.url("/internal/cs-admin/config-check?%s" % qs)


@sig.connect(Package, list, "cdb_module_show_configcheck", "now")
def _package_configcheck(objects, ctx):
    qs = "&".join("packages[]=%s" % obj.name for obj in objects)
    ctx.url("/internal/cs-admin/config-check?%s" % qs)
