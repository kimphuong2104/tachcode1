import unittest

from cs.variants.classification_helper import calculate_classification_value_checksum
from cs.variants.tests import common


class TestClassificationHelper(unittest.TestCase):
    def test_calculate_classification_value_checksum_text_(self):
        classification_data = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE")
        }
        checksum = calculate_classification_value_checksum(classification_data)
        self.assertIsInstance(checksum, str)
        assert checksum, "Checksum should contain chars"

    def test_calculate_classification_value_checksum_float(self):
        classification_data = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23)
        }
        checksum = calculate_classification_value_checksum(classification_data)
        self.assertIsInstance(checksum, str)
        assert checksum, "Checksum should contain chars"

    def test_calculate_classification_value_checksum_int(self):
        classification_data = {
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123)
        }
        checksum = calculate_classification_value_checksum(classification_data)
        self.assertIsInstance(checksum, str)
        assert checksum, "Checksum should contain chars"

    def test_calculate_classification_value_checksum_bool(self):
        classification_data = {
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False)
        }
        checksum = calculate_classification_value_checksum(classification_data)
        self.assertIsInstance(checksum, str)
        assert checksum, "Checksum should contain chars"

    def test_calculate_classification_value_checksum_text_equal(self):
        classification_data1 = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE")
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE")
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_text_not_equal(self):
        classification_data1 = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE")
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE2")
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertNotEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_float_equal(self):
        classification_data1 = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_float_not_equal(self):
        classification_data1 = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 3.21)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertNotEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_int_equal(self):
        classification_data1 = {
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_int_not_equal(self):
        classification_data1 = {
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_INT": common.get_int_property_entry("PROP_INT", 321)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertNotEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_bool_equal(self):
        classification_data1 = {
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_bool_not_equal(self):
        classification_data1 = {
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False)
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", True)
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertNotEqual(checksum1, checksum2)

    def test_calculate_classification_value_checksum_order_independent(self):
        classification_data1 = {
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE"),
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23),
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123),
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False),
        }
        checksum1 = calculate_classification_value_checksum(classification_data1)

        classification_data2 = {
            "PROP_FLOAT": common.get_float_property_entry("PROP_FLOAT", 1.23),
            "PROP_TEXT": common.get_text_property_entry("PROP_TEXT", "VALUE"),
            "PROP_BOOL": common.get_bool_property_entry("PROP_BOOL", False),
            "PROP_INT": common.get_int_property_entry("PROP_INT", 123),
        }
        checksum2 = calculate_classification_value_checksum(classification_data2)

        self.assertEqual(checksum1, checksum2)
