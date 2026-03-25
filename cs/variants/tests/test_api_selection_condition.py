#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import constants
from cdb.objects import operations
from cs.classification import catalog, classes, computations, units
from cs.variants.api.selection_condition import (
    evaluate_selection_condition_with_properties,
)
from cs.variants.selection_condition import SelectionCondition
from cs.variants.tests import common


class TestAPISelectionCondition(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp()

        self.class_prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        self.class_prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

    def test_evaluate_selection_condition_with_properties_no_selection_condition_all_props(
        self,
    ):
        with self.assertRaises(ValueError):
            evaluate_selection_condition_with_properties(
                None,
                {
                    self.class_prop1: [{"property_type": "text", "value": "VALUE1"}],
                    self.class_prop2: [{"property_type": "text", "value": "VALUE2"}],
                },
                ignore_not_set_properties=False,
            )

    def test_evaluate_selection_condition_with_properties_no_selection_condition_not_all_props(
        self,
    ):
        with self.assertRaises(ValueError):
            evaluate_selection_condition_with_properties(
                None,
                {
                    self.class_prop1: [{"property_type": "text", "value": "VALUE1"}],
                },
                ignore_not_set_properties=False,
            )

    def test_evaluate_selection_condition_with_properties_with_all_props_false(self):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {
                self.class_prop1: [{"property_type": "text", "value": "VALUE1"}],
                self.class_prop2: [{"property_type": "text", "value": "VALUE2"}],
            },
        )

        self.assertFalse(result)

    def test_evaluate_selection_condition_with_properties_with_all_props_true(self):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {
                self.class_prop1: [{"property_type": "text", "value": "VALUE1"}],
                self.class_prop2: [{"property_type": "text", "value": "VALUE1"}],
            },
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_with_none_props_raises(self):
        with self.assertRaises(computations.PropertyValueNotSetException):
            evaluate_selection_condition_with_properties(
                self.selection_condition,
                {
                    self.class_prop1: [{"property_type": "text", "value": None}],
                    self.class_prop2: [{"property_type": "text", "value": None}],
                },
                ignore_not_set_properties=False,
            )

    def test_evaluate_selection_condition_with_properties_with_none_props_ignore(self):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {
                self.class_prop1: [{"property_type": "text", "value": None}],
                self.class_prop2: [{"property_type": "text", "value": None}],
            },
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_with_none_props_ignore2(self):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {
                self.class_prop1: [{"property_type": "text", "value": "VALUE1"}],
                self.class_prop2: [{"property_type": "text", "value": None}],
            },
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_not_all_props(self):
        with self.assertRaises(computations.PropertyValueNotFoundException):
            evaluate_selection_condition_with_properties(
                self.selection_condition,
                {self.class_prop1: [{"property_type": "text", "value": "VALUE1"}]},
                ignore_not_set_properties=False,
            )

    def test_evaluate_selection_condition_with_properties_not_all_props_with_ignore(
        self,
    ):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {self.class_prop1: [{"property_type": "text", "value": "VALUE1"}]},
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_all_props_with_ignore(self):
        result = evaluate_selection_condition_with_properties(
            self.selection_condition,
            {
                self.class_prop1: [{"property_type": "text", "value": "DIFFERENT"}],
                self.class_prop2: [{"property_type": "text", "value": "VALUE1"}],
            },
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_float_constraint_true(self):
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop
        unit_object_id = units.Unit.ByKeys(symbol="m").cdb_object_id

        def float_value(value):
            return {
                "float_value_normalized": value,
                "unit_label": "m",
                "unit_object_id": unit_object_id,
                "float_value": value,
            }

        new_selection_condition = operations.operation(
            constants.kOperationNew,
            SelectionCondition,
            variability_model_id=self.variability_model.cdb_object_id,
            expression="{0} == 2.71".format(float_prop),
        )
        result = evaluate_selection_condition_with_properties(
            new_selection_condition,
            {float_prop: [{"property_type": "float", "value": float_value(2.71)}]},
            ignore_not_set_properties=True,
        )

        self.assertTrue(result)

    def test_evaluate_selection_condition_with_properties_float_constraint_false(self):
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop
        unit_object_id = units.Unit.ByKeys(symbol="m").cdb_object_id

        def float_value(value):
            return {
                "float_value_normalized": value,
                "unit_label": "m",
                "unit_object_id": unit_object_id,
                "float_value": value,
            }

        new_selection_condition = operations.operation(
            constants.kOperationNew,
            SelectionCondition,
            variability_model_id=self.variability_model.cdb_object_id,
            expression="{0} != 2.71".format(float_prop),
        )
        result = evaluate_selection_condition_with_properties(
            new_selection_condition,
            {float_prop: [{"property_type": "float", "value": float_value(2.71)}]},
            ignore_not_set_properties=True,
        )

        self.assertFalse(result)
