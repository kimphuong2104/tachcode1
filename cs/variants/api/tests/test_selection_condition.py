#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import json

from cdb import testcase
from cs.variants.api.selection_condition import (
    SelectionConditionEvaluationError,
    SelectionConditionEvaluator,
    SelectionConditionsExpressionLookup,
)
from cs.variants.tests.common import (
    get_bool_property_entry,
    get_float_property_entry,
    get_int_property_entry,
    get_text_property_entry,
)
from cs.vp.bom import AssemblyComponent


def get_test_properties(use_not_set_properties=False):
    return {
        "text_prop": get_text_property_entry(
            "text_prop", None if use_not_set_properties else "abc"
        ),
        "int_prop": get_int_property_entry(
            "int_prop", None if use_not_set_properties else 123
        ),
        "float_prop": get_float_property_entry(
            "float_prop", None if use_not_set_properties else 42.123
        ),
        "bool_prop": get_bool_property_entry(
            "bool_prop", None if use_not_set_properties else False
        ),
    }


class SelectionConditionEvaluatorForTests(SelectionConditionEvaluator):
    # pylint: disable=super-init-not-called
    def __init__(
        self, expression_to_test, ref_object=None, use_not_set_properties=False
    ):
        self.properties = get_test_properties(
            use_not_set_properties=use_not_set_properties
        )

        self.selection_conditions_lookup = SelectionConditionsExpressionLookup({})
        if expression_to_test is not None:
            ref_object_id = ref_object["cdb_object_id"]
            self.selection_conditions_lookup.data[ref_object_id] = (
                "expression_cdb_object_id",
                expression_to_test,
            )

    # pylint: disable=signature-differs
    def __call__(
        self,
        ref_object=None,
        ignore_not_found_selection_condition=False,
        ignore_not_set_properties=False,
    ):
        return super().__call__(
            ref_object=ref_object,
            ignore_not_found_selection_condition=ignore_not_found_selection_condition,
            ignore_not_set_properties=ignore_not_set_properties,
        )


class TestSelectionCondition(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSelectionCondition, cls).setUpClass()

        cls.ref_object = AssemblyComponent.Query(max_rows=1)[0]

    def execute_selection_condition_evaluator(
        self,
        expression_to_test,
        use_not_set_properties=False,
        ref_object=None,
        ignore_not_found_selection_condition=False,
        ignore_not_set_properties=False,
    ):
        selection_condition_evaluator_for_tests = SelectionConditionEvaluatorForTests(
            expression_to_test,
            ref_object=self.ref_object,
            use_not_set_properties=use_not_set_properties,
        )
        return selection_condition_evaluator_for_tests(
            ref_object=self.ref_object if ref_object is None else ref_object,
            ignore_not_found_selection_condition=ignore_not_found_selection_condition,
            ignore_not_set_properties=ignore_not_set_properties,
        )

    def assert_exception(
        self,
        assert_raises,
        expression_cdb_object_id_expected=True,
        use_not_set_properties=False,
    ):
        exception_message = assert_raises.exception.build_message()
        self.maxDiff = None
        self.assertIn(self.ref_object.DBInfo(), exception_message)
        if expression_cdb_object_id_expected:
            self.assertIn("expression_cdb_object_id", exception_message)
        self.assertIn(
            json.dumps(
                get_test_properties(use_not_set_properties=use_not_set_properties),
                indent=2,
            ),
            exception_message,
        )

    def test_SelectionConditionEvaluator_all_props_true(self):
        result = self.execute_selection_condition_evaluator(
            'text_prop == "abc" and int_prop == 123 and float_prop == 42.123 and bool_prop is False'
        )

        self.assertTrue(result)

    def test_SelectionConditionEvaluator_all_props_false(self):
        result = self.execute_selection_condition_evaluator(
            'text_prop != "abc" and int_prop == 123 and float_prop == 42.123 and bool_prop is False',
        )

        self.assertFalse(result)

    def test_SelectionConditionEvaluator_ref_object_syntax_error(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator('text_prop == "abc')

        self.assert_exception(assert_raises)

    def test_SelectionConditionEvaluator_ref_object_handle_syntax_error(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator(
                'text_prop == "abc', ref_object=self.ref_object.ToObjectHandle()
            )

        self.assert_exception(assert_raises)

    def test_SelectionConditionEvaluator_ref_object_record_syntax_error(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator(
                'text_prop == "abc', ref_object=self.ref_object.GetRecord()
            )

        self.assert_exception(assert_raises)

    def test_SelectionConditionEvaluator_ref_object_prop_missing(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator('text_prop_missing == "abc"')

        self.assert_exception(assert_raises)

    def test_SelectionConditionEvaluator_ref_object_prop_not_set(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator(
                'text_prop == "abc"', use_not_set_properties=True
            )

        self.assert_exception(assert_raises, use_not_set_properties=True)

    def test_SelectionConditionEvaluator_ref_object_prop_not_set_but_ignored(self):
        result = self.execute_selection_condition_evaluator(
            'text_prop == "abc"',
            use_not_set_properties=True,
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_SelectionConditionEvaluator_ref_object_not_found_selection_condition(self):
        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            self.execute_selection_condition_evaluator(None)

        self.assert_exception(assert_raises, expression_cdb_object_id_expected=False)

    def test_SelectionConditionEvaluator_ref_object_not_found_selection_condition_but_ignored(
        self,
    ):
        result = self.execute_selection_condition_evaluator(
            None, ignore_not_found_selection_condition=True
        )

        self.assertTrue(result)
