# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

from __future__ import absolute_import
__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte
from cdb import sig
from cdb import util

from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel


class CreatelinkspApp(BaseApp):
    pass


@Root.mount(app=CreatelinkspApp, path="/cs-tools-semanticlinks-createLinksApp")
def _mount_app():
    return CreatelinkspApp()


@CreatelinkspApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("button_new")


@CreatelinkspApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-tools-semanticlinks-createLinksApp", "0.0.1")
    return "cs-tools-semanticlinks-createLinksApp-MainComponent"


@CreatelinkspApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-tools-semanticlinks-createLinksApp", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-tools-semanticlinks-createLinksApp.js")
    lib.add_file("cs-tools-semanticlinks-createLinksApp.js.map")
    static.Registry().add(lib)
