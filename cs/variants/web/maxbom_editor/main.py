# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import os

from webob import exc

from cdb import rte, sig, util
from cs.classification.rest import utils as classification_rest_utils
from cs.classification.web import (
    CLASSIFICATION_COMPONENT_NAME,
    CLASSIFICATION_COMPONENT_VERSION,
)
from cs.classification.web.admin import COMPONENT_NAME as CLASSIFICATION_ADMIN_NAME
from cs.classification.web.admin import (
    COMPONENT_VERSION as CLASSIFICATION_ADMIN_VERSION,
)
from cs.classification.web.editor import COMPONENT_NAME as CLASSIFICATION_EDITOR_NAME
from cs.classification.web.editor import (
    COMPONENT_VERSION as CLASSIFICATION_EDITOR_VERSION,
)
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.variants.api.variants_classification import VariantsClassification
from cs.variants.selection_condition import get_expression_dd_field_length
from cs.variants.web import add_threed_csp_header
from cs.variants.web.bom_table_extensions import (
    COMPONENT_NAME as BOM_TABLE_EXTENSION_COMPONENT_NAME,
)
from cs.variants.web.bom_table_extensions import VERSION as BOM_TABLE_EXTENSION_VERSION
from cs.variants.web.common import COMPONENT_NAME as COMMON_COMPONENT_NAME
from cs.variants.web.common import VERSION as COMMON_VERSION
from cs.variants.web.common import update_app_setup as update_common_app_setup
from cs.variants.web.maxbom_editor import COMPONENT_NAME, VERSION
from cs.variants.web.util import link_rest_object
from cs.vp import products
from cs.vp.bom.web.preview import VERSION as PREVIEW_VERSION
from cs.vp.bom.web.table import VERSION as BOM_TABLE_VERSION
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel
from cs.web.components.outlet_config import replace_outlets


class MaxBomEditorApp(ConfigurableUIApp):
    def __init__(self, product_oid):
        super().__init__()
        self.product = products.Product.ByKeys(cdb_object_id=product_oid)

        if self.product is None:
            raise exc.HTTPNotFound()

    def get_title(self):
        return "%s / %s" % (
            util.get_label("web.maxbom_editor.document_title"),
            self.product.GetDescription(),
        )

    def update_app_setup(self, app_setup, model, request):
        super().update_app_setup(app_setup, model, request)

        # BaseErrorModel doesn't have the method update_app_setup
        if hasattr(model, "update_app_setup"):
            model.update_app_setup(app_setup, request)

        replace_outlets(model, app_setup)


class MaxBomEditorModel(SinglePageModel):
    page_name = "cs-variants-web-maxbom_editor"

    def __init__(self):
        super().__init__()

        self.add_plugin_context("cs-variants-maxbom-filter")

    def get_base_path(self, path):
        return "/".join(path.split("/")[:3])

    def update_app_setup(self, app_setup, request):
        product = request.app.product

        variability_models = product.VariabilityModels
        class_codes = [
            variability_model.class_code for variability_model in variability_models
        ]

        update_common_app_setup(
            request,
            app_setup,
            product,
            variability_models=variability_models,
        )

        variants_classification = VariantsClassification(class_codes)

        app_setup[COMPONENT_NAME] = {
            "product_id": link_rest_object(request, product),
            "catalog_values": classification_rest_utils.ensure_json_serialiability(
                variants_classification.get_catalog_values()
            ),
            "expression_dd_field_length": get_expression_dd_field_length(),
        }


@Root.mount(app=MaxBomEditorApp, path="/maxbom_editor/{product_oid}")
def _mount_app(product_oid):
    return MaxBomEditorApp(product_oid)


@MaxBomEditorApp.path(path="", model=MaxBomEditorModel)
def _get_model():
    return MaxBomEditorModel()


@MaxBomEditorApp.view(model=MaxBomEditorModel, name="document_title", internal=True)
def default_document_title(_, request):
    return request.app.get_title()


@MaxBomEditorApp.view(model=MaxBomEditorModel, name="app_component", internal=True)
def _setup(_, request):
    add_threed_csp_header(request)

    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)
    request.app.include(CLASSIFICATION_EDITOR_NAME, CLASSIFICATION_EDITOR_VERSION)
    request.app.include(CLASSIFICATION_ADMIN_NAME, CLASSIFICATION_ADMIN_VERSION)
    request.app.include("cs-vp-bom-web-table", BOM_TABLE_VERSION)
    request.app.include("cs-vp-bom-web-filter", "15.8.0")
    request.app.include("cs-vp-bom-web-preview", PREVIEW_VERSION)
    request.app.include("cs-vp-bom-web-product_structure", "15.10.0")
    request.app.include(COMMON_COMPONENT_NAME, COMMON_VERSION)
    request.app.include(BOM_TABLE_EXTENSION_COMPONENT_NAME, BOM_TABLE_EXTENSION_VERSION)
    request.app.include(COMPONENT_NAME, VERSION)


@MaxBomEditorApp.view(model=MaxBomEditorModel, name="base_path", internal=True)
def get_base_path(model, request):
    return model.get_base_path(request.path)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-variants-web-maxbom_editor.js")
    lib.add_file("cs-variants-web-maxbom_editor.js.map")
    static.Registry().add(lib)
