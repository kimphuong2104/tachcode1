# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP
from cs.costing.calculations import Calculation


class CostingApp(BaseApp):
    pass

@Root.mount(app=CostingApp, path="/cs-costing-web")
def _mount_app():
    return CostingApp()


@CostingApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Costing"


@CostingApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-costing-web", "15.4.0")
    return "cs-costing-web-MainComponent"


@CostingApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-costing-web", "15.4.0",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-costing-web.js")
    lib.add_file("cs-costing-web.js.map")
    static.Registry().add(lib)


@sig.connect(Calculation, DETAIL_VIEW_SETUP)
def _app_setup(clsname, request, app_setup):
    app_setup.merge_in(
        ["appSettings"],
        {
            "calculationSearch": Calculation.set_revision_search_pattern()
        }
    )
    try:
        from cs.threed.hoops import add_threed_libs
        from cs.threed.hoops.web.utils import add_csp_header

        request.after(add_csp_header)
        add_threed_libs(request)
    except ImportError:
        pass
    request.app.include("cs-web-components-pdf", "15.1.0")
    request.app.include("cs-vp-bom-web-preview", "15.7.0")
