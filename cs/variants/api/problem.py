# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module problem

Generate a problem for the constraints library from a variability model.
"""

import constraint

from cs.classification import util
from cs.classification.computations import (
    PropertyValueNotFoundException,
    PropertyValueNotSetException,
    property_codes_used_in_expression,
    replace_expression,
)
from cs.classification.validation import ClassificationValidator
from cs.variants import exceptions
from cs.variants.api.variants_classification import VariantsClassification
from cs.variants.classification_helper import (
    calculate_classification_value_checksum,
    get_property_entry_value,
    has_property_entry_none_value,
    make_classification_property_dict,
)

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def generate_problem(
    variability_model_or_view, presets=None, constrain_classification_checksum=None
):
    """
    Generate a problem, suitable for generating a solution space using a backtracking solver.

    :param variability_model_or_view: The variability model or a view in a variability model
    :type variability_model_or_view: cs.variants.VariabilityModel or cs.variants.VariantsView

    :param presets: Used to set the value of some variables to some fixed value.
                    Must be a dictionary of the form `{<PROPERTY CODE>: <VALUE>}`.
    :type presets: dict of (str, str or int or float)

    :param constrain_classification_checksum: Used to constrain the solution.
                                 The solution will not contain equal property combination,
                                 which lead to the same checksum.
    :type constrain_classification_checksum: list of str

    :raises cs.variants.exceptions.InvalidPresets: If an invalid preset is given, because
        the property value does not exist in the solution space, this exception is raised.

    :raises cs.variants.exceptions.InvalidPropertyCodes: If an invalid preset is given, because
        the property code is not contained in the classification classes, this exception is raised.
    """

    if presets is None:
        presets = {}

    problem = constraint.Problem()

    class_codes = {variability_model_or_view.class_code}

    variants_classification = VariantsClassification(class_codes)
    props = variants_classification.get_variant_driving_properties()
    for prop_code in presets:
        if prop_code not in props:
            raise exceptions.InvalidPropertyCode(prop_code)

    all_catalog_values = variants_classification.get_catalog_values()

    empty_property_values = variants_classification.get_property_values()

    for property_code, prop in props.items():
        property_type = prop["type"]
        values = []
        if property_type == "boolean":
            # special treatment for boolean properties, because they don't have catalog values
            # but should be added as variable anyway
            values = [
                make_classification_property_dict(
                    property_code, True, empty_property_values
                ),
                make_classification_property_dict(
                    property_code, False, empty_property_values
                ),
            ]
        elif property_type in ("block", "multilang"):
            # blocks and multilang currently not supported
            pass
        else:
            if property_code in all_catalog_values:
                catalog_values = all_catalog_values[property_code]
                values = [
                    make_classification_property_dict(
                        property_code,
                        catalog_value["value"],
                        empty_property_values,
                        label=catalog_value["label"],
                        description=catalog_value["description"],
                    )
                    for catalog_value in catalog_values
                ]

            # Property is not enum only
            if prop["flags"][4] == 0:
                values.append(empty_property_values[property_code])

        if values:
            values = adapt_values_to_presets(presets, property_code, values)
            problem.addVariable(property_code, values)

    all_class_codes = variants_classification.get_all_class_codes()
    if ClassificationValidator.has_constraints(all_class_codes):
        problem.addConstraint(ClassConstraint(all_class_codes))

    if constrain_classification_checksum is not None:
        problem.addConstraint(
            ClassificationChecksumConstraint(constrain_classification_checksum)
        )
    return problem


def adapt_values_to_presets(presets, property_code, values):
    if property_code in presets:
        # No multiple allowed to hard code to index 0
        preset_value = presets[property_code][0]

        # Ignoring none in presets for filtering!
        if not has_property_entry_none_value(preset_value):
            found_catalog_entry = False
            for property_entry in values:
                if util.are_property_values_equal(
                    preset_value["property_type"],
                    preset_value["value"],
                    # Multiple not support so hard code to index 0
                    property_entry[0]["value"],
                ):
                    values = [property_entry]
                    found_catalog_entry = True
                    break

            if not found_catalog_entry:
                raise exceptions.InvalidPresets(property_code, presets[property_code])
    return values


class ExpressionCacheEntry:
    def __init__(self, expression):
        self.code = None
        self.properties = None

        self.prepare_expression(expression)

    def prepare_expression(self, expression):
        self.properties = property_codes_used_in_expression(expression)

        eval_expression = replace_expression(expression)
        self.code = compile(eval_expression, "<string>", "eval")

    def prepare_properties(
        self, properties, evaluate_with_none_values, replace_with_empty_strings
    ):
        property_values = {}
        for each_code in self.properties:
            try:
                # cs.variants does not support multivalued properties so hardcode to 0
                try:
                    property_entry = properties[each_code][0]
                except KeyError as exc:
                    raise PropertyValueNotFoundException(each_code, "") from exc

                property_values[each_code] = get_property_entry_value(
                    property_entry,
                    use_float_normalized=True,
                    allow_none_values=evaluate_with_none_values,
                    replace_with_empty_strings=replace_with_empty_strings,
                )
            except ValueError as exc:
                # Provide here an empty string for index string because we dont have one
                raise PropertyValueNotSetException(each_code, "") from exc

        return property_values

    def eval(self, properties, evaluate_with_none_values, replace_with_empty_strings):
        property_values = self.prepare_properties(
            properties, evaluate_with_none_values, replace_with_empty_strings
        )

        result = eval(self.code, property_values)  # nosec
        return result


class ClassificationExpressionCacheEvaluator:
    def __init__(self):
        self.expression_cache = {}

    def prepare_expression(self, expression):
        entry = ExpressionCacheEntry(expression)
        self.expression_cache[expression] = entry
        return entry

    def __call__(
        self,
        expression,
        properties,
        evaluate_with_none_values,
        replace_with_empty_strings,
    ):
        try:
            expression_entry = self.expression_cache[expression]
        except KeyError:
            expression_entry = self.prepare_expression(expression)

        return expression_entry.eval(
            properties, evaluate_with_none_values, replace_with_empty_strings
        )


class ClassConstraint(constraint.Constraint):
    def __init__(self, class_codes):
        super().__init__()
        self.class_codes = class_codes
        self.evaluator = ClassificationExpressionCacheEvaluator()

    # noinspection PyProtectedMember
    # pylint: disable=protected-access
    def do_constraints_exist(self):
        ClassificationValidator._load_constraints()

        for each_code in self.class_codes:
            if ClassificationValidator._constraints_by_class_code[each_code]:
                return True

        return False

    def __call__(
        self, variables, domains, assignments, forwardcheck=False, ignore_errors=True
    ):
        error_messages = ClassificationValidator.check_constraints(
            self.class_codes,
            assignments,
            skip_after_failure=True,
            # with this parameter constraint are ignored if not all variables are set
            # this allows for pruning the solution space on partial solutions
            ignore_errors=ignore_errors,
            expression_evaluator=self.evaluator,
        )
        return len(error_messages) == 0


class ClassificationChecksumConstraint(constraint.Constraint):
    def __init__(self, classification_checksums):
        super().__init__()
        self._classification_checksums = set(classification_checksums)
        self.last_checksum = None

    def preProcess(self, variables, domains, constraints, vconstraints):
        # The default behaviour will skip this constraint for one variable,
        # but we need to make sure it gets called to give correct checksums back
        pass

    def __call__(self, variables, domains, assignments, forwardcheck=False):
        self.last_checksum = calculate_classification_value_checksum(assignments)
        return self.last_checksum not in self._classification_checksums
