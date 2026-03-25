# -*- mode: python; coding: utf-8 -*-
#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from webob import exc

from cs.platform.web import JsonAPI, root
from cs.variants import VariabilityModel
from cs.variants.web import common
from cs.variants.web.editor import get_variant_manager_setup_information
from cs.variants.web.util import get_object_from_rest_link
from cs.vp.products import Product


class VariantEditorInternal(JsonAPI):
    pass


@root.Internal.mount(app=VariantEditorInternal, path="variant_manager")
def _mount_internal():
    return VariantEditorInternal()


@VariantEditorInternal.path(path="setup_information")
class VariantEditorInternalVariabilityModel:
    pass


@VariantEditorInternal.json(
    model=VariantEditorInternalVariabilityModel, request_method="POST"
)
def get_variant_editor_setup_information(_, request):
    product = None
    variability_model = None

    product_rest_link = request.json.get("productRestLink")
    if product_rest_link is not None:
        product = get_object_from_rest_link(Product, product_rest_link)

    variability_model_rest_link = request.json.get("variabilityModelRestLink")
    if variability_model_rest_link is not None:
        variability_model = get_object_from_rest_link(
            VariabilityModel, variability_model_rest_link
        )

    if product is None and variability_model is None:
        raise exc.HTTPNotFound("Product and/or VariabilityModel not found")

    if product is not None and variability_model is not None:
        if variability_model.Product != product:
            raise exc.HTTPUnprocessableEntity(
                "VariabilityModel does not belong to given product"
            )

    if product is None:
        product = variability_model.Product

    if variability_model is None:
        variability_models = product.VariabilityModels
    else:
        variability_models = [variability_model]

    app_setup = {}
    common.update_app_setup(
        request, app_setup, product=product, variability_models=variability_models
    )
    result = app_setup[common.COMPONENT_NAME]

    app_setup_data = get_variant_manager_setup_information(variability_models)
    result.update(app_setup_data)

    return result
