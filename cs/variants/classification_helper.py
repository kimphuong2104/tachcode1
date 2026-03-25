# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: python_template 4042 2019-08-27 07:30:13Z js $"

import datetime
import hashlib
import json

from cdb import ElementsError, typeconversion
from cs.classification import prepare_write
from cs.classification.object_classification import ClassificationUpdater
from cs.classification.util import are_property_values_equal


def add_catalog_value_label_and_description_to_property_entry(
    property_entry, label=None, description=None
):
    additional_value = {}
    if label is not None and label != "":
        additional_value["label"] = label
    if description is not None and description != "":
        additional_value["description"] = description

    if additional_value:
        property_entry["addtl_value"] = additional_value


def make_classification_property_dict(
    prop_code, prop_value, empty_property_values, label=None, description=None
):
    # THINK ABOUT: what do we do about multiple classification?
    property_value = dict(empty_property_values[prop_code][0])
    property_value["value"] = prop_value

    add_catalog_value_label_and_description_to_property_entry(
        property_value, label=label, description=description
    )

    return [property_value]


def has_property_entry_none_value(entry):
    return get_property_entry_value(entry) is None


def get_property_entry_value(
    entry,
    use_float_normalized=False,
    allow_none_values=True,
    replace_with_empty_strings=False,
    entry_type_key="property_type",
):
    property_type = entry[entry_type_key]
    if property_type == "float":
        if use_float_normalized:
            result = entry["value"]["float_value_normalized"]
        else:
            result = entry["value"]["float_value"]
    else:
        result = entry["value"]

    if result is None:
        if property_type == "text" and replace_with_empty_strings:
            return ""
        if not allow_none_values:
            raise ValueError("Entry is None. {0}".format(entry))

    return result


def is_variant_classification_data_equal(data_left, data_right):
    for data_left_key, data_left_entries in data_left.items():
        if data_left_key not in data_right:
            return False

        # variant classification does not allow multi valued so hard code to index 0
        data_left_entry = data_left_entries[0]
        data_right_entry = data_right[data_left_key][0]

        if not are_property_values_equal(
            data_left_entry["property_type"],
            data_left_entry["value"],
            data_right_entry["value"],
        ):
            return False

    return True


def calculate_classification_value_checksum(classification_data):
    def date_to_str(dt):
        if isinstance(dt, datetime.date):
            return typeconversion.to_legacy_date_format(dt)
        return dt

    # No security check because its not relevant its just a checksum
    hash_obj = hashlib.md5()  # nosec
    sorted_property_codes = sorted(classification_data.keys())

    for code in sorted_property_codes:
        property_entries = sorted(classification_data[code], key=lambda v: v["id"])

        for property_entry in property_entries:
            hash_obj.update(
                json.dumps(
                    property_entry["value"], default=date_to_str, sort_keys=True
                ).encode("utf-8")
            )

    return hash_obj.hexdigest()


def ensure_existence_of_float_normalize(property_values):
    ClassificationUpdater(None).calculate_normalized_float_values(property_values)


def is_part_classification_available():
    """checks if part classification is available

    :return: True if available False if not
    """
    try:
        prepare_write("part")
    except ElementsError:
        return False
    return True
