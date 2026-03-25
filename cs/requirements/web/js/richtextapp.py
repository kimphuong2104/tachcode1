# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.platform.web.root import Root

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel


class RichtextApp(BaseApp):
    pass


@Root.mount(app=RichtextApp, path="/cs-requirements-web-richtext")
def _mount_app():
    return RichtextApp()


@RichtextApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Richtext"


@RichtextApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-requirements-web-richtext", "0.0.1")
    request.app.include("cs-requirements-web-richtext-wrapper", "0.0.1")
    return "cs-requirements-web-richtext-wrapper-MainComponent"


@RichtextApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-requirements-web-richtext-wrapper", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'richtext_wrapper', 'build'))
    lib.add_file("cs-requirements-web-richtext-wrapper.js")
    lib.add_file("cs-requirements-web-richtext-wrapper.js.map")
    static.Registry().add(lib)
