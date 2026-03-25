# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp, BaseModel

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

APP = "cs-workflow-web"
MOUNT = "/cs-workflow-web"
VERSION = "15.2.0"
FILE = __file__
BUILD_DIR = os.path.join(os.path.dirname(FILE), 'js', 'build')


class WebApp(BaseApp):
    pass


@Root.mount(app=WebApp, path=MOUNT)
def _mount_app():
    return WebApp()


@WebApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Workflows"


@WebApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(APP, VERSION)
    return "cs-workflow-web-MainComponent"


@WebApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@WebApp.view(model=BaseModel, name="application_title", internal=True)
def get_application_title(self, request):
    return "Workflows"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(APP, VERSION, BUILD_DIR)
    lib.add_file("{}.js".format(APP))
    lib.add_file("{}.js.map".format(APP))
    static.Registry().add(lib)
