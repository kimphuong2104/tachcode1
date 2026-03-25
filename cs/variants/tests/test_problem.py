#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
# pylint: disable=comparison-with-itself, comparison-of-constants
import datetime
from unittest import TestCase

from cdb import auth
from cs.classification.computations import (
    PropertyValueNotFoundException,
    PropertyValueNotSetException,
    property_codes_used_in_expression,
)
from cs.classification.util import convert_datestr_to_datetime
from cs.variants import calculate_classification_value_checksum
from cs.variants.api.problem import (
    ClassificationExpressionCacheEvaluator,
    generate_problem,
)
from cs.variants.tests.common import VariantsTestCase


class TestProblem(TestCase):
    def setUp(self):
        super().setUp()

        self.classification_expression_cache_evaluator = (
            ClassificationExpressionCacheEvaluator()
        )

    def _test_expressions(
        self,
        expressions,
        properties,
        evaluate_with_none_values=True,
        replace_with_empty_strings=False,
    ):
        for expression, value in expressions:
            if isinstance(value, type):
                with self.assertRaises(value):
                    self.classification_expression_cache_evaluator(
                        expression,
                        properties,
                        evaluate_with_none_values,
                        replace_with_empty_strings,
                    )
            else:
                eval_value = self.classification_expression_cache_evaluator(
                    expression,
                    properties,
                    evaluate_with_none_values,
                    replace_with_empty_strings,
                )
                self.assertEqual(
                    eval_value,
                    value,
                    "Expression (%s) not computed correctly" % expression,
                )

    def test_literal_expression(self):
        properties = {}
        expressions = [
            ("2 * 3 + 5", 2 * 3 + 5),
            ("(None is None) is True", (None is None) is True),
            ("True and False", True and False),
            ("10 if True else 20", 10),
            ("10 if False else 20", 20),
            ("2 ** 32", 2**32),
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
            self.classification_expression_cache_evaluator(
                "$(date)", properties, False, True
            )
        )
        self.assertLessEqual(now, date)

        time = convert_datestr_to_datetime(
            self.classification_expression_cache_evaluator(
                "$(time)", properties, False, True
            )
        )
        self.assertLessEqual(now, time)

    def test_referencing_properties(self):
        """Variables in expressions should be replaced with the property value at the object"""
        properties = {
            "COLOR": [{"property_type": "text", "value": "red"}],
            "COUNT": [{"property_type": "integer", "value": 3}],
            "TEXT": [{"property_type": "text", "value": "testteext"}],
        }
        expressions = [
            ("COLOR in ('red', 'yellow', 'green')", True),
            ("COUNT", 3),
            ("COUNT * 4", 12),
            ("TEXT", "testteext"),
            ("TEXT + '_2'", "testteext_2"),
        ]
        self._test_expressions(expressions, properties)

    def _test_codes(self, expressions):
        for expr in expressions:
            prop_codes = property_codes_used_in_expression(expr["expression"])
            self.assertSetEqual(
                prop_codes, expr["expected_prop_codes"], "Property codes do not match!"
            )

    def test_find_property_codes_from_expression(self):
        expressions = [
            {"expression": " ", "expected_prop_codes": set()},
            {"expression": "COUNT", "expected_prop_codes": set(["COUNT"])},
            {"expression": "COUNT * 4", "expected_prop_codes": set(["COUNT"])},
            {
                "expression": "COLOR in ('red', 'yellow', 'green')",
                "expected_prop_codes": set(["COLOR"]),
            },
            {
                "expression": "LENGTH * WIDTH",
                "expected_prop_codes": set(["LENGTH", "WIDTH"]),
            },
        ]
        self._test_codes(expressions)

    def test_value_properties(self):
        properties = {"COLOR": [{"property_type": "text", "value": "red"}]}
        expressions = [
            ("'red' in COLOR", True),
            ("'black' in COLOR", False),
            ("['red', 'green'] == COLOR", False),
        ]
        self._test_expressions(expressions, properties)

    def test_none_handling_with_handling_true(self):
        properties = {
            "NONE_VALUE": [{"property_type": "text", "value": None}],
            "NON_NONE_VALUE": [{"property_type": "text", "value": "ABC"}],
        }
        expressions = [
            ("NONE_VALUE == 'ABC'", False),
            ("NON_NONE_VALUE == 'ABC'", True),
            ("NONE_VALUE is None", True),
            ("NON_NONE_VALUE is None", False),
        ]
        self._test_expressions(
            expressions,
            properties,
            evaluate_with_none_values=True,
            replace_with_empty_strings=False,
        )

    def test_none_handling_with_handling_false(self):
        properties = {
            "NONE_VALUE": [{"property_type": "text", "value": None}],
            "NON_NONE_VALUE": [{"property_type": "text", "value": "ABC"}],
        }
        expressions = [
            ("NONE_VALUE == 'ABC'", PropertyValueNotSetException),
            ("NON_NONE_VALUE == 'ABC'", True),
            ("NONE_VALUE is None", PropertyValueNotSetException),
            ("NON_NONE_VALUE is None", False),
        ]
        self._test_expressions(
            expressions,
            properties,
            evaluate_with_none_values=False,
            replace_with_empty_strings=False,
        )

    def test_not_found_properties(self):
        properties = {
            "NON_NONE_VALUE": [{"property_type": "text", "value": "ABC"}],
        }
        expressions = [
            ("NONE_VALUE == 'ABC'", PropertyValueNotFoundException),
            ("NON_NONE_VALUE == 'ABC'", True),
            ("NONE_VALUE is None", PropertyValueNotFoundException),
            ("NON_NONE_VALUE is None", False),
        ]
        self._test_expressions(
            expressions,
            properties,
            evaluate_with_none_values=False,
            replace_with_empty_strings=False,
        )


class TestProblemWithDatabase(VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp(with_occurrences=with_occurrences)

    def test_generate_problem_without_constraints(self):
        problem_object = generate_problem(self.variability_model)

        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        self.assertEqual(0, len(problem_object._constraints))

    def test_generate_problem_with_constraints(self):
        self.generate_constraint()
        problem_object = generate_problem(self.variability_model)

        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        self.assertEqual(1, len(problem_object._constraints))

    def test_generate_problem_without_constraints_and_property_constrains(self):
        problem_object = generate_problem(
            self.variability_model,
            constrain_classification_checksum=[
                calculate_classification_value_checksum(
                    {"abc": [{"id": "abc", "value": "123"}]}
                )
            ],
        )

        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        self.assertEqual(1, len(problem_object._constraints))

    def test_generate_problem_with_constraints_and_property_constrains(self):
        self.generate_constraint()
        problem_object = generate_problem(
            self.variability_model,
            constrain_classification_checksum=[
                calculate_classification_value_checksum(
                    {"abc": [{"id": "abc", "value": "123"}]}
                )
            ],
        )

        # noinspection PyProtectedMember
        # pylint: disable=protected-access
        self.assertEqual(2, len(problem_object._constraints))
