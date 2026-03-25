# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import logging
import os

from cdb import rte, sig
from cs.materials.web.curves.main import LIB_NAME as CURVES_LIB_NAME
from cs.materials.web.curves.main import LIB_VERSION as CURVES_LIB_VERSION
from cs.platform.web import static
from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

LIB_NAME = "cs-materials-web-components"
LIB_VERSION = "15.1.1"
LOG = logging.getLogger(__name__)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        LIB_NAME, LIB_VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(LIB_NAME + ".js")
    lib.add_file(LIB_NAME + ".js.map")
    static.Registry().add(lib)


class MaterialDetailsModel(SinglePageModel):
    page_name = "csmat-material-details"


class MaterialDetailsApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(MaterialDetailsApp, self).update_app_setup(app_setup, model, request)
        self.include(CURVES_LIB_NAME, CURVES_LIB_VERSION)
        self.include(LIB_NAME, LIB_VERSION)


@byname_app.BynameApp.mount(app=MaterialDetailsApp, path="csmat_material")
def _mount_material_details_app():
    return MaterialDetailsApp()


@MaterialDetailsApp.path(
    path="details/{material_key}", model=MaterialDetailsModel, absorb=True
)
def _get_material_details_model(absorb, material_key):
    return MaterialDetailsModel()


@MaterialDetailsApp.view(model=MaterialDetailsModel, name="base_path", internal=True)
def _get_material_details_base_path(model, request):
    return request.path
