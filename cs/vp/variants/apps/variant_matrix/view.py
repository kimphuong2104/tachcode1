# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module view

This is the documentation for the view module.
"""
# Some imports

from cdb import CADDOK
from cdb import util
import cdbwrapc

from cs.platform.web.rest.generic.model import ObjectCollection
from cs.platform.web.root import get_v1

from cs.vp.variants.apps. rest_additions import _make_variant_operations_dict

from cs.vp.variants.apps.variant_matrix.main import VariantMatrixApp
from cs.vp.variants.apps.variant_matrix.main import VariantMatrixModel
from cs.vp.variants.apps.variant_matrix.utils import APP_ID as utils_id
from cs.vp.variants.apps.variant_matrix.utils import CheckVariantModel

from cs.platform.web.rest.relship.main import make_relship_target
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.root.main import get_internal


from cs.vp import products


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def _setup(model, request):
    # english locale is always there, no need to load that explicitly
    # if CADDOK.ISOLANG != 'en':
    #     request.include("moment/locale/%s.js" % CADDOK.ISOLANG)

    def urls(names, app):
        return {
            rest_name: request.link(
                ObjectCollection(clazz, extra_parameters={}, rule=''),
                app=app
            )
            for rest_name, clazz in names
        }

    collection_app = get_v1(request).child("collection")
    base_urls = {
        clazz: request.link(
            ObjectCollection(clazz, extra_parameters={}, rule=''),
            app=collection_app
        ).split("?withFiles")[0]
        for clazz in ["product", "variant", "property",
                      "part", "variant_part"]
    }
    utils_app = get_internal(request).child(utils_id)
    util_urls = {"check_variant": request.link(CheckVariantModel(), app=utils_app)}

    from cdbwrapc import CDBClassDef

    class_app = get_v1(request).child("class")
    type_urls = {
        rest_name: request.link(
            CDBClassDef(clazz),
            app=class_app
        )
        for rest_name, clazz in [
            ("product", "cdbvp_product"),
            ("variant", "cdbvp_variant"),
            ("property", "cdbvp_property"),
            ("property_value", "cdbvp_property_value"),
            ("part", "part"),
            ("bom_item", "bom_item"),
            ("cdbvp_bom_predicate", "cdbvp_bom_predicate")]
    }

    # push settings from python to JS
    return {
        "debug": False,
        "language": CADDOK.ISOLANG,
        "product_object_id": model.product_object_id,
        "links": {
            "app_root": model.get_path(request),
            "base_urls": base_urls,
            "type_urls": type_urls,
            "util_urls": util_urls
        },
        "class_labels": model.class_labels,
        "title": util.get_label("cdbvp_variant_matrix"),
        "labels": model.labels
    }


@VariantMatrixApp.view(model=VariantMatrixModel, name="additional_head", internal=True)
def _additional_head(_model, _request):
    return "\n".join(['<link rel="shortcut icon" cdbicon="cdbvp_variant_matrix" href="/resources/icons/byname/cdbvp_variant_matrix/0">',
                      '<link rel="icon" cdbicon="cdbvp_variant_matrix" href="/resources/icons/byname/cdbvp_variant_matrix/0">',
                      '<link rel="apple-touch-icon" cdbicon="cdbvp_variant_matrix" href="/resources/icons/byname/cdbvp_variant_matrix/0">'])


@VariantMatrixApp.view(model=VariantMatrixModel, name="document_title", internal=True)
def _item_title(model, _request):
    return cdbwrapc.getApplicationWndName(util.get_label("cdbvp_variant_matrix"))


@VariantMatrixApp.html(model=VariantMatrixModel, name="content", internal=True)
def _app_content(self, _request):
    """Return a root div for react to render into.
    """
    return '<div id="root">Fatal Error</div>'


@products.ProductApp.json(model=products.Product, name="variant_matrix")
def _init_data(product, request):
    def complete(obj, relname, **kwargs):
        return request.view(make_relship_target(obj, relname), name="complete-target", **kwargs)

    def simple(obj, relname, **kwargs):
        return request.view(make_relship_target(obj, relname), **kwargs)

    collection_app = get_v1(request).child("collection")
    property_app = collection_app.child(GenericApp, rest_name="property")
    variant_app = collection_app.child(GenericApp, rest_name="variant")
    property_value_app = collection_app.child(GenericApp, rest_name="cdbvp_property_value")

    # product
    objects = [request.view(product)]

    variants = complete(product, "Variants")
    targets = variants.get("targets")
    for variant in product.Variants:
        matchingVariant = [x for x in targets if x.get("cdb_object_id") == variant.cdb_object_id][0]  # pylint: disable=undefined-loop-variable
        _make_variant_operations_dict(None, variant, matchingVariant)

    # relships
    # -> variants
    # -> properties
    relships = [
        variants,
        complete(product, "Properties"),
        simple(product, "TopLevelProperties")
    ]

    # variants
    for variant in product.Variants:
        # relships
        # -> property values
        relships.append(complete(variant, "PropertyValues", app=variant_app))

        # property values
        for pv in variant.PropertyValues:
            # relships
            # -> enum definitions
            relships.append(simple(pv, "EnumValue", app=property_value_app))

    # properties
    for prop in product.Properties:
        # relships
        # -> enum definitions
        # -> subproperties
        relships.extend([
            complete(prop, "EnumValues", app=property_app),
            simple(prop, "SubProperties", app=property_app)
        ])

    return {
        "objects": objects,
        "relships": relships
    }


# Exported objects
__all__ = []


# Guard importing as main module
if __name__ == "__main__":
    pass
