# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import mock

from cdb import ElementsError, constants
from cdb.objects import operations
from cs.classification.api import get_classification
from cs.classification.computations import PropertyValueNotFoundException
from cs.variants import VariantPart, api
from cs.variants.classification_helper import is_variant_classification_data_equal
from cs.variants.exceptions import SelectionConditionEvaluationError
from cs.variants.tests import common


class TestInstantiationsOld(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp()

        # the variant will match on the first component (for the subassembly)
        # but will not match on the on subassembly's component

        comp = self.maxbom.Components[0]
        self.expression = "CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'" % self.prop1
        self.selection_condition2 = common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        self.variant = common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        )

        VariantPart.Query().Delete()

    def change_selection_condition_to_expression_long(self):
        self.expression_long = self.expression

        while len(self.expression_long) < 6000:
            self.expression_long += " or False"

        self.selection_condition2.Delete()
        comp = self.maxbom.Components[0]
        self.selection_condition2 = common.generate_selection_condition(
            self.variability_model, comp, self.expression_long
        )

    def assertRelationshipToMaxBOM(
        self, instance, max_bom, variant, original_max_bom=None
    ):
        instance.Reload()
        expected_cdb_copy_of_item_id = (
            max_bom.cdb_object_id
            if original_max_bom is None
            else original_max_bom.cdb_object_id
        )
        self.assertEqual(expected_cdb_copy_of_item_id, instance.cdb_copy_of_item_id)
        variant_parts = VariantPart.KeywordQuery(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=max_bom.teilenummer,
            maxbom_t_index=max_bom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )
        self.assertEqual(1, len(variant_parts), "No variant part found")

    def assertNotExistingVariantPart(self, instance, max_bom, variant):
        variant_parts = VariantPart.KeywordQuery(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=max_bom.teilenummer,
            maxbom_t_index=max_bom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )
        self.assertEqual(
            0, len(variant_parts), "No variant part expected but was found"
        )

    def test_instantiation_without(self):
        """the instantiate_part method will not generate a persistent product structure"""

        instance = api.instantiate_part(self.variant, self.maxbom, persistent=False)

        self.assertIsNotNone(instance, "The part has not been instantiated")
        self.assertLessEqual(
            len(instance.Components),
            0,
            "The instance has a persistent product structure",
        )

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_instantiation_without_expression_long(self):
        self.change_selection_condition_to_expression_long()

        instance = api.instantiate_part(self.variant, self.maxbom, persistent=False)

        self.assertIsNotNone(instance, "The part has not been instantiated")
        self.assertLessEqual(
            len(instance.Components),
            0,
            "The instance has a persistent product structure",
        )

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_instantiation_simple(self):
        """the instantiate_part method will generate a 100% product structure"""

        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertIsNotNone(instance, "The part has not been instantiated")
        self.assertGreater(
            len(instance.Components),
            0,
            "The instance has no persistent product structure",
        )
        self.assertTrue(
            is_variant_classification_data_equal(
                get_classification(self.variant)["properties"],
                get_classification(instance)["properties"],
            )
        )

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        component = instance.Components[0]
        subinstance = component.Item
        self.assertIsNotNone(subinstance)
        self.assertNotEqual(
            (subinstance.teilenummer, subinstance.t_index),
            (self.subassembly.teilenummer, self.subassembly.t_index),
            "The subassembly has not been instantiated",
        )

        self.assertLessEqual(
            len(subinstance.Components),
            0,
            "The persistent structure has not been filtered",
        )

    def test_instantiation_simple_with_selection_condition_with_missing_prop(self):
        self.selection_condition.Update(expression="missing_prop == 'VALUE1'")

        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            api.instantiate_part(self.variant, self.maxbom)

        self.assertIsInstance(
            assert_raises.exception.__cause__, PropertyValueNotFoundException
        )

    def test_instantiation_without_part_classification_license(self):
        with mock.patch(
            "cs.variants.api.helpers.is_part_classification_available",
            return_value=False,
        ) as mock_is_part_classification_available:
            instance = api.instantiate_part(self.variant, self.maxbom)

            mock_is_part_classification_available.assert_called()

        self.assertIsNotNone(instance, "The part has not been instantiated")
        self.assertGreater(
            len(instance.Components),
            0,
            "The instance has no persistent product structure",
        )
        self.assertDictEqual({}, get_classification(instance)["properties"])

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        component = instance.Components[0]
        subinstance = component.Item
        self.assertIsNotNone(subinstance)
        self.assertNotEqual(
            (subinstance.teilenummer, subinstance.t_index),
            (self.subassembly.teilenummer, self.subassembly.t_index),
            "The subassembly has not been instantiated",
        )

        self.assertLessEqual(
            len(subinstance.Components),
            0,
            "The persistent structure has not been filtered",
        )

    def test_instantiation_simple_expression_long(self):
        self.change_selection_condition_to_expression_long()

        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertIsNotNone(instance, "The part has not been instantiated")
        self.assertGreater(
            len(instance.Components),
            0,
            "The instance has no persistent product structure",
        )

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        component = instance.Components[0]
        subinstance = component.Item
        self.assertIsNotNone(subinstance)
        self.assertNotEqual(
            (subinstance.teilenummer, subinstance.t_index),
            (self.subassembly.teilenummer, self.subassembly.t_index),
            "The subassembly has not been instantiated",
        )

        self.assertLessEqual(
            len(subinstance.Components),
            0,
            "The persistent structure has not been filtered",
        )

    def test_reinstantiate_simple(self):
        """reinstantiate_parts method will recompute the 100% product structure"""

        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        comp = self.maxbom.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].expression = "1 == 0"

        api.reinstantiate_parts([instance])
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)
        self.assertEqual(
            0, len(instance.Components), "The product structure has not been recomputed"
        )

    def test_reinstantiate_simple_with_selection_condition_with_missing_prop(self):
        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        comp = self.maxbom.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].Update(expression="missing_prop == 'VALUE1'")

        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            api.reinstantiate_parts([instance])

        self.assertIsInstance(
            assert_raises.exception.__cause__, PropertyValueNotFoundException
        )

    def test_reinstantiate_simple_after_adding_new_selection_condition(self):
        self.selection_condition.Delete()
        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(1, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        comp = self.maxbom.Components[0].Item.Components[0]
        common.generate_selection_condition(self.variability_model, comp, "1 == 0")

        api.reinstantiate_parts([instance])
        instance.Reload()
        self.assertEqual(1, len(instance.Components))
        self.assertNotEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_reinstantiate_simple_after_adding_new_selection_condition_long(self):
        self.selection_condition.Delete()

        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(1, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        comp = self.maxbom.Components[0].Item.Components[0]
        expression = "1 == 0"
        while len(expression) < 6000:
            expression += " or False"
        common.generate_selection_condition(self.variability_model, comp, expression)

        api.reinstantiate_parts([instance])
        instance.Reload()
        self.assertEqual(1, len(instance.Components))
        self.assertNotEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_reinstantiate_simple_after_adding_removing_selection_condition(self):
        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertNotEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        self.selection_condition.Delete()

        api.reinstantiate_parts([instance])
        instance.Reload()
        self.assertEqual(1, len(instance.Components))
        self.assertEqual("CON-VP-000002", instance.Components[0].teilenummer)
        self.assertEqual(1, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_reinstantiate_simple_no_change(self):
        instance = api.instantiate_part(self.variant, self.maxbom)

        part_number = instance.Components[0].teilenummer
        self.assertEqual(1, len(instance.Components))
        self.assertNotEqual("CON-VP-000002", part_number)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        api.reinstantiate_parts([instance])
        instance.Reload()
        self.assertEqual(1, len(instance.Components))
        self.assertEqual(part_number, instance.Components[0].teilenummer)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        api.reinstantiate_parts([instance])
        instance.Reload()
        self.assertEqual(1, len(instance.Components))
        self.assertEqual(part_number, instance.Components[0].teilenummer)
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

    def test_reinstantiate_multiple(self):
        """reinstantiate_parts method will recompute the 100% product structure for multiple parts"""
        instance_1 = api.instantiate_part(self.variant, self.maxbom)
        instance_2 = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance_1.Components))
        self.assertRelationshipToMaxBOM(instance_1, self.maxbom, self.variant)

        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

        comp = self.maxbom.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].expression = "1 == 0"

        api.reinstantiate_parts([instance_1, instance_2])
        self.assertEqual(
            0, len(instance_1.Components), "instance_1 has not been recomputed"
        )
        self.assertRelationshipToMaxBOM(instance_1, self.maxbom, self.variant)
        self.assertEqual(
            0, len(instance_2.Components), "instance_2 has not been recomputed"
        )
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

    def test_reinstantiate_multiple_sequentially(self):
        """
        reinstantiate_parts method will recompute the 100% product structure
        for multiple parts sequentially
        """

        instance_1 = api.instantiate_part(self.variant, self.maxbom)
        instance_2 = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance_1.Components))
        self.assertRelationshipToMaxBOM(instance_1, self.maxbom, self.variant)

        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

        comp = self.maxbom.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].expression = "1 == 0"

        api.reinstantiate_parts([instance_1])
        self.assertEqual(
            0, len(instance_1.Components), "instance_1 has not been recomputed"
        )
        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

        api.reinstantiate_parts([instance_2])
        self.assertEqual(
            0, len(instance_1.Components), "instance_1 has not been recomputed"
        )
        self.assertEqual(
            0, len(instance_2.Components), "instance_2 has not been recomputed"
        )
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

    def test_reinstantiate_switch_to_new_index_bom(self):
        """reinstantiate_parts method will recompute the 100% product structure for a new indexed bom"""
        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        maxbom_indexed = operations.operation(constants.kOperationIndex, self.maxbom)
        comp = maxbom_indexed.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].expression = "1 == 0"

        # Old MaxBOM should make no change
        api.reinstantiate_parts([instance])
        self.assertEqual(1, len(instance.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        # New index MaxBOM should show change
        api.reinstantiate_parts([instance], maxbom=maxbom_indexed)
        self.assertEqual(
            0, len(instance.Components), "instance has not been recomputed"
        )
        self.assertRelationshipToMaxBOM(
            instance, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance, self.maxbom, self.variant)

    def test_reinstantiate_multiple_to_new_index_bom(self):
        """reinstantiate_parts method will recompute the 100% product structure
        for multiple parts with new indexed bom"""
        instance_1 = api.instantiate_part(self.variant, self.maxbom)
        instance_2 = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance_1.Components))
        self.assertRelationshipToMaxBOM(instance_1, self.maxbom, self.variant)

        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

        maxbom_indexed = operations.operation(constants.kOperationIndex, self.maxbom)

        api.reinstantiate_parts([instance_1, instance_2], maxbom=maxbom_indexed)

        self.assertEqual(1, len(instance_1.Components))
        self.assertRelationshipToMaxBOM(
            instance_1, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance_1, self.maxbom, self.variant)

        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(
            instance_2, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance_2, self.maxbom, self.variant)

    def test_reinstantiate_multiple_to_new_index_bom_with_sc_change(self):
        """reinstantiate_parts method will recompute the 100% product structure
        for multiple parts with new indexed bom"""
        instance_1 = api.instantiate_part(self.variant, self.maxbom)
        instance_2 = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance_1.Components))
        self.assertRelationshipToMaxBOM(instance_1, self.maxbom, self.variant)

        self.assertEqual(1, len(instance_2.Components))
        self.assertRelationshipToMaxBOM(instance_2, self.maxbom, self.variant)

        maxbom_indexed = operations.operation(constants.kOperationIndex, self.maxbom)
        comp = maxbom_indexed.Components[0]
        selection_conditions = comp.SelectionConditions.KeywordQuery(
            variability_model_id=self.variant.variability_model_id
        )
        selection_conditions[0].expression = "1 == 0"

        api.reinstantiate_parts([instance_1, instance_2], maxbom=maxbom_indexed)
        self.assertEqual(
            0, len(instance_1.Components), "instance_1 has not been recomputed"
        )
        self.assertEqual(
            0, len(instance_2.Components), "instance_2 has not been recomputed"
        )
        self.assertRelationshipToMaxBOM(
            instance_1, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance_1, self.maxbom, self.variant)
        self.assertRelationshipToMaxBOM(
            instance_2, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance_2, self.maxbom, self.variant)

    def test_reinstantiate_switch_to_new_index_bom_comp_of_subassembly(self):
        """reinstantiate_parts method will recompute the 100% product structure
        for a new indexed bom with comp of subassembly rule"""
        self.selection_condition.Delete()
        instance = api.instantiate_part(self.variant, self.maxbom)

        self.assertEqual(1, len(instance.Components))
        self.assertEqual(1, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        maxbom_indexed = operations.operation(constants.kOperationIndex, self.maxbom)
        comp = maxbom_indexed.Components[0].Item.Components[0]
        common.generate_selection_condition(self.variability_model, comp, "1 == 0")

        # Old MaxBOM should make no change (that is wrong because the subassembly is shared)
        api.reinstantiate_parts([instance])
        self.assertEqual(1, len(instance.Components))
        self.assertEqual(0, len(instance.Components[0].Item.Components))
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)

        # New index MaxBOM should show change
        api.reinstantiate_parts([instance], maxbom=maxbom_indexed)
        self.assertEqual(1, len(instance.Components))
        self.assertEqual(
            0,
            len(instance.Components[0].Item.Components),
            "instance_1 has not been recomputed",
        )
        self.assertRelationshipToMaxBOM(
            instance, maxbom_indexed, self.variant, original_max_bom=self.maxbom
        )
        self.assertNotExistingVariantPart(instance, self.maxbom, self.variant)

    def test_delete_with_instantiations(self):
        """Test deleting variants with instantiations"""
        api.instantiate_part(self.variant, self.maxbom)
        with self.assertRaises(ElementsError):
            operations.operation(constants.kOperationDelete, self.variant)

    def test_delete_without_instantiations(self):
        """Test deleting variants without instantiations"""
        operations.operation(constants.kOperationDelete, self.variant)

    def test_instantiate_subassembly(self):
        """The instantiate_part method will instatiate variable subassemblies"""
        comp = self.maxbom.Components[0]
        for selection_condition in comp.SelectionConditions:
            operations.operation(constants.kOperationDelete, selection_condition)

        comp.Reload()

        instance = api.instantiate_part(self.variant, self.maxbom)
        subinstance = instance.Components[0].Item

        self.assertIsNotNone(subinstance)
        self.assertNotEqual(
            (subinstance.teilenummer, subinstance.t_index),
            (self.subassembly.teilenummer, self.subassembly.t_index),
            "The subassembly has not been instantiated",
        )

        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)
        self.assertEqual(
            self.subassembly.cdb_object_id, subinstance.cdb_copy_of_item_id
        )

    def test_dont_instantiate_subassembly(self):
        """The instantiate_part method will not instantiate non variable components with predicates

        CON-VP-000001
            CON-VP-000002 - expression
                CON-VP-000003 - self.expression
        """

        comp = self.maxbom.Components[0]
        operations.operation(constants.kOperationDelete, self.selection_condition)
        comp.Reload()

        instance = api.instantiate_part(self.variant, self.maxbom)
        subinstance = instance.Components[0].Item

        self.assertIsNotNone(subinstance)
        self.assertEqual(
            (subinstance.teilenummer, subinstance.t_index),
            (self.subassembly.teilenummer, self.subassembly.t_index),
            "The subassembly has been instantiated",
        )

        instance = api.instantiate_part(self.variant, self.maxbom)
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.variant)
        subinstance.Reload()
        self.assertEqual("", subinstance.cdb_copy_of_item_id)
