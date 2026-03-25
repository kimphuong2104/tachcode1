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

# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import logging
import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

LIB_NAME = "cs-materials-web-curves"
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


class CurvesModel(SinglePageModel):
    page_name = "csmat-curves"


class CurvesApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(CurvesApp, self).update_app_setup(app_setup, model, request)
        self.include(LIB_NAME, LIB_VERSION)


@byname_app.BynameApp.mount(app=CurvesApp, path="csmat_curves")
def _mount_curves_app():
    return CurvesApp()


@CurvesApp.path(path="{rest_name}/{cdb_object_id}", model=CurvesModel, absorb=True)
def _get_curves_model(absorb, rest_name, cdb_object_id):
    return CurvesModel()


@CurvesApp.view(model=CurvesModel, name="base_path", internal=True)
def _get_curves_base_path(model, request):
    return request.path
