# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import cdb
from cdb.objects import operations

from cs import documents

from cs.classification import api, catalog, classes, units
from cs.classification.tests import utils


class FloatPropertyTest(utils.ClassificationTestCase):

    def setUp(self):
        super(FloatPropertyTest, self).setUp()
        self.document = operations.operation(
            cdb.constants.kOperationNew,
            documents.Document,
            titel="titel",
            z_categ1="142",
            z_categ2="153"
        )

    def test_float_property(self):
        prop_code = "TEST_PROP_FLOAT"
        addtl_prop_data = api.create_additional_props([prop_code])

        self.assertTrue(prop_code in addtl_prop_data["metadata"])
        prop = addtl_prop_data["metadata"][prop_code]
        self.assertEqual("float", prop["type"])
        self.assertEqual("", prop["default_unit_object_id"])
        self.assertEqual("", prop["default_unit_symbol"])
        self.assertListEqual([None, 6], prop["float_format"])

        self.assertTrue(prop_code in addtl_prop_data["properties"])
        value = addtl_prop_data["properties"][prop_code][0]
        self.assertEqual("float", value["property_type"])
        empty_value = {
            'float_value': None,
            'float_value_normalized': None,
            'unit_object_id': ''
        }
        self.assertDictEqual(empty_value, value["value"])

        classification_data = api.get_classification(self.document)

        classification_data["properties"] = addtl_prop_data["properties"]
        classification_data["properties"][prop_code][0]["value"]["float_value"] = 10.10

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        input_value = classification_data["properties"][prop_code][0]["value"]
        persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"])
        self.assertIsNotNone(persistent_classification_data["properties"][prop_code][0]["id"])
        self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
        self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value_normalized"])
        self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

        classification_data = persistent_classification_data
        classification_data["properties"][prop_code][0]["value"]["float_value"] = 20.20

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        input_value = classification_data["properties"][prop_code][0]["value"]
        persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"])
        self.assertIsNotNone(persistent_classification_data["properties"][prop_code][0]["id"])
        self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
        self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value_normalized"])
        self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])


    def test_calculate_with_units(self):
        """
        E073472
        """

        mm = units.Unit.KeywordQuery(symbol="mm")[0]
        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        qmm = units.Unit.KeywordQuery(symbol="mm²")[0]
        qcm = units.Unit.KeywordQuery(symbol="cm ^ 2")[0]

        classes = ["TEST_CLASS_FLOAT_FORMULA"]
        classification_data = api.get_new_classification(classes)
        classification_data["properties"]["TEST_CLASS_FLOAT_FORMULA_BREITE"][0]["value"]["float_value"] = 1.0
        classification_data["properties"]["TEST_CLASS_FLOAT_FORMULA_LAENGE"][0]["value"]["float_value"] = 10.0

        api.update_classification(
           self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=False,
            update_index=False
        )

        persistent_classification_data = api.get_classification(self.document, narrowed=False)
        persistent_value = dict(persistent_classification_data["properties"]["TEST_CLASS_FLOAT_FORMULA_BREITE"][0]["value"])
        self.assertAlmostEqual(persistent_value["float_value"], 1.0)
        self.assertAlmostEqual(persistent_value["float_value_normalized"], 10.0)
        self.assertAlmostEqual(persistent_value["unit_object_id"], cm.cdb_object_id)
        persistent_value = dict(persistent_classification_data["properties"]["TEST_CLASS_FLOAT_FORMULA_LAENGE"][0]["value"])
        self.assertAlmostEqual(persistent_value["float_value"], 10.0)
        self.assertAlmostEqual(persistent_value["float_value_normalized"], 10.0)
        self.assertAlmostEqual(persistent_value["unit_object_id"], mm.cdb_object_id)

        persistent_value = dict(persistent_classification_data["properties"]["TEST_CLASS_FLOAT_FORMULA_TEST_PROP_AREA"][0]["value"])
        self.assertAlmostEqual(persistent_value["float_value"], 100.0)
        self.assertAlmostEqual(persistent_value["float_value_normalized"], 1.0)
        self.assertAlmostEqual(persistent_value["unit_object_id"], qmm.cdb_object_id)
