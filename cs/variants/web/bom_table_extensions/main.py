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
from cs.variants.api.filter import (
    CsVariantsBomTableAttributesPlugin,
    CsVariantsMengeRendererAttributesPlugin,
    CsVariantsSelectionConditionRendererAttributesPlugin,
    CsVariantsVariantFilterPlugin,
)
from cs.variants.web.bom_table_extensions import COMPONENT_NAME, VERSION
from cs.variants.web.common import COMPONENT_NAME as COMMON_COMPONENT_NAME
from cs.variants.web.common import VERSION as COMMON_VERSION
from cs.vp.bom.enhancement.register import BomTableScope, PluginRegister
from cs.vp.bom.web.bommanager.main import BommanagerModel
from cs.vp.variants.filter import CsVpVariantsAttributePlugin, CsVpVariantsFilterPlugin
from cs.web.components.configurable_ui import ConfigurableUIModel


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-variants-web-bom_table_extensions.js")
    lib.add_file("cs-variants-web-bom_table_extensions.js.map")
    static.Registry().add(lib)


@sig.connect(BommanagerModel, ConfigurableUIModel, "application_setup")
def update_app_setup(_, request, __):
    request.app.include(COMMON_COMPONENT_NAME, COMMON_VERSION)
    request.app.include(COMPONENT_NAME, VERSION)


PluginRegister().unregister_plugin(CsVpVariantsAttributePlugin)
PluginRegister().unregister_plugin(CsVpVariantsFilterPlugin)

PluginRegister().register_plugin(
    CsVariantsBomTableAttributesPlugin,
    [
        BomTableScope.INIT,
        BomTableScope.LOAD,
    ],
)
PluginRegister().register_plugin(
    CsVariantsVariantFilterPlugin,
    [
        BomTableScope.SEARCH,
        BomTableScope.DIFF_LOAD,
        BomTableScope.DIFF_SEARCH,
        BomTableScope.MAPPING,
        BomTableScope.FIND_LBOMS,
        BomTableScope.SYNC_LBOM,
        BomTableScope.SYNC_RBOM,
    ],
)

PluginRegister().register_plugin(
    CsVariantsSelectionConditionRendererAttributesPlugin,
    BomTableScope.LOAD,
)
PluginRegister().register_plugin(
    CsVariantsMengeRendererAttributesPlugin,
    BomTableScope.LOAD,
)
