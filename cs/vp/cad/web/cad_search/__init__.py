# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.web.components.base.main import GLOBAL_CUSTOMIZATION_HOOK

CLASSIFICATION_COMPONENT_VERSION = "15.10.0"
CLASSIFICATION_COMPONENT_NAME = "cs-vp-cad-web-cad_search"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-cad-web-cad_search", "15.10.0",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-cad-web-cad_search.js")
    lib.add_file("cs-vp-cad-web-cad_search.js.map")
    static.Registry().add(lib)


@sig.connect(GLOBAL_CUSTOMIZATION_HOOK)
def _add_classification_lib(request):
    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)