# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK, GLOBAL_CUSTOMIZATION_HOOK
from cs.web.components.configurable_ui import ConfigurableUIModel

from cs.classification.tools import get_active_classification_languages

CLASSIFICATION_COMPONENT_VERSION = "15.1.0"
CLASSIFICATION_COMPONENT_NAME = "cs-classification-web-component"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(CLASSIFICATION_COMPONENT_NAME,
                         CLASSIFICATION_COMPONENT_VERSION,
                         os.path.join(os.path.dirname(__file__), "component", "build"))
    lib.add_file(CLASSIFICATION_COMPONENT_NAME + '.js')
    lib.add_file(CLASSIFICATION_COMPONENT_NAME + '.js.map')
    static.Registry().add(lib)


@sig.connect(ConfigurableUIModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def _update_app_setup(app_setup, request):
    app_setup.merge_in([CLASSIFICATION_COMPONENT_NAME], {
        'active_classification_languages': get_active_classification_languages()
    })


@sig.connect(GLOBAL_CUSTOMIZATION_HOOK)
def _add_classification_lib(request):
    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)
