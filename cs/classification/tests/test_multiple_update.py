# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import datetime

from cdb import constants, cdbuuid, testcase
from cdb.objects.operations import operation

from cs.classification import api, ClassificationConstants, FloatRangeObjectPropertyValue, MultilangObjectPropertyValue, ObjectClassification, units
from cs.classification.tests import utils
from cs.classification.object_classification import ClassificationUpdater


class TestMultipleUpdate(utils.ClassificationTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestMultipleUpdate, cls).setUpClass()

    def setUp(self):
        super(TestMultipleUpdate, self).setUp()

    initial_values = {
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL": True,
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE": datetime.datetime(2002, 3, 11, 0, 0),
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT": 123.456,
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT": 789,
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG": {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        },
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF": cdbuuid.create_uuid(),
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT": "testtext"
    }

    initial_multivalues = {
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE_MULTIVALUE": datetime.datetime(2002, 3, 11, 0, 0),
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_MULTIVALUE": 123.456,
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT_MULTIVALUE": 789,
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG_MULTIVALUE": {
            "de": {
                "iso_language_code": "de",
                "text_value": "de value"
            },
            "en": {
                "iso_language_code": "en",
                "text_value": "en value"
            }
        },
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF_MULTIVALUE": cdbuuid.create_uuid(),
        "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE": "testtext"
    }

    def _set_initial_values(self, data):
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE_MULTIVALUE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_MULTIVALUE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_MULTIVALUE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT_MULTIVALUE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT_MULTIVALUE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG_MULTIVALUE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG_MULTIVALUE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF_MULTIVALUE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF_MULTIVALUE"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"]
        data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0][ClassificationConstants.VALUE] = TestMultipleUpdate.initial_multivalues["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"]

    def _get_simple_prop_value(self, prop_value, language=None):
        prop_type = prop_value["property_type"]
        if "float" == prop_type:
            return prop_value[ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
        elif "multilang" == prop_type:
            return prop_value[ClassificationConstants.VALUE][language][ClassificationConstants.MULTILANG_VALUE]
        else:
            return prop_value[ClassificationConstants.VALUE]

    def _set_simple_prop_value(self, prop_value, value):
        prop_type = prop_value["property_type"]
        if "float" == prop_type:
            prop_value[ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = value
        elif "multilang" == prop_type:
            if not prop_value[ClassificationConstants.VALUE]:
                prop_value[ClassificationConstants.VALUE] = value
        else:
            prop_value[ClassificationConstants.VALUE] = value

    def test_class_assignments(self):
        """  Test setting class assignments for multiple objects. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = {
                ClassificationConstants.ASSIGNED_CLASSES: assigned_classes,
                ClassificationConstants.PROPERTIES: {}
            }
            api.update_classification(doc_1, data)

            ClassificationUpdater.multiple_update(docs, data)
            for doc in docs:
                classification = api.get_classification(doc)
                self.assertListEqual(assigned_classes, classification[ClassificationConstants.ASSIGNED_CLASSES])

    def test_with_previous_class_assignments(self):
        """  Test setting class assignments for multiple objects. """

        with testcase.error_logging_disabled():
            doc_with_assigned_class = self.create_document("doc_with_assigned_class")
            prev_assigned_data = api.get_new_classification(["TEST_CLASS_COMPUTATION"])
            prev_assigned_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_TIME"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 3.5
            api.update_classification(doc_with_assigned_class, prev_assigned_data)

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            docs = [doc_with_assigned_class]
            ClassificationUpdater.multiple_update(docs, data)

            classification = api.get_classification(doc_with_assigned_class)
            self.assertTrue("TEST_CLASS_COMPUTATION" in classification[ClassificationConstants.ASSIGNED_CLASSES])
            self.assertTrue("TEST_CLASS_ALL_PROPERTY_TYPES" in classification[ClassificationConstants.ASSIGNED_CLASSES])
            self.assertAlmostEqual(
                3.5,
                classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_TIME"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )

    def test_exclusive_class_assignments(self):
        """  Test setting exclusive class assignments for multiple objects. """

        with testcase.error_logging_disabled():
            doc = self.create_document("test doc with exclusive class assigments")
            docs = [doc]

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_1_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            ClassificationUpdater.multiple_update(docs, data)

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_2_2_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            errors, _ = ClassificationUpdater.multiple_update(docs, data)
            self.assertTrue(len(errors) > 0, "Exclusive error expected")

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])
            self.assertTrue("TEST_CLASS_EXCLUSIVE_2_2_1" not in classification[ClassificationConstants.ASSIGNED_CLASSES])

    def test_exclusive_class_assignments_same_class(self):

        with testcase.error_logging_disabled():
            doc = self.create_document("test doc with exclusive class assigments")
            docs = [doc]

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_1_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            ClassificationUpdater.multiple_update(docs, data)

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_1_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            errors, _ = ClassificationUpdater.multiple_update(docs, data)
            self.assertTrue(len(errors) == 0, "No exclusive error expected")

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])

    def test_exclusive_class_assignments_subclass(self):

        with testcase.error_logging_disabled():
            doc = self.create_document("test doc with exclusive class assigments")
            docs = [doc]

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            ClassificationUpdater.multiple_update(docs, data)

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])

            assigned_classes = ["TEST_CLASS_EXCLUSIVE_1_1"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            errors, _ = ClassificationUpdater.multiple_update(docs, data)
            self.assertTrue(len(errors) == 0, "No exclusive error expected")

            classification = api.get_classification(doc)
            self.assertTrue("TEST_CLASS_EXCLUSIVE_1_1" in classification[ClassificationConstants.ASSIGNED_CLASSES])

    def test_new_classification_simple_property_types(self):
        """  Test new classification for multiple objects. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)

            ClassificationUpdater.multiple_update(docs, data)
            for doc in docs:
                persistent_classification_data = api.get_classification(doc)
                self.assertListEqual(assigned_classes, persistent_classification_data[ClassificationConstants.ASSIGNED_CLASSES])

                for prop_code, value in TestMultipleUpdate.initial_values.items():
                    if isinstance(value, dict):
                        for key, single_value in value.items():
                            self.assertEqual(
                                single_value["text_value"],
                                self._get_simple_prop_value(persistent_classification_data[ClassificationConstants.PROPERTIES][prop_code][0], key)
                            )
                    else:
                        self.assertEqual(
                            value,
                            self._get_simple_prop_value(persistent_classification_data[ClassificationConstants.PROPERTIES][prop_code][0])
                        )

    def test_update_classification_delete_simple_single_value_properties(self):
        """  Test update classification to delete simple single valued properties. """

        def delete_property(prop_code):
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete_all"
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc_data_updated in [api.get_classification(doc_1), api.get_classification(doc_2)]:
                self.assertEqual(
                    None,
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )
                self.assertEqual(
                    None,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["id"]
                )

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)

            api.update_classification(doc_1, data)

            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL")
            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE")
            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT")
            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT")
            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF")
            delete_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT")

    def test_update_classification_simple_single_value_properties(self):
        """  Test update classification for simple single valued properties. """

        def update_property(prop_code, new_value):
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(update_data[ClassificationConstants.PROPERTIES][prop_code][0], None)

            # test multiple update with no values
            ClassificationUpdater.multiple_update(docs, update_data)
            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                TestMultipleUpdate.initial_values[prop_code],
                self._get_simple_prop_value(doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )
            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                None,
                self._get_simple_prop_value(doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )

            # test multiple update with new values
            self._set_simple_prop_value(update_data[ClassificationConstants.PROPERTIES][prop_code][0], new_value)
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    new_value,
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)

            api.update_classification(doc_1, data)

            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL", False)
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE", datetime.datetime(2012, 4, 17, 0, 0))
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT", 456.786)
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT", 123)
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF", cdbuuid.create_uuid())
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT", "new testtext")

    def test_update_classification_delete_multilang_properties(self):
        """  Test update classification to delete single multilang values. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)
            api.update_classification(doc_1, data)

            # check multiple updates with none
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["operation"] = "delete_all"
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc_data_updated in [api.get_classification(doc_1), api.get_classification(doc_2)]:
                for lang in ["de", "en"]:
                    self.assertEqual(
                        None,
                        doc_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE][lang]["text_value"]
                    )
                    self.assertEqual(
                        None,
                        doc_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE][lang]["id"]
                    )

    def test_update_classification_delete_float_range_properties(self):
        """  Test update classification to delete float range values. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"]
            data = api.get_new_classification(assigned_classes, with_defaults=True)
            api.update_classification(doc_1, data)

            prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT"
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete_all"
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc_data_updated in [api.get_classification(doc_1), api.get_classification(doc_2)]:
                for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                    self.assertEqual(
                        None,
                        doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["value"][range_identifier]["float_value"]
                    )
                    self.assertEqual(
                        None,
                        doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["value"][range_identifier]["id"]
                    )

    def test_update_classification_update_float_range_property(self):
        """  Test update classification to update single float range value. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"]
            data = api.get_new_classification(assigned_classes, with_defaults=True)
            api.update_classification(doc_1, data)

            prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT"
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["float_value"] = 123.456
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["float_value"] = 456.789
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc_data_updated in [api.get_classification(doc_1), api.get_classification(doc_2)]:
                self.assertAlmostEqual(
                    123.456,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["float_value"]
                )
                self.assertAlmostEqual(
                    456.789,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["float_value"]
                )

    def test_update_classification_update_multivalued_float_range_property(self):
        """  Test update classification to update float range value. """

        def _compare_value(prop_code, pos_1, data_1, pos_2, data_2):
            for range_identifier in ["min", "max"]:
                self.assertAlmostEqual(
                    data_1[ClassificationConstants.PROPERTIES][prop_code][pos_1]["value"][range_identifier]["float_value"],
                    data_2[ClassificationConstants.PROPERTIES][prop_code][pos_2]["value"][range_identifier]["float_value"]
                )
                self.assertEqual(
                    data[ClassificationConstants.PROPERTIES][prop_code][pos_1]["value"][range_identifier]["unit_object_id"],
                    persistent_data[ClassificationConstants.PROPERTIES][prop_code][pos_2]["value"][range_identifier]["unit_object_id"]
                )

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            docs = [doc_1]

            prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT_MULTIVALUE"
            assigned_classes = ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)

            data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["float_value"] = 10.0
            data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["unit_object_id"] = cm.cdb_object_id
            data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["float_value"] = 10.0
            data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["unit_object_id"] = m.cdb_object_id

            api.update_classification(doc_1, data)

            # don't add same value twice
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["float_value"] = 10.0
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["unit_object_id"] = cm.cdb_object_id
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["float_value"] = 10.0
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["unit_object_id"] = m.cdb_object_id
            ClassificationUpdater.multiple_update(docs, update_data)

            persistent_data = api.get_classification(doc_1)
            self.assertEqual(1, len(persistent_data[ClassificationConstants.PROPERTIES][prop_code]))
            _compare_value(prop_code, 0, data, 0, persistent_data)

            # add new value
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["float_value"] = 20.0
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["min"]["unit_object_id"] = cm.cdb_object_id
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["float_value"] = 20.0
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["value"]["max"]["unit_object_id"] = m.cdb_object_id
            ClassificationUpdater.multiple_update(docs, update_data)

            persistent_data = api.get_classification(doc_1)
            self.assertEqual(2, len(persistent_data[ClassificationConstants.PROPERTIES][prop_code]))
            _compare_value(prop_code, 0, data, 0, persistent_data)
            _compare_value(prop_code, 0, update_data, 1, persistent_data)

            # remove single value
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete"
            ClassificationUpdater.multiple_update(docs, update_data)

            persistent_data = api.get_classification(doc_1)
            self.assertEqual(1, len(persistent_data[ClassificationConstants.PROPERTIES][prop_code]))
            _compare_value(prop_code, 0, data, 0, persistent_data)

            # remove not existing value
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete"
            ClassificationUpdater.multiple_update(docs, update_data)

            persistent_data = api.get_classification(doc_1)
            self.assertEqual(1, len(persistent_data[ClassificationConstants.PROPERTIES][prop_code]))
            _compare_value(prop_code, 0, data, 0, persistent_data)

    def test_update_classification_multilang_properties(self):
        """  Test update classification for single multilang values. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)
            api.update_classification(doc_1, data)

            # check multiple updates with none
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = None
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            for lang in ["de", "en"]:
                self.assertEqual(
                    TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][lang]["text_value"],
                    doc_1_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE][lang]["text_value"]
                )
            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                MultilangObjectPropertyValue.get_empty_value(),
                doc_2_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]
            )

            # check multiple updates with empty strings
            update_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": ""
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": ""
                }
            }
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            for lang in ["de", "en"]:
                self.assertEqual(
                    TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][lang]["text_value"],
                    doc_1_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE][lang]["text_value"]
                )
            doc_2_data_updated = api.get_classification(doc_2)
            for lang in ["de", "en"]:
                self.assertEqual(
                    "",
                    doc_2_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE][lang]["text_value"]
                )

            # check multiple updates with partial languages
            update_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": ""
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "only en value updated"
                }
            }
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                TestMultipleUpdate.initial_values["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"]["de"]["text_value"],
                doc_1_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"]["text_value"]
            )
            self.assertEqual(
                "only en value updated",
                doc_1_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"]["text_value"]
            )

            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                "",
                doc_2_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"]["text_value"]
            )
            self.assertEqual(
                "only en value updated",
                doc_2_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"]["text_value"]
            )

            # check multiple updates with all languages set
            update_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "de value updated"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "en value updated"
                }
            }
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    "de value updated",
                    doc_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"]["text_value"]
                )
                self.assertEqual(
                    "en value updated",
                    doc_data_updated[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"]["text_value"]
                )

    def test_update_classification_simple_multivalued_property_types(self):
        """  Test update classification for multiple objects with simple multivalued properties. """

        def update_property(prop_code, new_value):
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(update_data[ClassificationConstants.PROPERTIES][prop_code][0], None)

            # test multiple update with no values
            ClassificationUpdater.multiple_update(docs, update_data)
            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                TestMultipleUpdate.initial_multivalues[prop_code],
                self._get_simple_prop_value(doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )
            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                None,
                self._get_simple_prop_value(doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )

            # test multiple update with same values
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                TestMultipleUpdate.initial_multivalues[prop_code]
            )
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                TestMultipleUpdate.initial_multivalues[prop_code],
                self._get_simple_prop_value(doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )
            self.assertEqual(
                1, len(doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                "Same values should not be duplicated!"
            )
            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                TestMultipleUpdate.initial_multivalues[prop_code],
                self._get_simple_prop_value(doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
            )

            # test multiple update with new value
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                new_value
            )
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    2,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "Different values should be added!"
                )
                self.assertEqual(
                    TestMultipleUpdate.initial_multivalues[prop_code],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )
                self.assertEqual(
                    new_value,
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][1])
                )

            # test that empty values are replaced
            for doc in docs:
                doc_data = api.get_classification(doc)
                doc_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE] = None
                api.update_classification(doc, doc_data)

            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                TestMultipleUpdate.initial_multivalues[prop_code]
            )
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    2,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "Empty values should be replaced!"
                )
                self.assertEqual(
                    TestMultipleUpdate.initial_multivalues[prop_code],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )

            # test delete single value
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                new_value
            )
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete"
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    1,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "One value should be deleted!"
                )
                self.assertEqual(
                    TestMultipleUpdate.initial_multivalues[prop_code],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )

            # test delete all values
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                new_value
            )
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    2,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "Two values should exist!"
                )

            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0]["operation"] = "delete_all"
            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    1,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "One empty value should exist!"
                )
                self.assertEqual(
                    None,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0]["id"],
                    "Value should not be persistent!"
                )

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]  # @UnusedVariable

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)
            api.update_classification(doc_1, data)

            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE_MULTIVALUE", datetime.datetime(2012, 4, 17, 0, 0))
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_MULTIVALUE", 456.786)
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT_MULTIVALUE", 123)
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF_MULTIVALUE", cdbuuid.create_uuid())
            update_property("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE", "new testtext")

            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]
            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_initial_values(data)

            # test adding multiple values at once
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            self._set_simple_prop_value(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0],
                TestMultipleUpdate.initial_multivalues[prop_code]
            )

            new_values = ["new testtext 1", "new testtext 2"]
            index = 1
            for new_value in new_values:
                update_data[ClassificationConstants.PROPERTIES][prop_code].append(
                    dict(update_data[ClassificationConstants.PROPERTIES][prop_code][0])
                )
                self._set_simple_prop_value(
                    update_data[ClassificationConstants.PROPERTIES][prop_code][index],
                    new_value
                )
                index += 1

            ClassificationUpdater.multiple_update(docs, update_data)
            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    3,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code]),
                    "Different values should be added!"
                )
                self.assertEqual(
                    TestMultipleUpdate.initial_multivalues[prop_code],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0])
                )
                self.assertEqual(
                    new_values[0],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][1])
                )
                self.assertEqual(
                    new_values[1],
                    self._get_simple_prop_value(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][2])
                )

    def test_update_classification_delete_from_top_level_blocks(self):
        """  Test update classification deleting from top level blocks. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.datetime(2003, 3, 11, 0, 0)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"].append(
                dict(data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0])
            )
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2013, 3, 11, 0, 0)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE] = datetime.datetime(2023, 3, 11, 0, 0)
            api.update_classification(doc_1, data)

            # check delete single value in blocks
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2023, 3, 11, 0, 0)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0]["operation"] = "delete"
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    1,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"]),
                    "One value should exist!"
                )
                self.assertIsNotNone(
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0]["id"],
                    "Value should be persistent!"
                )

            # check delete all in blocks
            data = api.get_classification(doc_1)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"].append(
                dict(data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0])
            )
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2013, 3, 11, 0, 0)
            api.update_classification(doc_1, data)

            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0]["operation"] = "delete_all"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0]["operation"] = "delete_all"
            ClassificationUpdater.multiple_update(docs, update_data)

            for doc in docs:
                doc_data_updated = api.get_classification(doc)
                self.assertEqual(
                    1,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"]),
                    "One empty value should exist!"
                )
                self.assertEqual(
                    None,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0]["id"],
                    "Value should not be persistent!"
                )
                self.assertEqual(
                    1,
                    len(doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"]),
                    "One empty value should exist!"
                )
                self.assertEqual(
                    None,
                    doc_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0]["id"],
                    "Value should not be persistent!"
                )

    def test_update_classification_top_level_blocks(self):
        """  Test update classification for top level blocks only. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.datetime(2003, 3, 11, 0, 0)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"].append(
                dict(data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0])
            )
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2013, 3, 11, 0, 0)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE] = datetime.datetime(2023, 3, 11, 0, 0)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.datetime(2003, 5, 11)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2013, 5, 11, 0, 0)

            api.update_classification(doc_1, data)
            doc_1_data_initial = api.get_classification(doc_1)

            # check multiple updates with no values set
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = None
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = None
            ClassificationUpdater.multiple_update(docs, update_data)

            # existing data should not be overwritten
            doc_1_data_updated = api.get_classification(doc_1)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE]
            )
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )

            doc_2_data_updated = api.get_classification(doc_2)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            self.assertEqual(
                None,
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
            )
            self.assertEqual(
                None,
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            self.assertEqual(
                None,
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                None,
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )

            # check multiple updates with values set
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.datetime(2103, 5, 11, 0, 0)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2113, 5, 11, 0, 0)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.datetime(2103, 5, 11, 0, 0)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE] = datetime.datetime(2113, 5, 11, 0, 0)
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][1][ClassificationConstants.VALUE]
            )
            # check if new value is added to the end ...
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][2][ClassificationConstants.VALUE]
            )
            # test if there are no updates for multivalued blocks
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )

            doc_2_data_updated = api.get_classification(doc_2)
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )
            # test if there are values added for new  multivalued blocks
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE_MULTIVALUE"][0][ClassificationConstants.VALUE]
            )

    def test_update_classification_multivalued_blocks_with_identifying_property(self):
        """  Test update classification for blocks with identifying prop. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            doc_2 = self.create_document("test doc 2")
            docs = [doc_1, doc_2]

            assigned_classes = ["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTY"]
            prop_code_autocreate = "TEST_CLASS_BLOCK_IDENTIFYING_PROPERTY_TEST_PROP_BLOCK_TEMPERATURE"
            prop_code_no_autocreate = "TEST_CLASS_BLOCK_IDENTIFYING_PROPERTY_TEST_PROP_BLOCK_TEMPERATURE_1"
            prop_code_max = "TEST_PROP_TEMPERATURE_MAX"
            prop_code_min = "TEST_PROP_TEMPERATURE_MIN"
            prop_code_type = "TEST_PROP_TEMPERATURE_TYPE"

            prop_code_nested = "TEST_CLASS_BLOCK_IDENTIFYING_PROPERTY_TEST_PROP_BLOCK_NESTED_WITH_IDENTIFYING_PROP"
            prop_code_temperature = "TEST_PROP_BLOCK_TEMPERATURE"

            data = api.get_new_classification(assigned_classes, with_defaults=True, create_all_blocks=True)
            data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 0.0
            data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 10.0
            data[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 20.0
            data[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 100.0

            data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE] = \
            data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]
            data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = -30.0
            data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 1000.0

            data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 77.0
            data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 88.0

            api.update_classification(doc_1, data)
            doc_1_data_initial = api.get_classification(doc_1)

            # check multiple updates with values set
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 9.0
            update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 99.0

            update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE] = \
            update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]
            update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = -500.0
            update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 0.0
            update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 11.0
            update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 22.0

            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )

            doc_2_data_updated = api.get_classification(doc_2)
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_no_autocreate][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_2_data_updated[ClassificationConstants.PROPERTIES][prop_code_nested][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_temperature][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )

    def test_update_classification_multivalued_blocks_adding_block_with_identifying_property(self):
        """  Test adding a new block value for blocks with identifying prop. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            docs = [doc_1]

            assigned_classes = ["TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE"]

            prop_code = "TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE_TEST_PROP_BLOCK_TEMPERATURES"
            prop_code_sub_block = "TEST_PROP_BLOCK_TEMPERATURE_WITHOUT_CREATE"
            prop_code_max = "TEST_PROP_TEMPERATURE_MAX"
            prop_code_min = "TEST_PROP_TEMPERATURE_MIN"
            prop_code_type = "TEST_PROP_TEMPERATURE_TYPE"

            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "Betriebstemperatur"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "Operating Temperature"
                }
            }
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 11.0
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 22.0

            api.update_classification(doc_1, data)
            doc_1_data_initial = api.get_classification(doc_1)

            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "Lagertemperatur"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "Storage Temperature"
                }
            }
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 0.0
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 100.0

            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]["de"]["text_value"],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]["de"]["text_value"]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]["de"]["text_value"],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_type][0][ClassificationConstants.VALUE]["de"]["text_value"]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_min][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block][1][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_max][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )

    def test_no_updates_for_blocks_with_non_unique_key_path(self):
        """  Test that blocks are not updated if their key path is not unique. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            docs = [doc_1]

            assigned_classes = ["TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE"]

            prop_code = "TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE_TEST_PROP_BLOCK_NESTED_SINGLE"
            prop_code_sub_block_multiple = "TEST_PROP_BLOCK_MULTIVALUE"
            prop_code_sub_block_single = "TEST_PROP_BLOCK_SINGLE"
            prop_code_text = "TEST_PROP_TEXT"

            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 1"
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 2 multiple"
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 2 single"
            data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 3 multiple"

            api.update_classification(doc_1, data)
            doc_1_data_initial = api.get_classification(doc_1)

            update_data = api.get_new_classification(assigned_classes, with_defaults=False)
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "updated test text level 1"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "updated test text level 2 multiple"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "updated test text level 2 single"
            update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "updated test text level 3 multiple"
            ClassificationUpdater.multiple_update(docs, update_data)

            doc_1_data_updated = api.get_classification(doc_1)
            ClassificationUpdater.multiple_update(docs, update_data)
            # test not changed values
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                doc_1_data_initial[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE]
            )

            # test changed values
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                update_data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE],
                doc_1_data_updated[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE]
            )

    def test_mandatory_properties(self):
        """  Test that mandatory properties are checked. """

        with testcase.error_logging_disabled():
            doc_1 = self.create_document("test doc 1")
            docs = [doc_1]

            assigned_classes = ["TEST_CLASS_MANDATORY_PROPERTIES"]
            mandatory_prop_paths = [
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_NESTED_MULTIVALUED_MANDATORY_PROPS/TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_NESTED_MULTIVALUED_MANDATORY_PROPS/TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_NESTED_MANDATORY_PROPS/TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_NESTED_MANDATORY_PROPS/TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BOOL_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_DATE_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_DATE_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_FLOAT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_FLOAT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_INT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_INT_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_MULTILANG_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_MULTILANG_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_OBJREF_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_OBJREF_MANDATORY_MULTIVALUE",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_TEXT_MANDATORY",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_TEXT_MANDATORY_MULTIVALUE",
            ]
            mandatory_prop_values = {
                "": None,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_NESTED_MULTIVALUED_MANDATORY_PROPS/TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_MULTIVALUE_WITH_NESTED_MULTIVALUED_MANDATORY_PROPS/TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_NESTED_MANDATORY_PROPS/TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BLOCK_WITH_NESTED_MANDATORY_PROPS/TEST_PROP_BLOCK_WITH_MANDATORY_PROPS/TEST_PROP_TEXT_MANDATORY_MULTIVALUE": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_BOOL_MANDATORY": True,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_DATE_MANDATORY": datetime.datetime(2002, 3, 11, 0, 0),
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_DATE_MANDATORY_MULTIVALUE": datetime.datetime(2002, 3, 11, 0, 0),
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_FLOAT_MANDATORY": 123.456,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_FLOAT_MANDATORY_MULTIVALUE": 123.456,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_INT_MANDATORY": 789,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_INT_MANDATORY_MULTIVALUE": 789,
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_MULTILANG_MANDATORY": {
                    "de": {
                        "iso_language_code": "de",
                        "text_value": "de value"
                    },
                    "en": {
                        "iso_language_code": "en",
                        "text_value": "en value"
                    }
                },
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_MULTILANG_MANDATORY_MULTIVALUE": {
                    "de": {
                        "iso_language_code": "de",
                        "text_value": "de value"
                    },
                    "en": {
                        "iso_language_code": "en",
                        "text_value": "en value"
                    }
                },
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_OBJREF_MANDATORY": cdbuuid.create_uuid(),
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_OBJREF_MANDATORY_MULTIVALUE": cdbuuid.create_uuid(),
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_TEXT_MANDATORY": "testtext",
                "TEST_CLASS_MANDATORY_PROPERTIES_TEST_PROP_TEXT_MANDATORY_MULTIVALUE": "testtext"
            }
            expected_errors = list(mandatory_prop_paths)
            update_data = api.get_new_classification(assigned_classes, with_defaults=False)

            for prop_code, prop_value in mandatory_prop_values.items():
                if prop_code:
                    prop_path = prop_code.split("/")
                    top_level_prop_code = prop_path[0]
                    prop_value_data = update_data[ClassificationConstants.PROPERTIES][top_level_prop_code][0]
                    for prop_path_segment in prop_path[1:]:
                        prop_value_data = prop_value_data["value"]["child_props"][prop_path_segment][0]
                    self._set_simple_prop_value(prop_value_data, prop_value)

                    expected_errors.remove(prop_code)

                errors, _ = ClassificationUpdater.multiple_update(docs, update_data)
                doc_1_data_updated = api.get_classification(doc_1)

                if expected_errors:
                    self.assertEqual(len(doc_1_data_updated["assigned_classes"]), 0)
                    self.assertTrue(len(errors) > 0)
                    for expected_error in expected_errors:
                        self.assertIn(expected_error, errors[doc_1.cdb_object_id].getDetails())
                else:
                    self.assertEqual(len(doc_1_data_updated["assigned_classes"]), 1)
                    self.assertTrue(len(errors) == 0)

    def test_computation(self):
        """  Test that properties are calculated. """

        with testcase.error_logging_disabled():
            doc = self.create_document("test doc 1")
            docs = [doc]

            assigned_classes = ["COMPUTER"]
            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_TYPE"][0][ClassificationConstants.VALUE] = "Desktop"
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE] = 2
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_MODULE_SIZE"][0][ClassificationConstants.VALUE] = 8192
            errors, _ = ClassificationUpdater.multiple_update(docs, data)

            self.assertTrue(len(errors) == 0)
            persistent_classification_data = api.get_classification(doc)
            self.assertEqual(
                persistent_classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_SIZE"][0][ClassificationConstants.VALUE],
                16384,
                "COMPUTER_COMPUTER_MAX_RAM_SIZE should be calculated"
            )

    def test_constraints(self):
        """  Test that constraints are checked. """

        with testcase.error_logging_disabled():
            doc = self.create_document("test doc 1")
            docs = [doc]
            assigned_classes = ["COMPUTER"]

            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE] = 4
            errors, _ = ClassificationUpdater.multiple_update(docs, data)
            self.assertTrue(len(errors) > 0)

            data = api.get_new_classification(assigned_classes, with_defaults=False)
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_TYPE"][0][ClassificationConstants.VALUE] = "Notebook"
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE] = 4
            data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_MODULE_SIZE"][0][ClassificationConstants.VALUE] = 8192

            errors, _ = ClassificationUpdater.multiple_update(docs, data)
            self.assertTrue(len(errors) > 0)
            error_message = str(errors[doc.cdb_object_id])
            self.assertEqual(error_message, "Notebooks können maximal 2 RAM Module haben.")

            persistent_classification_data = api.get_classification(doc)
            self.assertEqual(len(persistent_classification_data["assigned_classes"]), 0)


    def test_rights(self):
        with testcase.error_logging_disabled():
            doc_released = self.create_document("test doc released")
            assigned_classes = ["TEST_CLASS_RIGHTS_OLC"]
            create_data = api.get_new_classification(assigned_classes, with_defaults=False)
            create_data["properties"]["TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY"][0]["value"] = "mandatory text"
            create_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"] = "test text"
            api.update_classification(doc_released, create_data)

            obj_classification = ObjectClassification.ByKeys(
                class_code = "TEST_CLASS_RIGHTS_OLC",
                ref_object_id = doc_released.cdb_object_id
            )
            obj_classification.ChangeState(200)

            doc_draft = self.create_document("test doc draft")
            api.update_classification(doc_draft, create_data)

            op_data = api.get_new_classification(assigned_classes, with_defaults=False)
            op_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"] = "test text updated"
            errors, warnings = ClassificationUpdater.multiple_update([doc_released, doc_draft], op_data)

            self.assertEqual(0, len(errors))
            self.assertEqual(1, len(warnings))

            data = api.get_classification(doc_released)
            self.assertEqual(
                data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"],
                create_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"]
            )

            data = api.get_classification(doc_draft)
            self.assertEqual(
                data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"],
                op_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"]
            )

            op_data = api.get_new_classification(assigned_classes, with_defaults=False)
            op_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["operation"] = "delete_all"
            errors, warnings = ClassificationUpdater.multiple_update([doc_released, doc_draft], op_data)
            self.assertEqual(0, len(errors))
            self.assertEqual(1, len(warnings))

            data = api.get_classification(doc_released)
            self.assertEqual(
                data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"],
                create_data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"]
            )

            data = api.get_classification(doc_draft)
            self.assertEqual(
                data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"],
                None
            )
