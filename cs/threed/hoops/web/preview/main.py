# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.platform.web.root import Root

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.threed.hoops.web.utils import add_csp_header
from cs.threedlibs.web.communicator.main import VERSION as COMMUNICATOR_VERSION
from cs.vp.bom.web.preview import VERSION  as VP_PREVIEW_VERSION


__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


class PreviewApp(BaseApp):
    pass


@Root.mount(app=PreviewApp, path="/cs-threed-hoops-web-preview")
def _mount_app():
    return PreviewApp()


@PreviewApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Preview"


@PreviewApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.after(add_csp_header)

    request.app.include("cs-threedlibs-communicator", COMMUNICATOR_VERSION)
    request.app.include("cs-threed-hoops-web-cockpit", "15.5.1")
    request.app.include("cs-vp-bom-web-preview", VP_PREVIEW_VERSION)
    request.app.include("cs-threed-hoops-web-preview", "15.5.1")
    return "cs-threed-hoops-web-preview-MainComponent"


@PreviewApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@PreviewApp.view(model=BaseModel, name="application_title", internal=True)
def get_application_title(self, request):
    return "Preview"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-threed-hoops-web-preview", "15.5.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-threed-hoops-web-preview.js")
    lib.add_file("cs-threed-hoops-web-preview.js.map")
    static.Registry().add(lib)
