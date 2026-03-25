# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json

from cdb import util
from cdb import rte
from cdb import sig
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.platform.web.base import byname_app
from cs.web.components.base.main import LAYOUT
from cs.platform.web.util import render_file_template


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []


class VariantMatrixApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(VariantMatrixApp, self).update_app_setup(app_setup, model, request)

        from cs.vp.variants.apps.variant_matrix.view import _setup
        app_setup["cs-vp-variant-matrix"] = _setup(model, request)

        self.include("jquery", "2.1.0")
        self.include("cs-vp-utils", "15.5.0")
        self.include("cs-vp-list-component", "15.5.0")
        self.include("cs-vp-table-component", "15.5.0")
        self.include("cs-vp-variant-matrix", "15.5.0")


class VariantMatrixModel(BaseModel):
    """ Web UI model """

    # Labels used in the web app
    LABELS = [
        "button_cancel",
        "button_close",
        "cs_items_bom",
        "cdb_module2cdb_operations",
        "cdbvp_name",
        "cdbvp_variants_articles",
        "cdbvp_variants_properties",
        "cdbvp_variants_new_variant",
        "cdbvp_variants_shaped_assemblies",
        "cdbvp_variants_selected_variant",
        "cdbvp_variants_web_evaluation",
        "cdbvp_variants_web_filter",
        "cdbvp_variants_web_filter_properties_placeholder",
        "cdbvp_variants_web_filter_variants_placeholder",
        "cdbvp_variants_web_hide_variant_details",
        "cdbvp_variants_web_invalid_variant_err",
        "cdbvp_variants_web_new_variant",
        "cdbvp_variants_web_new_variant_enabled",
        "cdbvp_variants_web_new_variant_disabled",
        "cdbvp_variants_web_select_property_err",
        "cdbvp_variants_web_show_all_variants",
        "cdbvp_variants_web_show_variant_details",
        "cdbvp_variants_web_ajax_err",
        "cdbvp_variants_web_ajax_0",
        "cdbvp_variants_web_error",
        "cdbvp_variants_web_close"
    ]

    def __init__(self, product_object_id, absorb):
        super(VariantMatrixModel, self).__init__()
        self.absorb = absorb
        self.product_object_id = product_object_id

    @property
    def labels(self):
        """ Returns a dict (label id, localized string) containing all the
            labels that are used in the search app.
        """
        result = {lbl: util.Labels()[lbl] for lbl in self.LABELS}
        return result

    def get_path(self, request):
        """ Return the root path of current app. The absorbed parts are removed.
        """
        fullpath = request.link(self)
        if not self.absorb:
            return fullpath
        idx = fullpath.rfind(self.absorb)
        return fullpath if idx < 0 else fullpath[:idx]

    @property
    def class_labels(self):
        from cdbwrapc import CDBClassDef
        cdef = CDBClassDef("part")
        return {cd.getClassname(): cd.getDesignation()
                for cd in (cdef,) + cdef.getSubClasses(True)}


@byname_app.BynameApp.mount(app=VariantMatrixApp, path="variant_matrix")
def _mount_items_app():
    return VariantMatrixApp()


@VariantMatrixApp.path(path='{product_object_id}', model=VariantMatrixModel, absorb=True)
def _get_item_collection(product_object_id, absorb):
    return VariantMatrixModel(product_object_id, absorb)


@VariantMatrixApp.view(model=VariantMatrixModel, name="app_component", internal=True)
def _setup(self, request):
    return "cs-vp-variant-matrix-index_component"
