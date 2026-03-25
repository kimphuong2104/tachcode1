# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
cs.workplan
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os
from webob.exc import HTTPBadRequest

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.platform.web.root import Root

from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

from cs.platform.web.rest.support import decode_key_component

from cs.workplan import Workplan


class WorkplanApp(BaseApp):
    pass


@Root.mount(app=WorkplanApp, path="/cs-workplan")
def _mount_app():
    return WorkplanApp()


@WorkplanApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Workplan"


@WorkplanApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-workplan", "0.0.1")
    return "cs-workplan-MainComponent"


@WorkplanApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-workplan", "0.0.1", os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-workplan.js")
    lib.add_file("cs-workplan.js.map")
    static.Registry().add(lib)


class WorkplanVisualization(object):
    def __init__(self, orientation, workplan_id, workplan_index):

        self.workplan = Workplan.ByKeys(
            workplan_id=workplan_id, workplan_index=workplan_index
        )
        self.svg = self.workplan.cswp_workplan_visualization_render(orientation)

    def get_visualization(self):
        return self.svg


@WorkplanApp.path(path="visualization/{keys}", model=WorkplanVisualization)
def get_visualization_model(app, keys):
    key_values = [decode_key_component(k) for k in keys.split("@")]
    try:
        return WorkplanVisualization(key_values[0], key_values[1], key_values[2])
    except ValueError:
        raise HTTPBadRequest()


@WorkplanApp.json(model=WorkplanVisualization, request_method="GET")
def default_view(model, request):
    return {
        # "root_object_id": model.wor
        # "root_desc": model.root.GetDescription(),
        # "radius": model.radius,
        "svg": model.get_visualization()
    }
