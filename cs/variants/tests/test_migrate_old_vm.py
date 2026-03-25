#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import logging

from cdb import constants, testcase, util
from cdb.objects.operations import operation
from cs.classification.util import isclose
from cs.variants import VariabilityModel
from cs.variants.selection_condition import SelectionCondition
from cs.variants.tests.common import ensure_running_classification_core
from cs.variants.tools.migrate_old_vm.migrate import migrate_old_vm
from cs.variants.tools.migrate_old_vm.options import MigrationOptions
from cs.variantstests import old_vm_migration_test_data
from cs.vp.products import Product


def build_terms_from_expression(expression):
    expression = expression.replace("(", "").replace(")", "")
    result_and = [each_and.strip() for each_and in expression.split("and")]
    result_or = []
    for each_and in result_and:
        result_or.extend([each_or.strip() for each_or in each_and.split("or")])

    return result_or


def compare_enum_value_to_classification_value(enum_value, classification_value):
    classification_value_value = classification_value.value
    is_float = False

    if isinstance(classification_value_value, dict):
        classification_value_value = classification_value_value["float_value"]
        is_float = True

    if is_float:
        try:
            return isclose(classification_value_value, enum_value["float_value"])
        except AttributeError:
            return isclose(classification_value_value, float(enum_value["value_txt"]))

    else:
        try:
            return classification_value.value == enum_value["text_value"]
        except AttributeError:
            return classification_value.value == enum_value["value_txt"]


class TestMigrateOldVm(testcase.RollbackTestCase):
    old_properties = {}
    old_property_values = {}

    @classmethod
    def setUpClass(cls):
        super(TestMigrateOldVm, cls).setUpClass()
        from cs.variants.tools.migrate_old_vm import LOGGER

        LOGGER.setLevel(logging.CRITICAL)

        ensure_running_classification_core()
        old_vm_migration_test_data.install()

        cls.default_instances_count_lookup = {
            "Variante 001": 8,
            "Variante manuell 001 [manual]": 4,
        }

        product = Product.ByKeys(code="Old_VM_Test_Data")
        cls.old_variants = {each.id: each for each in product.Variants}

        for each in product.AllProperties:
            enum_values = each.EnumValues.Execute()

            if enum_values:
                cls.old_properties[each.erp_code] = each
                cls.old_property_values[each.erp_code] = enum_values

    def setUp(self):
        super().setUp()

        util.tables.reload_all()
        self.options = MigrationOptions()

    def assertClassificationExpressionTerms(self, expected, result):
        expected_terms = []
        for each in expected:
            expected_terms.extend(build_terms_from_expression(each))

        result_terms = []
        for each in result:
            result_terms.extend(build_terms_from_expression(each))

        self.assertListEqual(sorted(expected_terms), sorted(result_terms))

    def assert_selection_conditions(self, new_variability_model):
        selection_conditions = SelectionCondition.KeywordQuery(
            variability_model_id=new_variability_model.cdb_object_id
        ).Execute()
        self.assertClassificationExpressionTerms(
            [
                'ALPHANUMERIC != "abc"',
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                'ALPHANUMERIC == "xyz"',
                "ALPHANUMERIC is False",
                "ALPHANUMERIC is not False",
                "BOOLEAN == 1",
                "BOOLEAN == 1",
                "BOOLEAN == False",
                "BOOLEAN == False",
                "BOOLEAN == True",
                "BOOLEAN == True",
                "BOOLEAN is False",
                "BOOLEAN is not False",
                'CALPHANUMERI == "abc"',
                'CALPHANUMERI == "xyz"',
                'CALPHANUMERI == "xyz"',
                'CALPHANUMERI == "xyz"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "abc"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "asdf"',
                'LALPHANUMERIC == "xyz"',
                'LALPHANUMERIC == "xyz"',
                'LALPHANUMERIC == "xyz"',
                'LALPHANUMERIC == "xyz"',
                'LALPHANUMERIC == "xyz"',
                'LALPHANUMERIC == "xyz"',
                "CBOOLEAN == False",
                "CBOOLEAN == False",
                "CBOOLEAN == False",
                "CBOOLEAN == True",
                "CBOOLEAN == True",
                "CBOOLEAN == True",
                "CBOOLEAN == True",
                "CBOOLEAN is not False",
                "CCNUMERIC < 456",
                "CCNUMERIC == 123",
                "CCNUMERIC == 123",
                "CCNUMERIC == 456",
                "CCNUMERIC == 456",
                "CCNUMERIC == 789",
                "CCNUMERIC == 789",
                "CCNUMERIC == 789",
                "CCNUMERIC == 789",
                "LNUMERIC != 123",
                "LNUMERIC < 456",
                "LNUMERIC == 123",
                "LNUMERIC == 123",
                "LNUMERIC == 123",
                "LNUMERIC == 123",
                "LNUMERIC == 123",
                "LNUMERIC == 123",
                "LNUMERIC == 456",
                "LNUMERIC == 456",
                "LNUMERIC == 456",
                "LNUMERIC == 456",
                "LNUMERIC == 456",
                "LNUMERIC >= 456",
                'NOTVARIANTDRI == "Not variant driving"',
                'NOTVARIANTDRI == "Not variant driving"',
                'NOTVARIANTDRI == "Not variant driving"',
                'NOTVARIANTDRI == "Not variant driving"',
                'NOTVARIANTDRI == "Not variant driving2"',
                'NOTVARIANTDRI == "Not variant driving2"',
                'NOTVARIANTDRI == "Not variant driving2"',
                "NUMERIC <= 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 12.34",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 123",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 456",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC == 789",
                "NUMERIC is False",
                "NUMERIC is not False",
            ],
            [each.get_expression() for each in selection_conditions],
        )

    def assert_classification_class(
        self,
        new_variability_model,
        product_to_test,
        assert_cdb_object_id_property_equal=True,
        assert_cdb_object_id_property_value_equal=True,
        assert_classification_terms=True,
    ):
        classification_class = new_variability_model.ClassificationClass
        self.assertEqual(product_to_test.code, classification_class.code)
        self.assertListEqual(
            sorted(["cs_variant", "part"]),
            sorted(classification_class.Applicabilities.dd_classname),
        )
        classification_class_properties = classification_class.Properties.Execute()
        self.assertEqual(len(self.old_properties), len(classification_class_properties))

        for each in classification_class_properties:
            # Remove postfix from class properties
            old_property_code = each.code.replace("_alphanumeric", "")

            old_property = self.old_properties[old_property_code]

            if assert_cdb_object_id_property_equal:
                self.assertEqual(each["cdb_object_id"], old_property["cdb_object_id"])
            else:
                self.assertNotEqual(
                    each["cdb_object_id"], old_property["cdb_object_id"]
                )

            property_values = each.property_values()
            old_property_values = self.old_property_values[old_property_code]

            if old_property.data_type == "boolean":
                self.assertEqual(0, len(property_values))
            else:
                self.assertEqual(len(old_property_values), len(property_values))

            for each_value in property_values:
                old_property_value = [
                    each_old_property_value
                    for each_old_property_value in old_property_values
                    if compare_enum_value_to_classification_value(
                        each_old_property_value, each_value
                    )
                ]
                if len(old_property_value) != 1:
                    pass
                self.assertEqual(1, len(old_property_value))
                old_property_value = old_property_value[0]

                if (
                    assert_cdb_object_id_property_value_equal
                    and old_property_value.CatalogueEnumValue is None
                ):
                    self.assertEqual(
                        each_value["cdb_object_id"], old_property_value["cdb_object_id"]
                    )
                else:
                    self.assertNotEqual(
                        each_value["cdb_object_id"], old_property_value["cdb_object_id"]
                    )

            if each.code == "NOTVARIANTDRI":
                for_variants = 0
            else:
                for_variants = 1
            self.assertEqual(for_variants, each.for_variants)

            if each.code == "ALPHANUMERIC":
                self.assertListEqual(
                    sorted(["abc", "xyz"]), sorted(each.ClassPropertyValues.text_value)
                )
                self.assertListEqual(
                    [], sorted(each.Property.PropertyValues.text_value)
                )

            if each.code == "CCNUMERIC":
                self.assertListEqual(
                    sorted([789]), sorted(each.ClassPropertyValues.float_value)
                )
                self.assertListEqual(
                    sorted([123, 456]), sorted(each.Property.PropertyValues.float_value)
                )

        if not assert_classification_terms:
            return

        classification_class_constraints = classification_class.Constraints
        self.assertListEqual(
            sorted([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]),
            sorted(classification_class_constraints.equivalent),
        )
        self.assertClassificationExpressionTerms(
            [
                '(ALPHANUMERIC == "abc")',
                '(ALPHANUMERIC == "xyz" and '
                'CBOOLEAN is not False) or (CALPHANUMERI == "xyz")',
                "(BOOLEAN == False)",
                "(BOOLEAN == False)",
                "(BOOLEAN == True and " + "NUMERIC == 789) or (CCNUMERIC == 123)",
                "(BOOLEAN == True) or " + '(CALPHANUMERI == "xyz")',
                "(BOOLEAN is False)",
                '(CALPHANUMERI == "abc")',
                "(LNUMERIC != 456 and CCNUMERIC < 789)",
                "(NUMERIC is not False)",
            ],
            classification_class_constraints.when_condition,
        )
        self.assertClassificationExpressionTerms(
            [
                'ALPHANUMERIC == "abc"',
                'ALPHANUMERIC == "xyz"',
                "BOOLEAN is not False",
                'LALPHANUMERIC != "asdf"',
                "LALPHANUMERIC is not False",
                "CBOOLEAN == False",
                "CCNUMERIC == 123",
                "LNUMERIC is False",
                "NUMERIC <= 456",
                "NUMERIC == 12.34",
            ],
            classification_class_constraints.expression,
        )

    def assert_variants(
        self,
        new_variability_model,
        instances_count_lookup=None,
        assert_cdb_object_id_equal=True,
    ):
        if instances_count_lookup is None:
            instances_count_lookup = self.default_instances_count_lookup

        variants = new_variability_model.Variants.Execute()
        self.assertEqual(len(variants), len(self.old_variants))

        for each in variants:
            old_variant = self.old_variants[each.id]

            # Need to check starts with because we postfix information
            self.assertTrue(each.name.startswith(old_variant.name))
            if assert_cdb_object_id_equal:
                self.assertEqual(each["cdb_object_id"], old_variant["cdb_object_id"])
            else:
                self.assertNotEqual(each["cdb_object_id"], old_variant["cdb_object_id"])

            count = instances_count_lookup.get(each.name)
            if count is not None:
                self.assertEqual(count, len(each.Instances))

    def test_migrate_old_vm_no_convert_no_variant_driving(self):
        product_to_test = Product.ByKeys(code="Car Seat")

        before_variability_models = len(VariabilityModel.Query())
        migrate_old_vm([product_to_test], self.options)
        after_variability_models = len(VariabilityModel.Query())

        self.assertEqual(before_variability_models, after_variability_models)

    def test_migrate_old_vm_success(self):
        self.maxDiff = None
        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")

        before_variability_model_ids = VariabilityModel.Query().cdb_object_id
        migrate_old_vm([product_to_test], self.options)
        after_variability_models = VariabilityModel.Query().Execute()

        self.assertEqual(
            len(before_variability_model_ids) + 1, len(after_variability_models)
        )

        new_variability_model = [
            each
            for each in after_variability_models
            if each.cdb_object_id not in before_variability_model_ids
        ][0]
        new_variability_model.Reload()

        self.assertEqual(
            product_to_test.cdb_object_id, new_variability_model.product_object_id
        )

        self.assert_classification_class(new_variability_model, product_to_test)
        self.assert_selection_conditions(new_variability_model)
        self.assert_variants(new_variability_model)

    def test_migrate_old_vm_success_keep_cdb_object_id_of_variant_off(self):
        self.options.keep_cdb_object_id_of_variant = False

        self.maxDiff = None
        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")

        before_variability_model_ids = VariabilityModel.Query().cdb_object_id
        migrate_old_vm([product_to_test], self.options)
        after_variability_models = VariabilityModel.Query().Execute()

        self.assertEqual(
            len(before_variability_model_ids) + 1, len(after_variability_models)
        )

        new_variability_model = [
            each
            for each in after_variability_models
            if each.cdb_object_id not in before_variability_model_ids
        ][0]
        new_variability_model.Reload()

        self.assertEqual(
            product_to_test.cdb_object_id, new_variability_model.product_object_id
        )

        self.assert_classification_class(new_variability_model, product_to_test)
        self.assert_selection_conditions(new_variability_model)
        self.assert_variants(new_variability_model, assert_cdb_object_id_equal=False)

    def test_migrate_old_vm_success_keep_cdb_object_id_of_property_off(self):
        self.options.keep_cdb_object_id_of_property = False

        self.maxDiff = None
        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")

        before_variability_model_ids = VariabilityModel.Query().cdb_object_id
        migrate_old_vm([product_to_test], self.options)
        after_variability_models = VariabilityModel.Query().Execute()

        self.assertEqual(
            len(before_variability_model_ids) + 1, len(after_variability_models)
        )

        new_variability_model = [
            each
            for each in after_variability_models
            if each.cdb_object_id not in before_variability_model_ids
        ][0]
        new_variability_model.Reload()

        self.assertEqual(
            product_to_test.cdb_object_id, new_variability_model.product_object_id
        )

        self.assert_classification_class(
            new_variability_model,
            product_to_test,
            assert_cdb_object_id_property_equal=False,
        )
        self.assert_selection_conditions(new_variability_model)
        self.assert_variants(new_variability_model)

    def test_migrate_old_vm_success_keep_cdb_object_id_of_enum_def_off(self):
        self.options.keep_cdb_object_id_of_enum_def = False

        self.maxDiff = None
        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")

        before_variability_model_ids = VariabilityModel.Query().cdb_object_id
        migrate_old_vm([product_to_test], self.options)
        after_variability_models = VariabilityModel.Query().Execute()

        self.assertEqual(
            len(before_variability_model_ids) + 1, len(after_variability_models)
        )

        new_variability_model = [
            each
            for each in after_variability_models
            if each.cdb_object_id not in before_variability_model_ids
        ][0]
        new_variability_model.Reload()

        self.assertEqual(
            product_to_test.cdb_object_id, new_variability_model.product_object_id
        )

        self.assert_classification_class(
            new_variability_model,
            product_to_test,
            assert_cdb_object_id_property_value_equal=False,
        )
        self.assert_selection_conditions(new_variability_model)
        self.assert_variants(new_variability_model)

    def test_migrate_old_vm_duplicate_class_codes(self):
        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")
        product_to_test_copied = Product.ByKeys(code="Old_VM_Test_Data_2")
        if product_to_test_copied is None:
            product_to_test_copied = operation(
                constants.kOperationCopy, product_to_test, code="Old_VM_Test_Data_2"
            )

        # change all numeric to alphanumeric
        for each in product_to_test_copied.AllProperties:
            if each.data_type == "numeric":
                each.data_type = "alphanumeric"

        before_variability_model_ids = VariabilityModel.Query().cdb_object_id
        migrate_old_vm([product_to_test, product_to_test_copied], self.options)
        after_variability_models = VariabilityModel.Query().Execute()

        self.assertEqual(
            len(before_variability_model_ids) + 2, len(after_variability_models)
        )

        product_to_test.Reload()
        product_to_test_copied.Reload()

        self.assertEqual(1, len(product_to_test.VariabilityModels))
        new_variability_model = product_to_test.VariabilityModels[0]

        self.assertEqual(1, len(product_to_test_copied.VariabilityModels))
        new_variability_model_copied = product_to_test_copied.VariabilityModels[0]

        self.assertEqual(
            product_to_test.cdb_object_id, new_variability_model.product_object_id
        )
        self.assertEqual(
            product_to_test_copied.cdb_object_id,
            new_variability_model_copied.product_object_id,
        )

        self.assert_classification_class(new_variability_model, product_to_test)
        self.assert_selection_conditions(new_variability_model)
        self.assert_variants(new_variability_model)

        self.assert_classification_class(
            new_variability_model_copied,
            product_to_test_copied,
            assert_cdb_object_id_property_equal=False,
            assert_cdb_object_id_property_value_equal=False,
            assert_classification_terms=False,
        )

    def test_migrate_old_vm_duplicate_class_codes_option_postfix_off(self):
        self.options.postfix_class_prop_code_with_different_type = False

        product_to_test = Product.ByKeys(code="Old_VM_Test_Data")
        product_to_test_copied = Product.ByKeys(code="Old_VM_Test_Data_2")
        if product_to_test_copied is None:
            product_to_test_copied = operation(
                constants.kOperationCopy, product_to_test, code="Old_VM_Test_Data_2"
            )

        # change all numeric to alphanumeric
        for each in product_to_test_copied.AllProperties:
            if each.data_type == "numeric":
                each.data_type = "alphanumeric"

        with self.assertRaises(ValueError) as ex:
            migrate_old_vm([product_to_test, product_to_test_copied], self.options)
        self.assertIn(
            "Code of class property is already in use with a different datatype.",
            str(ex.exception),
        )
