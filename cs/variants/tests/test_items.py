# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections
import datetime
import unittest

from cdb import ElementsError, constants, sqlapi, util
from cdb.objects import operations
from cdb.validationkit import operation
from cs.classification import api as classification_api
from cs.classification import applicability
from cs.classification.api import get_classification
from cs.classification.validation import ClassificationValidator
from cs.variants import VariantPart, api
from cs.variants.classification_checks import (
    UeExceptionChangedPropertiesNotAllowedOnItem,
    UeExceptionNotAllowedToDelete,
)
from cs.variants.classification_helper import is_variant_classification_data_equal
from cs.variants.items import _is_db_attribute_equal
from cs.variants.selection_condition import (
    SelectionCondition,
    map_expression_to_correct_attribute,
)
from cs.variants.tests import common
from cs.vp.items import Item


class TestItemsWithFloat(common.VariantsTestCaseWithFloat):
    def setUp(self):
        super().setUp()
        self.variant = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )
        # Reset caches in cs.classification
        ClassificationValidator.reload_all()

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

    def test__check_item_classification_change_allowed__same_classification(self):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)

        classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_not_allowed__delete_classification_class(
        self,
    ):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["assigned_classes"].remove(
            self.variability_model.ClassificationClass.code
        )

        classification_api.rebuild_classification(new_part_classification)
        with self.assertRaises(UeExceptionNotAllowedToDelete):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_allowed__delete_other_class(self):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_class = self.create_new_class()
        classification_api.rebuild_classification(
            new_part_classification, new_classes=[new_class.code]
        )
        classification_api.update_classification(new_part, new_part_classification)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["assigned_classes"].remove(new_class.code)
        classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_not_allowed__changed_for_variant_classification_float(
        self,
    ):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "CS_VARIANTS_TEST_CLASS_%s" % self.prop_float
        ][0]["value"] = common.get_float_value(
            2, unit_label="m", float_value_normalized=2
        )

        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_not_allowed__changed_for_variant_classification(
        self,
    ):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"]["CS_VARIANTS_TEST_CLASS_%s" % self.prop1][
            0
        ]["value"] = "VALUE2"

        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_allowed__add_and_change_non_variant_class(
        self,
    ):
        new_class = self.create_new_class(for_variants=False)

        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification = classification_api.rebuild_classification(
            new_part_classification, new_classes=[new_class.code]
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "abc"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "abc",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "xyz"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "xyz",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_not_allowed__add_and_change_non_variant_class(
        self,
    ):
        new_class = self.create_new_class(for_variants=False)

        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification = classification_api.rebuild_classification(
            new_part_classification, new_classes=[new_class.code]
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "abc"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "abc",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "xyz"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "xyz",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        # This will be not allowed
        new_part_classification["properties"]["CS_VARIANTS_TEST_CLASS_%s" % self.prop1][
            0
        ]["value"] = "VALUE2"
        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "123"

        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_allowed__add_and_change_new_variant_class(
        self,
    ):
        new_class = self.create_new_class(for_variants=True)

        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification = classification_api.rebuild_classification(
            new_part_classification, new_classes=[new_class.code]
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "abc"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "abc",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "xyz"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "xyz",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_not_allowed__add_and_change_new_variant_class(
        self,
    ):
        new_class = self.create_new_class(for_variants=True)

        new_part = api.instantiate_part(self.variant, self.maxbom)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification = classification_api.rebuild_classification(
            new_part_classification, new_classes=[new_class.code]
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "abc"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "abc",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "xyz"
        classification_api.update_classification(new_part, new_part_classification)
        new_part_classification = classification_api.get_classification(new_part)
        self.assertEqual(
            "xyz",
            new_part_classification["properties"][
                "%s_%s" % (new_class.code, self.new_prop1)
            ][0]["value"],
        )

        # This will be not allowed
        new_part_classification["properties"]["CS_VARIANTS_TEST_CLASS_%s" % self.prop1][
            0
        ]["value"] = "VALUE2"
        new_part_classification["properties"][
            "%s_%s" % (new_class.code, self.new_prop1)
        ][0]["value"] = "123"

        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_allowed__non_variant_prop(self):
        variability_class = self.variability_model.ClassificationClass
        self.new_prop = "NEW_PROP_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_prop, ["ABC"])]),
            variability_class,
            for_variants=False,
        )
        variant_classification = classification_api.get_classification(
            self.variant, pad_missing_properties=True
        )
        variant_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "ABC"
        classification_api.update_classification(self.variant, variant_classification)

        new_part = api.instantiate_part(self.variant, self.maxbom)
        common.check_classification(new_part, variant_classification["properties"])

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "XYZ"
        classification_api.update_classification(new_part, new_part_classification)

        common.check_classification(new_part, new_part_classification["properties"])

    def test__check_item_classification_change_not_allowed__variant_prop_afterwards(
        self,
    ):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        variability_class = self.variability_model.ClassificationClass
        self.new_prop = "NEW_PROP_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_prop, ["ABC"])]),
            variability_class,
            for_variants=True,
        )
        variant_classification = classification_api.get_classification(
            self.variant, pad_missing_properties=True
        )
        variant_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "ABC"
        classification_api.update_classification(self.variant, variant_classification)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "ABC"
        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "XYZ"
        with self.assertRaises(UeExceptionChangedPropertiesNotAllowedOnItem):
            classification_api.update_classification(new_part, new_part_classification)

    def test__check_item_classification_change_allowed__non_variant_prop_afterwards(
        self,
    ):
        new_part = api.instantiate_part(self.variant, self.maxbom)

        variability_class = self.variability_model.ClassificationClass
        self.new_prop = "NEW_PROP_%s" % self.timestamp
        common.create_and_add_props_to_class(
            collections.OrderedDict([(self.new_prop, ["ABC"])]),
            variability_class,
            for_variants=False,
        )
        variant_classification = classification_api.get_classification(
            self.variant, pad_missing_properties=True
        )
        variant_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "ABC"
        classification_api.update_classification(self.variant, variant_classification)

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "ABC"
        classification_api.update_classification(new_part, new_part_classification)

        common.check_classification(new_part, new_part_classification["properties"])

        new_part_classification = classification_api.get_classification(new_part)
        new_part_classification["properties"][
            "%s_%s" % (variability_class.code, self.new_prop)
        ][0]["value"] = "XYZ"
        classification_api.update_classification(new_part, new_part_classification)

        common.check_classification(new_part, new_part_classification["properties"])

    def test_update_variant_part_name(self):
        start_names = {
            "fr": "un test avec 40 caractères doner kebab§$",
            "en": "a test with 40 characters doner kebab§$%",
            "zh": "一个 40 个字符的测试烤肉串§$%&~#一个 40 个字符的测试烤肉串§$%&",
            "pt": "um teste com 40 caracteres doner kebab§$",
            "tr": "40 karakterden oluşan bir döner kebabı§$",
            "de": "ein test mit 40 zeichen Dönerspieß§$%&~#",
            "ko": "40자 테스트 doner kebab§$%&~#40자 테스트 doner k",
            "it": "un test con doner kebab di 40 caratteri§",
            "pl": "test z 40 znakami doner kebab§$%&~#12345",
            "cs": "test se 40 znaky doner kebab§$%&~#123456",
            "ja": "40文字のドネルケバブを使ったテスト§$％＆〜＃40文字のドネルケバブを使ったテ",
            "es": "una prueba con 40 caracteres doner kebab",
        }
        for lang_key, lang_entry in start_names.items():
            self.assertEqual(
                40,
                len(lang_entry),
                "'{0}' is not exactly 40 chars long: {1}".format(
                    lang_key, len(lang_entry)
                ),
            )
            self.subassembly.SetLocalizedValue("i18n_benennung", lang_key, lang_entry)

        self.subassembly.update_variant_part_name(self.variant)

        result_names = self.subassembly.GetLocalizedValues("i18n_benennung")
        for lang_key, lang_entry in start_names.items():
            result_entry = result_names[lang_key]
            result_entry_without_var_prefix = result_entry[5:]

            self.assertTrue(lang_entry.startswith(result_entry_without_var_prefix))

    def test_delete_max_bom_without_instanced_parts(self):
        operation(constants.kOperationDelete, self.maxbom)

    def test_delete_max_bom_with_instanced_parts(self):
        api.instantiate_part(self.variant, self.maxbom)
        with self.assertRaises(ElementsError) as assert_raises:
            operation(constants.kOperationDelete, self.maxbom)

        the_exception = assert_raises.exception
        expected_message = "{0}".format(
            util.CDBMsg(
                util.CDBMsg.kFatal, "cs_variants_delete_max_bom_with_instanced_parts"
            )
        )
        self.assertIn(expected_message, str(the_exception))


class TestItemsFunctions(unittest.TestCase):
    def test__is_db_attribute_equal__equals(self):
        source_attributes = ["abc", 123, 123.456, datetime.datetime.min, None]
        copied_attributes = ["abc", 123, 123.456, datetime.datetime.min, None]

        for source_index, source_attribute in enumerate(source_attributes):
            for copied_index, copied_attribute in enumerate(copied_attributes):
                self.assertEqual(
                    _is_db_attribute_equal(source_attribute, copied_attribute),
                    source_index == copied_index,
                )

    def test__is_db_attribute_equal__non_equals(self):
        source_attributes = ["abc", 123, 123.456, datetime.datetime.max, None]
        copied_attributes = ["xyz", 456, 456.123, datetime.datetime.min, None]

        for source_index, source_attribute in enumerate(source_attributes):
            for copied_index, copied_attribute in enumerate(copied_attributes):
                self.assertEqual(
                    _is_db_attribute_equal(source_attribute, copied_attribute),
                    source_index == 4 and copied_index == 4,
                )


class TestItems(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp(with_occurrences=with_occurrences)
        self.variant = common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        )

    def test_instantiation_operation(self):
        next_item_number = "{0}".format(
            sqlapi.SQLinteger(
                sqlapi.SQLselect(
                    "counter_curr FROM cdb_counter WHERE counter_name='part_seq'"
                ),
                0,
                0,
            )
            + 1
        )

        operation(
            "cs_variant_instantiate",
            self.variant,
            preset={"max_bom_id": self.maxbom.cdb_object_id},
        )

        instance = Item.ByKeys(teilenummer=next_item_number)
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

        variant_part = VariantPart.KeywordQuery(
            variability_model_id=self.variant.variability_model_id,
            variant_id=self.variant.id,
            maxbom_teilenummer=self.maxbom.teilenummer,
            maxbom_t_index=self.maxbom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )
        self.assertGreater(
            len(variant_part),
            0,
            "The instance has not been assigned to the variant/maxbom",
        )

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

    def test_instantiation_operation_with_selection_condition_with_missing_prop(self):
        self.selection_condition.Update(expression="missing_prop == 'VALUE1'")

        with self.assertRaises(ElementsError) as assert_raises:
            operation(
                "cs_variant_instantiate",
                self.variant,
                preset={"max_bom_id": self.maxbom.cdb_object_id},
            )

        self.assertIn("missing_prop", str(assert_raises.exception))

    def test_reinstantiate_operation(self):
        instance = api.instantiate_part(self.variant, self.maxbom)
        self.assertEqual(1, len(instance.Components))

        comp = self.maxbom.Components[0]
        common.generate_selection_condition(self.variability_model, comp, "1 == 0")

        operation("cs_variant_reinstantiate_part", instance)
        self.assertEqual(
            0, len(instance.Components), "The product structure has not been recomputed"
        )

    def test_reinstantiate_operation_with_selection_condition_with_missing_prop(self):
        instance = api.instantiate_part(self.variant, self.maxbom)
        self.assertEqual(1, len(instance.Components))

        comp = self.maxbom.Components[0]
        SelectionCondition.CreateNoResult(
            variability_model_id=self.variability_model["cdb_object_id"],
            ref_object_id=comp["cdb_object_id"],
            **map_expression_to_correct_attribute("missing_prop == 'VALUE1'")
        )

        with self.assertRaises(ElementsError) as assert_raises:
            operation("cs_variant_reinstantiate_part", instance)

        self.assertIn("missing_prop", str(assert_raises.exception))
