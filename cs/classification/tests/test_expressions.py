# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import datetime
import math

from cdb import auth, testcase
from cs.documents import Document

from cs.classification import computations, api
from cs.classification.tests import utils
from cs.classification.util import convert_datestr_to_datetime
from cs.classification.validation import ClassificationValidator


class TestExpressions(utils.ClassificationTestCase):

    def setUp(self):
        super(TestExpressions, self).setUp()

    def _test_expressions(self, expressions, properties):
        for expr, value in expressions:
            print("Expression = " + expr)
            eval_value = computations.evaluate_expression(expr, properties, False, True)
            self.assertEqual(
                eval_value, value,
                "Expression (%s) not computed correctly" % expr
            )

    def test_literal_expression(self):
        """An expression containing only literals should evaluate as in python"""
        properties = {}
        expressions = [
            ("2 * 3 + 5", 2 * 3 + 5),
            ("(None is None) is True", (None is None) is True),
            ("True and False", True and False),
            ("10 if True else 20", 10 if True else 20),
            ("10 if False else 20", 10 if False else 20),
            ("2 ** 32", 2 ** 32),
            ("2 > 3", 2 > 3),
            ("int(2.13) == 2", int(2.13) == 2),
            ("2 in [1, 2, 3]", 2 in [1, 2, 3]),
            ("43 in [1, 2, 3]", 43 in [1, 2, 3]),
        ]
        self._test_expressions(expressions, properties)

    def test_variable_expression(self):
        """Variables should be replaced"""
        properties = {}
        expressions = [
            ("$(login)", auth.get_login()),
            ("$(org_id)", auth.get_department()),
            ("$(name)", auth.get_name()),
            ("$(persno)", auth.persno),
        ]
        self._test_expressions(expressions, properties)

        now = datetime.datetime.utcnow()
        date = convert_datestr_to_datetime(
            computations.evaluate_expression("$(date)", properties, False, True)
        )
        self.assertTrue(now <= date)

        time = convert_datestr_to_datetime(
            computations.evaluate_expression("$(time)", properties, False, True)
        )
        self.assertTrue(now <= time)

    def test_function_calls(self):
        """An expression containing only literals should evaluate as in python"""
        properties = {
            "WEIGHT": [
                {
                    "property_type": "float",
                    "value": {
                        "float_value_normalized": 33.33,
                        "float_value": 33.33
                    }
                }
            ]
        }
        expressions = [
            ("round(1.572*(WEIGHT)+479.65)", round(1.572 * 33.33 + 479.65)),
            ("round(pow(1.572*(WEIGHT)+479.65, 2))", round(pow(1.572 * 33.33 + 479.65, 2))),
            ("math.log(WEIGHT, 10)", math.log(33.33, 10)),
            ("math.cos(WEIGHT)", math.cos(33.33)),
            ("math.sin(WEIGHT)", math.sin(33.33)),
            ("math.tan(WEIGHT)", math.tan(33.33)),
        ]
        self._test_expressions(expressions, properties)

    def test_referencing_properties(self):
        """Variables in expressions should be replaced with the property value at the object"""
        properties = {
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                }
            ],
            "COUNT": [
                {
                    "property_type": "integer",
                    "value": 3
                }
            ],
            "TEXT": [
                {
                    "property_type": "text",
                    "value": "testteext"
                }
            ],
            "WEIGHT": [
                {
                    "property_type": "float",
                    "value": {
                        "float_value_normalized": 33.33,
                        "float_value": 33.33
                    }
                },
                {
                    "property_type": "float",
                    "value": {
                        "float_value_normalized": 123.456,
                        "float_value": 123.456
                    }
                }
            ]
        }
        expressions = [
            ("COLOR in ('red', 'yellow', 'green')", True),
            ("COUNT", 3),
            ("COUNT * 4", 12),
            ("TEXT", "testteext"),
            ("TEXT[:]", ["testteext"]),
            ("TEXT + '_2'", "testteext_2"),
            ("WEIGHT", [33.33, 123.456]),
            ("WEIGHT[0]", 33.33),
            ("WEIGHT[1]", 123.456),
            ("WEIGHT[:0]", [33.33]),
            ("WEIGHT[1:]", [123.456]),
            ("WEIGHT[:]", [33.33, 123.456]),
            ("WEIGHT[0:2]", [33.33, 123.456]),
            ("WEIGHT[0:-1]", [33.33]),
            ("WEIGHT[0:COUNT-2]", [33.33]),
            ("WEIGHT[0:len(WEIGHT)-1]", [33.33]),
            ("WEIGHT[0:len(WEIGHT)]", [33.33, 123.456])
        ]
        expressions = [
            ("TEXT[:]", ["testteext"]),
        ]
        self._test_expressions(expressions, properties)

    def _test_codes(self, expressions):
        for expr in expressions:
            prop_codes = computations.property_codes_used_in_expression(expr["expression"])
            self.assertSetEqual(
                prop_codes, expr["expected_prop_codes"], "Property codes do not match!"
            )

    def test_find_property_codes_from_expression(self):
        expressions = [
            {
                "expression": " ",
                "expected_prop_codes": set()
            },
            {
                "expression": "COUNT",
                "expected_prop_codes": set(["COUNT"])
            },
            {
                "expression": "COUNT * 4",
                "expected_prop_codes": set(["COUNT"])
            },
            {
                "expression": "COLOR in ('red', 'yellow', 'green')",
                "expected_prop_codes": set(["COLOR"])
            },
            {
                "expression": "LENGTH * WIDTH",
                "expected_prop_codes": set(["LENGTH", "WIDTH"])
            }
        ]
        self._test_codes(expressions)

    def test_multi_value_properties(self):
        """ Test expressions for multivalued properties """
        properties = {
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                },
                {
                    "property_type": "text",
                    "value": "blue"
                },
                {
                    "property_type": "text",
                    "value": "green"
                }
            ],
            "POS": [
                {
                    "property_type": "integer",
                    "value": 1
                }
            ]
        }

        expressions = [
            ("'red' in COLOR", True),
            ("'black' in COLOR", False),
            ("['red', 'green', 'blue'] == COLOR", False),
            ("['red', 'blue', 'green'] == COLOR", True),
            ("['red', 'blue', 'green'] == COLOR[:]", True),
            ("['blue', 'green'] == COLOR[1:]", True),
            ("['red', 'blue'] == COLOR[:2]", True),
            ("['blue'] == COLOR[1:2]", True),
            ("len(COLOR[:]) == 3", True),
            ("set(['red', 'blue']).issubset(COLOR[:])", True),
            ("set(['red', 'black']).issubset(COLOR[:])", False),
            ("set(['red', 'black']).issuperset(COLOR[:])", False),
            ("set(['red', 'green', 'blue', 'black']).issuperset(COLOR[:])", True),
            ("set(['red', 'black']).difference(COLOR[:]) == set(['black'])", True),
            ("set(['red', 'black']).intersection(COLOR[:]) == set(['red'])", True),
            ("set(['red', 'black']).intersection(COLOR[:]) == set(['red'])", True)
        ]
        self._test_expressions(expressions, properties)

        properties = {
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                }
            ]
        }
        expressions = [
            ("'red' in COLOR", True),
            ("'black' in COLOR", False),
            ("['red'] == COLOR[:]", True),
            ("['red', 'green'] == COLOR", False),
            ("len(COLOR[:]) == 1", True),
            ("set(['red']).issubset(COLOR[:])", True),
            ("set(['red', 'black']).issubset(COLOR[:])", False),
            ("set(['black', 'blue']).issuperset(COLOR[:])", False),
            ("set(['red', 'green']).issuperset(COLOR[:])", True),
            ("set(['red', 'black']).difference(COLOR[:]) == set(['black'])", True),
            ("set(['red', 'black']).intersection(COLOR[:]) == set(['red'])", True),
            ("set(['red', 'black']).intersection(COLOR[:]) == set(['red'])", True)
        ]
        self._test_expressions(expressions, properties)


    def test_simple_values(self):
        """ Test expressions for multivalued properties """
        iso_date_value = datetime.datetime.utcnow().isoformat()
        properties = {
            "BOOL_TRUE": [
                {
                    "property_type": "boolean",
                    "value": True
                }
            ],
            "BOOL_FALSE": [
                {
                    "property_type": "boolean",
                    "value": False
                }
            ],
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                }
            ],
            "DATE": [
                {
                    "property_type": "datetime",
                    "value": iso_date_value
                }
            ],
            "POS": [
                {
                    "property_type": "integer",
                    "value": 1
                }
            ],
            "WEIGHT": [
                {
                    "property_type": "float",
                    "value": {
                        "float_value_normalized": 33.33,
                        "float_value": 33.33
                    }
                }
            ]
        }
        expressions = [
            ("BOOL_TRUE is True", True),
            ("BOOL_FALSE is False", True),
            ("COLOR", "red"),
            ("DATE", iso_date_value),
            ("POS", 1),
            ("WEIGHT", 33.33)
        ]
        self._test_expressions(expressions, properties)


class TestExpressionsEvaluatorApi(utils.ClassificationTestCase):
    def setUp(self):
        super(TestExpressionsEvaluatorApi, self).setUp()

    def test_function_evaluator(self):
        expected_expression = "True"
        expected_properties = {
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                }
            ]
        }
        expected_evaluate_with_none_values = True
        expected_replace_with_empty_strings = False

        expected_return = "function_evaluator"

        def function_evaluator(expression, properties, evaluate_with_none_values, replace_with_empty_strings):
            self.assertEqual(expected_expression, expression)
            self.assertDictEqual(expected_properties, properties)
            self.assertEqual(expected_evaluate_with_none_values, evaluate_with_none_values)
            self.assertEqual(expected_replace_with_empty_strings, replace_with_empty_strings)

            return expected_return

        result = computations.evaluate_expression(
            expected_expression,
            expected_properties,
            expected_evaluate_with_none_values,
            expected_replace_with_empty_strings,
            expression_evaluator=function_evaluator
        )
        self.assertEqual(expected_return, result)

    def test_class_evaluator(self):
        expected_expression = "True"
        expected_properties = {
            "COLOR": [
                {
                    "property_type": "text",
                    "value": "red"
                }
            ]
        }
        expected_evaluate_with_none_values = False
        expected_replace_with_empty_strings = True

        class ClassEvaluator(object):
            def __init__(self):
                self.expressions = []

            def __call__(
                    inner_self, expression, properties, evaluate_with_none_values, replace_with_empty_strings
            ):
                self.assertEqual(expected_expression, expression)
                self.assertDictEqual(expected_properties, properties)
                self.assertEqual(expected_evaluate_with_none_values, evaluate_with_none_values)
                self.assertEqual(expected_replace_with_empty_strings, replace_with_empty_strings)

                inner_self.expressions.append(expression)
                return len(inner_self.expressions)

        class_evaluator = ClassEvaluator()

        result = computations.evaluate_expression(
            expected_expression,
            expected_properties,
            expected_evaluate_with_none_values,
            expected_replace_with_empty_strings,
            expression_evaluator=class_evaluator
        )
        self.assertEqual(1, result)

        result = computations.evaluate_expression(
            expected_expression,
            expected_properties,
            expected_evaluate_with_none_values,
            expected_replace_with_empty_strings,
            expression_evaluator=class_evaluator
        )
        self.assertEqual(2, result)
        self.assertListEqual(class_evaluator.expressions, [expected_expression, expected_expression])

    def test_class_evaluator_full_recursive(self):
        with testcase.error_logging_disabled():
            doc = Document.ByKeys(z_nummer="CLASS000005", z_index="")
            classification_data = api.get_classification(doc)

        class ClassEvaluator(object):
            def __init__(self):
                self.expressions = []

            def __call__(
                    inner_self, expression, properties, evaluate_with_none_values, replace_with_empty_strings
            ):
                inner_self.expressions.append(expression)
                return computations.check_expression(
                    expression, properties, evaluate_with_none_values, replace_with_empty_strings
                )

        class_evaluator = ClassEvaluator()

        result = ClassificationValidator().check_violated_constraints(
            ["TEST_CLASS_CONSTRAINTS"],
            classification_data["properties"],
            expression_evaluator=class_evaluator
        )
        self.assertEqual(1, len(result))
        self.assertEqual(9, len(class_evaluator.expressions))
