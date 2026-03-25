# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Utilities to retrieve classification information from variant objects
"""
from cs.classification import api as classification_api
from cs.classification import classes as classification_classes
from cs.classification import classification_data
from cs.classification import util as classification_util
from cs.variants import (
    VARIANT_DRIVING_FLAG_INDEX,
    VARIANT_STATUS_INVALID,
    VARIANT_STATUS_OK,
)

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ["VariantsClassification"]


class VariantsClassification:
    """
    Utility class to to deal with classification data.
    """

    def __init__(self, class_codes=None):
        """
        Create instance for given classification class codes.
        """
        self._class_codes = set(class_codes) if class_codes else set()
        self._classification_data = None
        self._catalog_values = None
        self._properties_by_class = None
        self._variant_driving_properties = None

    def get_all_class_codes(self):
        """
        Returns all class codes including base class codes.
        """
        return classification_classes.ClassificationClass.get_base_class_codes(
            class_codes=self._class_codes, include_given=True
        )

    def get_catalog_values(self):
        """
        Returns sorted and unique catalog values for all variant driving properties of given classes.
        """
        if self._catalog_values:
            return self._catalog_values

        self._catalog_values = classification_api.get_all_catalog_values(
            self._class_codes,
            active_only=True,
            for_variants=True,
            with_normalized_values=True,
        )

        for prop_code, property_values in self._catalog_values.items():
            if not property_values:
                continue
            # make values unique
            values = set()
            unique_property_values = []
            for property_value in property_values:
                is_unique = True
                if property_value["type"] == "float":
                    value = property_value["value"]["float_value_normalized"]
                    for float_value in values:
                        if classification_util.isclose(value, float_value):
                            is_unique = False
                            break
                else:
                    value = property_value["value"]
                    is_unique = value not in values
                if is_unique:
                    values.add(value)
                    unique_property_values.append(property_value)

            # sort by float_value_normalized
            if unique_property_values[0]["type"] == "float":

                def sort_func(entry):
                    return (
                        entry["pos"],
                        entry["value"]["float_value_normalized"],
                    )

                unique_property_values = sorted(unique_property_values, key=sort_func)

            self._catalog_values[prop_code] = unique_property_values

        return self._catalog_values

    def get_classification_data(self):
        """
        Returns empty classification data including metadata.
        """
        if not self._classification_data:
            self._classification_data = classification_api.get_new_classification(
                self._class_codes, narrowed=False
            )
        return self._classification_data

    def get_property_values(self):
        """
        Returns property value data structure.
        """
        return self.get_classification_data()["properties"]

    def get_variant_driving_properties_by_class(self):
        """
        Returns a ordered property list by class.
        """
        if self._properties_by_class:
            return self._properties_by_class
        self._properties_by_class = {}
        for class_code in self._class_codes:
            if len(self._class_codes) == 1:
                classification_data = self.get_classification_data()
            else:
                # necessary to compute the correct classes_view for each class
                classification_data = classification_api.get_new_classification(
                    [class_code], narrowed=False
                )
            classes = classification_data["metadata"]["classes"]
            class_props = []
            for clazz_code in classification_data["metadata"]["classes_view"]:
                class_obj = classes[clazz_code]
                for group in class_obj["property_groups"]:
                    for prop_ref in group["properties"]:
                        prop = classes[prop_ref["class_code"]]["properties"][
                            prop_ref["prop_code"]
                        ]
                        # Enrich prop with class code so that variant filter
                        # can render "PropertyValue" Controls correct
                        prop["class_code"] = prop_ref["class_code"]
                        if prop["flags"][VARIANT_DRIVING_FLAG_INDEX]:
                            class_props.append(prop)
            self._properties_by_class[class_code] = class_props
        return self._properties_by_class

    def get_variant_driving_properties(self):
        """
        Returns all variant driving properties of given classes in a map by property code.
        """
        if self._variant_driving_properties:
            return self._variant_driving_properties

        self._variant_driving_properties = {}
        for _, clazz in self.get_classification_data()["metadata"]["classes"].items():
            for prop_code, prop in clazz["properties"].items():
                if prop["flags"][VARIANT_DRIVING_FLAG_INDEX] == 1:
                    self._variant_driving_properties[prop_code] = prop
        return self._variant_driving_properties

    # pylint: disable=too-many-locals
    def get_variants_classification(
        self, variability_model, evaluate_status=True, add_enum_labels=False
    ):
        """
        Retrieve the classification of the variant objects in the variability model.
        Returns

            .. code-block:: python

                {
                    "variant": "<cs.variants.Variant object>",
                    "classification": {"<PROPERTY_CODE>": ["<PROPERTY_VALUE>"]},
                }

            :param variability_model: Variability model
            :param evaluate_status: Should the status of the variants be evaluated
            :param add_enum_labels: Adds enum labels for the variant driven properties [default: False]
        """

        from cs.variants.api import problem

        class_constraint = problem.ClassConstraint(self.get_all_class_codes())

        result = []
        variant_objects = variability_model.Variants
        variant_obj_ids = [
            variant_object.cdb_object_id for variant_object in variant_objects
        ]

        if not variant_objects:
            return result

        # private method of classification is used by intention because of performance reasons.
        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        property_values, _ = classification_data.ClassificationData._load_data(
            variant_obj_ids,
            ["cs_variant"],
            narrowed=False,
            request=None,
            calc_checksums=False,
        )

        if add_enum_labels:
            variant_driving_text_prop_codes = [
                each_key
                for each_key, each_value in self.get_variant_driving_properties().items()
                if each_value["type"] == "text"
            ]
            enum_values_by_prop_code = classification_util.get_enum_values_with_labels(
                variant_driving_text_prop_codes
            )
        else:
            enum_values_by_prop_code = {}

        for variant_object, variant_property_values in zip(
            variant_objects, property_values
        ):
            variant_classification = {}
            variant_result_data = {
                "variant": variant_object,
                "classification": variant_classification,
            }

            for prop_code, prop in self.get_variant_driving_properties().items():
                property_value = variant_property_values.get(prop_code)
                if property_value:
                    variant_classification[prop_code] = property_value
                else:
                    if prop["type"] == "float":
                        none_value = {
                            "float_value": None,
                            "float_value_normalized": None,
                            "unit_object_id": prop["default_unit_object_id"],
                            "unit_label": prop["default_unit_symbol"],
                        }
                    else:
                        none_value = None
                    variant_classification[prop_code] = [
                        {
                            "property_type": prop["type"],
                            "value": none_value,
                            "id": None,
                            "value_path": prop_code,
                        }
                    ]

            if evaluate_status:
                if class_constraint(
                    None, {}, variant_classification, ignore_errors=False
                ):
                    variant_status = VARIANT_STATUS_OK
                else:
                    variant_status = VARIANT_STATUS_INVALID

                variant_result_data["status"] = variant_status

            if add_enum_labels:
                classification_util.add_enum_labels(
                    variant_classification, enum_values_by_prop_code
                )

            result.append(variant_result_data)

        result.sort(
            key=lambda variant: (
                # valid variants should come first
                0
                if variant.get("status", VARIANT_STATUS_OK) == VARIANT_STATUS_OK
                else 1,
                # variants with the same status should be sorted according to their ids
                variant["variant"].id,
            )
        )

        return result
