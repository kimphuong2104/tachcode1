# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Utilities for api
"""
from cdb import constants, sqlapi, util
from cdb.objects import operations
from cs.classification import api as classification_api
from cs.variants.api.constants_api import CLASSIFICATION_FLAG_FOR_INSTANTIATOR
from cs.variants.classification_helper import is_part_classification_available

# This value is used while testing.
# Do not set this manually!
REUSE_ENABLED = None


def is_reuse_enabled():
    """
    checks if property "vmr" (resue) is enabled
    :return: True if enabled, False if not, default True
    """
    if REUSE_ENABLED is not None:
        return REUSE_ENABLED
    prop = util.get_prop("vmr")
    if prop:
        return prop.lower() == "true"
    return True


def copy_variant_classification(variant, instance):
    """
    copies the variant classification to the part (instance)

    this checks also for part classification. If the part classification is not
    available then nothing is copied.

    :param variant: cs.variants.Variant
    :param instance: cs.vp.items.Item
    :return:
    """
    if not is_part_classification_available():
        return

    variant_classification = classification_api.get_classification(variant)
    property_values = variant_classification["properties"]

    classification_data = classification_api.get_classification(instance)

    classification_data = classification_api.rebuild_classification(
        classification_data, [variant.VariabilityModel.class_code]
    )
    for prop_code, values in property_values.items():
        classification_data["properties"][prop_code] = values

    classification_data[CLASSIFICATION_FLAG_FOR_INSTANTIATOR] = True

    classification_api.update_classification(instance, classification_data)


def delete_with_operation(obj_to_delete):
    """
    delete the `obj_to_delete` object with operation
    :param obj_to_delete: object to delete
    :return:
    """
    operations.operation(constants.kOperationDelete, obj_to_delete)


def count_part_used_in_bom_items(teilenummer, t_index):
    """
    return the number of usages in bom_items for the given part

    :param teilenummer: teilenummer
    :param t_index: t_index
    :return: the number of usages in bom_items
    rtype: int
    """
    query = f"""count(*) from einzelteile
            WHERE teilenummer='{teilenummer}'
            AND (t_index='{t_index}' OR is_imprecise=1)"""

    result = sqlapi.SQLselect(query)
    n = sqlapi.SQLinteger(result, 0, 0)
    return n
