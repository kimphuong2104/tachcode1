# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
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

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.vp.bomcreator import msg


class BomcreatorApp(BaseApp):
    pass


@Root.mount(app=BomcreatorApp, path="/cs-vp-bomcreator")
def _mount_app():
    return BomcreatorApp()


@BomcreatorApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return msg("WSM_BOM_app_title")


@BomcreatorApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-vp-bomcreator", "0.0.1")
    return "cs-vp-bomcreator-MainComponent"


@BomcreatorApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-bomcreator", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-bomcreator.js")
    lib.add_file("cs-vp-bomcreator.js.map")
    static.Registry().add(lib)
