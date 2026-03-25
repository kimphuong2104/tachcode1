# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import os

from webob import exc

from cdb import rte, sig, util
from cs.classification.web import (
    CLASSIFICATION_COMPONENT_NAME,
    CLASSIFICATION_COMPONENT_VERSION,
)
from cs.platform.web import root, static
from cs.platform.web.rest.support import get_restlink
from cs.variants.web.common import COMPONENT_NAME as COMMON_COMPONENT_NAME
from cs.variants.web.common import VERSION as COMMON_VERSION
from cs.variants.web.editor import COMPONENT_NAME, VERSION
from cs.vp import products
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel


class VariantEditorApp(ConfigurableUIApp):
    def __init__(self, product_oid):
        super().__init__()
        self.product = products.Product.ByKeys(cdb_object_id=product_oid)
        if self.product is None:
            raise exc.HTTPNotFound()

    def update_app_setup(self, app_setup, model, request):
        super().update_app_setup(app_setup, model, request)

        app_setup.merge_in(
            [COMPONENT_NAME], {"product_rest_link": get_restlink(self.product)}
        )


class VariantEditorModel(SinglePageModel):
    page_name = "cs-variants-web-editor"


@root.Root.mount(app=VariantEditorApp, path="/variant_editor/{product_oid}")
def _mount_app(product_oid):
    return VariantEditorApp(product_oid)


@VariantEditorApp.path(path="", model=VariantEditorModel)
def _get_model():
    return VariantEditorModel()


@VariantEditorApp.view(model=VariantEditorModel, name="document_title", internal=True)
def default_document_title(_, request):
    return "%s / %s" % (
        util.get_label("web.variant_editor.document_title"),
        request.app.product.GetDescription(),
    )


@VariantEditorApp.view(model=VariantEditorModel, name="app_component", internal=True)
def _setup(_, request):
    request.app.include(CLASSIFICATION_COMPONENT_NAME, CLASSIFICATION_COMPONENT_VERSION)
    request.app.include("cs-vp-bom-web-filter", "15.8.0")
    request.app.include(COMMON_COMPONENT_NAME, COMMON_VERSION)
    request.app.include(COMPONENT_NAME, VERSION)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-variants-web-editor.js")
    lib.add_file("cs-variants-web-editor.js.map")
    static.Registry().add(lib)
