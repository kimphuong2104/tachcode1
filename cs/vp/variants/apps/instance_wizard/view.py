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

import cdbwrapc

from cdb import CADDOK
from cdb import util
from cdb.constants import kOperationSearch
from cdb.elink import isCDBPC
from cs.platform.web.rest.app import CollectionApp
from cs.platform.web.rest.generic.main import App as GenericApp
from cs.platform.web.rest.generic.model import ObjectCollection
from cs.platform.web.rest.relship.main import make_relship_target
from cs.platform.web.root import get_v1
from cs.platform.web.root.main import get_internal

from webob.exc import HTTPBadRequest

from cs.vp import products
from cs.vp.variants import Variant
from cs.vp.variants.apps.instance_wizard.main import InstanceWizardApp
from cs.vp.variants.apps.instance_wizard.main import InstanceWizardModel
from cs.vp.variants.apps.instance_wizard.utils import APP_ID as utils_id
from cs.vp.variants.apps.instance_wizard.utils import BOMTextSearchModel, BOMPredicateSearchModel, safe_int
from cs.vp.variants.items import Item


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

    from cdbwrapc import CDBClassDef

    class_app = get_v1(request).child("class")
    type_urls = {
        rest_name: request.link(
            CDBClassDef(clazz),
            app=class_app
        )
        for rest_name, clazz in [
            ("product", "cdbvp_product"),
            ("variant", "cdbvp_product_variant"),
            ("property", "cdbvp_property"),
            ("cdbvp_property_value", "cdbvp_property_value"),
            ("part", "part"),
            ("bom_item", "bom_item"),
            ("cdbvp_bom_predicate", "cdbvp_bom_predicate")]
    }

    utils_app = get_internal(request).child(utils_id)
    util_urls = {"bom_text_search": request.link(BOMTextSearchModel(), app=utils_app),
                 "bom_predicate_search": request.link(BOMPredicateSearchModel(), app=utils_app)}

    # push settings from python to JS
    app_setup = {
        "product_object_id": model.product_object_id,
        "variant_id": model.variant_id,
        "teilenummer": model.teilenummer,
        "t_index": model.t_index,
        "instance_oid": model.instance_oid,
        "debug": CADDOK.get("ELINK_DEBUG", False),
        "language": CADDOK.ISOLANG,
        "links": {
            "app_root": model.get_path(request),
            "base_urls": base_urls,
            "type_urls": type_urls,
            "util_urls": util_urls
        },
        "class_labels": model.class_labels,
        "title": util.get_label("cdbvp_instantiate_max_bom"),
        "labels": model.labels,
        "isCDBPC": isCDBPC(),
        # "frameComponentName": "cs.vp.variants.apps.instance_wizard.root_component",
        # "basePathElements": [
        #     {
        #         "basePath": "/byname/instance_wizard/:productObjectId/:variantObjectId/:teileNummer/:tIndex",
        #         "indexComponentName": "cs.vp.variants.apps.instance_wizard.index_component"
        #     },
        #     {
        #         "basePath": "/byname/instance_wizard/:productObjectId/:variantObjectId/:teileNummer",
        #         "indexComponentName": "cs.vp.variants.apps.instance_wizard.index_component"
        #     }
        # ],
        "treeDownReferences": {
            "propertyTree": {
                type_urls["variant"]: {
                    "references": [
                        {
                            "id": "TopPropertyValues",
                            "viewName": "complete-target"
                        }
                    ],
                    "additionalContentReferences": []
                },
                type_urls["cdbvp_property_value"]: {
                    "references": [
                        {
                            "id": "SubPropertyValues",
                            "viewName": "complete-target"
                        }
                    ],
                    "additionalContentReferences": []
                }
            },
            "bomTree": {
                type_urls["part"]: {
                    "references": [
                        {
                            "id": "Components",
                            "viewName": "complete-bom-item-target",
                            "useContextParams": True
                        }
                    ],
                    "additionalContentReferences": []
                },
                type_urls["bom_item"]: {
                    "references": [
                        {
                            "id": "SelectionPredicates",
                            "viewName": "complete-target"
                        }
                    ],
                    "additionalContentReferences": [
                        {
                            "id": "Item",
                            "viewName": "complete-bom-item-target"
                        }
                    ]
                },
                type_urls["cdbvp_bom_predicate"]: {
                    "references": [],
                    "additionalContentReferences": []
                }
            }
        },
        "initial_data": initial_data(model, request)
    }

    return app_setup


@InstanceWizardApp.view(model=InstanceWizardModel, name="additional_head", internal=True)
def _additional_head(_model, _request):
    return "\n".join(['<link rel="shortcut icon" href="/static/imgid/branding_web_favicon.ico">',
                      '<link rel="icon" href="/static/imgid/branding_web_favicon.ico">',
                      '<link rel="apple-touch-icon" href="/static/imgid/branding_web_app_icon.png">'])


@InstanceWizardApp.view(model=InstanceWizardModel, name="document_title", internal=True)
def _item_title(model, _request):
    return cdbwrapc.getApplicationWndName(util.get_label("cdbvp_instantiate_max_bom"))


def initial_data(model, request):
    maxbom = Item.ByKeys(teilenummer=model.teilenummer, t_index=model.t_index)

    if model.variant is None:
        raise HTTPBadRequest()

    collection_app = get_v1(request).child("collection")
    property_value_app = collection_app.child(GenericApp, rest_name="cdbvp_property_value")
    variant_app = collection_app.child(GenericApp, rest_name="variant")
    part_app = collection_app.child(GenericApp, rest_name="part")

    relships = []
    top_level_target = make_relship_target(model.variant, "TopPropertyValues")
    relships.append(request.view(top_level_target, app=variant_app))

    for prop_val in model.variant.PropertyValues:
        target = make_relship_target(prop_val, "SubPropertyValues")
        prop_val_view = request.view(target, app=property_value_app)
        relships.append(prop_val_view)
    all_property_values = make_relship_target(model.variant, "PropertyValues")
    relships.append(request.view(all_property_values, app=variant_app, name="complete-target-with-status"))

    return dict(objects=([request.view(model.variant.Product, app=collection_app)] +
                         [request.view(maxbom, app=part_app, name='with-status')] +
                         [request.view(model.variant, app=variant_app, name='with-status')]),
                relships=relships)


@InstanceWizardApp.html(model=InstanceWizardModel, name="content", internal=True)
def _app_content(self, _request):
    """Return a root div for react to render into.
    """
    return '<div id="root"></div>'


# Exported objects
__all__ = []


# Guard importing as main module
if __name__ == "__main__":
    pass
