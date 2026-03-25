#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cs.classification import catalog, classes

LANGUAGE_CODES = [
    "cs",
    "de",
    "en",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "pl",
    "pt",
    "tr",
    "zh",
]


def map_multilingual_attribute(
    target_attribute_name, source_object, source_attribute_name, fallback_value=None
):
    result = {}
    try:
        source_values = source_object.GetLocalizedValues(source_attribute_name)
    except AttributeError:
        if fallback_value is not None:
            source_values = {each: None for each in LANGUAGE_CODES}
        else:
            raise

    for iso_code in LANGUAGE_CODES:
        target_key = "{0}_{1}".format(target_attribute_name, iso_code)
        source_value = source_values[iso_code]

        if fallback_value is not None and (source_value == "" or source_value is None):
            source_value = fallback_value

        result[target_key] = source_value

    return result


def is_old_property_alphanumeric(old_property):
    return old_property.data_type == "alphanumeric"


def is_old_property_numeric(old_property):
    return old_property.data_type == "numeric"


def is_old_property_boolean(old_property):
    return old_property.data_type == "boolean"


def get_property_catalog_class(old_property):
    if is_old_property_alphanumeric(old_property):
        return catalog.TextProperty
    elif is_old_property_numeric(old_property):
        return catalog.FloatProperty
    elif is_old_property_boolean(old_property):
        return catalog.BooleanProperty
    else:
        raise ValueError(
            "Not supported property data_type: {0}".format(old_property.data_type)
        )


def get_property_value_class(old_property):
    if is_old_property_alphanumeric(old_property):
        return catalog.TextPropertyValue
    elif is_old_property_numeric(old_property):
        return catalog.FloatPropertyValue
    elif is_old_property_boolean(old_property):
        return None
    else:
        raise ValueError(
            "Not supported property data_type: {0}".format(old_property.data_type)
        )


def get_property_class_class(old_property):
    if is_old_property_alphanumeric(old_property):
        return classes.TextClassProperty
    elif is_old_property_numeric(old_property):
        return classes.FloatClassProperty
    elif is_old_property_boolean(old_property):
        return classes.BooleanClassProperty
    else:
        raise ValueError(
            "Not supported property data_type: {0}".format(old_property.data_type)
        )
