#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cdb import sqlapi
from cs.classification import api as classification_api
from cs.classification import computations
from cs.variants.exceptions import SelectionConditionEvaluationError
from cs.variants.selection_condition import get_expression_long


class NotSetSelectionConditionEvaluatorOption:
    pass


class SelectionConditionsExpressionLookup:
    def __init__(self, selection_condition_query_context):
        self.selection_condition_query_context = selection_condition_query_context
        self.data = {}

    def build(self):
        selection_condition_table = sqlapi.SQLselect(
            "ref_object_id, expression, cdb_object_id "
            "FROM cs_selection_condition "
            "WHERE {0}".format(
                " and ".join(
                    [
                        "{0}='{1}'".format(
                            sqlapi.quote(each_key), sqlapi.quote(each_value)
                        )
                        for each_key, each_value in self.selection_condition_query_context.items()
                    ]
                )
            )
        )

        for i in range(sqlapi.SQLrows(selection_condition_table)):
            ref_object_id = sqlapi.SQLstring(selection_condition_table, 0, i)
            selection_condition_cdb_object_id = sqlapi.SQLstring(
                selection_condition_table, 2, i
            )

            selection_condition_expression = sqlapi.SQLstring(
                selection_condition_table, 1, i
            )
            if selection_condition_expression == "":
                selection_condition_expression = get_expression_long(
                    selection_condition_cdb_object_id
                )

            self.data[ref_object_id] = (
                selection_condition_cdb_object_id,
                selection_condition_expression,
            )

    def __getitem__(self, ref_object_id):
        return self.get_expression(ref_object_id)

    def __iter__(self):
        return self.data.__iter__()

    def __contains__(self, item):
        return self.data.__contains__(item)

    def get_cdb_object_id(self, ref_object_id):
        return self.data[ref_object_id][0]

    def get_expression(self, ref_object_id):
        return self.data[ref_object_id][1]


class SelectionConditionEvaluator:
    def __init__(
        self,
        cdb_object_id=NotSetSelectionConditionEvaluatorOption,
        variability_model_id=NotSetSelectionConditionEvaluatorOption,
        ref_object_id=NotSetSelectionConditionEvaluatorOption,
        properties=None,
    ):
        self.properties = properties

        selection_condition_query_context = {
            each_key: each_value
            for each_key, each_value in {
                "cdb_object_id": cdb_object_id,
                "variability_model_id": variability_model_id,
                "ref_object_id": ref_object_id,
            }.items()
            if each_value is not NotSetSelectionConditionEvaluatorOption
        }

        self.selection_conditions_lookup = SelectionConditionsExpressionLookup(
            selection_condition_query_context
        )
        self.selection_conditions_lookup.build()

    def __call__(
        self,
        ref_object=None,
        ref_object_id=None,
        properties=None,
        ignore_not_found_selection_condition=False,
        ignore_not_set_properties=False,
    ):
        if properties is None:
            if self.properties is None:
                raise SelectionConditionEvaluationError(
                    "No properties provided to evaluate selection condition",
                    ref_object_id=ref_object_id,
                )

            properties = self.properties

        if ref_object_id is None:
            if ref_object is None:
                raise SelectionConditionEvaluationError(
                    "A ref_object_id or a ref_object needs to be provided",
                    ref_object_id=ref_object_id,
                    properties=properties,
                )

            ref_object_id = ref_object["cdb_object_id"]

        try:
            selection_condition_expression = self.selection_conditions_lookup[
                ref_object_id
            ]
        except KeyError as exc:
            if ignore_not_found_selection_condition:
                return True
            else:
                raise SelectionConditionEvaluationError(
                    "No selection condition found for ref object",
                    ref_object_id=ref_object_id,
                    properties=properties,
                ) from exc

        try:
            return evaluate_selection_condition_expression(
                selection_condition_expression,
                properties,
                ignore_not_set_properties=ignore_not_set_properties,
            )
        except Exception as ex:
            raise SelectionConditionEvaluationError(
                str(ex),
                ref_object_id=ref_object_id,
                properties=properties,
                selection_condition_cdb_object_id=self.selection_conditions_lookup.get_cdb_object_id(
                    ref_object_id
                ),
            ) from ex  # noqa: E999

    def has_selection_condition(self, bom_item):
        return bom_item["cdb_object_id"] in self.selection_conditions_lookup


def evaluate_selection_condition_expression(
    expression, properties, ignore_not_set_properties=False
):
    try:
        if computations.evaluate_expression(
            expression,
            properties,
            False,  # evaluate_with_none_values
            False,  # replace_with_empty_strings
        ):
            return True
        return False
    except (
        computations.PropertyValueNotFoundException,
        computations.PropertyValueNotSetException,
    ):
        if ignore_not_set_properties:
            return True
        else:
            raise


def evaluate_selection_condition_with_properties(
    selection_condition, properties, ignore_not_set_properties=False
):
    """
    Evaluate the expression of an selection condition with the given properties

    :param selection_condition: selection condition object
    :param properties: classification properties structure
    :param ignore_not_set_properties: Ignore not set and not found properties which yield to True in this case
    :return: Expression result
    """
    if selection_condition is None:
        raise ValueError("Need to provide a selection condition")

    return evaluate_selection_condition_expression(
        selection_condition.get_expression(),
        properties,
        ignore_not_set_properties=ignore_not_set_properties,
    )


def evaluate_selection_condition_with_variant(
    selection_condition, variant, ignore_not_set_properties=False
):
    """
    Evaluate the expression of an selection condition with the properties of the given variant

    :param selection_condition: selection condition object
    :param variant: variant object
    :param ignore_not_set_properties: Ignore not set and not found properties which yield to True in this case
    :return: Expression result
    """
    # Need normalized floats so no narrow
    properties = classification_api.get_classification(variant, narrowed=False)[
        "properties"
    ]
    return evaluate_selection_condition_with_properties(
        selection_condition,
        properties,
        ignore_not_set_properties=ignore_not_set_properties,
    )


def matches(bom_position, *variants):
    """
    Evaluates the given variants on the given bom position.

    :param bom_position: The bom position on which the variants are evaluated
    :type bom_position: cs.vp.bom.AssemblyComponent

    :param variants: The variants to be evaluated
    :type variants: List of cs.variants.Variant or property dictionaries

    :return: A list with the evaluation results, one of each variant in the given order.
    """
    selection_conditions_lookup = {
        each.variability_model_id: each for each in bom_position.SelectionConditions
    }
    result = [
        evaluate_selection_condition_with_variant(
            selection_conditions_lookup[variant.VariabilityModel.cdb_object_id], variant
        )
        for variant in variants
    ]
    return result


def match(bom_position, variant):
    """
    Evaluates one variants on the given bom position.

    :param bom_position: The bom position on which the variants are evaluated
    :type bom_position: cs.vp.bom.AssemblyComponent

    :param variant: The variant to be evaluated
    :type variant: cs.variants.Variant or property dictionaries

    :return: The evaluation result as a boolean
    """
    (result,) = matches(bom_position, variant)
    return result
