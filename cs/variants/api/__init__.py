# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module api

This is the documentation for the api module.
"""
import logging

from cdb import constants, transactions, util
from cdb.objects import operations
from cs.classification import ObjectClassification
from cs.classification import api as classification_api
from cs.classification import constraints
from cs.classification import util as classification_util
from cs.classification.validation import ClassificationValidator
from cs.variants import VariantPart, calculate_classification_value_checksum, exceptions
from cs.variants.api import helpers
from cs.variants.api.constants_api import MAX_LIMIT_VARIANT_EDITOR_TABLE
from cs.variants.api.instantiate import (
    build_instance,
    make_indexed_instance,
    make_root_instance,
    rebuild_instance,
)
from cs.variants.api.instantiate_lookup import InstantiateLookup
from cs.variants.api.problem import ClassificationChecksumConstraint, generate_problem
from cs.variants.api.variants_classification import VariantsClassification
from cs.variants.exceptions import (
    MultiplePartsReinstantiateWithFailedPartsError,
    NotAllowedToReinstantiateError,
    VariantIncompleteError,
)

LOG = logging.getLogger(__name__)


class DuplicateVariantException(Exception):
    pass


def save_variant(variability_model, values, **args):
    """
    Generate a persistent variant from its property values.

    :param variability_model: The variability model for the new variant
    :type variability_model: cs.variants.VariabilityModel

    :param values: The property values for the new variant
    :type values: a dictionary as got from get_variants_classification

    The remaining keyword arguments are passed to the variant.

    :raises: ConstaintsViolationException, SearchIndexException

    :return: The variant object
    """
    from cs.variants import Variant

    # assign classification class and set values
    classification_data = classification_api.get_new_classification(
        [variability_model.ClassificationClass.code]
    )
    for property_code, property_entries in values.items():
        # Multiple not supported so hard code to index 0
        value = property_entries[0]["value"]

        # for float value we need to copy the dictionary since
        # get_classification has side effects on it
        if isinstance(value, dict):
            value = dict(value)
        classification_data["properties"][property_code][0]["value"] = value

    with transactions.Transaction():
        variability_model_id = variability_model.cdb_object_id
        default_args = {
            "id": Variant.new_id(variability_model_id),
            "variability_model_id": variability_model_id,
        }
        default_args.update(args)
        variant = operations.operation(constants.kOperationNew, Variant, **default_args)

        # save classification data
        classification_api.update_classification(variant, classification_data)

    object_classification = ObjectClassification.ByKeys(
        ref_object_id=variant.cdb_object_id, class_code=variability_model.class_code
    )
    if object_classification:
        # ensure that variability model class cannot be deleted by user
        object_classification.not_deletable = 1

    return variant


def exclude_variant(variability_model, classification_dataset, **kwargs):
    expression = " and "
    expression_array = []

    for property_key, property_entries in classification_dataset.items():
        # No multiple supported so hard code to index 0
        property_entry = property_entries[0]
        property_type = property_entry["property_type"]

        if property_type == "float":
            if property_entry["value"]["float_value_normalized"] is not None:
                expression_array.append(
                    "%s == %s"
                    % (property_key, property_entry["value"]["float_value_normalized"])
                )
        elif property_type in ("boolean", "integer"):
            expression_array.append(
                "%s == %s" % (property_key, property_entry["value"])
            )
        else:
            expression_array.append(
                "%s == '%s'" % (property_key, property_entry["value"])
            )

    expression = expression.join(expression_array)
    generate_constraint(
        variability_model.ClassificationClass,
        when_condition="",
        expression="not (%s)" % expression,
        **kwargs
    )


def instantiate_part(variant, maxbom, persistent=True):
    """
    Instantiate a maxbom by creating a new part.
    The newly created part will have the filtered maxbom structure as its
    product structure.

    :param variant: the variant which is used for instantiation
    :type variant: cs.variants.Variant

    :param maxbom: the MaxBOM object which is used for instantiaton
    :type maxbom: cdb.Object

    :param persistent: if true bom positions will be created for the newly instantiated part
    :type persistent: bool

    :raises cs.variants.exceptions.VariantIncompleteError: raised if the variant has not all variant
        driving properties set
    :raises cs.variants.exceptions.SelectionConditionEvaluationError: raised if an error occurred during
        selection condition evaluation
    """
    if not check_classification_attributes(variant):
        raise VariantIncompleteError(variant)

    with transactions.Transaction():
        root_instance = make_root_instance(maxbom, variant)

        if persistent is True:
            lookup = InstantiateLookup(maxbom, variant)
            lookup.build_variant_bom()
            if helpers.is_reuse_enabled():
                lookup.build_reuse()
            build_instance(root_instance, lookup)

        return root_instance


def reinstantiate_parts(all_parts, maxbom=None):
    """
    Recompute the product structure of an instantiated part by filtering the maxbom
    according to the part's variant.

    .. important::

        this method only runs successfully if the user has the access rights to modify
        the bom of the part

    :param all_parts: a list of all parts which should be reinstantiated
    :type all_parts: list

    :param maxbom: optional parameter. the MaxBOM object which is used to reinstantiate the part.
                    If this is not provided the MaxBOM of the corresponding `VariantPart` is used.
    :type maxbom: cdb.Object

    :raises NotAllowedToReinstantiateError: raised if the user doesn't have the necessary access
        rights on the part for reinstantiation.
    :raises cs.variants.exceptions.VariantIncompleteError: raised if the variant has not all variant
        driving properties set
    :raises cs.variants.exceptions.SelectionConditionEvaluationError: raised if an error occurred during
        selection condition evaluation
    :raises cs.variants.exceptions.NotAllowedToReinstantiateError: raised if the user is not allowed
        to reinstantiate part
    """
    variant_parts = VariantPart.get_all_belonging_to_parts(all_parts)
    variant_parts_lookup = {
        (each.teilenummer, each.t_index): each for each in variant_parts
    }
    failed_parts_exceptions = {}

    for each_part in all_parts:
        with transactions.Transaction():
            # noinspection PyBroadException
            try:
                variant_part = variant_parts_lookup.get(
                    (each_part.teilenummer, each_part.t_index), None
                )
                if variant_part is None:
                    raise exceptions.NotAnInstanceException(each_part)

                variant_part_variant = variant_part.Variant
                if variant_part_variant is None:
                    raise exceptions.NotAnInstanceException(each_part)

                if not check_classification_attributes(variant_part_variant):
                    raise VariantIncompleteError(variant_part_variant)

                if maxbom is None:
                    maxbom = variant_part.MaxBOM
                    if maxbom is None:
                        raise exceptions.NotAnInstanceException(each_part)

                # only allow this operation if the user has enough access rights on the object
                if each_part.CheckAccess("save"):
                    part_to_reinstantiate = each_part
                    if (
                        variant_part.maxbom_teilenummer != maxbom.teilenummer
                        or variant_part.maxbom_t_index != maxbom.t_index
                    ):
                        variant_part.Update(
                            maxbom_teilenummer=maxbom.teilenummer,
                            maxbom_t_index=maxbom.t_index,
                        )

                elif each_part.CheckAccess("index"):
                    part_to_reinstantiate = make_indexed_instance(each_part)
                else:
                    raise NotAllowedToReinstantiateError(each_part)

                lookup = InstantiateLookup(maxbom, variant_part_variant)
                lookup.build_variant_bom()
                if helpers.is_reuse_enabled():
                    lookup.build_reuse()
                lookup.collect_modifications(part_to_reinstantiate)
                rebuild_instance(part_to_reinstantiate, lookup)

            except Exception as ex:  # pylint: disable=broad-except
                if len(all_parts) == 1:
                    raise
                failed_parts_exceptions[each_part.cdb_object_id] = ex

    if failed_parts_exceptions:
        raise MultiplePartsReinstantiateWithFailedPartsError(
            all_parts, failed_parts_exceptions
        )


class Solver:
    def __init__(self, problem_object, limit=None):
        self.solution_iter = enumerate(problem_object.getSolutionIter())
        self.limit = limit if limit is not None else float("inf")
        self.complete = False

        self.checksum_function = calculate_classification_value_checksum

        classification_checksum_constraint = None
        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        for each_constraint, _ in problem_object._constraints:
            if isinstance(each_constraint, ClassificationChecksumConstraint):
                classification_checksum_constraint = each_constraint
                break

        if classification_checksum_constraint is not None:

            def checksum_function(_):
                return classification_checksum_constraint.last_checksum

            self.checksum_function = checksum_function

    def __iter__(self):
        return self

    def __next__(self):
        try:
            index, solution = next(self.solution_iter)
        except StopIteration:
            self.complete = True
            raise

        if index >= self.limit:
            raise StopIteration()

        checksum = self.checksum_function(solution)
        return solution, checksum


def solve(
    variability_model, presets=None, limit=None, constrain_classification_checksum=None
):
    """
    Generates the determined solution space of a given variability model.

    This is done as follows:

    - collect the property in the classification class, which have a finite set of predefined values
    - for each possible combination of predefined property values yield a dictionary mapping
      the property id to the selected value
    - exclude combinations which violates constraints and formulas

    :param variability_model: The variability model
    :type variability_model: cs.variants.VariabilityModel

    :param presets: Used to set the value of some variables to some fixed value.
                    Must be a dictionary of the form `{<PROPERTY CODE>: <VALUE>}`.
    :type presets: dict of str: list of dict

    :param limit: Set a limit to the dimension of the computed solution space.
                  If not given the complete solution space will be computed
    :type limit: int

    :param constrain_classification_checksum: Used to constrain the solution.
                                 The solution will not contain equal property combination,
                                 which lead to the same checksum.
    :type constrain_classification_checksum: list of str

    :raises cs.variants.exceptions.InvalidPresets: If an invalid preset is given, because
        the property value does not exist in the solution space, this exception is raised.

    :raises cs.variants.exceptions.InvalidPropertyCodes: If an invalid preset is given, because
        the property code is not contained in the classification classes, this exception is raised.

    :return: A generator which yields the solution dictionaries
    """
    if limit is None:
        limit = float("inf")

    limit = min([limit, get_max_limit()])

    problem_object = generate_problem(
        variability_model,
        presets=presets,
        constrain_classification_checksum=constrain_classification_checksum,
    )
    return Solver(problem_object, limit)


def solve_view(view, presets=None, limit=None):
    """
    Generates the determined solution space of a given variability model view.

    This is done as follows:

    - collect the property in the classification class, which have a finite set of predefined values
    - for each possible combination of predefined property values yield a dictionary mapping
      the property id to the selected value
    - exclude combinations which violates constraints and formulas

    :param view: The variability model view
    :type view: cs.variants.VariantsView

    :param presets: Used to set the value of some variables to some fixed value.
                    Must be a dictionary of the form `{<PROPERTY CODE>: <VALUE>}`.
    :type presets: dict of (str, str or int or float)

    :param limit: Set a limit to the dimension of the computed solution space.
                  If not given the complete solution space will be computed
    :type limit: int

    :raises cs.variants.exceptions.InvalidPresets: If an invalid preset is given, because
        the property value does not exist in the solution space, this exception is raised.

    :raises cs.variants.exceptions.InvalidPropertyCodes: If an invalid preset is given, because
        the property code is not contained in the classification classes, this exception is raised.

    :return: A generator which yields the solution dictionaries
    """

    if limit is None:
        limit = float("inf")

    limit = min([limit, get_max_limit()])

    problem_object = generate_problem(view, presets=presets)
    return Solver(problem_object, limit)


def get_max_limit():
    try:
        limit = int(util.get_prop("lmvr"))
    except (ValueError, TypeError):
        limit = MAX_LIMIT_VARIANT_EDITOR_TABLE

    # negative limit means no limit
    if limit < 0:
        return float("inf")

    return limit


def check_classification_attributes(variant):
    """
    Check if all variant driven attributes are evaluated

    Evaluated means:
        - text: value is not None and not an empty string ''
        - for all other props value must not be None

    We use the classification.util.is_property_value_set function to validate

    :param variant: the variant to check
    :return: True if valid, False otherwise
    """
    # Only get variability classification class
    variant_variability_model = variant.VariabilityModel
    variant_variability_model_classification_class = (
        variant_variability_model.ClassificationClass
    )

    vc = VariantsClassification([variant_variability_model_classification_class.code])
    all_variant_driven_properties = vc.get_variant_driving_properties()

    variant_classification = classification_api.get_classification(variant)
    property_values = variant_classification["properties"]

    for each in all_variant_driven_properties.values():
        prop = property_values[each["code"]]
        if not classification_util.is_property_value_set(prop):
            return False

    return True


def generate_constraint(classification_class, when_condition, expression, **kwargs):
    """
    Generate a new constraint for an classification class

    :param classification_class: classification class object
    :param when_condition: condition for when part of constraint
    :param expression: the expression of the constraint
    :param kwargs: additional args for constraint
    :return: the newly created constraint
    """
    new_constraint = constraints.Constraint.Create(
        classification_class_id=classification_class.cdb_object_id,
        when_condition=when_condition,
        expression=expression,
        **kwargs
    )

    # Because we do not use an operation we have to manually reload the cache
    ClassificationValidator.reload_constraints()

    return new_constraint
