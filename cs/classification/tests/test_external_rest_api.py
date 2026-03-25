# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from webtest import TestApp as Client

from cdb import sig, testcase
from cs.classification.tests import utils
from cs.documents import Document  # @UnresolvedImport
from cs.platform.web.root import Root
from cs.classification import api, ClassificationConstants


class TestExternalRestApi(utils.ClassificationTestCase):

    def setUp(self):
        super(TestExternalRestApi, self).setUp()
        self.client = Client(Root())
        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.empty_classification = {
            "assigned_classes": [],
            "properties": {}
        }

    def _flush_classification(self):
        url = "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id)
        result = self.client.get(url, status=200)
        existing_data = result.json
        existing_data['deleted_classes'] = existing_data['assigned_classes']
        self.client.put_json(url, existing_data)

    def test_flush_classification(self):
        """  Test get and update classification with external rest api. """

        urls = [
            "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id),
            "/api/v1/collection/document/{}@/classification".format(self.document_number)
        ]

        with testcase.error_logging_disabled():
            for url in urls:
                self._flush_classification()
                result = self.client.get(url, status=200)
                classification_data = result.json
                self.assertEqual(self.empty_classification[ClassificationConstants.ASSIGNED_CLASSES], classification_data[ClassificationConstants.ASSIGNED_CLASSES])
                self.assertEqual(self.empty_classification[ClassificationConstants.PROPERTIES], classification_data[ClassificationConstants.PROPERTIES])

    def test_get_classification_url_parameter(self):
        """  Test url parameter for get classification with external rest api. """

        def assert_dict_keys(test_me, expected_keys, shall_contain):
            for key in expected_keys:
                self.assertEqual(shall_contain, key in test_me)

        urls = [
            "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id),
            "/api/v1/collection/document/{}@/classification".format(self.document_number)
        ]
        data = {
            "assigned_classes": ["TEST_CLASS_CAPACITOR"],
            "properties": {}
        }

        with testcase.error_logging_disabled():
            for url in urls:
                api.update_classification(self.document, self.empty_classification, full_update_mode=True)
                # test default parameter
                result = self.client.get(url, status=200)
                assert_dict_keys(result.json, ["assigned_classes", "properties"], True)
                assert_dict_keys(result.json, ["metadata"], False)
                # test with_metadata
                result = self.client.get(url + "?with_metadata=0", status=200)
                assert_dict_keys(result.json, ["assigned_classes", "properties"], True)
                assert_dict_keys(result.json, ["metadata"], False)
                result = self.client.get(url + "?with_metadata=1", status=200)
                assert_dict_keys(result.json, ["assigned_classes", "properties", "metadata"], True)
                # test with_assigned_classes
                result = self.client.get(url + "?with_assigned_classes=0", status=200)
                assert_dict_keys(result.json, ["properties"], True)
                assert_dict_keys(result.json, ["assigned_classes", "metadata"], False)
                result = self.client.get(url + "?with_assigned_classes=1", status=200)
                assert_dict_keys(result.json, ["assigned_classes", "properties"], True)
                assert_dict_keys(result.json, ["metadata"], False)
                # test pad_missing_values
                self.client.put_json(url, data)
                result = self.client.get(url + "?pad_missing_values=0", status=200)
                properties = result.json["properties"]
                self.assertEqual(0, len(properties))
                result = self.client.get(url + "?pad_missing_values=1", status=200)
                result = self.client.get(url, status=200)
                properties = result.json["properties"]
                assert 0 < len(properties)

    def test_get_and_update_classification(self):
        """  Test get and update classification with external rest api. """

        urls = [
            "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id),
            "/api/v1/collection/document/{}@/classification".format(self.document_number)
        ]

        initial_data = {
            "assigned_classes": ["TEST_CLASS_ALL_PROPERTY_TYPES"],
            "properties": {}
        }

        with testcase.error_logging_disabled():
            for url in urls:
                self._flush_classification()
                self.client.put_json(url, initial_data)
                result = self.client.get(url, status=200)
                classification_data = result.json
                self.assertIsNone(classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["id"])
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "test text"
                classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = "2002-03-11T11:22:00"
                self.client.put_json(url, classification_data)
                result = self.client.get(url, status=200)
                classification_data = result.json
                self.assertEqual("test text", classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE])
                self.assertEqual("2002-03-11T11:22:00", classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE])
                self.assertIsNotNone(classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["id"])

    def test_get_new_classification(self):
        """  Test get new classification with external rest api. """

        url = "/api/cs.classification/v1/new_classification"
        data = {
            "new_classes": ["TEST_CLASS_ALL_PROPERTY_TYPES"],
            "with_defaults": True
        }
        with testcase.error_logging_disabled():
            result = self.client.post_json(url, data)
            assert result
            new_classification = result.json
            self.assertTrue("TEST_CLASS_ALL_PROPERTY_TYPES" in new_classification["assigned_classes"])
            self.assertTrue(len(new_classification["properties"]) > 0)

    def test_new_classification_and_set_values(self):
        """  Test new classification with external rest api. """

        with testcase.error_logging_disabled():
            url = "/api/cs.classification/v1/new_classification"
            data = {
                "new_classes": ["TEST_CLASS_ALL_PROPERTY_TYPES"],
                "with_defaults": True
            }
            result = self.client.post_json(url, data)
            assert result
            new_classification = result.json
            self.assertTrue("TEST_CLASS_ALL_PROPERTY_TYPES" in new_classification["assigned_classes"])
            self.assertTrue(len(new_classification["properties"]) > 0)

            new_classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "test text"
            new_classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["value"] = "2002-03-11T11:22:00"

            url = "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id)
            self.client.put_json(url, new_classification)

            result = self.client.get(url, status=200)
            classification_data = result.json
            self.assertEqual("test text", classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE])
            self.assertEqual("2002-03-11T11:22:00", classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE])

    def test_rebuild_classification(self):
        """  Test rebuild classification with external rest api. """

        url = "/api/cs.classification/v1/rebuild"

        data = {
            "assigned_classes": [],
            "new_classes": [],
            "properties": {}
        }
        expected = {
            "assigned_classes": [],
            "new_classes_metadata": {},
            "properties": {}
        }
        with testcase.error_logging_disabled():
            result = self.client.post_json(url, data)
            assert result
            validated_classification = result.json
            self.assertEqual(expected, validated_classification)

    def test_additional_properties(self):
        """  Test additional properties with external rest api. """

        urls = [
            "/api/cs.classification/v1/additional_properties/{}".format(self.document.cdb_object_id),
            "/api/v1/collection/document/{}@/additional_properties".format(self.document_number)
        ]

        with testcase.error_logging_disabled():
            for url in urls:
                create_url = "/api/cs.classification/v1/create_additional_properties"
                data = {
                    "property_codes": ["TEST_PROP_TEXT", "TEST_PROP_WEIGHT", "TEST_PROP_BLOCK_TEMPERATURE"]
                }
                result = self.client.post_json(create_url, data)
                assert result
                addtl_props = result.json
                self.assertSetEqual(set(data["property_codes"]), set(addtl_props["properties"].keys()))
                self.assertSetEqual(set(data["property_codes"]), set(addtl_props["metadata"].keys()))

                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext"
                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_WEIGHT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 180.81
                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_MIN"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = -33.33
                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_MAX"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 66.66
                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_TYPE"][0][ClassificationConstants.VALUE] = {
                    "de": {
                        "iso_language_code": "de",
                        "text_value": "Lagertemperatur"
                    },
                    "en": {
                        "iso_language_code": "en",
                        "text_value": "Storage temperature"
                    }
                }
                result = self.client.put_json(url, addtl_props)
                result = self.client.get(url, addtl_props)

                addtl_props = result.json
                self.assertEqual(
                    "testtext",
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE]
                )
                self.assertAlmostEqual(
                    180.81,
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_WEIGHT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
                )
                self.assertAlmostEqual(
                    -33.33,
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_MIN"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
                )
                self.assertAlmostEqual(
                    66.66,
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_MAX"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
                )
                self.assertEqual(
                    "Lagertemperatur",
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_TYPE"][0][ClassificationConstants.VALUE]["de"]["text_value"]
                )
                self.assertEqual(
                    "Storage temperature",
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_BLOCK_TEMPERATURE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_TEMPERATURE_TYPE"][0][ClassificationConstants.VALUE]["en"]["text_value"]
                )

                data = {
                    "deleted_properties": ["TEST_PROP_WEIGHT", "TEST_PROP_BLOCK_TEMPERATURE"]
                }

                result = self.client.put_json(url, data)

                result = self.client.get(url, addtl_props)
                addtl_props = result.json
                self.assertEqual(
                    "testtext",
                    addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE]
                )
                self.assertFalse("TEST_PROP_WEIGHT" in addtl_props[ClassificationConstants.PROPERTIES])
                self.assertFalse("TEST_PROP_BLOCK_TEMPERATURE" in addtl_props[ClassificationConstants.PROPERTIES])

    def test_computation(self):
        """  Test update classification with computation with external rest api. """

        urls = [
            "/api/cs.classification/v1/classification/{}".format(self.document.cdb_object_id),
            "/api/v1/collection/document/{}@/classification".format(self.document_number)
        ]

        initial_data = {
            "assigned_classes": ["COMPUTER"],
            "properties": {}
        }

        with testcase.error_logging_disabled():
            for url in urls:
                self.client.put_json(url, initial_data)
                result = self.client.get(url, status=200)
                classification_data = result.json
                classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_TYPE"][0][ClassificationConstants.VALUE] = "Notebook"
                classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE] = 2
                classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_MODULE_SIZE"][0][ClassificationConstants.VALUE] = 8192
                self.client.put_json(url, classification_data)
                result = self.client.get(url, status=200)
                data = result.json
                self.assertEqual(
                    classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE],
                    data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE]
                )
                self.assertEqual(
                    classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE],
                    data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE]
                )
                self.assertEqual(
                    classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_RAM_MODULES"][0][ClassificationConstants.VALUE] *
                    classification_data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_MODULE_SIZE"][0][ClassificationConstants.VALUE],
                    data[ClassificationConstants.PROPERTIES]["COMPUTER_COMPUTER_MAX_RAM_SIZE"][0][ClassificationConstants.VALUE]
                )

    def test_pre_assign_class(self):
        """ Test assigning class user exit. """

        try:

            @sig.connect(Document, "classification_select_class")
            def assign_class_pre(obj, assigned_class_codes, new_class):
                if 'TABLET' == new_class:
                    if 'COMPUTER' not in assigned_class_codes:
                        raise Exception('COMPUTER must be assigned')

            url = '/internal/classification/class/TABLET'
            data = {
                'activePropsOnly': True,
                'dataDictionaryClassName': 'document',
                'cdb_object_id': self.document.cdb_object_id,
                'withDefaults': True,
                'assignedClassCodes': [],
                'searchMode': False
            }
            with testcase.error_logging_disabled():
                try:
                    self.client.post_json(url, data)
                    self.fail("Exception expected.")
                except:
                    pass
                try:
                    data['assignedClassCodes'] = ['COMPUTER']
                    self.client.post_json(url, data)
                except:
                    self.fail("Exception not expected.")
        finally:
            sig.disconnect(assign_class_pre)
