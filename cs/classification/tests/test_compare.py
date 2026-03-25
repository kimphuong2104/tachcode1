# -*- mode: python; coding: utf-8 -*-
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import datetime

from cdb import cdbuuid

from cs.classification import api, units, util
from cs.classification.tests import utils

class TestClassificationCompare(utils.ClassificationTestCase):

    def _compare_simple_multivalues(self, class_code, property_code, left_values, right_values):
        left_doc = self.create_document("multivalue date property left")
        left_classification = api.get_new_classification([class_code])
        first = True
        for left_value in left_values:
            if first:
                left_classification["properties"][property_code][0]["value"] = left_value
                first = False
            else:
                new_value = api.add_multivalue(left_classification, property_code)
                new_value["value"] = left_value
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("multivalue date property right")
        right_classification = api.get_new_classification([class_code])
        first = True
        for right_value in right_values:
            if first:
                right_classification["properties"][property_code][0]["value"] = right_value
                first = False
            else:
                new_value = api.add_multivalue(right_classification, property_code)
                new_value["value"] = right_value
        api.update_classification(right_doc, right_classification)
        return api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )

    def test_with_metadata(self):
        left_doc = self.create_document("simple values left")
        left_assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES", "TEST_CLASS_COMPARE"]
        left_classification = api.get_new_classification(left_assigned_classes)
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values right")
        right_assigned_classes = ["TEST_CLASS_COMPARE", "TEST_CLASS_OBJECT_REF"]
        right_classification = api.get_new_classification(right_assigned_classes)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertIsNotNone(compare_data["metadata"])

    def test_no_assigned_classes(self):
        left_doc = self.create_document("simple values left")
        right_doc = self.create_document("simple values right")

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        expected_compare_data = {
            "assigned_classes": [],
            "assigned_classes_left": [],
            "assigned_classes_right": [],
            "classification_is_equal": True,
            "metadata": {"assigned_classes": set([]), "classes": {}, "classes_view": []},
            "properties": {}
        }
        self.assertDictEqual(compare_data, expected_compare_data)

    def test_same_assigned_classes(self):
        assigned_classes = ["TEST_CLASS_COMPARE"]

        left_doc = self.create_document("simple values left")
        left_classification = api.get_new_classification(assigned_classes)
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values right")
        right_classification = api.get_new_classification(assigned_classes)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )

        self.assertSetEqual(set(assigned_classes), set(compare_data["assigned_classes"]))
        self.assertSetEqual(set(), set(compare_data["assigned_classes_left"]))
        self.assertSetEqual(set(), set(compare_data["assigned_classes_right"]))

        self.assertTrue(compare_data["classification_is_equal"])

    def test_different_assigned_classes(self):
        left_doc = self.create_document("simple values left")
        left_assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES", "TEST_CLASS_COMPARE"]
        left_classification = api.get_new_classification(left_assigned_classes)
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values right")
        right_assigned_classes = ["TEST_CLASS_COMPARE", "TEST_CLASS_OBJECT_REF"]
        right_classification = api.get_new_classification(right_assigned_classes)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )

        assigned_classes = set(left_assigned_classes).intersection(set(right_assigned_classes))
        assigned_classes_left = set(left_assigned_classes).difference(set(right_assigned_classes))
        assigned_classes_right = set(right_assigned_classes).difference(set(left_assigned_classes))

        self.assertSetEqual(assigned_classes, set(compare_data["assigned_classes"]))
        self.assertSetEqual(assigned_classes_left, set(compare_data["assigned_classes_left"]))
        self.assertSetEqual(assigned_classes_right, set(compare_data["assigned_classes_right"]))

        self.assertFalse(compare_data["classification_is_equal"])

    def test_different_assigned_classes_number(self):
        left_doc = self.create_document("simple values left")
        left_assigned_classes = ["TEST_CLASS_COMPARE"]
        left_classification = api.get_new_classification(left_assigned_classes)
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values right")
        right_assigned_classes = ["TEST_CLASS_COMPARE", "TEST_CLASS_OBJECT_REF"]
        right_classification = api.get_new_classification(right_assigned_classes)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )

        assigned_classes = set(left_assigned_classes).intersection(set(right_assigned_classes))
        assigned_classes_left = set(left_assigned_classes).difference(set(right_assigned_classes))
        assigned_classes_right = set(right_assigned_classes).difference(set(left_assigned_classes))

        self.assertSetEqual(assigned_classes, set(compare_data["assigned_classes"]))
        self.assertSetEqual(assigned_classes_left, set(compare_data["assigned_classes_left"]))
        self.assertSetEqual(assigned_classes_right, set(compare_data["assigned_classes_right"]))

        self.assertFalse(compare_data["classification_is_equal"])

    def test_one_side_only_properties(self):

        left_doc = self.create_document("simple values left")
        left_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BOOL"][0]["value"] = True
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values right")
        right_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT"][0]["value"] = "Test value"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BOOL"
        self.assertEqual(compare_data["properties"][property_code][0]["value_left"], True)
        self.assertEqual(compare_data["properties"][property_code][0]["value_right"], None)
        self.assertFalse("id" in compare_data["properties"][property_code][0])
        self.assertFalse("value" in compare_data["properties"][property_code][0])

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_TEXT"
        self.assertEqual(compare_data["properties"][property_code][0]["value_left"], None)
        self.assertEqual(compare_data["properties"][property_code][0]["value_right"], "Test value")
        self.assertFalse("id" in compare_data["properties"][property_code][0])
        self.assertFalse("value" in compare_data["properties"][property_code][0])

    def test_equal_simple_properties(self):

        def check_equal_values(property_code):
            property_type = compare_data["properties"][property_code][0]["property_type"]
            self.assertTrue(
                util.are_property_values_equal(
                    property_type,
                    compare_data["properties"][property_code][0]["value"],
                    classification["properties"][property_code][0]["value"],
                    compare_normalized_values=False
                )
            )
            if property_type in ["float_range", "multilang"]:
                for _, value in compare_data["properties"][property_code][0]["value"].items():
                    self.assertFalse("id" in value)
                    self.assertFalse("value_left" in value)
                    self.assertFalse("value_right" in value)
            else:
                self.assertFalse("id" in compare_data["properties"][property_code][0])
                self.assertFalse("value_left" in compare_data["properties"][property_code][0])
                self.assertFalse("value_right" in compare_data["properties"][property_code][0])

        left_doc = self.create_document("simple values equal left")
        right_doc = self.create_document("simple values equal right")

        classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BOOL"][0]["value"] = True
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_DATE"][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT"][0]["value"]["float_value"] = 123.456
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT"][0]["value"]["float_value"] = 456.789
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 10.10
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 20.20
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["min"]["float_value"] = 10
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = 20
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_INT"][0]["value"] = 4711
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"] = "Test value de"
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["en"]["text_value"] = "Test value en"
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_OBJREF"][0]["value"] = left_doc.cdb_object_id
        classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT"][0]["value"] = "Test value"

        api.update_classification(left_doc, classification)
        api.update_classification(right_doc, classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data["classification_is_equal"])

        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_BOOL")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_DATE")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_INT")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_MULTILANG")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_OBJREF")
        check_equal_values("TEST_CLASS_COMPARE_TEST_PROP_TEXT")


    def test_different_simple_properties(self):

        def check_diff_values(property_code):
            property_type = compare_data["properties"][property_code][0]["property_type"]
            self.assertTrue(
                util.are_property_values_equal(
                    property_type,
                    compare_data["properties"][property_code][0]["value_left"],
                    left_classification["properties"][property_code][0]["value"],
                    compare_normalized_values=False
                )
            )
            self.assertTrue(
                util.are_property_values_equal(
                    property_type,
                    compare_data["properties"][property_code][0]["value_right"],
                    right_classification["properties"][property_code][0]["value"],
                    compare_normalized_values=False
                )
            )
            if property_type in ["float_range", "multilang"]:
                for _, value in compare_data["properties"][property_code][0]["value_left"].items():
                    self.assertFalse("id" in value)
                    self.assertFalse("value" in value)
                    for _, value in compare_data["properties"][property_code][0]["value_right"].items():
                        self.assertFalse("id" in value)
                        self.assertFalse("value" in value)
            else:
                self.assertFalse("id" in compare_data["properties"][property_code][0])
                self.assertFalse("value" in compare_data["properties"][property_code][0])
                self.assertTrue("value_left" in compare_data["properties"][property_code][0])
                self.assertTrue("value_right" in compare_data["properties"][property_code][0])
                if "objectref" == property_type:
                    self.assertFalse("addtl_value" in compare_data["properties"][property_code][0])
                    self.assertTrue("addtl_value_left" in compare_data["properties"][property_code][0])
                    self.assertTrue("addtl_value_right" in compare_data["properties"][property_code][0])

        left_doc = self.create_document("simple values differ left")
        left_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BOOL"][0]["value"] = True
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_DATE"][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT"][0]["value"]["float_value"] = 123.456
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT"][0]["value"]["float_value"] = 456.789
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 10.10
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 20.20
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["min"]["float_value"] = 10
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = 20
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_INT"][0]["value"] = 4711
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"] = "Test value de"
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["en"]["text_value"] = "Test value en"
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_OBJREF"][0]["value"] = left_doc.cdb_object_id
        left_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT"][0]["value"] = "Test value"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("simple values differ right")
        right_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BOOL"][0]["value"] = False
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_DATE"][0]["value"] = datetime.datetime(2012, 3, 11, 0, 0)
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT"][0]["value"]["float_value"] = 456.789
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT"][0]["value"]["float_value"] = 123.456
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 10
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 20
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["min"]["float_value"] = 10.10
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = 20.20
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_INT"][0]["value"] = 4712
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"] = "Testtext de"
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_MULTILANG"][0]["value"]["en"]["text_value"] = "Testtext en"
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_OBJREF"][0]["value"] = right_doc.cdb_object_id
        right_classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT"][0]["value"] = "Testtext"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_BOOL")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_DATE")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_INT")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_MULTILANG")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_OBJREF")
        check_diff_values("TEST_CLASS_COMPARE_TEST_PROP_TEXT")

    def _test_simple_list(self, class_code, property_code, test_values):

        def value_in_list(value, values):
            if isinstance(value, dict):
                for val in values:
                    if "float_value" in value:
                        if (
                                util.isclose(value["float_value"], val["float_value"]) and
                                value["unit_object_id"] == val["unit_object_id"]
                        ):
                            return True
                    elif "min" in value:
                        if (
                                util.isclose(value["min"]["float_value"], val["min"]["float_value"]) and
                                value["min"]["unit_object_id"] == val ["min"]["unit_object_id"] and
                                util.isclose(value["max"]["float_value"], val["max"]["float_value"]) and
                                value["max"]["unit_object_id"] == val["max"]["unit_object_id"]
                        ):
                            return True
                    elif "de" in value:
                        if (
                                value["de"]["text_value"] == val["de"]["text_value"] and
                                value["en"]["text_value"] == val["en"]["text_value"]
                        ):
                            return True
                return False
            else:
                return value in values

        def check_compare_diffs(property_code, compare_data):
            self.assertFalse(compare_data["classification_is_equal"])
            for property_value in compare_data["properties"][property_code]:
                self.assertFalse("id" in property_value)
                if "value" in property_value:
                    self.assertFalse("value_left" in property_value)
                    self.assertFalse("value_right" in property_value)
                    value = property_value["value"]
                    self.assertTrue(value_in_list(value, left_values))
                    self.assertTrue(value_in_list(value, right_values))
                else:
                    self.assertTrue("value_left" in property_value)
                    value = property_value["value_left"]
                    if value:
                        self.assertTrue(value_in_list(value, left_values))
                        self.assertFalse(value_in_list(value, right_values))
                    self.assertTrue("value_right" in property_value)
                    value = property_value["value_right"]
                    if value:
                        self.assertTrue(value_in_list(value, right_values))
                        self.assertFalse(value_in_list(value, left_values))

        left_values = test_values["identical"]["left"]
        right_values = test_values["identical"]["right"]
        compare_data = self._compare_simple_multivalues(class_code, property_code, left_values, right_values)
        self.assertTrue(compare_data["classification_is_equal"])
        for property_value in compare_data["properties"][property_code]:
            self.assertFalse("id" in property_value)
            self.assertFalse("value_left" in property_value)
            self.assertFalse("value_right" in property_value)
            value = property_value["value"]
            self.assertTrue(value_in_list(value, left_values))
            self.assertTrue(value_in_list(value, right_values))

        left_values = test_values["same_values"]["left"]
        right_values = test_values["same_values"]["right"]
        compare_data = self._compare_simple_multivalues(class_code, property_code, left_values, right_values)
        self.assertTrue(compare_data["classification_is_equal"])
        for property_value in compare_data["properties"][property_code]:
            self.assertFalse("id" in property_value)
            self.assertFalse("value_left" in property_value)
            self.assertFalse("value_right" in property_value)
            value = property_value["value"]
            self.assertTrue(value_in_list(value, left_values))
            self.assertTrue(value_in_list(value, right_values))

        left_values = test_values["different_same_length"]["left"]
        right_values = test_values["different_same_length"]["right"]
        compare_data = self._compare_simple_multivalues(class_code, property_code, left_values, right_values)
        check_compare_diffs(property_code, compare_data)

        left_values = test_values["different_left_longer"]["left"]
        right_values = test_values["different_left_longer"]["right"]
        compare_data = self._compare_simple_multivalues(class_code, property_code, left_values, right_values)
        check_compare_diffs(property_code, compare_data)

        left_values = test_values["different_right_longer"]["left"]
        right_values = test_values["different_right_longer"]["right"]
        compare_data = self._compare_simple_multivalues(class_code, property_code, left_values, right_values)
        check_compare_diffs(property_code, compare_data)

    def test_multivalued_date_property(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_DATE_MULTIVALUE"

        test_values = {
            "identical": {
                "left": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0)
                ],
                "right": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0)
                ]
            },
            "same_values": {
                "left": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0)
                ],
                "right": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0)
                ]
            },
            "different_same_length": {
                "left": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0)
                ],
                "right": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2099, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0)
                ]
            },
            "different_left_longer": {
                "left": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0),
                    datetime.datetime(2032, 3, 11, 0, 0)
            ],
                "right": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2099, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0)
                ]
            },
            "different_right_longer": {
                "left": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2022, 3, 11, 0, 0)
                ],
                "right": [
                    datetime.datetime(2002, 3, 11, 0, 0),
                    datetime.datetime(2099, 3, 11, 0, 0),
                    datetime.datetime(2012, 3, 11, 0, 0),
                    datetime.datetime(2032, 3, 11, 0, 0)
                ]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_float_property(self):

        def float_value(value, unit_symbol=None):
            unit = units_by_symbol.get(unit_symbol, None)
            unit_oid = unit.cdb_object_id if unit else None
            return {
                "float_value": value,
                "unit_object_id": unit_oid
            }

        units_by_symbol = {
            "cm": units.Unit.KeywordQuery(symbol="cm")[0],
            "m": units.Unit.KeywordQuery(symbol="m")[0]
        }

        class_code = "TEST_CLASS_COMPARE"

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_FLOAT_MULTIVALUE"
        test_values = {
            "identical": {
                "left":  [float_value(1.1), float_value(2.2), float_value(3.3)],
                "right": [float_value(1.1), float_value(2.2), float_value(3.3)]
            },
            "same_values": {
                "left":  [float_value(1.1), float_value(2.2), float_value(3.3)],
                "right": [float_value(1.1), float_value(3.3), float_value(2.2)]
            },
            "different_same_length": {
                "left":  [float_value(1.1), float_value(2.2), float_value(3.3)],
                "right": [float_value(3.3), float_value(9.9), float_value(1.1)]
            },
            "different_left_longer": {
                "left":  [float_value(1.1), float_value(2.2), float_value(3.3), float_value(4.4)],
                "right": [float_value(3.3), float_value(9.9), float_value(1.1)]
            },
            "different_right_longer": {
                "left":  [float_value(1.1), float_value(2.2), float_value(3.3)],
                "right": [float_value(3.3), float_value(9.9), float_value(1.1), float_value(8.8)]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_FLOAT_UNIT_MULTIVALUE"
        test_values = {
            "identical": {
                "left":  [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m")],
                "right": [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m")]
            },
            "same_values": {
                "left":  [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m")],
                "right": [float_value(1.1, "m"), float_value(3.3, "m"), float_value(2.2, "m")]
            },
            "different_same_length": {
                "left":  [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m")],
                "right": [float_value(3.3, "m"), float_value(22.0, "cm"), float_value(1.1, "m")]
            },
            "different_left_longer": {
                "left":  [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m"), float_value(4.4, "m")],
                "right": [float_value(3.3, "m"), float_value(2.2, "cm"), float_value(1.1, "m")]
            },
            "different_right_longer": {
                "left":  [float_value(1.1, "m"), float_value(2.2, "m"), float_value(3.3, "m")],
                "right": [float_value(3.3, "m"), float_value(9.9, "m"), float_value(1.1, "m"), float_value(8.8, "m")]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_float_range_property(self):

        def float_range_value(min_value, max_value, unit_symbol=None):
            unit = units_by_symbol.get(unit_symbol, None)
            unit_oid = unit.cdb_object_id if unit else None
            return {
                "min": {
                    "range_identifier": "min",
                    "float_value": min_value,
                    "unit_object_id": unit_oid
                },
                "max": {
                    "range_identifier": "max",
                    "float_value": max_value,
                    "unit_object_id": unit_oid
                }
            }

        units_by_symbol = {
            "cm": units.Unit.KeywordQuery(symbol="cm")[0],
            "m": units.Unit.KeywordQuery(symbol="m")[0]
        }

        class_code = "TEST_CLASS_COMPARE"

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_MULTIVALUE"
        test_values = {
            "identical": {
                "left":  [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4)],
                "right": [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4)]
            },
            "same_values": {
                "left":  [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4)],
                "right": [float_range_value(1.1, 2.2), float_range_value(3.3, 4.4), float_range_value(2.2, 3.3)]
            },
            "different_same_length": {
                "left":  [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4)],
                "right": [float_range_value(3.3, 4.4), float_range_value(9.9, 10.9), float_range_value(1.1, 2.2)]
            },
            "different_left_longer": {
                "left":  [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4), float_range_value(4.4, 5.5)],
                "right": [float_range_value(3.3, 4.4), float_range_value(9.9, 10.9), float_range_value(1.1, 2.2)]
            },
            "different_right_longer": {
                "left":  [float_range_value(1.1, 2.2), float_range_value(2.2, 3.3), float_range_value(3.3, 4.4)],
                "right": [float_range_value(3.3, 4.4), float_range_value(9.9, 10.9), float_range_value(1.1, 2.2), float_range_value(8.8, 9.9)]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

        property_code = "TEST_CLASS_COMPARE_TEST_PROP_FLOAT_RANGE_UNIT_MULTIVALUE"
        test_values = {
            "identical": {
                "left":  [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m")],
                "right": [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m")]
            },
            "same_values": {
                "left":  [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m")],
                "right": [float_range_value(1.1, 2.2, "m"), float_range_value(3.3, 4.4, "m"), float_range_value(2.2, 3.3, "m")]
            },
            "different_same_length": {
                "left":  [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m")],
                "right": [float_range_value(3.3, 4.4, "m"), float_range_value(22.0, 33.0, "cm"), float_range_value(1.1, 2.2, "m")]
            },
            "different_left_longer": {
                "left":  [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m"), float_range_value(4.4, 5.5, "m")],
                "right": [float_range_value(3.3, 4.4, "m"), float_range_value(2.2, 3.3, "cm"), float_range_value(1.1, 2.2, "m")]
            },
            "different_right_longer": {
                "left":  [float_range_value(1.1, 2.2, "m"), float_range_value(2.2, 3.3, "m"), float_range_value(3.3, 4.4, "m")],
                "right": [float_range_value(3.3, 4.4, "m"), float_range_value(9.9, 10.9, "m"), float_range_value(1.1, 2.2, "m"), float_range_value(8.8, 9.9, "m")]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_int_property(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_INT_MULTIVALUE"

        test_values = {
            "identical": {
                "left":  [1, 2, 3],
                "right": [1, 2, 3]
            },
            "same_values": {
                "left": [1, 2, 3],
                "right": [1, 3, 2]
            },
            "different_same_length": {
                "left": [1, 2, 3],
                "right": [3, 99, 1]
            },
            "different_left_longer": {
                "left": [1, 2, 3, 4],
                "right": [3, 99, 1]
            },
            "different_right_longer": {
                "left": [1, 2, 3],
                "right": [3, 99, 1, 33]
            }
        }

        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_objref_property(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_OBJREF_MULTIVALUE"

        oid_1 = cdbuuid.create_uuid()
        oid_2 = cdbuuid.create_uuid()
        oid_3 = cdbuuid.create_uuid()
        oid_4 = cdbuuid.create_uuid()
        oid_99 = cdbuuid.create_uuid()
        oid_33 = cdbuuid.create_uuid()

        test_values = {
            "identical": {
                "left":  [oid_1, oid_2, oid_3],
                "right": [oid_1, oid_2, oid_3]
            },
            "same_values": {
                "left": [oid_1, oid_2, oid_3],
                "right": [oid_1, oid_3, oid_2]
            },
            "different_same_length": {
                "left": [oid_1, oid_2, oid_3],
                "right": [oid_3, oid_99, oid_1]
            },
            "different_left_longer": {
                "left": [oid_1, oid_2, oid_3, oid_4],
                "right": [oid_3, oid_99, oid_1]
            },
            "different_right_longer": {
                "left": [oid_1, oid_2, oid_3],
                "right": [oid_3, oid_99, oid_1, oid_33]
            }
        }

        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_multilang_property(self):

        def multilang_value(de_value, en_value):
            return {
                "de": {
                    "iso_language_code": "de",
                    "text_value": de_value
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": en_value
                }
            }

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_MULTILANG_MULTIVALUE"
        test_values = {
            "identical": {
                "left":  [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3")],
                "right": [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3")]
            },
            "same_values": {
                "left":  [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3")],
                "right": [multilang_value("de 1", "en 1"), multilang_value("de 3", "en 3"), multilang_value("de 2", "en 2")]
            },
            "different_same_length": {
                "left":  [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3")],
                "right": [multilang_value("de 3", "en 3"), multilang_value("de 9", "en 9"), multilang_value("de 1", "en 1")]
            },
            "different_left_longer": {
                "left":  [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3"), multilang_value("de 4", "en 4")],
                "right": [multilang_value("de 3", "en 3"), multilang_value("de 9", "en 9"), multilang_value("de 1", "en 1")]
            },
            "different_right_longer": {
                "left":  [multilang_value("de 1", "en 1"), multilang_value("de 2", "en 2"), multilang_value("de 3", "en 3")],
                "right": [multilang_value("de 3", "en 3"), multilang_value("de 9", "en 9"), multilang_value("de 1", "en 1"), multilang_value("de 8", "en 8")]
            }
        }
        self._test_simple_list(class_code, property_code, test_values)

    def test_multivalued_text_property(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_TEXT_MULTIVALUE"

        test_values = {
            "identical": {
                "left":  ["text 1", "text 2", "text 3"],
                "right": ["text 1", "text 2", "text 3"]
            },
            "same_values": {
                "left": ["text 1", "text 2", "text 3"],
                "right": ["text 1", "text 3", "text 2"]
            },
            "different_same_length": {
                "left": ["text 1", "text 2", "text 3"],
                "right": ["text 3", "text 99", "text 1"]
            },
            "different_left_longer": {
                "left": ["text 1", "text 2", "text 3", "text 4"],
                "right": ["text 3", "text 99", "text 1"]
            },
            "different_right_longer": {
                "left": ["text 1", "text 2", "text 3"],
                "right": ["text 3", "text 99", "text 1", "text 33"]
            }
        }

        self._test_simple_list(class_code, property_code, test_values)

    def test_equal_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES"

        left_doc = self.create_document("block values equal left")
        right_doc = self.create_document("block values equal right")

        classification = api.get_new_classification([class_code])
        child_props = classification["properties"][property_code][0]["value"]["child_props"]

        child_property_code = "TEST_PROP_BOOL"
        child_props[child_property_code][0]["value"] = True
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_FLOAT"
        child_props[child_property_code][0]["value"]["float_value"] = 123.456
        child_property_code = "TEST_PROP_FLOAT_MULTIVALUE"
        child_props[child_property_code][0]["value"]["float_value"] = 11.11
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"]["float_value"] = 22.22
        child_property_code = "TEST_PROP_FLOAT_RANGE"
        child_props[child_property_code][0]["value"]["min"]["float_value"] = 10.10
        child_props[child_property_code][0]["value"]["max"]["float_value"] = 20.20
        child_property_code = "TEST_PROP_FLOAT_RANGE_MULTIVALUE"
        child_props[child_property_code][0]["value"]["min"]["float_value"] = 1.0
        child_props[child_property_code][0]["value"]["max"]["float_value"] = 5.0
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"]["min"]["float_value"] = 10.0
        child_props[child_property_code][1]["value"]["max"]["float_value"] = 50.0
        child_property_code = "TEST_PROP_FLOAT_RANGE_UNIT"
        child_props[child_property_code][0]["value"]["min"]["float_value"] = 100.0
        child_props[child_property_code][0]["value"]["max"]["float_value"] = 149.99
        child_property_code = "TEST_PROP_FLOAT_RANGE_UNIT_MULTIVALUE"
        child_props[child_property_code][0]["value"]["min"]["float_value"] = 500.0
        child_props[child_property_code][0]["value"]["max"]["float_value"] = 700.0
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"]["min"]["float_value"] = 800.0
        child_props[child_property_code][1]["value"]["max"]["float_value"] = 900.0
        child_property_code = "TEST_PROP_FLOAT_UNIT"
        child_props[child_property_code][0]["value"]["float_value"] = 100.0
        child_property_code = "TEST_PROP_FLOAT_UNIT_MULTIVALUE"
        child_props[child_property_code][0]["value"]["float_value"] = 110.0
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"]["float_value"] = 220.0
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 4711
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 123
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 456
        child_property_code = "TEST_PROP_MULTILANG"
        child_props[child_property_code][0]["value"]["de"]["text_value"] = "Test value de"
        child_props[child_property_code][0]["value"]["en"]["text_value"] = "Test value en"
        child_property_code = "TEST_PROP_MULTILANG_MULTIVALUE"
        child_props[child_property_code][0]["value"]["de"]["text_value"] = "Test value 1 de"
        child_props[child_property_code][0]["value"]["en"]["text_value"] = "Test value 1 en"
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"]["de"]["text_value"] = "Test value 2 de"
        child_props[child_property_code][1]["value"]["en"]["text_value"] = "Test value 2 en"
        child_property_code = "TEST_PROP_OBJREF"
        child_props[child_property_code][0]["value"] = cdbuuid.create_uuid()
        child_property_code = "TEST_PROP_OBJREF_MULTIVALUE"
        child_props[child_property_code][0]["value"] = cdbuuid.create_uuid()
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = cdbuuid.create_uuid()
        child_property_code = "TEST_PROP_TEXT"
        child_props[child_property_code][0]["value"] = "Test text"
        child_property_code = "TEST_PROP_TEXT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = "Test text 1"
        api.add_multivalue(classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = "Test text 2"

        api.update_classification(left_doc, classification)
        api.update_classification(right_doc, classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data["classification_is_equal"])

        block_property_value = compare_data["properties"][property_code][0]
        self.assertFalse("id" in block_property_value)
        self.assertFalse("value_left" in block_property_value)
        self.assertFalse("value_right" in block_property_value)
        self.assertTrue("value" in block_property_value)

    def test_equal_block_properties_with_different_order(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES"

        left_doc = self.create_document("block values equal left")
        right_doc = self.create_document("block values equal right")

        left_classification = api.get_new_classification([class_code])
        left_child_props = left_classification["properties"][property_code][0]["value"]["child_props"]

        right_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        right_child_props = right_classification["properties"][property_code][0]["value"]["child_props"]


        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        left_child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_FLOAT_MULTIVALUE"
        left_child_props[child_property_code][0]["value"]["float_value"] = 11.11
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"]["float_value"] = 22.22
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_FLOAT_RANGE_MULTIVALUE"
        left_child_props[child_property_code][0]["value"]["min"]["float_value"] = 1.0
        left_child_props[child_property_code][0]["value"]["max"]["float_value"] = 5.0
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"]["min"]["float_value"] = 10.0
        left_child_props[child_property_code][1]["value"]["max"]["float_value"] = 50.0
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_FLOAT_RANGE_UNIT_MULTIVALUE"
        left_child_props[child_property_code][0]["value"]["min"]["float_value"] = 500.0
        left_child_props[child_property_code][0]["value"]["max"]["float_value"] = 700.0
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"]["min"]["float_value"] = 800.0
        left_child_props[child_property_code][1]["value"]["max"]["float_value"] = 900.0
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_FLOAT_UNIT_MULTIVALUE"
        left_child_props[child_property_code][0]["value"]["float_value"] = 110.0
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"]["float_value"] = 220.0
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        left_child_props[child_property_code][0]["value"] = 123
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"] = 456
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_MULTILANG_MULTIVALUE"
        left_child_props[child_property_code][0]["value"]["de"]["text_value"] = "Test value 1 de"
        left_child_props[child_property_code][0]["value"]["en"]["text_value"] = "Test value 1 en"
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"]["de"]["text_value"] = "Test value 2 de"
        left_child_props[child_property_code][1]["value"]["en"]["text_value"] = "Test value 2 en"
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_OBJREF_MULTIVALUE"
        left_child_props[child_property_code][0]["value"] = cdbuuid.create_uuid()
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"] = cdbuuid.create_uuid()
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        child_property_code = "TEST_PROP_TEXT_MULTIVALUE"
        left_child_props[child_property_code][0]["value"] = "Test text 1"
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        left_child_props[child_property_code][1]["value"] = "Test text 2"
        right_child_props[child_property_code][0] = left_child_props[child_property_code][1]
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        right_child_props[child_property_code][1] = left_child_props[child_property_code][0]

        api.update_classification(left_doc, left_classification)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data["classification_is_equal"])

        block_property_value = compare_data["properties"][property_code][0]
        self.assertFalse("id" in block_property_value)
        self.assertFalse("value_left" in block_property_value)
        self.assertFalse("value_right" in block_property_value)
        self.assertTrue("value" in block_property_value)

    def test_different_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES"

        left_doc = self.create_document("block values equal left")
        right_doc = self.create_document("block values equal right")

        left_classification = api.get_new_classification([class_code])
        child_props = left_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        api.update_classification(left_doc, left_classification)

        right_classification = api.get_new_classification(["TEST_CLASS_COMPARE"])
        child_props = right_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 3, 11, 0, 0)
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        block_property_value = compare_data["properties"][property_code][0]
        self.assertFalse("id" in block_property_value)
        self.assertFalse("value_left" in block_property_value)
        self.assertFalse("value_right" in block_property_value)
        self.assertTrue("value" in block_property_value)

        self.assertEqual(
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"],
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_left"]
        )
        self.assertEqual(
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"],
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_right"]
        )

    def test_multivalued_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        child_property_code = "TEST_PROP_TEXT"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"] = "Equal block"
        api.add_multivalue(left_classification, "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE")
        left_classification["properties"][property_code][1]["value"]["child_props"][child_property_code][0]["value"] = "Left block"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"] = "Right block"
        api.add_multivalue(right_classification, "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE")
        right_classification["properties"][property_code][1]["value"]["child_props"][child_property_code][0]["value"] = "Equal block"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        self.assertEqual(
            compare_data["properties"][property_code][0]["value_left"]["child_props"][child_property_code][0]["value"],
            left_classification["properties"][property_code][1]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertIsNone(
            compare_data["properties"][property_code][0]["value_right"]
        )
        self.assertFalse(
            "value" in compare_data["properties"][property_code][0]
        )

        self.assertEqual(
            compare_data["properties"][property_code][1]["value"]["child_props"][child_property_code][0]["value"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertFalse(
            "value_left" in compare_data["properties"][property_code][1]
        )
        self.assertFalse(
            "value_right" in compare_data["properties"][property_code][1]
        )

        self.assertIsNone(
            compare_data["properties"][property_code][2]["value_left"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][2]["value_right"]["child_props"][child_property_code][0]["value"],
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertFalse(
            "value" in compare_data["properties"][property_code][2]
        )

    def test_equal_identifying_block_properties_same_order(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_IDENTIFYING_PROP"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        child_props = left_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 123
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 11
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 22

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        child_props = right_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 123
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 11
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 22

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data["classification_is_equal"])

        child_props = compare_data["properties"][property_code][2]["value"]["child_props"]
        for child_property_code, child_prop in child_props.items():
            self.assertTrue("value" in child_prop[0])
            self.assertFalse("value_left" in child_prop[0])
            self.assertFalse("value_right" in child_prop[0])

    def test_equal_identifying_block_properties_different_order(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_IDENTIFYING_PROP"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        child_props = left_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 123
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 11
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 22

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        child_props = right_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(right_classification, property_code + ":003/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 123
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 11
        api.add_multivalue(right_classification, property_code + ":003/" + child_property_code)
        child_props[child_property_code][1]["value"] = 22

        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertTrue(compare_data["classification_is_equal"])

        child_props = compare_data["properties"][property_code][2]["value"]["child_props"]
        for child_property_code, child_prop in child_props.items():
            self.assertTrue("value" in child_prop[0])
            self.assertFalse("value_left" in child_prop[0])
            self.assertFalse("value_right" in child_prop[0])

    def test_different_identifying_block_properties_same_order(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_IDENTIFYING_PROP"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        child_props = left_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 3, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 2, 22, 0, 0)
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 123
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 11
        api.add_multivalue(left_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 22

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(left_classification, property_code)
        child_props = left_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        child_props = right_classification["properties"][property_code][0]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 1"
        child_property_code = "TEST_PROP_DATE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2002, 1, 11, 0, 0)
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        child_props[child_property_code][0]["value"] = datetime.datetime(2012, 4, 22, 0, 0)
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = datetime.datetime(2022, 2, 22, 0, 0)
        child_property_code = "TEST_PROP_INT"
        child_props[child_property_code][0]["value"] = 456
        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        child_props[child_property_code][0]["value"] = 22
        api.add_multivalue(right_classification, property_code + "/" + child_property_code)
        child_props[child_property_code][1]["value"] = 33

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][1]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 2"

        api.add_multivalue(right_classification, property_code)
        child_props = right_classification["properties"][property_code][2]["value"]["child_props"]
        child_property_code = "TEST_PROP_IDENTIFYING"
        child_props[child_property_code][0]["value"] = "ID 3"

        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        child_property_code = "TEST_PROP_DATE"
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_left"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_right"],
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        child_property_code = "TEST_PROP_DATE_MULTIVALUE"
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_left"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_right"],
            None
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][1]["value"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][1]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][2]["value_left"],
            None
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][2]["value_right"],
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )

        child_property_code = "TEST_PROP_INT"
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_left"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_right"],
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )

        child_property_code = "TEST_PROP_INT_MULTIVALUE"
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_left"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][0]["value_right"],
            None
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][1]["value"],
            left_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][1]["value"]
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][2]["value_left"],
            None
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value"]["child_props"][child_property_code][2]["value_right"],
            right_classification["properties"][property_code][0]["value"]["child_props"][child_property_code][1]["value"]
        )

    def test_multivalued_nested_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED"
        nested_property_code = "TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        child_property_code = "TEST_PROP_TEXT_MULTIVALUE"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        prop_value = left_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Equal block 1"
        prop_value = api.add_multivalue(left_classification, "/".join([property_code + ":001", nested_property_code, child_property_code]))
        prop_value["value"] = "Equal block 2"
        api.add_multivalue(left_classification, property_code)
        prop_value = left_classification["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Left block 1"
        prop_value = api.add_multivalue(left_classification, "/".join([property_code+ ":002", nested_property_code, child_property_code]))
        prop_value["value"] = "Left block 2"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        prop_value = right_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Right block 1"
        prop_value = api.add_multivalue(right_classification, "/".join([property_code + ":001", nested_property_code, child_property_code]))
        prop_value["value"] = "Right block 2"
        api.add_multivalue(right_classification, property_code)
        prop_value = right_classification["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Equal block 2"
        prop_value = api.add_multivalue(right_classification, "/".join([property_code + ":002", nested_property_code, child_property_code]))
        prop_value["value"] = "Equal block 1"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        self.assertFalse(
            "value" in compare_data["properties"][property_code][0],
        )
        self.assertTrue(
            "value_left" in compare_data["properties"][property_code][0],
        )
        prop_values = compare_data["properties"][property_code][0]["value_left"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code]
        self.assertEqual(
            prop_values[0]["value"],
            "Left block 1"
        )
        self.assertEqual(
            prop_values[1]["value"],
            "Left block 2"
        )
        self.assertTrue(
            "value_right" in compare_data["properties"][property_code][0],
        )
        self.assertEqual(
            compare_data["properties"][property_code][0]["value_right"],
            None
        )

        self.assertTrue(
            "value" in compare_data["properties"][property_code][1],
        )
        prop_values = compare_data["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code]
        self.assertEqual(
            prop_values[0]["value"],
            "Equal block 1"
        )
        self.assertEqual(
            prop_values[1]["value"],
            "Equal block 2"
        )
        self.assertFalse(
            "value_left" in compare_data["properties"][property_code][1],
        )
        self.assertFalse(
            "value_right" in compare_data["properties"][property_code][1],
        )

        self.assertFalse(
            "value" in compare_data["properties"][property_code][2],
        )
        self.assertTrue(
            "value_left" in compare_data["properties"][property_code][2],
        )
        self.assertEqual(
            compare_data["properties"][property_code][2]["value_left"],
            None
        )
        self.assertTrue(
            "value_right" in compare_data["properties"][property_code][2],
        )
        prop_values = compare_data["properties"][property_code][2]["value_right"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code]
        self.assertEqual(
            prop_values[0]["value"],
            "Right block 1"
        )
        self.assertEqual(
            prop_values[1]["value"],
            "Right block 2"
        )

    def test_nested_identifying_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED_IDENTIFYING"
        id_property_code = "TEST_PROP_IDENTIFYING"
        nested_property_code = "TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        child_property_code = "TEST_PROP_TEXT_MULTIVALUE"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        left_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        prop_value = left_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Diff block"
        prop_value = api.add_multivalue(left_classification, "/".join([property_code + ":001", nested_property_code, child_property_code]))
        prop_value["value"] = "Diff block left"
        api.add_multivalue(left_classification, property_code)
        left_classification["properties"][property_code][1]["value"]["child_props"][id_property_code][0]["value"] = "ID 2"
        prop_value = left_classification["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Left block 1"
        prop_value = api.add_multivalue(left_classification, "/".join([property_code+ ":002", nested_property_code, child_property_code]))
        prop_value["value"] = "Left block 2"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        right_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 3"
        prop_value = right_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Right block 1"
        prop_value = api.add_multivalue(right_classification, "/".join([property_code + ":001", nested_property_code, child_property_code]))
        prop_value["value"] = "Right block 2"
        api.add_multivalue(right_classification, property_code)
        right_classification["properties"][property_code][1]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        prop_value = right_classification["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Diff block right"
        prop_value = api.add_multivalue(right_classification, "/".join([property_code + ":002", nested_property_code, child_property_code]))
        prop_value["value"] = "Diff block"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        self.assertFalse(
            "value" in compare_data["properties"][property_code][0]
        )
        self.assertTrue(
            "value_left" in compare_data["properties"][property_code][0]
        )
        self.assertEqual(
            "ID 2",
            compare_data["properties"][property_code][0]["value_left"]["child_props"][id_property_code][0]["value"]
        )
        prop_values = compare_data["properties"][property_code][0]["value_left"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code]
        self.assertEqual(
            "Left block 1",
            prop_values[0]["value"]
        )
        self.assertFalse(
            "value_left" in prop_values[0]
        )
        self.assertFalse(
            "value_right" in prop_values[0]
        )
        self.assertEqual(
            "Left block 2",
            prop_values[1]["value"]
        )
        self.assertFalse(
            "value_left" in prop_values[1]
        )
        self.assertFalse(
            "value_right" in prop_values[1]
        )

        self.assertTrue(
            "value_right" in compare_data["properties"][property_code][0]
        )
        self.assertEqual(
            None,
            compare_data["properties"][property_code][0]["value_right"]
        )

        self.assertTrue(
            "value" in compare_data["properties"][property_code][1]
        )
        self.assertEqual(
            "ID 1",
            compare_data["properties"][property_code][1]["value"]["child_props"][id_property_code][0]["value"]
        )

        prop_values = compare_data["properties"][property_code][1]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code]
        self.assertFalse(
            "value" in prop_values[0]
        )
        self.assertEqual(
            "Diff block left",
            prop_values[0]["value_left"]
        )
        self.assertEqual(
            None,
            prop_values[0]["value_right"]
        )
        self.assertEqual(
            "Diff block",
            prop_values[1]["value"]
        )
        self.assertFalse(
            "value_left" in prop_values[1]
        )
        self.assertFalse(
            "value_right" in prop_values[1]
        )
        self.assertFalse(
            "value" in prop_values[2]
        )
        self.assertEqual(
            None,
            prop_values[2]["value_left"]
        )
        self.assertEqual(
            "Diff block right",
            prop_values[2]["value_right"]
        )

        self.assertFalse(
            "value_left" in compare_data["properties"][property_code][1]
        )
        self.assertFalse(
            "value_right" in compare_data["properties"][property_code][1]
        )

        self.assertFalse(
            "value" in compare_data["properties"][property_code][2]
        )
        self.assertTrue(
            "value_left" in compare_data["properties"][property_code][2]
        )
        self.assertEqual(
            None,
            compare_data["properties"][property_code][2]["value_left"]
        )
        self.assertTrue(
            "value_right" in compare_data["properties"][property_code][2]
        )
        self.assertEqual(
            "ID 3",
            compare_data["properties"][property_code][2]["value_right"]["child_props"][id_property_code][0]["value"]
        )

    def test_nested_multivalued_identifying_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED_IDENTIFYING"
        id_property_code = "TEST_PROP_IDENTIFYING"
        nested_property_code = "TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        child_property_code = "TEST_PROP_TEXT"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        left_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        prop_value = left_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Nested block left"
        prop_value = api.add_multivalue(left_classification, "/".join([property_code + ":001", nested_property_code]))
        prop_value["value"]["child_props"][child_property_code][0]["value"] = "Nested block equal"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        right_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        prop_value = right_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"][child_property_code][0]
        prop_value["value"] = "Nested block equal"
        prop_value = api.add_multivalue(right_classification, "/".join([property_code + ":001", nested_property_code]))
        prop_value["value"]["child_props"][child_property_code][0]["value"] = "Nested block right"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        nested_block_values = compare_data["properties"][property_code][0]["value"]["child_props"][nested_property_code]
        self.assertFalse(
            "value" in nested_block_values[0]
        )
        self.assertTrue(
            "value_left" in nested_block_values[0]
        )
        self.assertEqual(
            "Nested block left",
            nested_block_values[0]["value_left"]["child_props"][child_property_code][0]["value"]
        )
        self.assertTrue(
            "value_right" in nested_block_values[0]
        )
        self.assertEqual(
            None,
            nested_block_values[0]["value_right"]
        )

        self.assertTrue(
            "value" in nested_block_values[1]
        )
        self.assertEqual(
            "Nested block equal",
            nested_block_values[1]["value"]["child_props"][child_property_code][0]["value"]
        )
        self.assertFalse(
            "value_left" in nested_block_values[1]
        )
        self.assertFalse(
            "value_right" in nested_block_values[1]
        )

        self.assertFalse(
            "value" in nested_block_values[2]
        )
        self.assertTrue(
            "value_left" in nested_block_values[2]
        )
        self.assertEqual(
            None,
            nested_block_values[2]["value_left"]
        )
        self.assertTrue(
            "value_right" in nested_block_values[2]
        )
        self.assertEqual(
            "Nested block right",
            nested_block_values[2]["value_right"]["child_props"][child_property_code][0]["value"]
        )


    def test_deep_nested_identifying_block_properties(self):

        class_code = "TEST_CLASS_COMPARE"
        property_code = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED_IDENTIFYING"
        id_property_code = "TEST_PROP_IDENTIFYING"
        nested_property_code = "TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_IDENTIFYING_PROP"
        child_property_code = "TEST_PROP_TEXT"

        left_doc = self.create_document("block values equal left")
        left_classification = api.get_new_classification([class_code])
        left_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        nested_block = left_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"]
        nested_block[id_property_code][0]["value"] = "ID 1"
        nested_block[child_property_code][0]["value"] = "ID 1 - Left text"
        api.add_multivalue(left_classification, "/".join([property_code + ":001", nested_property_code]))
        nested_block = left_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][1]["value"]["child_props"]
        nested_block[id_property_code][0]["value"] = "ID 2"
        nested_block[child_property_code][0]["value"] = "ID 2 - Text"
        api.update_classification(left_doc, left_classification)

        right_doc = self.create_document("block values equal right")
        right_classification = api.get_new_classification([class_code])
        right_classification["properties"][property_code][0]["value"]["child_props"][id_property_code][0]["value"] = "ID 1"
        nested_block = right_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"]
        nested_block[id_property_code][0]["value"] = "ID 2"
        nested_block[child_property_code][0]["value"] = "ID 2 - Text"
        api.add_multivalue(right_classification, "/".join([property_code + ":001", nested_property_code]))
        nested_block = right_classification["properties"][property_code][0]["value"]["child_props"][nested_property_code][1]["value"]["child_props"]
        nested_block[id_property_code][0]["value"] = "ID 1"
        nested_block[child_property_code][0]["value"] = "ID 1 - Right text"
        api.update_classification(right_doc, right_classification)

        compare_data = api.compare_classification(
            left_doc.cdb_object_id, right_doc.cdb_object_id, with_metadata=True, narrowed=False
        )
        self.assertFalse(compare_data["classification_is_equal"])

        nested_block = compare_data["properties"][property_code][0]["value"]["child_props"][nested_property_code][0]["value"]["child_props"]
        self.assertEqual(
            "ID 1", nested_block[id_property_code][0]["value"]
        )
        self.assertFalse(
            "value" in nested_block[child_property_code][0]
        )
        self.assertEqual(
            "ID 1 - Left text",
            nested_block[child_property_code][0]["value_left"]
        )
        self.assertEqual(
            "ID 1 - Right text",
            nested_block[child_property_code][0]["value_right"]
        )

        nested_block = compare_data["properties"][property_code][0]["value"]["child_props"][nested_property_code][1]["value"]["child_props"]
        self.assertEqual(
            "ID 2", nested_block[id_property_code][0]["value"]
        )
        self.assertFalse(
            "value_left" in nested_block[child_property_code][0]
        )
        self.assertFalse(
            "value_right" in nested_block[child_property_code][0]
        )
        self.assertEqual(
            "ID 2 - Text",
            nested_block[child_property_code][0]["value"]
        )
