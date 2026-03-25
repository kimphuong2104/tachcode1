# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte
from cdb import sig
from cdb import util as cdb_util

from cs.platform.web import static
from cs.platform.web.root import Root

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.classification.web import CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION


class ObjectplanApp(BaseApp):

    def __init__(self):
        super(ObjectplanApp, self).__init__()


@Root.mount(app=ObjectplanApp, path="/classification-objectplan")
def _mount_app():
    return ObjectplanApp()


@ObjectplanApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return cdb_util.get_label("web.cs-classification-objectplan.object_plan")


@ObjectplanApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-classification-web-objectplan", "0.0.1")
    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)
    return "cs-classification-web-objectplan-MainComponent"


@ObjectplanApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@ObjectplanApp.view(model=BaseModel, name="application_title", internal=True)
def get_application_title(self, request):
    return cdb_util.get_label("web.cs-classification-objectplan.object_plan")


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-classification-web-objectplan", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-classification-web-objectplan.js")
    lib.add_file("cs-classification-web-objectplan.js.map")
    static.Registry().add(lib)
