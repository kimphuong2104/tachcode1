# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import collections

import cdbwrapc
from cs.classification.rest import utils as classification_rest_utils
from cs.platform.web.rest.support import get_restlink
from cs.variants.web.util import view_rest_objects
from cs.web.components.ui_support import forms

COMPONENT_NAME = "cs-variants-web-common"
VERSION = "15.1.1"


def update_app_setup(request, app_setup, product=None, variability_models=None):
    from cs.variants.api import VariantsClassification

    def get_classnames(classname):
        classdef = cdbwrapc.CDBClassDef(classname)
        result = [classname]
        result.extend(classdef.getSubClassNames(True))
        return result

    rest_objects = set()
    if product is not None:
        rest_objects.add(product)

    if variability_models is None:
        variability_models = product.VariabilityModels
    rest_objects.update(variability_models)

    variability_models_by_link = {}
    for variability_model in variability_models:
        variability_models_by_link[
            get_restlink(variability_model, request=request)
        ] = variability_model

    variability_model_maxboms = collections.defaultdict(list)
    for variability_link, variability_model in variability_models_by_link.items():
        for maxbom in variability_model.MaxBOMs:
            rest_objects.add(maxbom)
            variability_model_maxboms[variability_link].append(
                get_restlink(maxbom, request=request)
            )

    classnames = {
        base_classname: get_classnames(base_classname)
        for base_classname in ["part", "bom_item", "bom_item_occurrence"]
    }

    app_setup[COMPONENT_NAME] = {
        "classnames": classnames,
        "variability_models": list(variability_models_by_link),
        "variability_model_maxboms": variability_model_maxboms,
        "rest_objects": view_rest_objects(request, rest_objects),
        "catalog_config_cs_variants": forms.FormInfoBase.get_catalog_config(
            request, "cs_variants", is_combobox=False, as_objs=False
        ),
    }

    if product is not None:
        app_setup[COMPONENT_NAME]["product"] = get_restlink(product, request=request)

    if variability_models is not None:
        class_codes = [
            variability_model.class_code for variability_model in variability_models
        ]

        variants_classification = VariantsClassification(class_codes)
        properties_by_class = (
            variants_classification.get_variant_driving_properties_by_class()
        )
        app_setup[COMPONENT_NAME][
            "property_definitions"
        ] = classification_rest_utils.ensure_json_serialiability(properties_by_class)
