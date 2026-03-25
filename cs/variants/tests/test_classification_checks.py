#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import collections

import mock

from cdb import constants
from cdb.objects import operations
from cs.classification import api as classification_api
from cs.classification import applicability, catalog, classes
from cs.variants import api
from cs.variants.classification_checks import (
    UeExceptionChangedPropertiesBasedOnNewestInstancedItem,
    UeExceptionForDuplicateVariants,
    UeExceptionNotAllowedToDelete,
)
from cs.variants.tests import common


class TestClassificationChecks(common.VariantsTestCaseWithFloat):
    def setUp(self):
        super().setUp()

        # the variant will match on the first component (for the subassembly)
        # but will not match on the on subassembly's component
        comp = self.maxbom.Components[0]
        expression = "CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'" % self.prop1
        common.generate_selection_condition(self.variability_model, comp, expression)

        self.variant = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
            name="TestClassificationChecks_Variant",
        )

        self.update_variant_classification_data()

    def update_variant_classification_data(self):
        self.variant_classification_data = classification_api.get_classification(
            self.variant
        )

    def change_prop_value(self, prop_name, new_value, classification_data=None):
        if classification_data is None:
            classification_data = self.variant_classification_data

        for each in classification_data["properties"].keys():
            if each.endswith(prop_name):
                if (
                    classification_data["properties"][each][0]["property_type"]
                    == "float"
                ):
                    if isinstance(new_value, dict):
                        classification_data["properties"][each][0]["value"] = new_value
                    else:
                        classification_data["properties"][each][0]["value"][
                            "float_value"
                        ] = float(new_value)
                else:
                    classification_data["properties"][each][0]["value"] = new_value
                break

    def create_prop(self, initial_value, for_variants=True):
        classification_class = self.variability_model.ClassificationClass
        prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        props = collections.OrderedDict([(prop, [initial_value])])
        common.create_and_add_props_to_class(
            props, classification_class, for_variants=for_variants
        )
        return prop

    def create_new_class(self, for_variants=True):
        self.new_prop1 = "NEW_PROP1_%s" % self.timestamp
        self.new_prop2 = "NEW_PROP2_%s" % self.timestamp
        props = collections.OrderedDict(
            [
                (self.new_prop1, ["VALUE1", "VALUE2"]),
                (self.new_prop2, ["VALUE1", "VALUE2"]),
            ]
        )
        clazz = common.generate_class_with_props(
            props, for_variants=for_variants, code="NEW_CLASS"
        )

        for classname in ["cs_variant", "part"]:
            applicabilities = clazz.Applicabilities.KeywordQuery(dd_classname=classname)

            if not applicabilities:
                operations.operation(
                    constants.kOperationNew,
                    applicability.ClassificationApplicability,
                    classification_class_id=clazz.cdb_object_id,
                    dd_classname=classname,
                    is_active=1,
                    write_access_obj="save",
                )

        return clazz

    def test_check_variant_classification_change_allowed__delete_class(self):
        self.variant_classification_data["assigned_classes"].remove(
            self.variability_model.ClassificationClass.code
        )
        classification_api.rebuild_classification(self.variant_classification_data)

        with self.assertRaises(UeExceptionNotAllowedToDelete):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__delete_new_class_not_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=False)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.variant_classification_data["assigned_classes"].remove(new_class.code)
        classification_api.rebuild_classification(self.variant_classification_data)

        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )
        self.update_variant_classification_data()
        self.assertNotIn(
            new_class.code, self.variant_classification_data["assigned_classes"]
        )

    def test_check_variant_classification_change_allowed__delete_new_class_with_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=True)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.variant_classification_data["assigned_classes"].remove(new_class.code)
        classification_api.rebuild_classification(self.variant_classification_data)

        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )
        self.update_variant_classification_data()
        self.assertNotIn(
            new_class.code, self.variant_classification_data["assigned_classes"]
        )

    def test_check_variant_classification_change_allowed__same_classification(self):
        api.instantiate_part(self.variant, self.maxbom)
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__add_new_class_not_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=False)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_new_class_prop_not_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=False)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_prop1, "123")
        self.change_prop_value(self.new_prop2, "456")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__add_new_class_with_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=True)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_new_class_prop_with_for_variants(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        new_class = self.create_new_class(for_variants=True)

        classification_api.rebuild_classification(
            self.variant_classification_data, new_classes=[new_class.code]
        )
        self.change_prop_value(self.new_prop1, "ABC")
        self.change_prop_value(self.new_prop2, "XYZ")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_prop1, "123")
        self.change_prop_value(self.new_prop2, "456")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_float_unit_but_same_value(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)
        self.change_prop_value(
            self.prop_float, common.get_float_value(0.2, unit_label="m")
        )

        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_float_unit_and_value(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)
        self.change_prop_value(
            self.prop_float, common.get_float_value(0.3, unit_label="m")
        )

        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__new_prop1_value(self):
        api.instantiate_part(self.variant, self.maxbom)
        self.change_prop_value(self.prop1, "NEW1")

        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__new_prop1_and_prop2_value(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)
        self.change_prop_value(self.prop1, "NEW1")
        self.change_prop_value(self.prop2, "NEW2")

        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_float_value(self):
        api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_float_prop, [4.2])]),
            classification_class,
            for_variants=True,
        )
        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 4.2)
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 123)
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_new_float_value_with_instantiate(
        self,
    ):
        classification_class = self.variability_model.ClassificationClass
        self.new_float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_float_prop, [4.2])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 4.2)
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.instantiate_part(self.variant, self.maxbom)

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 123)
        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_float_value_with_instantiate2(
        self,
    ):
        with mock.patch(
            "cs.variants.api.helpers.is_part_classification_available",
            return_value=False,
        ) as mock_instantiations_part_classification_available:
            with mock.patch(
                "cs.variants.classification_checks.is_part_classification_available",
                return_value=False,
            ) as mock_classification_checks_part_classification_available:
                classification_class = self.variability_model.ClassificationClass
                self.new_float_prop = (
                    "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
                )
                common.create_and_add_props_to_class(
                    collections.OrderedDict([(self.new_float_prop, [4.2])]),
                    classification_class,
                    for_variants=True,
                )

                self.update_variant_classification_data()
                self.change_prop_value(self.new_float_prop, 4.2)
                classification_api.update_classification(
                    self.variant, self.variant_classification_data
                )
                mock_classification_checks_part_classification_available.assert_not_called()

                api.instantiate_part(self.variant, self.maxbom)

                self.update_variant_classification_data()
                self.change_prop_value(self.new_float_prop, 123)

                mock_instantiations_part_classification_available.assert_called()
                with self.assertRaises(
                    UeExceptionChangedPropertiesBasedOnNewestInstancedItem
                ):
                    classification_api.update_classification(
                        self.variant, self.variant_classification_data
                    )
                mock_classification_checks_part_classification_available.assert_called()

    def test_check_variant_classification_change_allowed__change_new_float_value_with_reinstantiate(
        self,
    ):
        instantiated_part = api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_float_prop, [4.2])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 4.2)
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.reinstantiate_parts([instantiated_part])

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 123)
        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_text_value(self):
        api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_new_text_value_instantiate(
        self,
    ):
        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.instantiate_part(self.variant, self.maxbom)

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_text_value_reinstantiate(
        self,
    ):
        instantiated_part = api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.reinstantiate_parts([instantiated_part])

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_text_not_for_variants_value(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=False,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed__change_new_text_not_for_variants_value_instantiate(
        self,
    ):
        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=False,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.instantiate_part(self.variant, self.maxbom)

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allowed_change_new_text_not_for_variants_value_reinstantiate(
        self,
    ):
        instantiated_part = api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=False,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

        api.reinstantiate_parts([instantiated_part])

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW2")
        classification_api.update_classification(
            self.variant, self.variant_classification_data
        )

    def test_check_variant_classification_change_allow_change_new_text_not_for_variants_value_reinstantiate2(
        self,
    ):
        with mock.patch(
            "cs.variants.api.helpers.is_part_classification_available",
            return_value=False,
        ) as mock_instantiations_part_classification_available:
            with mock.patch(
                "cs.variants.classification_checks.is_part_classification_available",
                return_value=False,
            ) as mock_classification_checks_part_classification_available:
                instantiated_part = api.instantiate_part(self.variant, self.maxbom)

                classification_class = self.variability_model.ClassificationClass
                self.new_text_prop = (
                    "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
                )
                common.create_and_add_props_to_class(
                    collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
                    classification_class,
                    for_variants=False,
                )

                self.update_variant_classification_data()
                self.change_prop_value(self.new_text_prop, "NEW")
                mock_classification_checks_part_classification_available.assert_not_called()
                classification_api.update_classification(
                    self.variant, self.variant_classification_data
                )
                mock_classification_checks_part_classification_available.assert_called()

                api.reinstantiate_parts([instantiated_part])

                self.update_variant_classification_data()
                self.change_prop_value(self.new_text_prop, "NEW2")
                classification_api.update_classification(
                    self.variant, self.variant_classification_data
                )
                mock_instantiations_part_classification_available.assert_called()
                mock_classification_checks_part_classification_available.assert_called()

    def test_check_variant_classification_change_allowed__change_new_float_value_and_existing(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_float_prop, [4.2])]),
            classification_class,
            for_variants=True,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_float_prop, 4.2)
        self.change_prop_value(self.prop1, "NEW1")

        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_check_variant_classification_change_allowed__change_new_text_value_and_existing(
        self,
    ):
        api.instantiate_part(self.variant, self.maxbom)

        classification_class = self.variability_model.ClassificationClass
        self.new_text_prop = "CS_VARIANTS_TEST_TEXT_PROPERTY_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_text_prop, ["NEW"])]),
            classification_class,
            for_variants=False,
        )

        self.update_variant_classification_data()
        self.change_prop_value(self.new_text_prop, "NEW")
        self.change_prop_value(self.prop1, "NEW1")

        with self.assertRaises(UeExceptionChangedPropertiesBasedOnNewestInstancedItem):
            classification_api.update_classification(
                self.variant, self.variant_classification_data
            )

    def test_can_not_save_duplicate_variant_with_props(self):
        with self.assertRaises(UeExceptionForDuplicateVariants):
            common.generate_variant(
                self.variability_model,
                {
                    self.prop1: "VALUE1",
                    self.prop2: "VALUE2",
                    self.prop_float: common.get_float_value(200, unit_label="mm"),
                },
            )

    def test_can_save_non_duplicate_variant_with_props(self):
        common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

    def test_add_duplicate_other_class_values_to_variant_with_for_variants(self):
        variant1 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE2",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        new_class = self.create_new_class(for_variants=True)

        variant1_class_data = classification_api.get_classification(variant1)
        variant2_class_data = classification_api.get_classification(variant2)

        classification_api.rebuild_classification(
            variant1_class_data, new_classes=[new_class.code]
        )
        classification_api.rebuild_classification(
            variant2_class_data, new_classes=[new_class.code]
        )
        self.change_prop_value(
            self.new_prop1, "ABC", classification_data=variant1_class_data
        )
        self.change_prop_value(
            self.new_prop2, "XYZ", classification_data=variant1_class_data
        )
        self.change_prop_value(
            self.new_prop1, "ABC", classification_data=variant2_class_data
        )
        self.change_prop_value(
            self.new_prop2, "XYZ", classification_data=variant2_class_data
        )

        classification_api.update_classification(variant1, variant1_class_data)
        classification_api.update_classification(variant2, variant2_class_data)

    def test_add_duplicate_other_class_values_to_variant_not_for_variants(self):
        variant1 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE2",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        new_class = self.create_new_class(for_variants=False)

        variant1_class_data = classification_api.get_classification(variant1)
        variant2_class_data = classification_api.get_classification(variant2)

        classification_api.rebuild_classification(
            variant1_class_data, new_classes=[new_class.code]
        )
        classification_api.rebuild_classification(
            variant2_class_data, new_classes=[new_class.code]
        )
        self.change_prop_value(
            self.new_prop1, "ABC", classification_data=variant1_class_data
        )
        self.change_prop_value(
            self.new_prop2, "XYZ", classification_data=variant1_class_data
        )
        self.change_prop_value(
            self.new_prop1, "ABC", classification_data=variant2_class_data
        )
        self.change_prop_value(
            self.new_prop2, "XYZ", classification_data=variant2_class_data
        )

        classification_api.update_classification(variant1, variant1_class_data)
        classification_api.update_classification(variant2, variant2_class_data)

    def test_add_new_prop_for_variants_and_give_same_value(self):
        variant1 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE2",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        prop = self.create_prop(10, for_variants=True)
        prop_class_code = "{0}_{1}".format(
            self.variability_model.ClassificationClass.code, prop
        )

        variant1_class_data = classification_api.get_classification(variant1)
        variant2_class_data = classification_api.get_classification(variant2)

        self.change_prop_value(
            prop_class_code, 10, classification_data=variant1_class_data
        )
        self.change_prop_value(
            prop_class_code, 10, classification_data=variant2_class_data
        )

        classification_api.update_classification(variant1, variant1_class_data)
        classification_api.update_classification(variant2, variant2_class_data)

    def test_add_new_prop_not_for_variants_and_give_same_value(self):
        variant1 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE2",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        prop = self.create_prop(10, for_variants=False)
        prop_class_code = "{0}_{1}".format(
            self.variability_model.ClassificationClass.code, prop
        )

        variant1_class_data = classification_api.get_classification(variant1)
        variant2_class_data = classification_api.get_classification(variant2)

        self.change_prop_value(
            prop_class_code, 10, classification_data=variant1_class_data
        )
        self.change_prop_value(
            prop_class_code, 10, classification_data=variant2_class_data
        )

        classification_api.update_classification(variant1, variant1_class_data)
        classification_api.update_classification(variant2, variant2_class_data)

    def test_add_new_prop_for_variants_and_give_same_value_and_also_old_to_duplicate(
        self,
    ):
        variant1 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        variant2 = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE2",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(300, unit_label="mm"),
            },
        )

        prop = self.create_prop(10, for_variants=True)
        prop_class_code = "{0}_{1}".format(
            self.variability_model.ClassificationClass.code, prop
        )

        variant1_class_data = classification_api.get_classification(variant1)
        variant2_class_data = classification_api.get_classification(variant2)

        self.change_prop_value(
            prop_class_code, 10, classification_data=variant1_class_data
        )
        self.change_prop_value(
            prop_class_code, 10, classification_data=variant2_class_data
        )
        self.change_prop_value(
            self.prop1, "VALUE1", classification_data=variant2_class_data
        )

        classification_api.update_classification(variant1, variant1_class_data)
        with self.assertRaises(UeExceptionForDuplicateVariants):
            classification_api.update_classification(variant2, variant2_class_data)

    def test_can_not_save_duplicate_variant_with_int_prop(self):
        prop = self.create_prop(10)
        common.generate_variant(
            self.variability_model,
            {self.prop1: "VALUE1", self.prop2: "VALUE2", prop: 10},
        )

        with self.assertRaises(UeExceptionForDuplicateVariants):
            common.generate_variant(
                self.variability_model,
                {self.prop1: "VALUE1", self.prop2: "VALUE2", prop: 10},
            )

    def test_can_not_save_duplicate_variant_with_props_with_only_different_unit(self):
        with self.assertRaises(UeExceptionForDuplicateVariants):
            common.generate_variant(
                self.variability_model,
                {
                    self.prop1: "VALUE1",
                    self.prop2: "VALUE2",
                    self.prop_float: common.get_float_value(0.2, unit_label="m"),
                },
            )

    def test_can_save_non_duplicate_variant_with_props_with_different_unit_and_value(
        self,
    ):
        common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(0.3, unit_label="m"),
            },
        )

    def test_can_save_not_duplicate_variant_with_int_prop(self):
        prop = self.create_prop(10)
        common.generate_variant(
            self.variability_model,
            {self.prop1: "VALUE1", self.prop2: "VALUE2", prop: 10},
        )

        common.generate_variant(
            self.variability_model,
            {self.prop1: "VALUE1", self.prop2: "VALUE2", prop: 11},
        )

    def test_can_not_save_duplicate_variant_with_float_prop(self):
        classification_class = self.variability_model.ClassificationClass
        float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(values=[], code=float_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                float_prop: {
                    "unit_object_id": catalog_prop.unit_object_id,
                    "float_value": 10.1,
                },
            },
        )

        with self.assertRaises(UeExceptionForDuplicateVariants):
            common.generate_variant(
                self.variability_model,
                {
                    self.prop1: "VALUE1",
                    self.prop2: "VALUE2",
                    float_prop: {
                        "unit_object_id": catalog_prop.unit_object_id,
                        "float_value": 10.1,
                    },
                },
            )
