# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


import os

from cdb import rte, sig
from cs.platform.web import static
from cs.variants.web.xbommanager import VERSION
from cs.vp.bom.web.bommanager.main import BommanagerModel
from cs.web.components.configurable_ui import ConfigurableUIModel
from cs.web.components.ui_support import forms


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-variants-web-xbommanager",
        VERSION,
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-variants-web-xbommanager.js")
    lib.add_file("cs-variants-web-xbommanager.js.map")
    static.Registry().add(lib)


@sig.connect(BommanagerModel, ConfigurableUIModel, "application_setup")
def update_app_setup(_, request, app_setup):
    app_setup["cs-variants"] = {
        "variabilityModelCatalog": forms.FormInfoBase.get_catalog_config(
            request,
            "cs_variants_select_maxbom_variability_model_browser",
            is_combobox=False,
            as_objs=True,
        ),
        "variantCatalog": forms.FormInfoBase.get_catalog_config(
            request, "cs_variants", is_combobox=False, as_objs=True
        ),
    }
