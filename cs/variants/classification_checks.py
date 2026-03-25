# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from collections import defaultdict

from cdb import ue
from cs.classification import api as classification_api
from cs.classification import util as classification_util
from cs.variants.classification_helper import (
    ensure_existence_of_float_normalize,
    is_part_classification_available,
)


class UeExceptionChangedPropertiesBasedOnNewestInstancedItem(ue.Exception):
    def __init__(self, not_allowed_changed_properties_based_on_newest_instanced_item):
        super().__init__(
            "cs_variants_not_allowed_to_change_classification_property",
            " - "
            + "\n - ".join(
                not_allowed_changed_properties_based_on_newest_instanced_item
            ),
        )


class UeExceptionChangedPropertiesNotAllowedOnItem(ue.Exception):
    def __init__(self, not_allowed_changed_properties):
        super().__init__(
            "cs_variants_not_allowed_to_change_classification_property_item",
            " - " + "\n - ".join(not_allowed_changed_properties),
        )


class UeExceptionForDuplicateVariants(ue.Exception):
    def __init__(self, msg):
        super().__init__("cs_variant_duplicate_characteristics", msg)


class UeExceptionNotAllowedToDelete(ue.Exception):
    def __init__(self, classification_class):
        super().__init__(
            "cs_variants_not_allowed_to_delete_variability_class",
            "{name} ({code})".format(
                name=classification_class.name, code=classification_class.code
            ),
        )


class DuplicateCounter:
    def __init__(self):
        self.check_count = 0
        self.duplicate_count = defaultdict(int)
        self.error_msg_mapping = []

    def increase_check_count(self):
        self.check_count += 1

    def increase_duplicate_count(self, index):
        self.duplicate_count[index] += 1

    def assign_variant_msg(self, variant):
        self.error_msg_mapping.append("{0} {1}".format(variant["id"], variant["name"]))

    def get_duplicate_error_msg(self):
        for each_key, each_value in self.duplicate_count.items():
            if each_value == self.check_count:
                return self.error_msg_mapping[each_key]

        return None


class VariantVariabilityClassificationClassChecker:
    def __init__(self, variant, variants_classification):
        self.variant = variant
        self.variants_classification = variants_classification

        self.not_allowed_changed_properties_based_on_newest_instanced_item = []
        self.newest_instanced_item_properties = (
            self._get_newest_instanced_item_properties()
        )

        self.duplicate_counter = DuplicateCounter()
        self.classification_property_entries_of_all_other_variants = (
            self._get_classification_property_entries_of_all_other_variants()
        )

    def _get_classification_property_entries_of_all_other_variants(self):
        all_variants = self.variants_classification.get_variants_classification(
            self.variant.VariabilityModel
        )
        variant_cdb_object_id = self.variant.cdb_object_id

        result = defaultdict(list)
        for each in all_variants:
            if each["variant"]["cdb_object_id"] == variant_cdb_object_id:
                continue

            self.duplicate_counter.assign_variant_msg(each["variant"])
            classification_data = each["classification"]
            for (
                classification_code,
                classification_entries,
            ) in classification_data.items():
                # No multiple allowed for variant driving so hard code to index 0
                result[classification_code].append(classification_entries[0])

        return result

    def _get_newest_instanced_item_properties(self):
        newest_instanced_item = self.variant.get_newest_instanced_item()
        if newest_instanced_item is None:
            return None

        if is_part_classification_available():
            return classification_api.get_classification(
                newest_instanced_item, pad_missing_properties=False, narrowed=False
            )["properties"]
        else:
            # No part classification but there are instanced parts.
            # To trigger checks that only non set classification attributes are allowed
            # to change on variant. We have to return something different than None.
            return {}

    def check(self, property_definition, diff_property_entry):
        # Every change is allowed in variants without instanced items
        if self.newest_instanced_item_properties is not None:
            self.check_based_on_newest_instanced_item(
                property_definition, diff_property_entry
            )

        self.check_for_duplicate_variants(property_definition, diff_property_entry)

    def check_for_duplicate_variants(self, property_definition, diff_property_entry):
        classification_entries = (
            self.classification_property_entries_of_all_other_variants[
                property_definition["code"]
            ]
        )
        for index, each in enumerate(classification_entries):
            prop_type = diff_property_entry["property_type"]
            val_a = each["value"]
            val_b = diff_property_entry["value"]
            equal = classification_util.are_property_values_equal(
                prop_type, val_a, val_b
            )

            if equal:
                self.duplicate_counter.increase_duplicate_count(index)

        self.duplicate_counter.increase_check_count()

    def check_based_on_newest_instanced_item(
        self, property_definition, diff_property_entry
    ):
        """
            check if the value is changeable

            this function collect all properties which are not changeable.

            if part classification is not available change is only allowed
            when the prop has never had a value.
            This means:
                - old_value in diff is None
                - old_value not in diff

            otherwise changing the value is denied


        :   if part classification is available changes is allowed
            when the prop is not used in any instantiated part

            :param property_definition:
            :param diff_property_entry:
            :return:
        """
        property_code = property_definition["code"]

        if not is_part_classification_available():
            # this is the first time this value is changed
            if (
                "old_value" in diff_property_entry
                and diff_property_entry["old_value"] is None
            ):
                return

            # no diff -> no change
            if "old_value" not in diff_property_entry:
                return

            self.not_allowed_changed_properties_based_on_newest_instanced_item.append(
                "{name} ({code})".format(**property_definition)
            )
            return

        if property_code not in self.newest_instanced_item_properties:
            return

        # Because variant driving properties are not to be allowed to be multi valued => just compare index 0
        newest_item_property_value = self.newest_instanced_item_properties[
            property_code
        ][0]

        if not classification_util.are_property_values_equal(
            newest_item_property_value["property_type"],
            newest_item_property_value["value"],
            diff_property_entry["value"],
        ):
            self.not_allowed_changed_properties_based_on_newest_instanced_item.append(
                "{name} ({code})".format(**property_definition)
            )

    def raise_ue_exception_if_checks_failed(self):
        self._raise_ue_exception_changed_properties_based_on_newest_instanced_item()
        self._raise_ue_exception_for_duplicate_variants()

    def _raise_ue_exception_for_duplicate_variants(self):
        error_msg = self.duplicate_counter.get_duplicate_error_msg()
        if error_msg is not None:
            raise UeExceptionForDuplicateVariants(error_msg)

    def _raise_ue_exception_changed_properties_based_on_newest_instanced_item(self):
        if self.not_allowed_changed_properties_based_on_newest_instanced_item:
            raise UeExceptionChangedPropertiesBasedOnNewestInstancedItem(
                self.not_allowed_changed_properties_based_on_newest_instanced_item
            )


def check_for_not_allowed_variability_classification_class_deletion(
    classification_class, classification_diff_data
):
    if classification_class.code in classification_diff_data["deleted_classes"]:
        raise UeExceptionNotAllowedToDelete(classification_class)


def is_variability_classification_class_affected(
    classification_class, classification_diff_data
):
    return (
        classification_class.code in classification_diff_data["assigned_classes"]
        or classification_class.code in classification_diff_data["new_classes"]
    )


def get_all_variant_driving_properties_from_classification_diff_data(
    variants_classification, classification_diff_data
):
    all_variant_driven_properties = (
        variants_classification.get_variant_driving_properties()
    )

    classification_diff_data_properties = classification_diff_data["properties"]
    ensure_existence_of_float_normalize(classification_diff_data_properties)

    for (
        variant_driven_property_code,
        variant_driven_property,
    ) in all_variant_driven_properties.items():
        if variant_driven_property_code in classification_diff_data_properties:
            # Because variant driving properties are not allowed to be multi valued => just index 0
            yield variant_driven_property, classification_diff_data_properties[
                variant_driven_property_code
            ][0]
