# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import itertools

from cdb import rte
from cdb import sig
from cdb import tools
from cdb import misc

from cs.platform.web import static
from cs.platform.web.root import Root

from cdb.objects.iconcache import IconCache
from cs.platform.web.uisupport import get_uisupport

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.web.components.plugin_config import Csweb_plugin
from cs.web.components.ui_support.search_favourites import SearchFavouriteCollection
from cs.web.components.ui_support.operations import OperationInfoClass

from cs.audittrail import AuditTrail


class AuditTrailApp(BaseApp):
    client_favicon = "cdb_audittrail"

    def update_app_setup(self, app_setup, model, request):
        super(AuditTrailApp, self).update_app_setup(app_setup, model, request)
        plg_config = {}
        plg_libs = []
        plg_setup = []
        cfg_entries = []
        ctx_name = "cs-audittrail-detail"
        for entry in Csweb_plugin.get_plugin_config(ctx_name):
            cfg_entries.append({'discriminator': entry.get('discriminator'),
                                'component': entry.get('component')})
            for name, version in entry.get("libraries", []):
                plg_libs.append((name, version))
            fqpyname = entry.get("setup")
            if fqpyname is not None:
                try:
                    plg_setup.append(tools.getObjectByName(fqpyname))
                except ImportError as e:
                    misc.log_error("ConfigurableUIModel: Could not import setup"
                                   " function '%s': %s" % (fqpyname, e))
            plg_config[ctx_name] = cfg_entries
            app_setup.update(pluginConfiguration=plg_config)
            for fct in plg_setup:
                fct(model, request, app_setup)
            for name, version in itertools.chain(plg_libs):
                request.app.include(name, version)


class AuditTrailOutletApp(AuditTrailApp):
    pass


@Root.mount(app=AuditTrailOutletApp, path="/cs-audittrail-web-outlet")
def _mount_app():
    return AuditTrailOutletApp()


@Root.mount(app=AuditTrailApp, path="/cs-audittrail-web")
def _mount_app():
    return AuditTrailApp()


@AuditTrailApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Audit Trail"


@AuditTrailOutletApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-audittrail-web", "0.0.1")
    return "cs-audittrail-web-MainComponentOutlet"


@AuditTrailApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-audittrail-web", "0.0.1")
    return "cs-audittrail-web-MainComponent"


@AuditTrailApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@AuditTrailOutletApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-audittrail-web", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-audittrail-web.js")
    lib.add_file("cs-audittrail-web.js.map")
    static.Registry().add(lib)
