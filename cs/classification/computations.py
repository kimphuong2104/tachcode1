# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module computations

This is the documentation for the computations module.
"""

import ast
import datetime
import logging
import string

from cdb import auth, ue
from cdb.objects import ByID
from cdb.objects import references
from cdb.objects import expressions
from cdb.objects.core import Object

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

LOG = logging.getLogger(__name__)

fComputationFormula = expressions.Forward("cs.classification.computations.ComputationFormula")
fClassProperty = expressions.Forward("cs.classification.classes.ClassProperty")


class ComputationFormula(Object):
    __maps_to__ = "cs_classification_computation"
    __classname__ = "cs_classification_computation"

    ClassProperty = references.Reference_1(
        fClassProperty,
        fClassProperty.cdb_object_id == fComputationFormula.property_id
    )

    def _clear_formular_cache(self, ctx):
        from cs.classification.validation import ClassificationValidator
        ClassificationValidator.reload_formulas()

    def _check_parent_property(self, ctx):
        from cs.classification.classes import BlockClassProperty, MultilangClassProperty
        if not ctx.parent:
            return
        prop = ByID(ctx.parent.cdb_object_id)
        if isinstance(prop, BlockClassProperty) or isinstance(prop, MultilangClassProperty):
            raise ue.Exception("cs_classification_no_formula_support")

    event_map = {
        (('create'), 'pre_mask'): '_check_parent_property',
        (('modify', 'create', 'copy', 'delete'), 'post'): '_clear_formular_cache'
    }


class PropertyValueNotFoundException(Exception):

    def __init__(self, property_code, index):
        super(PropertyValueNotFoundException, self).__init__("")
        self.property_code = property_code
        self.index = index

    def raise_ue_exception(self):
        raise ue.Exception("cs_classification_property_value_not_found", self.property_code, str(self.index))


class PropertyValueNotSetException(Exception):

    def __init__(self, property_code, index):
        super(PropertyValueNotSetException, self).__init__("")
        self.property_code = property_code
        self.index = index


def replace_expression(expression):
    # remove new lines in expression
    eval_expression = expression.replace('\n', ' ')
    # replace supported variables
    eval_expression = eval_expression.replace('$(date)', '"{}"'.format(datetime.datetime.utcnow().isoformat()))
    eval_expression = eval_expression.replace('$(login)', '"{}"'.format(auth.get_login()))
    eval_expression = eval_expression.replace('$(org_id)', '"{}"'.format(auth.get_department()))
    eval_expression = eval_expression.replace('$(name)', '"{}"'.format(auth.get_name()))
    eval_expression = eval_expression.replace('$(persno)', '"{}"'.format(auth.persno))
    eval_expression = eval_expression.replace('$(time)', '"{}"'.format(datetime.datetime.utcnow().isoformat()))
    return "({})".format(eval_expression)


def check_expression(expression, properties, evaluate_with_none_values, replace_with_empty_strings):
    import math # needed for evaluation
    eval_expression = replace_expression(expression)
    transformer = ExperssionTransformer(properties, evaluate_with_none_values, replace_with_empty_strings)
    node = ast.parse(eval_expression, mode="eval")
    new_node = transformer.visit(node)
    code = compile(new_node, "<string>", "eval")
    result = eval(code)
    return result


def evaluate_expression(
        expression, properties, evaluate_with_none_values, replace_with_empty_strings,
        expression_evaluator=check_expression
):
    """
    Evaluate an expression with the given properties

    :param expression: string expression
    :param properties: dict with property code and property entries
    :param evaluate_with_none_values: should properties with an None value be evaluated
    :param replace_with_empty_strings: replace None text properties with an empty string
    :param expression_evaluator: optional expression used to evaluate the given expression.
                                 Default is `cs.classification.computations.check_expression`.

                                 The provide function need to have following signature:
                                 func(
                                    expression,
                                    properties,
                                    evaluate_with_none_values,
                                    replace_with_empty_strings
                                 )

                                 *These are the same parameters which are provided to this function*

    :return: result of evaluated expression
    """
    try:
        return expression_evaluator(
            expression, properties, evaluate_with_none_values, replace_with_empty_strings
        )
    except (PropertyValueNotSetException, PropertyValueNotFoundException):
        raise
    except SyntaxError as syntaxError:
        msg = "Syntax error in line {line} at position {pos} of expression '{expression}'".format(
            expression=expression, line=syntaxError.lineno, pos=syntaxError.offset
        )
        LOG.error(msg)
        raise ue.Exception("cs_classification_validation_error")
    except Exception as e: # pylint: disable=W0703
        LOG.error("Error evaluating expression '{expression}'".format(expression=expression))
        LOG.exception(e)
        raise ue.Exception("cs_classification_validation_error")


def evaluate_bool_expression(
        expression,
        properties,
        ignore_errors=False,
        evaluate_with_none_values=True,
        replace_with_empty_strings=False,
        expression_evaluator=check_expression
):
    """
    Evaluate an expression as an bool result

    :param expression: string expression
    :param properties: dict with property code and property entries
    :param ignore_errors: if errors occur during expression evaluation it will be treated as this option
    :param evaluate_with_none_values: should properties with an None value be evaluated
    :param replace_with_empty_strings: replace None text properties with an empty string
    :param expression_evaluator: see `cs.classification.computations.evaluate_expression`

    :return: bool result of evaluated expression
    """
    if not expression or 0 == len(expression):
        return None
    else:
        try:
            return bool(
                evaluate_expression(
                    expression, properties, evaluate_with_none_values, replace_with_empty_strings,
                    expression_evaluator=expression_evaluator
                )
            )
        except Exception: # pylint: disable=W0703
            return ignore_errors


def property_codes_used_in_expression(expression):
    if not expression or 0 == len(expression.strip(string.whitespace)):
        return set()
    eval_expression = replace_expression(expression)
    transformer = CodeTransformer()
    try:
        node = ast.parse(eval_expression, mode="eval")
        transformer.visit(node)
        return transformer.codes
    except Exception as ex:
        LOG.error("Error evaluating experssion: " + eval_expression)
        LOG.exception(ex)
        raise


class BaseTransformer(ast.NodeTransformer):
    functions = [
        "all",
        "any",
        "bool",
        "difference",
        "float",
        "int",
        "intersection",
        "issubset",
        "issuperset",
        "len",
        "min",
        "max",
        "pow",
        "round",
        "set",
        "str",
        "math",
        "cos",
        "log",
        "sin",
        "tan",
    ]
    operators = [
        "in",
        "is",
        "not"
    ]
    values = [
        "False",
        "None",
        "True"
    ]

    def _isnumber(self, n):
        try:
            float(n)
            return True
        except (ValueError, TypeError):
            return False


class CodeTransformer(BaseTransformer):

    def __init__(self):
        self.codes = set()

    def visit_Name(self, node):
        # simple variable names
        if node.id not in self.functions and node.id not in self.values and not self._isnumber(node.id):
            property_code = node.id
            self.codes.add(property_code)
        return node

    def visit_Subscript(self, node):
        # variable with list index
        property_code = node.value.id
        self.codes.add(property_code)


class ExperssionTransformer(BaseTransformer):

    def __init__(self, property_values, evaluate_with_none_values, replace_with_empty_strings):
        self.property_values = property_values
        self.evaluate_with_none_values = evaluate_with_none_values
        self.replace_with_empty_strings = replace_with_empty_strings

    def _get_raw_value(self, property_value):
        raw_value = None
        property_type = property_value['property_type']
        if 'block' == property_type or 'multilang' == property_type:
            # FIXME: blocks and multilang currently not supported
            pass
        elif 'float' == property_type:
            float_value = property_value["value"]
            if float_value:
                raw_value = float_value["float_value_normalized"]
                if raw_value is not None:
                    raw_value = float(raw_value)
        elif 'text' == property_type and self.replace_with_empty_strings:
            raw_value = '' if property_value['value'] is None else property_value['value']
        else:
            raw_value = property_value['value']
        return raw_value

    def _get_index_string(self, lower_index, upper_index):
        # get value from property here
        if lower_index is None and upper_index is None:
            return ""
        index_str = "[{lower}{sep}{upper}]".format(
            lower=lower_index,
            sep=":" if lower_index != upper_index else "",
            upper="" if upper_index == -1 or lower_index == upper_index else upper_index
        )
        return index_str

    def _get_value(self, property_code, lower_index=None, upper_index=None, as_list=False):
        # get value from property here
        if property_code in self.property_values:
            values = self.property_values[property_code]
        else:
            raise PropertyValueNotFoundException(
                property_code, self._get_index_string(lower_index, upper_index)
            )
        try:
            if lower_index is None and upper_index is None:
                if as_list or len(values) > 1:
                    raw_values = []
                    for value in values:
                        raw_values.append(self._get_raw_value(value))
                    return raw_values
                else:
                    raw_value = self._get_raw_value(values[0])
            elif lower_index == upper_index:
                selected_value = values[lower_index]
                raw_value = self._get_raw_value(selected_value)
                if as_list:
                    return [raw_value]
            else:
                if upper_index is None:
                    selected_values = values[lower_index:]
                else:
                    selected_values = values[lower_index:upper_index]
                raw_values = []
                for value in selected_values:
                    raw_values.append(self._get_raw_value(value))
                return raw_values
        except IndexError:
            LOG.error("Index error accessing property code {}".format(property_code))
        if raw_value is not None or self.evaluate_with_none_values:
            return raw_value
        else:
            raise PropertyValueNotSetException(
                property_code, self._get_index_string(lower_index, upper_index)
            )

    def _make_simple_node(self, value, node):
        if isinstance(value, datetime.datetime):
            new_node = ast.Constant(value.isoformat())
        else:
            new_node = ast.Constant(value)
        return new_node

    def _make_node(self, value, node):
        if isinstance(value, list):
            elts = []
            for val in value:
                elts.append(self._make_simple_node(val, node))
            new_node = ast.List(elts=elts, ctx=ast.Load())
        else:
            new_node = self._make_simple_node(value, node)
        new_node = ast.copy_location(new_node, node)
        return ast.fix_missing_locations(new_node)

    def visit_Name(self, node):
        # simple variable names
        if node.id not in self.functions and node.id not in self.values and not self._isnumber(node.id):
            value = self._get_value(node.id)
            return self._make_node(value, node)
        return node

    def visit_Subscript(self, node):

        def get_slice_value(slice):
            if slice is None:
                return slice
            if isinstance(slice, ast.Constant):
                return slice.value
            else:
                new_node = self.visit(ast.Expression(slice))
                code = compile(new_node, "<string>", "eval")
                return eval(code)

        # variable with list index
        name = node.value.id
        lower_index = 0
        upper_index = 0
        as_list = False
        try:
            if isinstance(node.slice, ast.Constant):
                lower_index = node.slice.value
                upper_index = node.slice.value
                as_list = False
            elif isinstance(node.slice, ast.Slice):
                lower_index = get_slice_value(node.slice.lower)
                upper_index = get_slice_value(node.slice.upper)
                as_list = True
            else:
                # THINKABOUT: error handling
                LOG.error("only integer values as index operator allowed")
        except Exception as e: # pylint: disable=W0703
            # THINKABOUT: error handling
            LOG.error("only integer values as index operator allowed")
            LOG.exception(e)
        value = self._get_value(name, lower_index, upper_index, as_list)
        return self._make_node(value, node)
