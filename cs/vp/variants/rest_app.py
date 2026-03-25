# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module rest_app

This is the documentation for the rest_app module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cs.vp import variants
from cs.vp import products

from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest import CollectionApp
from cs.platform.web.rest.generic import model as generic_model


class VariantApp(GenericApp):
    def __init__(self):
        super(VariantApp, self).__init__("variant")


@CollectionApp.mount(app=VariantApp, path="variant")
def _mount_app():
    return VariantApp()


@GenericApp.defer_links(model=variants.Variant)
def _defer_item(app, _item):
    return app.child(VariantApp())


@VariantApp.json(model=generic_model.ObjectCollection, request_method='POST')
def _create_variant(model, request):
    result = []
    for data in request.json:
        name = data.get('name', '')
        product_object_id = data.get('product_object_id')
        values = data.get('values')

        product = products.Product.ByKeys(cdb_object_id=product_object_id)
        if product and values:
            variant = variants.ProductVariant.CreateVariant(values, product_object_id, name=name)
            result.append(request.view(variant))
    return result
