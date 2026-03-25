# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import datetime
import pytz

from cdb import sig, testcase, ue, cdbuuid
from cdb.constants import kOperationCopy, kOperationNew
from cdb.objects import operations

from cs.documents import Document  # @UnresolvedImport

from cs.classification import api, ClassificationConstants
from cs.classification.classification_data import ClassesNotApplicableException
from cs.classification.tests import utils
from cs.classification.units import UnitCache


class TestExternalApi(utils.ClassificationTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExternalApi, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    def setUp(self):
        super(TestExternalApi, self).setUp()
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

    def test_external_api(self):
        """  Test get and update classification with external api. """

        with testcase.error_logging_disabled():
            # check that object is not classified
            classification_data = api.get_classification(self.document)
            self.assertEqual(
                set(self.empty_classification[ClassificationConstants.ASSIGNED_CLASSES]),
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES])
            )
            self.assertEqual(
                self.empty_classification[ClassificationConstants.PROPERTIES],
                classification_data[ClassificationConstants.PROPERTIES]
            )

            # get classification data for new class
            new_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(new_classes)
            )

            # TEST_PROP_BLOCK_WITH_DATE/TEST_PROP_DATE
            # TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK/TEST_PROP_BLOCK_WITH_SUB_BLOCK/TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE/TEST_PROP_DATE

            # set values
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"][0][ClassificationConstants.VALUE] = True
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2002, 3, 11)
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 123.456
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE] = 789
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "de value"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "en value"
                }
            }
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE] = self.document.cdb_object_id
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext"

            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2003, 3, 11)
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2004, 3, 11)

            # persist classification data
            api.update_classification(self.document, classification_data)

            persistent_classification_data = api.get_classification(self.document)
            self.assertEqual(
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(persistent_classification_data[ClassificationConstants.ASSIGNED_CLASSES])
            )
            self.assertEqual(
                True,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                datetime.datetime(2002, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertAlmostEqual(
                123.456,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                789,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                "de value",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"][ClassificationConstants.MULTILANG_VALUE]
            )
            self.assertEqual(
                "en value",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"][ClassificationConstants.MULTILANG_VALUE]
            )
            self.assertEqual(
                self.document.cdb_object_id,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                "testtext",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE]
            )

            self.assertEqual(
                datetime.datetime(2003, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                datetime.datetime(2004, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )

            # assign additional class
            new_classes = ["TEST_CLASS_COMPUTATION"]
            persistent_classification_data = api.rebuild_classification(persistent_classification_data, new_classes)
            self.assertEqual(
                set(persistent_classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(["TEST_CLASS_ALL_PROPERTY_TYPES", "TEST_CLASS_COMPUTATION"])
            )

            distance_default_unit = persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_DISTANCE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE_UNIT_OID]
            compatible_unit_oids = UnitCache.get_compatible_units(distance_default_unit)
            for compatible_unit_oid in compatible_unit_oids:
                compatible_unit = UnitCache.get_unit_info(compatible_unit_oid)
                if compatible_unit["symbol"] == "cm":
                    distance_unit_iod = compatible_unit["cdb_object_id"]

            persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_DISTANCE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 1800.0
            persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_DISTANCE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE_UNIT_OID] = distance_unit_iod

            persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_TIME"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 3.5

            # persist and calculate classification data
            api.update_classification(self.document, persistent_classification_data)

            self.assertAlmostEqual(
                1800.0,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_DISTANCE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertAlmostEqual(
                18.0,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_DISTANCE"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE_NORMALIZED]
            )
            self.assertAlmostEqual(
                3.5,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_TIME"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertAlmostEqual(
                5.142857142857143,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_SPEED"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                "Q",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_TYRE_SPEED_CLASS"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                68,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_PROP_COMPUTATION_A"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                34,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_COMPUTATION_TEST_PROP_COMPUTATION_B"][0][ClassificationConstants.VALUE]
            )

    def test_applicable_classes(self):
        from requests import ConnectionError
        from cdb.storage.index.errors import InvalidService

        try:
            all_applicable_classes = api.get_applicable_classes(self.document, deep=True, only_active=False, only_released=False)
            top_level_applicable_classes = api.get_applicable_classes(self.document, deep=False, only_active=False, only_released=False)
            self.assertTrue(len(top_level_applicable_classes) < len(all_applicable_classes))

            self.assertTrue("TEST_CLASS_APPLICABLE" in all_applicable_classes)
            self.assertTrue("TEST_CLASS_APPLICABLE" in top_level_applicable_classes)

            self.assertFalse("TEST_CLASS_ALL_PROPERTY_TYPES" in top_level_applicable_classes)
            self.assertTrue("TEST_CLASS_ALL_PROPERTY_TYPES" in all_applicable_classes)
        except (ConnectionError, InvalidService):
            # ignore solr connection exceptions
            pass

    def test_get_catalog_values(self):
        values = set()
        catalog_values = api.get_catalog_values("TEST_CLASS_RIVET", "TEST_CLASS_RIVET_TEST_PROP_RIVET_TYPE", False)
        for catalog_value in catalog_values:
            values.add(catalog_value["value"])
        expected_values = set(["Blind", "Countersunk", "Tubular"])
        self.assertEqual(expected_values, values)

    def test_get_float_catalog_values(self):
        catalog_values = api.get_catalog_values("TEST_CLASS_FLOAT_ENUMS", "TEST_CLASS_FLOAT_ENUMS_DURCHMESSER", False)
        for catalog_value in catalog_values:
            value = catalog_value["value"]
            self.assertTrue("float_value_normalized" in value, "float_value_normalized should exist.")
            if "m" == value["unit_label"]:
                self.assertAlmostEqual(1000 * value["float_value"], value["float_value_normalized"])
            elif "cm" == value["unit_label"]:
                self.assertAlmostEqual(10 * value["float_value"], value["float_value_normalized"])
            elif "mm" == value["unit_label"]:
                self.assertAlmostEqual(value["float_value"], value["float_value_normalized"])
            else:
                pass

    def test_get_catalog_values_for_classes(self):

        catalog_values = api.get_all_catalog_values(["TEST_CLASS_RIVET"], False)

        values = set()
        for catalog_value in catalog_values["TEST_CLASS_RIVET_TEST_PROP_RIVET_TYPE"]:
            values.add(catalog_value["value"])
        expected_values = set(["Blind", "Countersunk", "Tubular"])
        self.assertEqual(expected_values, values)

        values = set()
        for catalog_value in catalog_values["TEST_PROP_WEIGHT_TYPE"]:
            values.add(catalog_value["value"])
        expected_values = set(["Gross weight", "Net weight"])
        self.assertEqual(expected_values, values)

        catalog_values = api.get_all_catalog_values(["TEST_CLASS_FLOAT_ENUMS"], False)

        values = set()
        for catalog_value in catalog_values["TEST_CLASS_FLOAT_ENUMS_DURCHMESSER"]:
            values.add(catalog_value["value"]["float_value"])
        expected_values = set([1.0, 10.0, 100.0])
        self.assertSetEqual(expected_values, values)

        for catalog_value in catalog_values["TEST_CLASS_FLOAT_ENUMS_DURCHMESSER"]:
            value = catalog_value["value"]
            self.assertTrue("float_value_normalized" in value, "float_value_normalized should exist.")
            if "m" == value["unit_label"]:
                self.assertAlmostEqual(1000 * value["float_value"], value["float_value_normalized"])
            elif "cm" == value["unit_label"]:
                self.assertAlmostEqual(10 * value["float_value"], value["float_value_normalized"])
            elif "mm" == value["unit_label"]:
                self.assertAlmostEqual(value["float_value"], value["float_value_normalized"])
            else:
                pass

        for catalog_value in catalog_values["TEST_CLASS_FLOAT_ENUMS_VOLUMEN"]:
            value = catalog_value["value"]
            self.assertTrue("float_value_normalized" in value, "float_value_normalized should exist.")
            self.assertAlmostEqual(value["float_value"], value["float_value_normalized"])


    def test_additional_properties(self):

        with testcase.error_logging_disabled():
            classification_data = api.get_classification(self.document)
            new_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(new_classes)
            )
            # set values
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"][0][ClassificationConstants.VALUE] = True
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2002, 3, 11)
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE] = 123.456
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE] = 789
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "de value"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "en value"
                }
            }
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE] = self.document.cdb_object_id
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext"

            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2003, 3, 11)
            classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = datetime.date(2004, 3, 11)

            # persist classification data
            api.update_classification(self.document, classification_data)

            addtl_props = api.get_additional_props(self.document, with_metadata=True)
            self.assertDictEqual(addtl_props, self.empty_addtl_props)

            # add additional properties
            addtl_props = api.create_additional_props(["TEST_PROP_TEXT", "TEST_PROP_WEIGHT", "TEST_PROP_BLOCK_TEMPERATURE"])
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

            api.update_additional_props(self.document, addtl_props)

            addtl_props = api.get_additional_props(self.document, with_metadata=True)
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

            api.update_additional_props(
                self.document, {
                    "deleted_properties": ["TEST_PROP_WEIGHT", "TEST_PROP_BLOCK_TEMPERATURE"]
                }
            )

            addtl_props = api.get_additional_props(self.document)
            self.assertEqual(
                "testtext",
                addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE]
            )
            self.assertFalse("TEST_PROP_WEIGHT" in addtl_props[ClassificationConstants.PROPERTIES])
            self.assertFalse("TEST_PROP_BLOCK_TEMPERATURE" in addtl_props[ClassificationConstants.PROPERTIES])

            # check classification data
            persistent_classification_data = api.get_classification(self.document)
            self.assertEqual(
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(persistent_classification_data[ClassificationConstants.ASSIGNED_CLASSES])
            )

            self.assertEqual(
                True,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BOOL"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                datetime.datetime(2002, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertAlmostEqual(
                123.456,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0][ClassificationConstants.VALUE][ClassificationConstants.FLOAT_VALUE]
            )
            self.assertEqual(
                789,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                "de value",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["de"][ClassificationConstants.MULTILANG_VALUE]
            )
            self.assertEqual(
                "en value",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0][ClassificationConstants.VALUE]["en"][ClassificationConstants.MULTILANG_VALUE]
            )
            self.assertEqual(
                self.document.cdb_object_id,
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_OBJREF"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                "testtext",
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0][ClassificationConstants.VALUE]
            )

            self.assertEqual(
                datetime.datetime(2003, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )
            self.assertEqual(
                datetime.datetime(2004, 3, 11, 0, 0),
                persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS]["TEST_PROP_DATE"][0][ClassificationConstants.VALUE]
            )

    def test_signals(self):
        """ Test copy and update classification signal. """

        def check_signals(update_post):
            signals["classification_updated_pre"] = False
            signals["classification_updated_post"] = False
            self.assertFalse(signals["classification_updated_pre"])
            self.assertFalse(signals["classification_updated_post"])
            api.update_classification(self.document, classification)
            self.assertTrue(signals["classification_updated_pre"])
            self.assertEqual(update_post, signals["classification_updated_post"])

        try:


            @sig.connect(Document, "classification_update", "pre")
            def classification_updated(obj, data):
                signals["classification_updated_pre"] = True

            @sig.connect(Document, "classification_update", "post")
            def classification_updated_post(obj, data):
                signals["classification_updated_post"] = True

            signals = {
                "classification_updated_pre": False,
                "classification_updated_post": False
            }

            addtl_prop_code = "TEST_PROP_TEXT"
            class_code = "TEST_CLASS_ALL_PROPERTY_TYPES"
            prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"

            classification = api.create_additional_props([addtl_prop_code])
            classification[ClassificationConstants.ASSIGNED_CLASSES] = []
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

            classification[ClassificationConstants.PROPERTIES] = {}
            classification["deleted_properties"] = [addtl_prop_code]
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

            classification = {
                ClassificationConstants.ASSIGNED_CLASSES: [class_code],
                ClassificationConstants.PROPERTIES: {}
            }
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

            classification = {
                ClassificationConstants.ASSIGNED_CLASSES: [],
                ClassificationConstants.PROPERTIES: {}
            }
            check_signals(True)

            classification = api.get_new_classification( [class_code])
            classification[ClassificationConstants.PROPERTIES][prop_code][0]["value"] = "Text 1"
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

            api.add_multivalue(classification, prop_code)
            classification[ClassificationConstants.PROPERTIES][prop_code][1]["value"] = "Text 2"
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

            del classification[ClassificationConstants.PROPERTIES][prop_code][-1]
            check_signals(True)
            classification = api.get_classification(self.document)
            check_signals(False)

        finally:
            sig.disconnect(classification_updated)
            sig.disconnect(classification_updated_post)

    def test_pre_update(self):
        """ Test modifications in classification_update pre. """

        try:

            @sig.connect(Document, "classification_update", "pre")
            def classification_updated(obj, data):
                if signals and signals.get("classification_updated_pre", False):
                    signals["classification_updated_pre"] = False
                    data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
                    api.rebuild_classification(data, new_classes=["TEST_CLASS_RIGHTS_OLC"])

            signals = {
                "classification_updated_pre": True
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            api.update_classification(self.document, classification)

            classification = api.get_classification(self.document)
            self.assertSetEqual(
                set(classification["assigned_classes"]),
                set(assigned_classes + ["TEST_CLASS_RIGHTS_OLC"])
            )
            self.assertEqual(
                classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext"
            )
        finally:
            sig.disconnect(classification_updated)

    def test_ue_args(self):
        """ Test ue_args in signals. """

        try:

            @sig.connect(Document, "classification_update", "pre")
            def classification_update_pre(obj, data):
                if signals and signals.get("classification_update_pre", False):
                    signals["classification_update_pre"] = False
                    self.assertEqual(
                        data[ClassificationConstants.UE_ARGS]["cs.classification.aggregation_call"],
                        classification[ClassificationConstants.UE_ARGS]["cs.classification.aggregation_call"]
                    )
                    data[ClassificationConstants.UE_ARGS]["cs.classification.aggregation_call_pre"] = "ue_args from pre update"

            @sig.connect(Document, "classification_update", "post")
            def classification_update_post(obj, data):
                if signals and signals.get("classification_update_post", False):
                    signals["classification_update_post"] = False
                    self.assertEqual(
                        "ue_args from pre update",
                        classification[ClassificationConstants.UE_ARGS]["cs.classification.aggregation_call_pre"]
                    )

            signals = {
                "classification_update_pre": True,
                "classification_update_post": True
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            classification[ClassificationConstants.UE_ARGS] = {
                "cs.classification.aggregation_call": "ue_args before update"
            }
            api.update_classification(self.document, classification)

        finally:
            sig.disconnect(classification_update_pre)
            sig.disconnect(classification_update_post)

    def test_add_and_remove_class(self):
        """ Test signals for adding and removing classes. """

        try:

            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, data):
                signals["updated_data"] = data

            signals = {
                "updated_data": None
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES", "TEST_CLASS_ARTICLE"]
            classification = api.get_new_classification(assigned_classes)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
            api.update_classification(self.document, classification)

            data = signals["updated_data"]
            self.assertIsNotNone(data)
            self.assertSetEqual(set(assigned_classes), set(data["new_classes"]))
            self.assertListEqual([], data["deleted_classes"])
            self.assertListEqual([], data["deleted_properties"])

            classification = api.get_classification(self.document)
            classification["assigned_classes"] = ["TEST_CLASS_ARTICLE"]
            classification = api.rebuild_classification(classification, ["TABLET"])
            api.update_classification(self.document, classification)

            data = signals["updated_data"]
            self.assertIsNotNone(data)
            self.assertSetEqual(set(["TEST_CLASS_ARTICLE", "TABLET"]), set(data["assigned_classes"]))
            self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["deleted_classes"])
            self.assertListEqual(["TABLET"], data["new_classes"])
            self.assertTrue(len(data["deleted_properties"]) > 0)
            self.assertTrue(len(data["properties"]) > 0)

            classification = api.get_classification(self.document)

        finally:
            sig.disconnect(classification_updated)


    def test_add_and_remove_class_partial_update_mode(self):
        assigned_classes = ["TEST_CLASS_TYRE"]
        classification = api.get_new_classification(assigned_classes)
        api.update_classification(self.document, classification, full_update_mode=False)
        self.assertSetEqual(set(assigned_classes), set(classification["assigned_classes"]))

        assigned_classes = ["TEST_CLASS_SCREW"]
        classification = api.get_classification(self.document)
        classification["assigned_classes"] = assigned_classes
        classification["deleted_classes"] = ["TEST_CLASS_RIVET", "TEST_CLASS_TYRE"]
        api.update_classification(self.document, classification, full_update_mode=False)

        classification = api.get_classification(self.document)
        self.assertSetEqual(set(assigned_classes), set(classification["assigned_classes"]))


    def test_add_and_modify_property(self):
        """ Test signals for adding and modifying properties. """

        try:

            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, data):
                signals["updated_data"] = data

            signals = {
                "updated_data": None
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["old_value"],
                None
            )

            classification = api.get_classification(self.document)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext new"
            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext new"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["old_value"],
                "testtext"
            )

        finally:
            sig.disconnect(classification_updated)

    def test_pre_commit(self):
        """ Test pre_commit signal. """

        try:

            @sig.connect(Document, "classification_update", "pre_commit")
            def classification_pre_commit(obj, data, diff_data):
                signals["pre_commit_data"] = diff_data
                data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["value"] = now
                api.rebuild_classification(data, new_classes=["TEST_CLASS_RIGHTS_OLC"])

            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, diff_data):
                signals["updated_data"] = diff_data

            signals = {
                "pre_commit_data": None,
                "updated_data": None
            }

            now = datetime.datetime.utcnow().replace(microsecond=0)

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["value"]["float_value"] = 123.456
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 10.10
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 20.20
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"] = {
                "de": {
                    "iso_language_code": "de",
                    "text_value": "de value"
                },
                "en": {
                    "iso_language_code": "en",
                    "text_value": "en value"
                }
            }
            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]
            self.assertAlmostEqual(
                123.456,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["value"]["float_value"]
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["old_value"],
                None
            )
            self.assertAlmostEqual(
                10.10,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                20.20,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"]
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["old_value"],
                None
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["old_value"],
                None
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"],
                "de value"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["de"]["old_value"],
                None
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["en"]["text_value"],
                "en value"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["en"]["old_value"],
                None
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["value"],
                now
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["old_value"],
                None
            )

            classification = api.get_classification(self.document)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["value"]["float_value"] = 456.789
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 100.0
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 200.0
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext new"
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"] = "new de value"

            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]

            self.assertSetEqual(
                set(updated_data["assigned_classes"]),
                set(assigned_classes + ["TEST_CLASS_RIGHTS_OLC"])
            )

            self.assertAlmostEqual(
                456.789,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["value"]["float_value"]
            )
            self.assertAlmostEqual(
                123.456,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT"][0]["old_value"]["float_value"]
            )

            self.assertAlmostEqual(
                100.0,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                200.0,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"]
            )
            self.assertAlmostEqual(
                10.10,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["old_value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                20.20,
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["old_value"]["max"]["float_value"]
            )

            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext new"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["old_value"],
                "testtext"
            )

            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["de"]["text_value"],
                "new de value"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["de"]["old_value"],
                "de value"
            )

            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["en"]["text_value"],
                "en value"
            )
            self.assertFalse(
                "old_value" in updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_MULTILANG"][0]["value"]["en"]
            )

            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["value"],
                now
            )
            self.assertFalse(
                "old_value" in updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]
            )
        finally:
            sig.disconnect(classification_pre_commit)
            sig.disconnect(classification_updated)

    def test_pre_commit_float_range(self):
        """ Test pre_commit signal for float ranges. """

        # FIXME: add float range to all_prop_types class and integrate this test in test_pre_commit

        try:
            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, diff_data):
                signals["updated_data"] = diff_data

            signals = {
                "updated_data": None
            }

            now = datetime.datetime.utcnow().replace(microsecond=0)

            assigned_classes = ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"]
            prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_MULTIVALUE"

            classification = api.get_new_classification(assigned_classes)
            classification["properties"][prop_code][0]["value"]["min"]["float_value"] = 123.456
            classification["properties"][prop_code][0]["value"]["max"]["float_value"] = 456.789

            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]
            self.assertAlmostEqual(
                123.456,
                updated_data["properties"][prop_code][0]["value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                456.789,
                updated_data["properties"][prop_code][0]["value"]["max"]["float_value"]
            )
            self.assertEqual(
                updated_data["properties"][prop_code][0]["old_value"],
                None
            )

            classification = api.get_classification(self.document)
            classification["properties"][prop_code][0]["value"]["min"]["float_value"] = 456.789
            classification["properties"][prop_code][0]["value"]["max"]["float_value"] = 789.0

            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]

            self.assertAlmostEqual(
                456.789,
                updated_data["properties"][prop_code][0]["value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                789.0,
                updated_data["properties"][prop_code][0]["value"]["max"]["float_value"]
            )
            self.assertAlmostEqual(
                123.456,
                updated_data["properties"][prop_code][0]["old_value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                456.789,
                updated_data["properties"][prop_code][0]["old_value"]["max"]["float_value"]
            )
        finally:
            sig.disconnect(classification_updated)

    def test_remove_property_value(self):
        """ Test signals for removing property value. """

        try:

            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, data):
                signals["updated_data"] = data

            signals = {
                "updated_data": None
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0]["value"] = "testtext 1"

            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"].append(
                dict(classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0])
            )
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][1]["value"] = "testtext 2"
            api.update_classification(self.document, classification)

            classification = api.get_classification(self.document)
            del classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0]
            api.update_classification(self.document, classification)

            updated_data = signals["updated_data"]

            self.assertEqual(
                updated_data["deleted_properties"][0].property_path,
                "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE:000"
            )
        finally:
            sig.disconnect(classification_updated)

    def test_add_modify_and_remove_additional_property(self):
        """ Test signals for additional properties. """

        try:

            @sig.connect(Document, "classification_update", "post")
            def classification_updated(obj, data):
                signals["updated_data"] = data

            signals = {
                "updated_data": None
            }

            # add additional property
            addtl_props = api.create_additional_props(["TEST_PROP_TEXT"])
            addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext first"
            api.update_additional_props(self.document, addtl_props)

            updated_data = signals["updated_data"]
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["value"],
                "testtext first"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["old_value"],
                None
            )

            addtl_props = api.get_additional_props(self.document, with_metadata=True)
            addtl_props[ClassificationConstants.PROPERTIES]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext second"
            api.update_additional_props(self.document, addtl_props)
            updated_data = signals["updated_data"]
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["value"],
                "testtext second"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["old_value"],
                "testtext first"
            )

            classification = api.get_classification(self.document)
            classification = api.rebuild_classification(classification, ["TEST_CLASS_ALL_PROPERTY_TYPES"])
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
            classification["properties"]["TEST_PROP_TEXT"][0][ClassificationConstants.VALUE] = "testtext third"
            api.update_classification(self.document, classification)
            updated_data = signals["updated_data"]
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["value"],
                "testtext third"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_PROP_TEXT"][0]["old_value"],
                "testtext second"
            )

            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext"
            )
            self.assertEqual(
                updated_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["old_value"],
                None
            )
        finally:
            sig.disconnect(classification_updated)

    def test_external_api_with_computation(self):
        """  Test get and update classification with external api and computation. """

        with testcase.error_logging_disabled():
            # check that object is not classified
            classification_data = api.get_classification(self.document)
            self.assertEqual(
                set(self.empty_classification[ClassificationConstants.ASSIGNED_CLASSES]),
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES])
            )
            self.assertEqual(self.empty_classification[ClassificationConstants.PROPERTIES], classification_data[ClassificationConstants.PROPERTIES])

            # get classification data for new class
            new_classes = ["TEST_CLASS_VARIABLES"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(
                set(classification_data[ClassificationConstants.ASSIGNED_CLASSES]),
                set(new_classes)
            )
            api.update_classification(self.document, classification_data)

            persistent_classification_data = api.get_classification(self.document)
            m_date = persistent_classification_data[ClassificationConstants.PROPERTIES]["TEST_CLASS_VARIABLES_TEST_PROP_VARIABLE_DATETIME"][0][ClassificationConstants.VALUE]
            self.assertGreaterEqual(datetime.datetime.utcnow(), m_date)

    def test_date_formulas(self):
        """  Test date formulas with external api. """

        assigned_classes = ["TEST_CLASS_DATE_FORMULA"]
        classification = api.get_new_classification(assigned_classes)
        now = datetime.datetime.utcnow().replace(microsecond=0)
        classification["properties"]["TEST_CLASS_DATE_FORMULA_TEST_PROP_DATE"][0]["value"] = now
        api.update_classification(self.document, classification)

        persistent_classification_data = api.get_classification(self.document)
        self.assertEqual(
            now,
            persistent_classification_data["properties"]["TEST_CLASS_DATE_FORMULA_TEST_PROP_DATE"][0]["value"]
        )

    def test_date_values(self):
        """  Test date values with external api. """

        date_value = datetime.datetime(2002, 3, 11, 10, 15, 20, 30)
        date_value = date_value.replace(tzinfo=pytz.timezone('Asia/Taipei'))

        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification = api.get_new_classification(assigned_classes)
        classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = date_value
        api.update_classification(self.document, classification)

        persistent_classification = api.get_classification(self.document)
        # timezone and microseconds are not stored in database
        expected_date_value = date_value.replace(tzinfo=None)
        expected_date_value = expected_date_value.replace(microsecond=0)
        self.assertEqual(
            expected_date_value,
            persistent_classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0]["value"]
        )

        persistent_classification[ClassificationConstants.PROPERTIES]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_DATE"][0][ClassificationConstants.VALUE] = date_value
        api.update_classification(self.document, persistent_classification)

    def test_bool_defaults(self):
        """  Test default values for booleans. """
        classification_data = api.get_classification(self.document)
        classification_data = api.rebuild_classification(classification_data, ["TEST_CLASS_BOOL_DEFAULT"])

        # check default value
        self.assertEqual(
            True,
            classification_data["properties"]["TEST_CLASS_BOOL_DEFAULT_TEST_PROP_BOOL"][0]["value"]
        )
        self.assertEqual(
            False,
            classification_data["properties"]["TEST_CLASS_BOOL_DEFAULT_TEST_PROP_BOOL_2"][0]["value"]
        )

        api.update_classification(self.document, classification_data)
        persistent_classification_data = api.get_classification(self.document)

        # check default formula
        self.assertEqual(
            True,
            persistent_classification_data["properties"]["TEST_CLASS_BOOL_DEFAULT_TEST_PROP_BOOL_1"][0]["value"]
        )
        self.assertEqual(
            False,
            persistent_classification_data["properties"]["TEST_CLASS_BOOL_DEFAULT_TEST_PROP_BOOL_3"][0]["value"]
        )

    def test_empty_eav_entries(self):
        expected_property_codes = ["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"]

        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification = api.get_new_classification(assigned_classes)
        classification["properties"][expected_property_codes[0]][0]["value"] = "testtext 1"
        api.update_classification(self.document, classification)

        classification = api.get_classification(self.document, pad_missing_properties=False)
        self.assertListEqual(expected_property_codes, list(classification["properties"].keys()))

        classification = api.get_classification(self.document)
        expected_property_codes.append("TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_INT")
        classification["properties"][expected_property_codes[1]][0]["value"] = 123
        api.update_classification(self.document, classification)

        classification = api.get_classification(self.document, pad_missing_properties=False)
        self.assertSetEqual(set(expected_property_codes), set(classification["properties"].keys()))

    def test_readonly_properties(self):
        doc = operations.operation(
            kOperationNew,
            Document,
            titel="Document for classification test",
            z_categ1="142",
            z_categ2="153"
        )

        assigned_classes = ["TEST_CLASS_CONSTRAINTS"]
        classification = api.get_new_classification(assigned_classes)

        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"
        classification["properties"][changed_property_code][0]["value"] = "SQUARE"
        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"
        classification["properties"][changed_property_code][0]["value"]["float_value"] = 1.5
        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_DICKE"
        classification["properties"][changed_property_code][0]["value"]["float_value"] = .2
        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE"
        classification["properties"][changed_property_code][0]["value"]["float_value"] = 1.5
        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_MATERIAL"
        classification["properties"][changed_property_code][0]["value"] = "Holz"

        api.update_classification(doc, classification)
        classification = api.get_classification(doc)
        self.assertEqual(
            "SQUARE",
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"][0]["value"]
        )
        self.assertEqual(
            "Holz",
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_MATERIAL"][0]["value"]
        )
        self.assertAlmostEqual(
            1.5,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"][0]["value"]["float_value"]
        )
        self.assertAlmostEqual(
            .2,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_DICKE"][0]["value"]["float_value"]
        )
        self.assertAlmostEqual(
            1.5,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE"][0]["value"]["float_value"]
        )
        self.assertAlmostEqual(
            2.25,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"][0]["value"]["float_value"]
        )

        doc.ChangeState(200)
        classification = api.get_classification(doc)
        changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"
        classification["properties"][changed_property_code][0]["value"]["float_value"] = 2.5
        api.update_classification(doc, classification)

        classification = api.get_classification(doc)
        self.assertAlmostEqual(
            1.5,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"][0]["value"]["float_value"]
        )
        self.assertAlmostEqual(
            2.25,
            classification["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"][0]["value"]["float_value"]
        )

        classification = api.rebuild_classification(classification, ["TEST_CLASS_RIGHTS_MARKETING"])
        changed_property_code = "TEST_CLASS_RIGHTS_MARKETING_TEST_PROP_TEXT_MANDATORY"
        classification["properties"][changed_property_code][0]["value"] = "Testtext"
        changed_property_code = "TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY"
        classification["properties"][changed_property_code][0]["value"] = "4711"

        api.update_classification(doc, classification)

        classification = api.get_classification(doc)
        self.assertEqual(
            "Testtext",
            classification["properties"]["TEST_CLASS_RIGHTS_MARKETING_TEST_PROP_TEXT_MANDATORY"][0]["value"]
        )
        self.assertEqual(
            "4711",
            classification["properties"]["TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY"][0]["value"]
        )

        with self.assertRaisesRegex(ue.Exception, "Sie sind nicht berechtigt.*"):
            classification = api.rebuild_classification(classification, ["COMPUTER"])
            api.update_classification(doc, classification)

    def test_add_multivalue(self):
        assigned_classes = ["TEST_CLASS_COMPARE"]
        classification = api.get_new_classification(assigned_classes)

        prop_path = "TEST_CLASS_COMPARE_TEST_PROP_TEXT_MULTIVALUE"
        existing_values = len(classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT_MULTIVALUE"])
        new_value = api.add_multivalue(classification, prop_path)
        self.assertIsNotNone(new_value)
        self.assertEqual(
            existing_values + 1,
            len(classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT_MULTIVALUE"])
        )
        new_value["value"] = "New Text"
        self.assertEqual(
            "New Text",
            classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_TEXT_MULTIVALUE"][existing_values]["value"]
        )

        prop_path = "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED:001/TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        existing_values = len(
            classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED"][0]["value"][
                "child_props"]["TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"]
        )
        new_value = api.add_multivalue(classification, prop_path)
        self.assertIsNotNone(new_value)
        self.assertEqual(
            existing_values + 1,
            len(
                classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED"][0]["value"][
                    "child_props"]["TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"]
            )
        )

        new_value["value"]["child_props"]["TEST_PROP_TEXT"][0]["value"] = "New Text"
        self.assertEqual(
            "New Text",
            classification["properties"]["TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED"][0]["value"][
                "child_props"]["TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"][existing_values]["value"][
                "child_props"]["TEST_PROP_TEXT"][0]["value"]
        )

    def test_add_multivalue_with_wrong_paths(self):
        assigned_classes = ["TEST_CLASS_COMPARE"]
        classification = api.get_new_classification(assigned_classes)

        wrong_prop_paths = [
            "NOTEXISTING_PROP",
            "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED:001/NOTEXISTING_PROP"
            "TEST_CLASS_COMPARE_TEST_PROP_BLOCK_COMPARE_NESTED:999/TEST_PROP_BLOCK_WITH_ALL_PROP_TYPES_MULTIVALUE"
        ]

        for prop_path in wrong_prop_paths:
            with self.assertRaisesRegex(Exception, "Ungültiger Merkmalpfad: {}".format(prop_path)):
                api.add_multivalue(classification, prop_path)

    def test_reset_classification(self):
        new_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification_data = api.get_new_classification(new_classes)
        api.update_classification(self.document, classification_data)

        classification_data = api.get_classification(self.document)
        self.assertEqual(classification_data[ClassificationConstants.ASSIGNED_CLASSES], new_classes)


        self.empty_classification = {
            ClassificationConstants.ASSIGNED_CLASSES: [],
            ClassificationConstants.PROPERTIES: {}
        }
        api.update_classification(self.document, self.empty_classification)

        classification_data = api.get_classification(self.document)
        self.assertEqual(classification_data[ClassificationConstants.ASSIGNED_CLASSES], [])

        classification_data[ClassificationConstants.ASSIGNED_CLASSES] = new_classes
        api.update_classification(self.document, classification_data)

    def test_get_with_access_check(self):
        doc_numbers = ['CLASS000010', 'CLASS000012']
        for doc_number in doc_numbers:
            doc = Document.ByKeys(z_nummer=doc_number, z_index="")
            all_classification_data = api.get_classification(doc, check_rights=False)
            all_property_codes = set(all_classification_data["properties"].keys())

            filtered_classification_data = api.get_classification(doc, check_rights=True)
            filtered_property_codes = set(filtered_classification_data["properties"].keys())

            self.assertTrue(len(all_property_codes) > len(filtered_property_codes))

    def test_copy_signals(self):
        try:
            @sig.connect(Document, "classification_copy", "pre")
            def classification_copy_pre(obj, data):
                signals["classification_copy_pre"] = True
                data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"

            @sig.connect(Document, "classification_copy", "post")
            def classification_copy_post(obj, data):
                signals["classification_copy_post"] = True
                self.assertEqual(
                    data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                    "testtext"
                )

            signals = {
                "classification_copy_pre": False,
                "classification_copy_post": False
            }

            assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            classification = api.get_new_classification(assigned_classes)
            api.update_classification(self.document, classification)

            doc_copy = operations.operation(
                kOperationCopy,
                self.document,
                z_nummer=cdbuuid.create_uuid()[:19],
                z_index="",
                ursprungs_z=""
            )
            self.assertTrue(signals["classification_copy_pre"])
            self.assertTrue(signals["classification_copy_post"])

            classification = api.get_classification(doc_copy)
            self.assertSetEqual(
                set(classification["assigned_classes"]),
                set(assigned_classes)
            )
            self.assertEqual(
                classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"],
                "testtext"
            )
        finally:
            sig.disconnect(classification_copy_pre)
            sig.disconnect(classification_copy_post)
    
    def test_float_range(self):
        classification = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
        classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"] = 10.1
        api.update_classification(self.document, classification)

        classification = api.get_classification(self.document)
        self.assertAlmostEqual(
            10.10,
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"]
        )
        self.assertAlmostEqual(
            None,
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"]
        )
        classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"] = 20.20

        api.update_classification(self.document, classification)
        classification = api.get_classification(self.document)
        self.assertAlmostEqual(
            10.10,
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["min"]["float_value"]
        )
        self.assertAlmostEqual(
            20.20,
            classification["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_FLOAT_RANGE"][0]["value"]["max"]["float_value"]
        )

    def test_not_existing_class(self):
        with self.assertRaises(KeyError):
            api.get_new_classification(["not existing class code", "TEST_CLASS_ALL_PROPERTY_TYPES"])
        with self.assertRaisesRegexp(ClassesNotApplicableException, u"Klassen k.*nnen nicht zugeordnet werden:.*"):
            api.get_new_classification(["not existing class code", "TEST_CLASS_ALL_PROPERTY_TYPES"])

        classification = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
        with self.assertRaises(KeyError):
            api.rebuild_classification(classification, ["not existing class code"])
        with self.assertRaisesRegexp(ClassesNotApplicableException, u"Klassen k.*nnen nicht zugeordnet werden:.*"):
            api.rebuild_classification(classification, ["not existing class code"])


