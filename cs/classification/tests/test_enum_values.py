# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module util

This module contains test methods for the utility functions.
"""

from cs.classification.catalog import PropertyValue

import datetime
import pytest
import unittest

from cdb import ue
from cdb.constants import kOperationNew
from cdb.objects import operations
from cdb.testcase import RollbackTestCase

from cs.documents import Document  # @UnresolvedImport

from cs.classification import api, ClassificationConstants, tools, util
from cs.classification.catalog import TextProperty, TextPropertyValue, _set_property_values_active_state
from cs.classification.classes import ClassificationClass, ClassProperty, ClassPropertyValueExclude

ERROR_MESSAGE = 'cs_classification_property_value_not_modifiable'


class TestEnumValues(RollbackTestCase):

    class TestContext():

        class Parent():

            def __init__(self, cdb_object_id):
                self.cdb_object_id = cdb_object_id

        def __init__(self, cdb_object_id):
            self.parent = self.Parent(cdb_object_id) if cdb_object_id else None

    def setUp(self):
        super(TestEnumValues, self).setUp()

        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.empty_addtl_props = {
            ClassificationConstants.METADATA: {},
            ClassificationConstants.PROPERTIES: {}
        }
        self.empty_classification = {
            ClassificationConstants.ASSIGNED_CLASSES: [],
            ClassificationConstants.PROPERTIES: {}
        }
        api.update_classification(self.document, self.empty_classification)

    def test_enum_values_from_object_property_values(self):

        def check_enum_values(enum_values, prop_code, expected_values):
            pos = 0
            for value in enum_values[prop_code]:
                prop_val = value["value"]
                if isinstance(prop_val, dict) and "float_value" in prop_val:
                    self.assertAlmostEqual(expected_values[pos], prop_val["float_value"])
                else:
                    self.assertEqual(expected_values[pos], prop_val)
                pos = pos + 1

        def classify_object(title, date_value, float_value, float_value_min, float_value_max, int_value, text_value, text_value_en):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = date_value
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = float_value
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0][ClassificationConstants.VALUE]["min"][ClassificationConstants.FLOAT_VALUE] = float_value_min
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0][ClassificationConstants.VALUE]["max"][ClassificationConstants.FLOAT_VALUE] = float_value_max
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE] = int_value
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"]["text_value"] = text_value
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"]["text_value"] = text_value_en
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE] = self.document.cdb_object_id
            classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = text_value

            api.update_classification(doc, classification)
            return doc

        doc_1 = classify_object("Document enum value test", datetime.datetime(2012, 4, 19), 456.789, 2.2, 3.3, 456, "ein testtext", "a testtext")
        doc_2 = classify_object("Document enum value test", datetime.datetime(2002, 3, 11), 123.456, 1.1, 4.4, 123, "testtext", "testtext")

        enum_values = PropertyValue.object_property_values_to_json_data([doc_1.cdb_object_id, doc_2.cdb_object_id])
        self.assertNotIn("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE", enum_values)
        self.assertNotIn("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG", enum_values)
        check_enum_values(enum_values, "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE", [datetime.datetime(2002, 3, 11), datetime.datetime(2012, 4, 19)])
        check_enum_values(enum_values, "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT", [123.456, 456.789])
        check_enum_values(enum_values, "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT", [123, 456])
        check_enum_values(enum_values, "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF", [self.document.cdb_object_id])
        check_enum_values(enum_values, "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT", ["ein testtext", "testtext"])

    def _create_properties(self):

        prop = TextProperty.Create(
            cdb_objektart="cs_property",
            code="TEST_ENUM_VALUE_PROP",
            has_enum_values=1,
            name_de="TEST_ENUM_VALUE_PROP",
            status=200,
            cdb_status_txt="Released"
        )
        clazz = ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            code="TEST_ENUM_VALUE_CLASS",
            name_de="TEST_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )
        class_prop = ClassProperty.NewPropertyFromCatalog(prop, clazz.cdb_object_id)

        return prop, class_prop

    def _create_property_values(self, prop, prop_values, is_active):
        prop_value_objs = {}
        for prop_value in prop_values:
            value_args = {
                "property_object_id": prop.cdb_object_id,
                "is_active": is_active,
                "text_value": prop_value
            }
            prop_value_objs[prop_value] = TextPropertyValue.Create(**value_args)
        return prop_value_objs

    def _create_property_value_exclude(self, class_prop, prop_value):
        ClassPropertyValueExclude.Create(
            classification_class_id=class_prop.classification_class_id,
            class_property_id=class_prop.cdb_object_id,
            property_id=class_prop.catalog_property_id,
            property_value_id=prop_value.cdb_object_id,
            exclude=1
        )

    def _check_values(self, class_prop, expected_values):
        catalog_values = api.get_catalog_values(
            ClassificationClass.oid_to_code(class_prop.classification_class_id),
            class_prop.code,
            active_only=True,
            request=None
        )
        values = []
        for catalog_value in catalog_values:
            values.append(catalog_value['value'])

        self.assertSetEqual(set(values), set(expected_values))

    def test_activate_operation(self):
        prop, class_prop = self._create_properties()
        prop_values = {}
        prop_values.update(self._create_property_values(prop, ['Active catalog value 1', 'Active catalog value 2'], 1))
        prop_values.update(self._create_property_values(prop, ['Inactive catalog value 1', 'Inactive catalog value 2'], 0))
        prop_values.update(self._create_property_values(class_prop, ['Active class value 1', 'Active class value 2'], 1))
        prop_values.update(self._create_property_values(class_prop, ['Inactive class value 1', 'Inactive class value 2'], 0))
        self._create_property_value_exclude(class_prop, prop_values['Active catalog value 2'])

        self._check_values(class_prop, [
            'Active catalog value 1',
            'Active class value 1',
            'Active class value 2'
        ])

        _set_property_values_active_state(
            class_prop,
            [
                prop_values['Active catalog value 1'],
                prop_values['Active catalog value 2'],
                prop_values['Inactive class value 1']
            ],
            1
        )

        self._check_values(class_prop, [
            'Active catalog value 1',
            'Active catalog value 2',
            'Active class value 1',
            'Active class value 2',
            'Inactive class value 1'
        ])

    def test_deactivate_operation(self):
        prop, class_prop = self._create_properties()
        prop_values = {}
        prop_values.update(self._create_property_values(prop, ['Active catalog value 1', 'Active catalog value 2'], 1))
        prop_values.update(self._create_property_values(prop, ['Inactive catalog value 1', 'Inactive catalog value 2'], 0))
        prop_values.update(self._create_property_values(class_prop, ['Active class value 1', 'Active class value 2'], 1))
        prop_values.update(self._create_property_values(class_prop, ['Inactive class value 1', 'Inactive class value 2'], 0))

        self._check_values(class_prop, [
            'Active catalog value 1',
            'Active catalog value 2',
            'Active class value 1',
            'Active class value 2'
        ])
        class_prop.default_value_oid = prop_values['Active catalog value 1'].cdb_object_id

        _set_property_values_active_state(
            class_prop,
            [
                prop_values['Active catalog value 1'],
                prop_values['Active class value 1']
            ],
            0
        )
        # check if default value has been set to None
        self.assertIsNone(class_prop.default_value_oid)
        self._check_values(class_prop, [
            'Active catalog value 2',
            'Active class value 2'
        ])

        class_prop.default_value_oid = prop_values['Active class value 2'].cdb_object_id

        _set_property_values_active_state(
            class_prop,
            [
                prop_values['Active catalog value 2'],
                prop_values['Active class value 2']
            ],
            0
        )

        # check if default value has been set to None
        self.assertIsNone(class_prop.default_value_oid)
        self._check_values(class_prop, [])
        # check is has_enum_flag is False
        self.assertEqual(0, class_prop.has_enum_values)

    def test_parent_relation(self):
        prop, class_prop = self._create_properties()
        prop_values = {}
        prop_values.update(self._create_property_values(prop, ['Catalog value 1', 'Catalog value 2'], 1))
        prop_values.update(self._create_property_values(class_prop, ['Class value 1', 'Class value 2'], 1))

        catalog_prop_value = prop_values['Catalog value 1']
        catalog_prop_value.check_parent_relation(TestEnumValues.TestContext(None), ERROR_MESSAGE)
        catalog_prop_value.check_parent_relation(TestEnumValues.TestContext(prop.cdb_object_id), ERROR_MESSAGE)

        with self.assertRaisesRegex(ue.Exception, ".*"):
            catalog_prop_value.check_parent_relation(TestEnumValues.TestContext(class_prop.cdb_object_id), ERROR_MESSAGE)

        class_prop_value = prop_values['Class value 1']
        class_prop_value.check_parent_relation(TestEnumValues.TestContext(None), ERROR_MESSAGE)
        class_prop_value.check_parent_relation(TestEnumValues.TestContext(class_prop.cdb_object_id), ERROR_MESSAGE)

        with self.assertRaisesRegex(ue.Exception, ".*"):
            class_prop_value.check_parent_relation(TestEnumValues.TestContext(prop.cdb_object_id), ERROR_MESSAGE)

    def test_labels(self):
        catalog_prop_code = "TEST_PROP_ENUM_LABELS"
        class_prop_code = "TEST_CLASS_ENUM_LABELS_TEST_PROP_ENUM_LABELS"

        enum_values_by_code = util.get_enum_values_with_labels([catalog_prop_code, class_prop_code])

        expected_enum_labels = dict()
        expected_enum_labels[catalog_prop_code] = set(
            ['Lagertemperatur', 'Betriebstemperatur']
        )
        expected_enum_labels[class_prop_code] = set(
            ['Lagertemperatur', 'Umgebungstemperatur', 'Betriebstemperatur']
        )

        for code, enum_values in enum_values_by_code.items():
            if code in [catalog_prop_code, class_prop_code]:
                labels = set()
                for enum_value in enum_values:
                    labels.add(tools.get_label("label", enum_value))
                self.assertSetEqual(labels, expected_enum_labels[code])
            else:
                self.fail("unexpectd prop code found:" + code)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
