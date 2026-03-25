# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.platform.web.root import Root

from cs.web.components.base.main import BaseModel
from cs.web.components.configurable_ui import ConfigurableUIApp
from cs.web.components.pdf import setup_worker_url

from cs.vp.bom.web.preview import VERSION


class PreviewApp(ConfigurableUIApp):
    @classmethod
    def Actions(cls):
        from cdb import ue
        ue.actions(cls)
        
    @classmethod
    def on_cdbvp_xbom_manager_show_preview_now(cls, ctx):
        ctx.url("/cs-vp-bom-web-preview")

    def update_app_setup(self, app_setup, model, request):
        super(PreviewApp, self).update_app_setup(app_setup, model, request)
        setup_worker_url(model, request, app_setup)


@Root.mount(app=PreviewApp, path="/cs-vp-bom-web-preview")
def _mount_app():
    return PreviewApp()


@PreviewApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Preview"


@PreviewApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    # we need to include threed header here, otherwise we get:
    # Refused to connect to 'http://xxx' because it violates the following
    # Content Security Policy directive: "default-src 'self' 'unsafe-inline'". 
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        return

    request.app.include("cs-web-components-pdf", "15.1.0")
    request.app.include("cs-vp-bom-web-preview", VERSION)
    return "cs-vp-bom-web-preview-PreviewApp"


@PreviewApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-bom-web-preview", VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-bom-web-preview.js")
    lib.add_file("cs-vp-bom-web-preview.js.map")
    static.Registry().add(lib)
