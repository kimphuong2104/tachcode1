# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import imp
import os

from cs.vp import variants


def import_common(package):
    from cdb.comparch.packages import get_package_dir
    path = os.path.join(
        get_package_dir(package), "tests", "accepttests", "steps")
    return imp.load_source(
        package + ".common", os.path.join(path, "common.py"))


common = import_common("cs.vp")


def _create_product_properties(product):
    props = []
    for t in variants.properties.PropertyTypeCatalog().getCatalogEntries():
        props.append(common.generateProductProperty(product, user_input={
            "data_type": t,
            "name_de": "Test property %s" % t,
        }))
    return props


def _create_enum_values(product, props):
    for p in props:
        if p.data_type == "boolean":
            # enum values are generated automatically for boolean
            continue
        val = _get_value(p)
        common.generateProductPropertyValue(p, preset={
            "value_txt_de": val,
            "value_txt_en": val,
            "name": val,
            "value": 3,
        })


def _get_value(prop):
    if prop.data_type == "alphanumeric":
        return "Hello world"
    elif prop.data_type == "numeric":
        return 42
    else:
        return 1


def _get_property_map(product):
    return {
        prop.id: prop.EnumValues[0].value for prop in product.Properties
    }


def generateProductWithEnumValues(product_code="GENERATED_PRODUCT"):
    product = common.generateProduct({
        "code": product_code,
    })

    props = _create_product_properties(product)
    _create_enum_values(product, props)

    product.Reload()
    return product


def generateVariantForProduct(product):
    property_map = _get_property_map(product)

    return variants.ProductVariant.CreateVariant(property_map, product.cdb_object_id)