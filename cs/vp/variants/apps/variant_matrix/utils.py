# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module utils

This is the documentation for the utils module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.platform.web import PlatformApp
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.relship.main import make_relship_target
from cs.platform.web.root import get_v1
from cs.platform.web.root.main import Internal

from cs.vp import products
from cs.vp.variants.vpmsolvers import BasicVPMSolver
from cs.vp.variants.varianttableadapters import ProductAdapter


def safe_int(arg):
    try:
        return int(arg)
    except ValueError:
        return None

APP_ID = "cs.vp.variants.apps.variant_matrix"


class VariantMatrixUtilsBaseApp(PlatformApp):
    pass


@Internal.mount(app=VariantMatrixUtilsBaseApp, path=APP_ID)
def _mount():
    return VariantMatrixUtilsBaseApp()


class CheckVariantModel(object):
    def __init__(self, *args, **kwargs):
        self.product_object_id = kwargs.get('product_object_id', '')


@VariantMatrixUtilsBaseApp.path(model=CheckVariantModel, path='utils/check_variant')
def get_check_variant_model():
    return CheckVariantModel()


@VariantMatrixUtilsBaseApp.json(model=CheckVariantModel, request_method='POST')
def check_variant(model, request):
    data = request.json
    product_object_id = data.get('product_object_id')
    product = products.Product.ByKeys(cdb_object_id=product_object_id)

    values = data.get('values')
    if values == None or len(values) == 0:
        return False

    def check_constraint(constraint):
        prop_ids, prop_values = list(zip(*values.items()))
        return constraint.compute(list(map(int, prop_ids)))(*prop_values)

    variant_valid = all((check_constraint(constraint) for constraint in product.AllConstraints))
    return variant_valid
