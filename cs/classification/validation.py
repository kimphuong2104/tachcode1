# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module validation
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import string

from collections import defaultdict

import cdbwrapc
from cdb import i18n, sqlapi, ue

from cs.classification import computations, tools, util
from cs.classification.rules import RuleValues
from cs.classification.units import normalize_value, UnitCache

LOG = logging.getLogger(__name__)


class ClassificationValidationException(Exception):

    def __init__(self, code, error_message_key='cs_classification_validation_error'):
        super(ClassificationValidationException, self).__init__("")
        self._code = code
        self._error_message_key = error_message_key

    def to_ue_Exception(self):
        return ue.Exception(self._error_message_key, self._code)


class TooManyFormulasException(ClassificationValidationException):

    def __init__(self, property_code):
        super(TooManyFormulasException, self).__init__(property_code, "cs_classification_too_many_formulas")


class TooManyRulesException(ClassificationValidationException):

    def __init__(self, property_code):
        super(TooManyRulesException, self).__init__(property_code, "cs_classification_too_many_rules")


class ClassificationValidator(object):

    _constraints_by_class_code = None
    _formulas_by_property_code = None
    _rules_by_property_code = None

    @classmethod
    def _load_constraints(cls):
        if cls._constraints_by_class_code is None:
            cls.reload_constraints()

    @classmethod
    def _load_formulas(cls):
        if cls._formulas_by_property_code is None:
            cls.reload_formulas()

    @classmethod
    def _load_rules(cls):
        if cls._rules_by_property_code is None:
            cls.reload_rules()

    @classmethod
    def calculate_formulars(
            cls, properties, base_units_by_code,
            prop_codes_for_evaluation=None, expression_evaluator=computations.check_expression
    ):
        """
        Calculate formulas for given prop codes and properties

        :param properties: dict with property code and property entries
        :param base_units_by_code: dict with the base units for the property codes
        :param prop_codes_for_evaluation: prop codes which should evaluated
        :param expression_evaluator: see `cs.classification.computations.evaluate_expression`

        :return: result of evaluated formula
        """
        cls._load_formulas()
        changed_properties = set()
        calculated_formular_oids = set()
        while True:
            # iterate until the values don't change anymore
            changes = False
            for code in properties:
                if prop_codes_for_evaluation and code not in prop_codes_for_evaluation:
                    continue
                formulas = cls._formulas_by_property_code.get(code, [])
                if not formulas:
                    continue
                applicable_formulas = []
                default_formula = None
                for formula in formulas:
                    when_condition = formula["when_condition"]
                    if not when_condition or 0 == len(when_condition.strip(string.whitespace)):
                        default_formula = formula
                    elif computations.evaluate_bool_expression(
                            when_condition, properties, False, expression_evaluator=expression_evaluator
                    ):
                        applicable_formulas.append(formula)
                if len(applicable_formulas) > 1:
                    raise TooManyFormulasException(code)
                formula = default_formula
                if len(applicable_formulas) == 1:
                    formula = applicable_formulas[0]
                if formula and formula["cdb_object_id"] not in calculated_formular_oids:
                    try:
                        new_value = computations.evaluate_expression(
                            formula["value_formula"],
                            properties,
                            evaluate_with_none_values=False,
                            replace_with_empty_strings=True,
                            expression_evaluator=expression_evaluator
                        )
                        formula_evaluated = True
                    except (computations.PropertyValueNotSetException,
                            computations.PropertyValueNotFoundException):
                        new_value = None
                        formula_evaluated = False
                    property_values = properties.get(code)
                    if not property_values or 0 == len(property_values):
                        calculated_formular_oids.add(formula["cdb_object_id"])
                        continue
                    else:
                        property_value = property_values[0]
                    # currently  no typechecks for computed values
                    property_type = property_value["property_type"]
                    if "float" == property_type:
                        changed_properties.add(code)
                        float_value = property_value["value"]
                        if (
                            (float_value["float_value_normalized"] is None and new_value is not None) or
                            (float_value["float_value_normalized"] is not None and new_value is None) or
                            not util.isclose(float_value["float_value_normalized"], new_value)
                        ):
                            default_unit_id = base_units_by_code.get(code, {}).get("default_unit_object_id")
                            unit_object_id = base_units_by_code.get(code, {}).get("unit_object_id")
                            if default_unit_id and default_unit_id != unit_object_id:
                                # calculate value for default unit
                                float_value["unit_object_id"] = default_unit_id
                                float_value["float_value"] = normalize_value(
                                    new_value,
                                    unit_object_id,
                                    default_unit_id,
                                    code
                                )
                            else:
                                float_value["unit_object_id"] = unit_object_id
                                float_value["float_value"] = new_value
                            if float_value["unit_object_id"]:
                                unit_info = UnitCache.get_unit_info(float_value["unit_object_id"])
                                float_value["unit_label"] = unit_info["label"] if unit_info else ""
                            float_value["float_value_normalized"] = new_value
                            if formula_evaluated:
                                calculated_formular_oids.add(formula["cdb_object_id"])
                            changes = True
                    elif "integer" == property_type:
                        changed_properties.add(code)
                        if new_value is None:
                            new_val = new_value
                        else:
                            new_val = int(new_value)
                        if property_value['value'] != new_val:
                            # avoid rounding issues if float is returned
                            property_value['value'] = new_val
                            if formula_evaluated:
                                calculated_formular_oids.add(formula["cdb_object_id"])
                            changes = True
                    elif property_type in ("block", "multilang"):
                        # currently no support for calculated multilang properties
                        calculated_formular_oids.add(formula["cdb_object_id"])
                    else:
                        changed_properties.add(code)
                        if property_value['value'] != new_value:
                            property_value['value'] = new_value
                            if "text" == property_type:
                                lang = i18n.default()
                                decsription_col = "description_" + lang
                                label_col = "label_" + lang
                                stmt = "SELECT {}, {} FROM cs_class_property_values_v WHERE property_code = '{}' and text_value = '{}'".format(
                                    decsription_col, label_col, code, new_value
                                )
                                rset = sqlapi.RecordSet2(sql=stmt)
                                if rset:
                                    description = rset[0][decsription_col] if decsription_col in rset[0] else ""
                                    label = rset[0][label_col] if label_col in rset[0] else ""
                                    property_value['addtl_value'] = {
                                        "description": description,
                                        "label": label
                                    }
                                elif 'addtl_value' in property_value:
                                    del property_value['addtl_value']
                            elif "objectref" == property_type:
                                if new_value:
                                    property_value["addtl_value"] = tools.get_addtl_objref_value(
                                        new_value, request=None
                                    )
                                elif 'addtl_value' in property_value:
                                    del property_value['addtl_value']
                            if formula_evaluated:
                                calculated_formular_oids.add(formula["cdb_object_id"])
                            changes = True
            if not changes:
                break
        return changed_properties

    @classmethod
    def calculate_rules(
            cls, properties,
            prop_codes_for_evaluation=None,
            expression_evaluator=computations.check_expression,
            ignore_errors=False
    ):
        """
        Calculate rules for given prop codes and properties

        :param properties: dict with property code and property entries
        :param prop_codes_for_evaluation: prop codes which should evaluated
        :param expression_evaluator: see `cs.classification.computations.evaluate_expression`

        :return: result of evaluated rules
        """

        cls._load_rules()
        rule_results_by_property_code = {}
        for code in properties:
            if prop_codes_for_evaluation and code not in prop_codes_for_evaluation:
                continue
            rules = cls._rules_by_property_code.get(code, [])
            applicable_rule = None
            for rule in rules:
                if computations.evaluate_bool_expression(
                    rule["expression"], properties, expression_evaluator=expression_evaluator
                ):
                    if applicable_rule and (
                        rule["editable"] != applicable_rule["editable"] or
                        rule["mandatory"] != applicable_rule["mandatory"]
                    ):
                        if ignore_errors:
                            LOG.warning("Too many applicable rules for property %s found.", code)
                        else:
                            raise TooManyRulesException(code)
                    applicable_rule = rule
                    rule_results_by_property_code[code] = {
                        "editable": applicable_rule["editable"],
                        "mandatory": applicable_rule["mandatory"]
                    }
        return rule_results_by_property_code

    @classmethod
    def check_violated_constraints(
            cls, class_codes, properties,
            skip_after_failure=False, ignore_errors=False, property_code=None,
            expression_evaluator=computations.check_expression
    ):
        """
        Check which constraint are violated for given class codes and properties

        :param class_codes: list of class codes which constraint should be checked
        :param properties: dict with property code and property entries
        :param skip_after_failure: ends after first violated constraint
        :param ignore_errors: ignore errors in constraint expression
        :param property_code: just evaluate constraints which contain this property code
        :param expression_evaluator: see `cs.classification.computations.evaluate_expression`

        :return: list of violated constraints
        """
        def skip_evaluation(constraint, property_code):
            if not property_code:
                return False
            if property_code in computations.property_codes_used_in_expression(constraint["expression"]):
                return False
            if property_code in computations.property_codes_used_in_expression(constraint["when_condition"]):
                return False
            return True

        cls._load_constraints()

        violated_constraints = []
        for code in class_codes:
            contraints = cls._constraints_by_class_code.get(code, [])
            for constraint in contraints:
                if skip_evaluation(constraint, property_code):
                    continue
                contraint_result = True
                if computations.evaluate_bool_expression(
                    constraint["when_condition"], properties, expression_evaluator=expression_evaluator
                ) is not False:
                    contraint_result = computations.evaluate_bool_expression(
                        constraint["expression"], properties,
                        ignore_errors=ignore_errors,
                        evaluate_with_none_values=False,
                        expression_evaluator=expression_evaluator
                    )
                if contraint_result and constraint["equivalent"]:
                    if computations.evaluate_bool_expression(
                        constraint["expression"], properties, expression_evaluator=expression_evaluator
                    ) is not False:
                        contraint_result = computations.evaluate_bool_expression(
                            constraint["when_condition"], properties,
                            ignore_errors=ignore_errors,
                            evaluate_with_none_values=False,
                            expression_evaluator=expression_evaluator
                        )
                if contraint_result is False:
                    violated_constraints.append(constraint)
                    if skip_after_failure:
                        return violated_constraints
        return violated_constraints

    @classmethod
    def check_constraints(
            cls, class_codes, properties, skip_after_failure=False, ignore_errors=False, property_code=None,
            expression_evaluator=computations.check_expression, with_logging=True
    ):
        """
        Check which constraint for given class codes and properties

        :param class_codes: list of class codes which constraint should be checked
        :param properties: dict with property code and property entries
        :param skip_after_failure: ends after first violated constraint
        :param ignore_errors: ignore errors in constraint expression
        :param property_code: just evaluate constraints which contain this property code
        :param expression_evaluator: see `cs.classification.computations.evaluate_expression`

        :return: list of error messages
        """
        error_messages = []
        violated_constraints = cls.check_violated_constraints(
            class_codes, properties, skip_after_failure, ignore_errors, property_code,
            expression_evaluator=expression_evaluator
        )
        for constraint in violated_constraints:
            if with_logging:
                LOG.error(
                    """contraint violated %s: %s
                       when_condition='%s'
                       expression='%s'
                       equivalent='%d'""",
                    constraint["name"], constraint["error_message"], constraint["when_condition"],
                    constraint["expression"], constraint["equivalent"]
                )
            error_message = constraint["error_message"]
            if error_message:
                error_messages.append(error_message)
            else:
                error_messages.append(
                    cdbwrapc.get_label("web.cs-classification-component.error_constraints_fallback")
                )

        return error_messages

    @classmethod
    def get_property_codes_for_validation(cls, class_codes, property_codes):
        property_codes_for_validation = defaultdict(dict)

        cls._load_constraints()
        for code in class_codes:
            contraints = cls._constraints_by_class_code.get(code, [])
            for constraint in contraints:
                try:
                    for property_code in computations.property_codes_used_in_expression(
                        constraint["when_condition"]
                    ):
                        property_codes_for_validation[property_code]["constraint"] = True
                    for property_code in computations.property_codes_used_in_expression(
                        constraint["expression"]
                    ):
                        property_codes_for_validation[property_code]["constraint"] = True
                except Exception as e: # pylint: disable=W0703
                    LOG.error(
                        "formula evaluation error for class {code}: {constraint_data}".format(
                            code=code, constraint_data=constraint
                        )
                    )
                    # LOG.exception(e)

        exitFlag = False
        cls._load_formulas()
        for code in property_codes:
            if exitFlag:
                break
            formulas = cls._formulas_by_property_code.get(code, [])
            for formula in formulas:
                try:
                    for property_code in computations.property_codes_used_in_expression(
                        formula["when_condition"]
                    ):
                        property_codes_for_validation[property_code]["formula"] = True
                    property_codes_used_in_expression = computations.property_codes_used_in_expression(
                        formula["value_formula"]
                    )
                    if property_codes_used_in_expression:
                        for property_code in property_codes_used_in_expression:
                            property_codes_for_validation[property_code]["formula"] = True
                    elif not formula["when_condition"]:
                        for property_code in property_codes:
                            property_codes_for_validation[property_code]["formula"] = True
                        exitFlag = True
                        break
                except Exception as e: # pylint: disable=W0703
                    LOG.error(
                        "formula evaluation error for property {code}: {formula_data}".format(
                            code=code, formula_data=formula
                        )
                    )
                    LOG.exception(e)

        cls._load_rules()
        for code in property_codes:
            rules = cls._rules_by_property_code.get(code, [])
            for rule in rules:
                try:
                    for property_code in computations.property_codes_used_in_expression(rule["expression"]):
                        property_codes_for_validation[property_code]["rule"] = True
                except Exception as e: # pylint: disable=W0703
                    LOG.error(
                        "rule evaluation error for property {code}: {rule_data}".format(
                            code=code, rule_data=rule
                        )
                    )
                    LOG.exception(e)

        return property_codes_for_validation

    @classmethod
    def get_validated_catalog_values(cls, class_codes, property_code, properties, enum_values):
        cls._load_constraints()
        catalog_values = []
        property_value = properties[property_code][0]["value"]
        for enum_value in enum_values:
            properties[property_code][0]["value"] = enum_value["value"]
            error_messages = cls.check_constraints(
                class_codes, properties, skip_after_failure=True, ignore_errors=True,
                property_code=property_code, with_logging=False
            )
            enum_value["error_message"] = tools.join_error_messages(error_messages)
            catalog_values.append(enum_value)
        properties[property_code][0]["value"] = property_value
        return catalog_values

    @classmethod
    def has_formula(cls, property_code):
        cls._load_formulas()
        return property_code in cls._formulas_by_property_code

    @classmethod
    def has_constraints(
            cls, class_codes
    ):
        """
        Do at least a constraint exist for the given class codes

        :param class_codes: list of class codes which should be inspected

        :return: True if at least an constraint exist in one of the class codes otherwise False
        """
        cls._load_constraints()

        for each in class_codes:
            # defaultdict with list
            # -> empty list => False
            # -> at least an entry => True
            if cls._constraints_by_class_code[each]:
                return True

        return False

    @classmethod
    def reload_all(cls):
        cls.reload_constraints()
        cls.reload_formulas()
        cls.reload_rules()

    @classmethod
    def reload_constraints(cls):
        default_lang = i18n.default()
        cls._constraints_by_class_code = defaultdict(list)
        constraint_query = """
            SELECT
                cs_classification_constraint.name_{lang},
                cs_classification_class.code,
                cs_classification_constraint.when_condition,
                cs_classification_constraint.expression,
                cs_classification_constraint.equivalent,
                cs_classification_constraint.error_message_{lang}
            FROM cs_classification_constraint
            LEFT JOIN cs_classification_class ON
                cs_classification_constraint.classification_class_id = cs_classification_class.cdb_object_id
        """.format(lang=default_lang)
        result = sqlapi.RecordSet2(sql=constraint_query)
        for row in result:
            constraint_data = {
                "when_condition": row.when_condition,
                "expression": row.expression,
                "equivalent": row.equivalent if row.equivalent else 0,
                "name": row["name_%s" % default_lang],
                "error_message": row["error_message_%s" % default_lang]
            }
            cls._constraints_by_class_code[row["code"]].append(constraint_data)

    @classmethod
    def reload_formulas(cls):
        cls._formulas_by_property_code = defaultdict(list)
        formular_query = """
            SELECT cs_class_property.code, cs_class_property.cdb_classname, cs_classification_computation.*
            FROM cs_classification_computation
            LEFT JOIN cs_class_property
            ON cs_classification_computation.property_id = cs_class_property.cdb_object_id
            WHERE cs_class_property.for_variants is NULL or cs_class_property.for_variants = 0
        """
        result = sqlapi.RecordSet2(sql=formular_query)
        for row in result:
            formular_data = {
                'cdb_object_id': row["cdb_object_id"],
                'value_formula': row["value_formula"],
                'when_condition': row["when_condition"],
                'property_classname': row["cdb_classname"]
            }
            cls._formulas_by_property_code[row["code"]].append(formular_data)

    @classmethod
    def reload_rules(cls):
        cls._rules_by_property_code = defaultdict(list)

        rule_query = """
            SELECT cs_class_property.code, cs_classification_rule.* FROM cs_classification_rule
            LEFT JOIN cs_class_property
            ON cs_classification_rule.class_property_id = cs_class_property.cdb_object_id
        """
        result = sqlapi.RecordSet2(sql=rule_query)
        for row in result:
            rule_data = {
                'editable': RuleValues.by_label(row["editable"]).id,
                'expression': row["expression"],
                'mandatory': RuleValues.by_label(row["mandatory"]).id,
            }
            cls._rules_by_property_code[row["code"]].append(rule_data)
