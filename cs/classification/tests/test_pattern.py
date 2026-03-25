
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/import unittest

import unittest
import re
import cdb

from cdb import ue, ElementsError
from cdb.constants import kOperationNew
from cdb.objects import operations
from cdb.testcase import RollbackTestCase
from cs.classification import applicability, catalog, classes
from cs.classification.catalog import Property, TextPropertyValue
from cs.classification.pattern import Pattern


class TestPattern(RollbackTestCase):

    def setUp(self):
        super(TestPattern, self).setUp()

    def test_succesful_expected_regex(self):
        input_str = "CCAA----CCCCCAAA"
        output_expected = r"^..[^\W0-9_][^\W0-9_]----.....[^\W0-9_][^\W0-9_][^\W0-9_]$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)

    def test_failed_expected_regex(self):
        input_str = "CCAA"
        output_expected = r"^..[^\W0-9_][^\W0-9_]"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertNotEqual(output_expected, output_generated)

    def test_failed_user_input(self):
        input_str = "CCAAf"
        with self.assertRaisesRegex(ue.Exception, ".*tiges Zeichen in der Schablone: f.*"):
            output_generated = Pattern.create_reg_ex(input_str)

    def test_all_characters(self):
        all_char = ['!', '"', '#', '$', '%', "'", '(', ')', '*', ',', '.', '/', ';',
                    '<', '=', '>', '?', '@', '[', ']', '^', "`", '{', '|', '}', '~']

        alpha_char = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                      'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
                      'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                      'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']

        not_alpha_char = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '_']

        num_char = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

        sign = ['+', '-']

        separator = ['&', '+', '-', "\\", ":", "_"]

        separator_no_sign = ['&', "\\", ":", "_"]

        # Test all alphanumeric
        input_str = "A"
        output_expected = r"^[^\W0-9_]$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)
        regex = re.compile(output_generated)

        # Expected match
        for symb in alpha_char:
            match = regex.match(symb)
            self.assertEqual(match.group(0), symb)

        # Expected not match
        for symb in (not_alpha_char + all_char + sign + separator):
            match = regex.match(symb)
            self.assertEqual(match, None)

        # Test numeric
        input_str = "N"
        output_expected = r"^\d$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)
        regex = re.compile(output_generated)

        # Expected match
        for symb in num_char:
            match = regex.match(symb)
            self.assertEqual(match.group(0), symb)

        # Expected not match
        for symb in (alpha_char + all_char + sign + separator):
            match = regex.match(symb)
            self.assertEqual(match, None)

        # Test char
        input_str = "C"
        output_expected = r"^.$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)
        regex = re.compile(output_generated)

        # Expected match
        for symb in (not_alpha_char + all_char + alpha_char + sign + separator):
            match = regex.match(symb)
            self.assertEqual(match.group(0), symb)

        # Test sign
        input_str = "V"
        output_expected = r"^[+-]$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)
        regex = re.compile(output_generated)

        # Expected match
        for symb in sign:
            match = regex.match(symb)
            self.assertEqual(match.group(0), symb)

        # Expected not match
        for symb in (not_alpha_char + all_char + alpha_char + separator_no_sign):
            match = regex.match(symb)
            self.assertEqual(match, None)

    def test_failed_user_input_form(self):
        expected_error = "ltiges Zeichen in der Schablone"
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "s"
            }
        with self.assertRaises(ElementsError) as e:
            # Create new catalog property
            catalog_prop = operations.operation(
                cdb.constants.kOperationNew,
                catalog.TextProperty,
                **args_cat
                )
        self.assertIn(expected_error, str(e.exception))

    def test_validate_regex(self):
        input_str = "A&N&A"
        output_expected = r"^[^\W0-9_]&\d&[^\W0-9_]$"
        output_generated = Pattern.create_reg_ex(input_str)
        self.assertEqual(output_expected, output_generated)

        regex = re.compile(output_generated)
        correct_test_string = "a&1&a"
        self.assertEqual(regex.match(correct_test_string).group(0), correct_test_string)

        incorrect_test_string = "a&1"
        self.assertEqual(regex.match(incorrect_test_string), None)

    def test_conflictive_prop_value(self):
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "C"
            }
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextProperty,
            **args_cat
            )
        # Arguments for new property value
        args_prop = {
            "property_object_id": catalog_prop.cdb_object_id,
            "is_active": 1,
            "text_value": "error"
        }
        expected_error = "Die Eingabe stimmt nicht mit dem Format der Schablone überein"
        with self.assertRaises(ElementsError) as e:
            prop_value = operations.operation(
                cdb.constants.kOperationNew,
                catalog.TextPropertyValue,
                **args_prop
            )
        self.assertIn(expected_error, str(e.exception))

    def test_correct_prop_value(self):
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "C"
            }
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextProperty,
            **args_cat
            )
        # Arguments for new property value
        args_prop = {
            "property_object_id": catalog_prop.cdb_object_id,
            "is_active": 1,
            "text_value": "a"
        }
        prop_value = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextPropertyValue,
            **args_prop
        )
        self.assertEqual(prop_value.text_value, "a")

    def test_edit_cat_pattern(self):
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "C"
            }
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextProperty,
            **args_cat
            )
        # Change the pattern
        args_new = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "CA"
            }

        operations.operation(
            cdb.constants.kOperationModify,
            catalog_prop,
            **args_new
            )
        self.assertEqual(catalog_prop.regex, r"^.[^\W0-9_]$")

    def test_wrong_prop_in_class(self):
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "C"
            }
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextProperty,
            **args_cat
            )
        catalog_prop.ChangeState(catalog.Property.RELEASED)

        # Arguments for new property class
        args_class = {
            "code": "NT_PROP_CLASS_CODE",
            "name_en": "NT_PROP_CLASS_NAME",
            }
        prop_class = operations.operation(
            cdb.constants.kOperationNew,
            classes.ClassificationClass,
            **args_class
        )

        prop_class = classes.ClassProperty.NewPropertyFromCatalog(catalog_prop, prop_class.cdb_object_id)

        expected_error = "Die Eingabe stimmt nicht mit dem Format der Schablone überein"
        # Arguments for new property value
        args_prop = {
            "property_object_id": prop_class.cdb_object_id,
            "is_active": 1,
            "text_value": "aaa"
        }
        with self.assertRaises(ElementsError) as e:
            prop_value = operations.operation(
                cdb.constants.kOperationNew,
                catalog.TextPropertyValue,
                **args_prop
            )
        self.assertIn(expected_error, str(e.exception))

    def test_propagate_in_class(self):
        # Arguments for new catalog property
        args_cat = {
            "code": "NT_CAT_PROP_CODE",
            "name_en": "NT_CAT_PROP_NAME",
            "pattern": "C"
            }
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextProperty,
            **args_cat
            )
        catalog_prop.ChangeState(catalog.Property.RELEASED)

        # Arguments for new property class
        args_class = {
            "code": "NT_PROP_CLASS_CODE",
            "name_en": "NT_PROP_CLASS_NAME",
            }
        prop_class = operations.operation(
            cdb.constants.kOperationNew,
            classes.ClassificationClass,
            **args_class
        )

        prop_class = classes.ClassProperty.NewPropertyFromCatalog(catalog_prop, prop_class.cdb_object_id)

        # Arguments for new property value
        args_prop = {
            "property_object_id": prop_class.cdb_object_id,
            "is_active": 1,
            "text_value": "a"
        }
        class_prop_value = operations.operation(
            cdb.constants.kOperationNew,
            catalog.TextPropertyValue,
            **args_prop
        )
        # Change the pattern
        args_modify = {
            "pattern": "CA"
        }
        operations.operation(
            cdb.constants.kOperationModify,
            catalog_prop,
            **args_modify
        )
        catalog_prop.Reload()
        self.assertEqual(catalog_prop.regex, r"^.[^\W0-9_]$")
        prop_class.Reload()
        self.assertEqual(prop_class.regex, catalog_prop.regex)

        # Check pattern in class property value
        # Arguments for changes on property value
        args_modify = {
            "text_value": "b",
            "is_active": 1,
        }

        expected_error = "Die Eingabe stimmt nicht mit dem Format der Schablone überein"
        with self.assertRaises(ElementsError) as e:
            operations.operation(
                cdb.constants.kOperationModify,
                class_prop_value,
                **args_modify
            )
        self.assertIn(expected_error, str(e.exception))

        # Modify an inactive one
        # Arguments for changes on property value
        args_modify = {
            "text_value": "b",
            "is_active": 0,
        }

        operations.operation(
            cdb.constants.kOperationModify,
            class_prop_value,
            **args_modify
        )
        self.assertEqual(class_prop_value.text_value, "b")

    def test_validate_text_prop_value_fail(self):
        # Locate catalog property
        cat_prop = Property.KeywordQuery(code="TEST_PATTERN_PROP")[0]

        # Arguments for new property value
        args_prop = {
            "property_object_id": cat_prop.cdb_object_id,
            "is_active": 1,
            "text_value": "non compliant value"
        }
        expected_error = "Die Eingabe stimmt nicht mit dem Format der Schablone überein"
        with self.assertRaises(ElementsError) as e:
            prop_value = operations.operation(
                cdb.constants.kOperationNew,
                TextPropertyValue,
                **args_prop
            )
        self.assertIn(expected_error, str(e.exception))

    def test_validate_text_prop_value_success(self):
        # Locate catalog property
        cat_prop = Property.KeywordQuery(code="TEST_PATTERN_PROP")[0]

        # Arguments for new property value
        args_prop = {
            "property_object_id": cat_prop.cdb_object_id,
            "is_active": 1,
            "text_value": "f44g&h33s_j67j"
        }

        prop_value = operations.operation(
            cdb.constants.kOperationNew,
            TextPropertyValue,
            **args_prop
        )

        self.assertEqual(prop_value.text_value, "f44g&h33s_j67j")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
