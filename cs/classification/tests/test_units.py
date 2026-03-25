# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from cdb import testcase
from cdb.objects import ByID
from cs.documents import Document  # @UnresolvedImport
from cs.classification import api, ClassificationConstants
from cs.classification.tests import utils
from cs.classification.units import Unit, normalize_value


class TestUnits(utils.ClassificationTestCase):

    def setUp(self):
        super(TestUnits, self).setUp()
        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.empty_classification = {
            ClassificationConstants.ASSIGNED_CLASSES: [],
            ClassificationConstants.PROPERTIES: {}
        }
        # ensure that classification is empty
        api.update_classification(self.document, self.empty_classification)
        classification_data = api.get_classification(self.document)
        self.assertEqual(
            self.empty_classification[ClassificationConstants.ASSIGNED_CLASSES],
            classification_data[ClassificationConstants.ASSIGNED_CLASSES]
        )
        self.assertEqual(
            self.empty_classification[ClassificationConstants.PROPERTIES],
            classification_data[ClassificationConstants.PROPERTIES]
        )

    def test_matching_unit_object_ids(self):
        """  Test if unit object ids match for property definitions and empty values. """

        with testcase.error_logging_disabled():
            classification_data = {}
            new_classes = ["TEST_CLASS_UNITS"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(classification_data[ClassificationConstants.ASSIGNED_CLASSES], new_classes)

            property_default_unit_oid = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_1"]["default_unit_object_id"]
            value_unit_object_id = classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["unit_object_id"]
            self.assertEqual(property_default_unit_oid, value_unit_object_id)

            property_default_unit_oid = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_2"]["default_unit_object_id"]
            value_unit_object_id = classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_2"][0]["value"]["unit_object_id"]
            self.assertEqual(property_default_unit_oid, value_unit_object_id)

            property_default_unit_oid = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"]["child_props_data"]["TEST_PROP_FLOAT_WITH_UNIT_1"]["default_unit_object_id"]
            value_unit_object_id = classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"][0]["value"]["child_props"]["TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["unit_object_id"]
            self.assertEqual(property_default_unit_oid, value_unit_object_id)

            property_default_unit_oid = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"]["child_props_data"]["TEST_PROP_FLOAT_WITH_UNIT_2"]["default_unit_object_id"]
            value_unit_object_id = classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"][0]["value"]["child_props"]["TEST_PROP_FLOAT_WITH_UNIT_2"][0]["value"]["unit_object_id"]
            self.assertEqual(property_default_unit_oid, value_unit_object_id)

    def test_property_metadata_for_units(self):
        """  Test property metadata concerning units. """

        with testcase.error_logging_disabled():
            classification_data = {}
            new_classes = ["TEST_CLASS_UNITS"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(classification_data[ClassificationConstants.ASSIGNED_CLASSES], new_classes)

            prop = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_1"]
            property_default_unit_oid = prop["default_unit_object_id"]
            unit = ByID(property_default_unit_oid)
            self.assertEqual("km", unit.symbol)
            self.assertEqual(0, prop["flags"][8])

            prop = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_2"]
            property_default_unit_oid = prop["default_unit_object_id"]
            unit = ByID(property_default_unit_oid)
            self.assertEqual("minute", unit.symbol)
            self.assertEqual(1, prop["flags"][8])

            prop = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"]["child_props_data"]["TEST_PROP_FLOAT_WITH_UNIT_1"]
            property_default_unit_oid = prop["default_unit_object_id"]
            unit = ByID(property_default_unit_oid)
            self.assertEqual("dm", unit.symbol)
            self.assertEqual(0, prop["flags"][8])

            prop = classification_data["new_classes_metadata"]["TEST_CLASS_UNITS"]["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"]["child_props_data"]["TEST_PROP_FLOAT_WITH_UNIT_2"]
            property_default_unit_oid = prop["default_unit_object_id"]
            unit = ByID(property_default_unit_oid)
            self.assertEqual("minute", unit.symbol)
            self.assertEqual(1, prop["flags"][8])

    def test_normalization(self):
        """  Test normalization for float values. """

        with testcase.error_logging_disabled():
            classification_data = {}
            new_classes = ["TEST_CLASS_UNITS"]
            classification_data = api.rebuild_classification(classification_data, new_classes)
            self.assertEqual(classification_data[ClassificationConstants.ASSIGNED_CLASSES], new_classes)

            classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["float_value"] = 1.5
            classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"][0]["value"]["child_props"]["TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["float_value"] = 20.0

            api.update_classification(self.document, classification_data)

            self.assertAlmostEqual(
                1500.0,
                classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["float_value_normalized"]
            )
            self.assertAlmostEqual(
                2.0,
                classification_data["properties"]["TEST_CLASS_UNITS_TEST_PROP_BLOCK_WITH_UNIT"][0]["value"]["child_props"]["TEST_PROP_FLOAT_WITH_UNIT_1"][0]["value"]["float_value_normalized"]
            )

    def test_percentage(self):
        percent = Unit.KeywordQuery(symbol="pct")[0]
        permill = Unit.KeywordQuery(symbol="permill")[0]

        normalized_value = normalize_value(10.0, percent.cdb_object_id, percent.cdb_object_id, "TEST_PROP")
        self.assertEqual(10.0, normalized_value)
        normalized_value = normalize_value(10.0, permill.cdb_object_id, percent.cdb_object_id, "TEST_PROP")
        self.assertEqual(1.0, normalized_value)
