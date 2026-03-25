# -*- mode: python; coding: utf-8 -*-

#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

#
__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.variants.web.frontend_scripts import COMPONENT_NAME, VERSION
from cs.web.components.base.main import BaseModel
from cs.web.components.configurable_ui import ConfigurableUIModel


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-variants-web-frontend_scripts.js")
    lib.add_file("cs-variants-web-frontend_scripts.js.map")
    static.Registry().add(lib)


# TODO: Monitor CR E057013 -> change if other options exists
@sig.connect(BaseModel, ConfigurableUIModel, "application_setup")
def update_app_setup(model, _, __):
    model.add_library(COMPONENT_NAME, VERSION)
