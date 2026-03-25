# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from cs.documents import Document  # @UnresolvedImport

from cs.classification import api, ClassificationConstants, tools
from cs.classification.util import create_block_descriptions, create_class_description, replace_pattern

from cs.classification.tests import utils


class TestDescriptionTags(utils.ClassificationTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDescriptionTags, cls).setUpClass()

    def setUp(self):
        super(TestDescriptionTags, self).setUp()
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

    def test_descriptions(self):
        prop_data = {
            "TEST_PROP_A": "a",
            "TEST_PROP_B": "b",
        }
        description = tools.parse_raw('TEST_PROP_A + "..." + TEST_PROP_B') % prop_data
        self.assertEqual("a...b", description)

        prop_data = {
            "TEST_PROP_A": "5"
        }
        description = tools.parse_raw('"> " + TEST_PROP_A') % prop_data
        self.assertEqual("> 5", description)

        description = tools.parse_raw('"> " + TEST_PROP_A($unit)') % prop_data
        self.assertEqual("> 5", description)

    def test_formats(self):
        expected_formats = {}
        formats = tools.parse_formats('TEST_PROP_A + "..." + TEST_PROP_B')
        self.assertDictEqual(expected_formats, formats)

        formats = tools.parse_formats('TEST_PROP_A(%6.2f; $(unit)) + "..." + TEST_PROP_B(%2f)')
        expected_formats = {
            "TEST_PROP_A": {"format_string": "%6.2f", "with_unit": True},
            "TEST_PROP_B": {"format_string": "%2f", "with_unit": False},
        }
        self.assertDictEqual(expected_formats, formats)

    def test_float_block_prop_description(self):
        block_prop_code = "TEST_PROP_BLOCK_STORAGE_CONDITIONS"
        data = api.create_additional_props([block_prop_code])
        data["properties"][block_prop_code][0]["value"]["child_props"]["TEST_PROP_STORAGE_TYPE"][0]["value"] = "Indoor"
        block_temperature = data["properties"][block_prop_code][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Lagertemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Storage Temperature"
        block_temperature["TEST_PROP_TEMPERATURE_MIN"][0]["value"]["float_value"] = 0.0
        block_temperature["TEST_PROP_TEMPERATURE_MAX"][0]["value"]["float_value"] = 90.0

        create_block_descriptions(
            block_prop_code, data["properties"][block_prop_code][0],
            decimal_seperator='.', group_seperator=None, dateformat=None
        )
        self.assertEqual(
            "Indoor - Lagertemperatur (0.0°C, 90.0°C)",
            data["properties"][block_prop_code][0]["value"]["description"]
        )

        block_temperature["TEST_PROP_TEMPERATURE_MIN"][0]["value"]["float_value"] = None
        create_block_descriptions(
            block_prop_code, data["properties"][block_prop_code][0],
            decimal_seperator='.', group_seperator=None, dateformat=None
        )
        self.assertEqual(
            "Indoor - Lagertemperatur (, 90.0°C)",
            data["properties"][block_prop_code][0]["value"]["description"]
        )

    def test_nested_block_prop_description(self):
        block_prop_code = "TEST_PROP_BLOCK_STORAGE_CONDITIONS"
        data = api.create_additional_props([block_prop_code])
        data["properties"][block_prop_code][0]["value"]["child_props"]["TEST_PROP_STORAGE_TYPE"][0]["value"] = "Indoor"
        block_temperature = data["properties"][block_prop_code][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Lagertemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Storage Temperature"
        block_temperature["TEST_PROP_TEMPERATURE_MIN"][0]["value"]["float_value"] = 10.0
        block_temperature["TEST_PROP_TEMPERATURE_MAX"][0]["value"]["float_value"] = 90.0

        create_block_descriptions(
            block_prop_code, data["properties"][block_prop_code][0],
            decimal_seperator='.', group_seperator=None, dateformat=None
        )
        self.assertEqual(
            "Indoor - Lagertemperatur (10.0°C, 90.0°C)",
            data["properties"][block_prop_code][0]["value"]["description"]
        )

    def test_class_description(self):
        class_code = "SCHRAUBE"
        data = api.get_new_classification([class_code])
        data["properties"]["SCHRAUBE_DURCHMESSER"][0]["value"]["float_value"] = 5.0
        data["properties"]["SCHRAUBE_LAENGE"][0]["value"]["float_value"] = 12.0
        data["properties"]["SCHRAUBE_FESTIGKEITSKLASSE"][0]["value"]["float_value"] = 8.8
        data["properties"]["SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["min"]["float_value"] = 1.1
        data["properties"]["SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = 2.2

        description_tag = api.get_class_description_tags([class_code], languages=["de", "en"])[class_code]["de"]
        description = create_class_description(
            description_tag,
            data["properties"],
            decimal_seperator='.'
        )
        self.assertEqual(
            "M5x12 8.8, 1.10cm .. 2.20cm",
            description
        )

        data["properties"]["SCHRAUBE_FESTIGKEITSKLASSE"][0]["value"]["float_value"] = 0.0
        data["properties"]["SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = None
        description = create_class_description(
            description_tag,
            data["properties"],
            decimal_seperator='.'
        )
        self.assertEqual(
            "M5x12 0.0, 1.10cm",
            description
        )


    def test_aggregated_class_description(self):
        class_code = "HSK_AUTOMATISCH"
        data = api.get_new_classification([class_code])
        data["properties"]["MOTOR_SPINDELN_LEISTUNGSAUFNAHME"][0]["value"]["float_value"] = 5.0
        data["properties"]["MOTOR_SPINDELN_LAENGE"][0]["value"]["float_value"] = 500.0
        data["properties"]["HSK_AUTOMATISCH_NORM"][0]["value"] = "DIN XYZ"

        description_tag = api.get_class_description_tags([class_code], languages=["de", "en"], aggregate_parent_class_tags=True)[class_code]["de"]
        description = create_class_description(
            description_tag,
            data["properties"],
            decimal_seperator='.'
        )
        self.assertEqual(
            "5kW-HSK Länge 500mm DIN XYZ",
            description
        )

    def test_class_descriptions(self):
        class_codes = ["SCHRAUBE", "HSK_AUTOMATISCH"]
        data = api.get_new_classification(class_codes)
        data["properties"]["SCHRAUBE_DURCHMESSER"][0]["value"]["float_value"] = 5.0
        data["properties"]["SCHRAUBE_LAENGE"][0]["value"]["float_value"] = 12.0
        data["properties"]["SCHRAUBE_FESTIGKEITSKLASSE"][0]["value"]["float_value"] = 8.8
        data["properties"]["MOTOR_SPINDELN_LEISTUNGSAUFNAHME"][0]["value"]["float_value"] = 5.0
        data["properties"]["MOTOR_SPINDELN_LAENGE"][0]["value"]["float_value"] = 500.0
        data["properties"]["HSK_AUTOMATISCH_NORM"][0]["value"] = "DIN XYZ"

        class_descriptions = api.create_class_descriptions(
            data, languages=["de", "en"], aggregate_parent_class_tags=True, decimal_seperator='.'
        )
        self.assertEqual(
            "5kW-HSK Länge 500mm DIN XYZ",
            class_descriptions["HSK_AUTOMATISCH"]["de"]
        )
        self.assertEqual(
            "5kW-HSK Length 500mm DIN XYZ",
            class_descriptions["HSK_AUTOMATISCH"]["en"]
        )
        self.assertEqual(
            "M5x12 8.8, ",
            class_descriptions["SCHRAUBE"]["de"]
        )
        self.assertEqual(
            "M5x12 8.8",
            class_descriptions["SCHRAUBE"]["en"]
        )

        class_descriptions = api.get_descriptions(
            data, "HSK_AUTOMATISCH", languages=["de", "en"], aggregate_parent_class_tags=True
        )
        self.assertEqual(
            "5kW-HSK Länge 500mm DIN XYZ",
            class_descriptions["de"]
        )
        self.assertEqual(
            "5kW-HSK Length 500mm DIN XYZ",
            class_descriptions["en"]
        )

        class_descriptions = api.get_descriptions(
            data, "SCHRAUBE", languages=["de", "en"], aggregate_parent_class_tags=True
        )
        self.assertEqual(
            "M5x12 8,8, ",
            class_descriptions["de"]
        )
        self.assertEqual(
            "M5x12 8.8",
            class_descriptions["en"]
        )

        api.update_classification(self.document, data)
        class_descriptions = api.get_descriptions_for_object(
            self.document, "HSK_AUTOMATISCH", languages=["de", "en"], aggregate_parent_class_tags=True
        )
        self.assertEqual(
            "5kW-HSK Länge 500mm DIN XYZ",
            class_descriptions["de"]
        )
        self.assertEqual(
            "5kW-HSK Length 500mm DIN XYZ",
            class_descriptions["en"]
        )

        class_descriptions = api.get_descriptions_for_object(
            self.document, "SCHRAUBE", languages=["de", "en"], aggregate_parent_class_tags=True
        )
        self.assertEqual(
            "M5x12 8,8, ",
            class_descriptions["de"]
        )
        self.assertEqual(
            "M5x12 8.8",
            class_descriptions["en"]
        )


    def test_float_pattern(self):

        class_code = "SCHRAUBE"
        data = api.get_new_classification([class_code])
        data["properties"]["SCHRAUBE_DURCHMESSER"][0]["value"]["float_value"] = 5.0
        data["properties"]["SCHRAUBE_LAENGE"][0]["value"]["float_value"] = 12.0
        data["properties"]["SCHRAUBE_FESTIGKEITSKLASSE"][0]["value"]["float_value"] = 0.0
        data["properties"]["SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["min"]["float_value"] = 0.0
        data["properties"]["SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]["max"]["float_value"] = 2.2
        data["properties"]["SCHRAUBE_TEST_PROP_INT"][0]["value"] = 0

        pattern = '"M"+SCHRAUBE_DURCHMESSER(%.0f)+"x"+SCHRAUBE_LAENGE(%.0f)+" "+SCHRAUBE_FESTIGKEITSKLASSE(%.1f)+ ", "+SCHRAUBE_TEST_PROP_FLOAT_RANGE_UNIT(%.2f; $(unit))+", "+SCHRAUBE_TEST_PROP_INT(%d)'
        description = replace_pattern(pattern, data["properties"], decimal_seperator='.')

        self.assertEqual(
            "M5x12 0.0, 0.00cm .. 2.20cm, 0",
            description
        )

        data["properties"]["SCHRAUBE_TEST_PROP_INT"][0]["value"] = 1234
        description = replace_pattern(pattern, data["properties"], decimal_seperator='.', group_seperator=',')

        self.assertEqual(
            "M5x12 0.0, 0.00cm .. 2.20cm, 1,234",
            description
        )

        data["properties"]["SCHRAUBE_TEST_PROP_INT"][0]["value"] = None
        description = replace_pattern(pattern, data["properties"], decimal_seperator='.', group_seperator=',')

        self.assertEqual(
            "M5x12 0.0, 0.00cm .. 2.20cm, ",
            description
        )

