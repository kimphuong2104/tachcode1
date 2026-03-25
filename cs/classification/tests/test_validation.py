# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import logging
import pytest

from webtest import TestApp as Client

from cdb import testcase
from cs.documents import Document  # @UnresolvedImport
from cs.platform.web.root import Root

from cs.classification import api, tools
from cs.classification.classes import ClassificationClass
from cs.classification.object_classification import ClassificationUpdater
from cs.classification.tests import utils
from cs.classification.validation import ClassificationValidator

LOG = logging.getLogger(__name__)


class TestValidation(utils.ClassificationTestCase):

    def setUp(self):
        super(TestValidation, self).setUp()
        self.client = Client(Root())
        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.empty_classification = {
            "assigned_classes": [],
            "properties": {}
        }
        self.rectangle_or_squre_rule_result = {
            'TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE': {
                'editable': 1,
                'mandatory': 1
            },
            'TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE': {
                'editable': 1,
                'mandatory': 1
            }
        }
        self.circle_rule_result = {
            'TEST_CLASS_CONSTRAINTS_TEST_PROP_RADIUS': {
                'editable': 1,
                'mandatory': 1
            }
        }

    def _check_figure_type_enum_values(
        self,
        values,
        excpected_valid_enum_values,
        expected_invalid_enum_values
    ):
        valid_enum_values, invalid_enum_values = self._get_figure_type_enum_values(values)

        self.assertListEqual(
            excpected_valid_enum_values,
            valid_enum_values
        )
        self.assertListEqual(
            expected_invalid_enum_values,
            invalid_enum_values
        )

    def _get_figure_type_enum_values(self, values):

        def get_raw_values(enum_values):
            raw_values = []
            for enum_value in enum_values:
                raw_values.append(enum_value["value"])
            return raw_values

        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_CONSTRAINTS",
            "classCodes": ["TEST_CLASS_CONSTRAINTS"],
            "propertyCode": "TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE",
            "searchMode": False,
            "values": values
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]

        valid_enum_values = []
        invalid_enum_values = []
        for enum_value in enum_values["TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"]:
            error_message = enum_value.get('error_message', '')
            if error_message:
                invalid_enum_values.append(enum_value)
            else:
                valid_enum_values.append(enum_value)
        return \
            get_raw_values(valid_enum_values), \
            get_raw_values(invalid_enum_values)

    def _get_float_value(self, prop_code, values):
        try:
            return values[prop_code][0]["value"]["float_value"]
        except Exception as e: # pylint: disable=W0703
            LOG.exception(e)
            self.fail("Unable to get value for property " + prop_code)

    def _get_value(self, prop_code, values):
        try:
            return values[prop_code][0]["value"]
        except Exception as e: # pylint: disable=W0703
            LOG.exception(e)
            self.fail("Unable to get value for property " + prop_code)

    def test_assigning_class_with_validation(self):

        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_CONSTRAINTS"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "searchMode": False,
                "withDefaults": True,
                "activePropsOnly": True
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            self.assertEqual(
                None,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA", class_data["values"]),
                "None should be default."
            )
            self.assertEqual(
                None,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE", class_data["values"]),
                "None should be default."
            )
            self.assertEqual(
                None,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_DICKE", class_data["values"]),
                "None should be default."
            )
            self.assertEqual(
                "RECTANGLE",
                self._get_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE", class_data["values"]),
                "Rectangle should be default figure type."
            )
            self.assertEqual(
                None,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE", class_data["values"]),
                "None should be default."
            )
            self.assertEqual(
                None,
                self._get_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_MATERIAL", class_data["values"]),
                "None should be default."
            )
            self.assertEqual(
                None,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_RADIUS", class_data["values"]),
                "None should be default."
            )
            self.assertDictEqual(
                self.rectangle_or_squre_rule_result,
                class_data["rule_results"]
            )
            expected_prop_codes_for_validation = {
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE': {
                    'formula': True,
                    'constraint': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_RADIUS': {
                    'formula': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE': {
                    'formula': True,
                    'constraint': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA': {
                    'formula': True,
                    'constraint': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_MATERIAL': {
                    'formula': True,
                    'constraint': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE': {
                    'formula': True,
                    'rule': True,
                    'constraint': True
                },
                'TEST_CLASS_CONSTRAINTS_TEST_PROP_DICKE': {
                    'formula': True,
                    'constraint': True
                }
            }
            self.assertDictEqual(
                expected_prop_codes_for_validation,
                class_data["prop_codes_for_validation"]
            )

            self._check_figure_type_enum_values(
                class_data["values"],
                ["CIRCLE", "RECTANGLE", "SQUARE"],
                []
            )

    def test_circle(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_CONSTRAINTS"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "searchMode": False,
                "withDefaults": True,
                "activePropsOnly": True
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"
            class_data["values"][changed_property_code][0]["value"] = "CIRCLE"
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_CONSTRAINTS"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            expected_validation_result = {
                "changed_property_code": changed_property_code,
                "error_message": "",  # no constraint violation expected
                "has_errors": False,  # no constraint violation expected
                "properties": result["properties"],  # no property values changed
                "rule_results": self.circle_rule_result
            }
            self.assertDictEqual(
                expected_validation_result,
                result,
                "Validation fails for CIRCLE."
            )

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_RADIUS"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 17.6
            result = self.client.post_json(url, json_data).json
            # check computation results
            self.assertAlmostEqual(
                972.6464,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA", result["properties"]),
                msg="Area should be computed."
            )
            # check constraint results
            self.assertIn("", result["error_message"])

    def test_rectangle_and_square(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_CONSTRAINTS"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 14.5
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_CONSTRAINTS"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            expected_validation_result = {
                "changed_property_code": changed_property_code,
                "error_message": "",  # no constraint violation expected
                "has_errors": False,  # no constraint violation expected
                "properties": result["properties"],  # no property values changed
                "rule_results": result["rule_results"]  # no rules need to be evaluated
            }
            self.assertDictEqual(
                expected_validation_result,
                result,
                "Validation fails for RECTANGLE with only BREITE set."
            )
            self._check_figure_type_enum_values(
                class_data["values"],
                ["CIRCLE", "RECTANGLE", "SQUARE"],
                []
            )

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 4.4
            result = self.client.post_json(url, json_data).json
            # check computation results
            self.assertAlmostEqual(
                14.5 * 4.4,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA", result["properties"]),
                msg="Area should be computed."
            )
            # check constraint results
            self.assertEqual("", result["error_message"])
            self._check_figure_type_enum_values(
                class_data["values"],
                ["CIRCLE", "RECTANGLE"],
                ["SQUARE"]
            )

            class_data["values"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"] = \
                result["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"]

            ClassificationUpdater(self.document, None).update({
                "assigned_classes": ["TEST_CLASS_CONSTRAINTS"],
                "properties": class_data["values"]
            })

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_DICKE"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 0.55
            result = self.client.post_json(url, json_data).json
            # check constraint results
            self.assertEqual(
                "Die Dicke muss mindestens 1% der Fläche betragen.",
                result["error_message"]
            )

            class_data["values"][changed_property_code][0]["value"]["float_value"] = 0.95
            result = self.client.post_json(url, json_data).json
            # check constraint results
            self.assertEqual(
                "",
                result["error_message"],
                "no constraint violation expected"
            )

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_MATERIAL"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"] = "Holz"
            result = self.client.post_json(url, json_data).json
            # check constraint results
            self.assertEqual(
                "Die Fläche ist zu gross für Kunststoff und Holz.",
                result["error_message"]
            )

            class_data["values"][changed_property_code][0]["value"] = "Stahl"
            result = self.client.post_json(url, json_data).json
            # check constraint results
            self.assertEqual(
                "",
                result["error_message"],
                "no constraint violation expected"
            )

            ClassificationUpdater(self.document, None).update({
                "assigned_classes": ["TEST_CLASS_CONSTRAINTS"],
                "properties": class_data["values"]
            })

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"] = "SQUARE"
            result = self.client.post_json(url, json_data).json
            # check constraint results
            self.assertAlmostEqual(
                210.25,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA", result["properties"]),
                msg="Area should be computed."
            )
            self.assertIn("Bei einem Quadrat müssen Höhe und Breite übereinstimmen!", result["error_message"])
            self.assertIn("Die Dicke muss mindestens 1% der Fläche betragen.", result["error_message"])
            self.assertIn("Die Flächengröße erfordert Beton als Material.", result["error_message"])

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_HOEHE"
            json_data["changed_property_code"] = changed_property_code
            json_data["validation_mode"] = class_data["prop_codes_for_validation"][changed_property_code]
            class_data["values"][changed_property_code][0]["value"]["float_value"] = \
                class_data["values"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"][0]["value"]["float_value"]
            result = self.client.post_json(url, json_data).json
            # check computation results
            self.assertAlmostEqual(
                14.5 * 14.5,
                self._get_float_value("TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA", result["properties"]),
                msg="Area should be computed."
            )
            self._check_figure_type_enum_values(
                class_data["values"],
                ["CIRCLE", "SQUARE"],
                ["RECTANGLE"]
            )

    def test_equivalent_constraint(self):
        with testcase.error_logging_disabled():
            test_class_code = "TEST_CLASS_EQUIVALENT_CONSTRAINT"
            classification_data = api.get_new_classification([test_class_code])

            classification_data["properties"]["TEST_CLASS_EQUIVALENT_CONSTRAINT_TEST_PROP_VERSTELLUNG"][0]["value"] = "Elektrisch"
            classification_data["properties"]["TEST_CLASS_EQUIVALENT_CONSTRAINT_TEST_PROP_VERSION"][0]["value"] = "Einfach"

            with self.assertRaises(api.ConstaintsViolationException):
                ClassificationUpdater(self.document, None).update(classification_data)

            classification_data["properties"]["TEST_CLASS_EQUIVALENT_CONSTRAINT_TEST_PROP_VERSION"][0]["value"] = "Komfort"

    def test_creating_missing_values_with_formula(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_CONSTRAINTS"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_FIGURE_TYPE"
            class_data["values"][changed_property_code][0]["value"] = "CIRCLE"
            class_data["values"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"] = None

            changed_property_code = "TEST_CLASS_CONSTRAINTS_TEST_PROP_RADIUS"
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 4.7
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_CONSTRAINTS"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            with self.assertRaises(KeyError):
                result["properties"]["TEST_CLASS_CONSTRAINTS_TEST_PROP_AREA"]["value"]

    def test_multiple_formulas(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES_TEST_PROP_FIGURE_TYPE"
            class_data["values"][changed_property_code][0]["value"] = "SQUARE"
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            try:
                result = self.client.post_json(url, json_data).json
            except Exception as e: # pylint: disable=W0703
                if "Mehrere Formeln zur Vorbelegung des Merkmals" in str(e):
                    # expected error
                    pass
                else:
                    self.fail("Too many formulars error expected.")

    def test_multiple_inconsistent_rules(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES_TEST_PROP_FIGURE_TYPE"
            class_data["values"][changed_property_code][0]["value"] = ""
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_TOO_MANY_FORMUARS_AND_RULES"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            try:
                result = self.client.post_json(url, json_data).json
            except Exception as e:
                if "Inkonsistente Regeln" in str(e):
                    # expected error
                    pass
                else:
                    self.fail("Too many rules error expected.")

    def test_multiple_consistent_rules(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_MULTIPLE_CONSISTENT_RULES"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_MULTIPLE_CONSISTENT_RULES_TYPE_FOR_RULES"
            class_data["values"][changed_property_code][0]["value"] = "Typ 1"
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_MULTIPLE_CONSISTENT_RULES"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertDictEqual({
                    'editable': 2,
                    'mandatory': 0
                }, result['rule_results']['TEST_CLASS_MULTIPLE_CONSISTENT_RULES_TEST_PROP_DESCRIPTION']
            )

    def test_boolean_values(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_CONSTRAINTS_EMPTY_VALUES"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_CONSTRAINTS_EMPTY_VALUES_TEST_PROP_INT"
            class_data["values"][changed_property_code][0]["value"] = 10
            class_data["values"]["TEST_CLASS_CONSTRAINTS_EMPTY_VALUES_TEST_PROP_BOOL"][0]["value"] = True
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_CONSTRAINTS_EMPTY_VALUES"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            expected_validation_result = {
                "changed_property_code": changed_property_code,
                "error_message": "",  # no constraint violation expected
                "has_errors": False,  # no constraint violation expected
                "properties": result["properties"],  # no property values changed
                "rule_results": result["rule_results"]  # no rules need to be evaluated
            }
            self.assertDictEqual(
                expected_validation_result,
                result,
                "Validation fails for int = 10 and bool = False."
            )

            changed_property_code = "TEST_CLASS_CONSTRAINTS_EMPTY_VALUES_TEST_PROP_BOOL"
            class_data["values"][changed_property_code][0]["value"] = False
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            expected_validation_result = {
                "changed_property_code": changed_property_code,
                "error_message": "Bool not True",
                "has_errors": True,
                "properties": result["properties"],  # no property values changed
                "rule_results": result["rule_results"]  # no rules need to be evaluated
            }
            self.assertDictEqual(
                expected_validation_result,
                result,
                "Validation fails for int = 10 and bool = False."
            )

    def test_for_variants(self):
        with testcase.error_logging_disabled():
            test_class_code = "TEST_CLASS_VARIANTS"
            classification_data = api.get_new_classification([test_class_code])

            classification_data["properties"]["TEST_CLASS_VARIANTS_COMPUTER_TYPE"][0]["value"] = "Desktop"
            classification_data["properties"]["TEST_CLASS_VARIANTS_COMPUTER_TYPE_1"][0]["value"] = "Desktop"

            api.update_classification(self.document, classification_data)

            classification_data = api.get_classification(self.document)

            self.assertEqual(
                "Desktop",
                classification_data["properties"]["TEST_CLASS_VARIANTS_COMPUTER_TYPE"][0]["value"]
            )
            self.assertEqual(
                "Formula Value",
                classification_data["properties"]["TEST_CLASS_VARIANTS_COMPUTER_TYPE_1"][0]["value"]
            )

    def test_float_with_enum_values_validation(self):
        """
        E055753
        Float characteristics with enum values and a constraint are not validated
        """
        values = {
            "TEST_CLASS_FLOAT_ENUMS_VOLUMEN": [
                {
                    "value_path": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
                    "property_type": "float",
                    "id": None,
                    "value": {
                        "float_value_normalized": None,
                        "float_value": 2
                    }
                }
            ]
        }
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_FLOAT_ENUMS",
            "classCodes": ["TEST_CLASS_FLOAT_ENUMS"],
            "propertyCode": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
            "searchMode": False,
            "values": values
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        errors = [x["error_message"] for x in enum_values["TEST_CLASS_FLOAT_ENUMS_VOLUMEN"]]
        self.assertNotEqual("", errors[0], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")
        self.assertEqual("", errors[1], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")

    def test_float_with_enum_values_validation_with_units(self):
        """
        E055753
        Float characteristics with enum values and a constraint are not validated
        """
        values = {
            "TEST_CLASS_FLOAT_ENUMS_DURCHMESSER": [
                {
                    "value_path": "TEST_CLASS_FLOAT_ENUMS_DURCHMESSER",
                    "property_type": "float",
                    "id": None,
                    "value": {
                        "float_value_normalized": None,
                        "float_value": 1000
                    }
                }
            ]
        }
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_FLOAT_ENUMS",
            "classCodes": ["TEST_CLASS_FLOAT_ENUMS"],
            "propertyCode": "TEST_CLASS_FLOAT_ENUMS_DURCHMESSER",
            "searchMode": False,
            "values": values
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        errors = [x["error_message"] for x in enum_values["TEST_CLASS_FLOAT_ENUMS_DURCHMESSER"]]
        self.assertNotEqual("", errors[0])
        self.assertNotEqual("", errors[1])
        self.assertEqual("", errors[2])

    def test_float_with_catalog_enum_values_with_units(self):
        """
        E055753
        Float characteristics with enum values and a constraint are not validated
        """
        url = "/internal/classification/enum_values"
        json_data = {
            "propertyCode": "TEST_PROP_FLOAT_ENUM_2",
            "searchMode": False,
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        for each in enum_values["TEST_PROP_FLOAT_ENUM_2"]:
            self.assertTrue("float_value_normalized" in each["value"])

    def test_enum_values_validate_additional_object_values(self):
        with testcase.error_logging_disabled():
            doc = Document.ByKeys(z_nummer="CLASS000005", z_index="")
            classification_data = api.get_classification(doc)

        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_CONSTRAINTS",
            "classCodes": ["TEST_CLASS_CONSTRAINTS"],
            "propertyCode": "TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE",
            "searchMode": False,
            "values": classification_data["properties"],
            "additionalEnumValueObjectIds": [doc.cdb_object_id]
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        errors = [x["error_message"] for x in enum_values["TEST_CLASS_CONSTRAINTS_TEST_PROP_BREITE"]]
        self.assertNotEqual("", errors[0])

    def test_enum_values_additional_object_values_none_has_no_effect(self):
        values = {
            "TEST_CLASS_FLOAT_ENUMS_VOLUMEN": [
                {
                    "value_path": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
                    "property_type": "float",
                    "id": None,
                    "value": {
                        "float_value_normalized": None,
                        "float_value": 2
                    }
                }
            ]
        }
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_FLOAT_ENUMS",
            "classCodes": ["TEST_CLASS_FLOAT_ENUMS"],
            "propertyCode": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
            "searchMode": False,
            "values": values,
            "additionalEnumValueObjectIds": None
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        errors = [x["error_message"] for x in enum_values["TEST_CLASS_FLOAT_ENUMS_VOLUMEN"]]
        self.assertNotEqual("", errors[0], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")
        self.assertEqual("", errors[1], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")

    def test_enum_values_additional_object_values_empty_list_has_no_effect(self):
        values = {
            "TEST_CLASS_FLOAT_ENUMS_VOLUMEN": [
                {
                    "value_path": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
                    "property_type": "float",
                    "id": None,
                    "value": {
                        "float_value_normalized": None,
                        "float_value": 2
                    }
                }
            ]
        }
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": "TEST_CLASS_FLOAT_ENUMS",
            "classCodes": ["TEST_CLASS_FLOAT_ENUMS"],
            "propertyCode": "TEST_CLASS_FLOAT_ENUMS_VOLUMEN",
            "searchMode": False,
            "values": values,
            "additionalEnumValueObjectIds": []
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        errors = [x["error_message"] for x in enum_values["TEST_CLASS_FLOAT_ENUMS_VOLUMEN"]]
        self.assertNotEqual("", errors[0], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")
        self.assertEqual("", errors[1], "Validation fails for TEST_CLASS_FLOAT_ENUMS_VOLUMEN > 2")

    def test_formula_with_empty_strings(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_TYRE"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_TYRE_BREITE"
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 225.0
            class_data["values"]["TEST_CLASS_TYRE_TEST_PROP_ASPECT_RATIO"][0]["value"] = 55
            class_data["values"]["TEST_CLASS_TYRE_TEST_PROP_RIM_DIAMETER"][0]["value"]["float_value"] = 16.0
            class_data["values"]["TEST_CLASS_TYRE_TEST_PROP_LOAD_CAPACITY_INDEX"][0]["value"] = 95

            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_TYRE"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(False, result["has_errors"])
            tyre_code = "225.0 / 55  16.0 "
            self.assertEqual(tyre_code, result["properties"]["TEST_CLASS_TYRE_TEST_PROP_TEXT"][0]["value"])

            class_data["values"]["TEST_CLASS_TYRE_TEST_PROP_TYRE_TYPE"][0]["value"] = "R"
            class_data["values"]["TEST_CLASS_TYRE_TEST_TYRE_SPEED_CLASS"][0]["value"] = "W"
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": "TEST_CLASS_TYRE_TEST_PROP_RIM_DIAMETER",
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(False, result["has_errors"])
            tyre_code = "225.0 / 55 R 16.0 W"
            self.assertEqual(tyre_code, result["properties"]["TEST_CLASS_TYRE_TEST_PROP_TEXT"][0]["value"])

    def test_validated_catalog_values_for_empty_strings(self):
        class_code = "SEAT"
        class_codes = [class_code]
        classification_data = api.get_new_classification(class_codes)

        property_code = "SEAT_TEST_PROP_ADJUSTMENT"
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": class_code,
            "classCodes": class_codes,
            "propertyCode": property_code,
            "searchMode": False,
            "values": classification_data["properties"]
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        for enum_value in enum_values[property_code]:
            self.assertEqual(enum_value.get("error_message", ""), "", "No error message expected.")

        classification_data["properties"]["SEAT_TEST_PROP_TYPE"][0]["value"] = "COMFORT"
        url = "/internal/classification/enum_values"
        json_data = {
            "clazzCode": class_code,
            "classCodes": class_codes,
            "propertyCode": property_code,
            "searchMode": False,
            "values": classification_data["properties"]
        }
        result = self.client.post_json(url, json_data)
        enum_values = result.json["enums"]
        for enum_value in enum_values[property_code]:
            if "MANUAL" == enum_value["value"]:
                self.assertNotEqual(enum_value.get("error_message", ""), "", "Error message expected.")
            else:
                self.assertEqual(enum_value.get("error_message", ""), "", "No error message expected.")


    def test_labels(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_ENUM_LABELS_WITH_VALIDATION"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_INT"
            class_data["values"][changed_property_code][0]["value"] = 0
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(
                "",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_ENUM_LABELS"][0]["addtl_value"]["description"]
            )
            self.assertEqual(
                "Umgebungstemperatur",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_ENUM_LABELS"][0]["addtl_value"]["label"]
            )
            class_data["values"].update(result["properties"])

            class_data["values"][changed_property_code][0]["value"] = 1
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(
                "",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_ENUM_LABELS"][0]["addtl_value"]["description"]
            )
            self.assertEqual(
                "Lagertemperatur",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_ENUM_LABELS"][0]["addtl_value"]["label"]
            )

            addtl_value_obj_ref = tools.get_addtl_objref_value(
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_OBJREF"][0]["value"],
                None
            )
            self.assertEqual(
                addtl_value_obj_ref["ui_link"],
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_OBJREF"][0]["addtl_value"]["ui_link"]
            )
            self.assertEqual(
                addtl_value_obj_ref["ui_text"],
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_OBJREF"][0]["addtl_value"]["ui_text"]
            )
            class_data["values"].update(result["properties"])

            class_data["values"][changed_property_code][0]["value"] = 99
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertNotIn(
                "addtl_value",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_ENUM_LABELS"][0]
            )
            self.assertNotIn(
                "addtl_value",
                result["properties"]["TEST_CLASS_ENUM_LABELS_WITH_VALIDATION_TEST_PROP_OBJREF"][0]
            )
            class_data["values"].update(result["properties"])

    def test_do_constraints_exist_with_constraints(self):
        self.assertTrue(
            ClassificationValidator.has_constraints(["TEST_CLASS_CONSTRAINTS"])
        )
        self.assertTrue(
            ClassificationValidator.has_constraints(
                ["TEST_CLASS_CONSTRAINTS_EMPTY_VALUES"]
            )
        )
        self.assertTrue(
            ClassificationValidator.has_constraints(
                ["TEST_CLASS_CONSTRAINTS_NO_ERROR_MESSAGE"]
            )
        )
        self.assertTrue(
            ClassificationValidator.has_constraints(
                ["TEST_CLASS_EQUIVALENT_CONSTRAINT"]
            )
        )

    def test_do_constraints_exist_without_constraints(self):
        self.assertFalse(
            ClassificationValidator.has_constraints(["TEST_CLASS_AUTOMOTIVE"])
        )
        self.assertFalse(
            ClassificationValidator.has_constraints(["TEST_CLASS_COMPUTATION"])
        )
        self.assertFalse(
            ClassificationValidator.has_constraints(["TEST_CLASS_DATE_FORMULA"])
        )
        self.assertFalse(
            ClassificationValidator.has_constraints(["TEST_CLASS_RULES_MANDATORY"])
        )

    def test_do_constraints_exist_multiple_classes_mixed(self):
        self.assertTrue(
            ClassificationValidator.has_constraints(
                ["TEST_CLASS_AUTOMOTIVE", "TEST_CLASS_CONSTRAINTS"]
            )
        )

    def test_do_constraints_exist_multiple_classes_with_constraints(self):
        self.assertTrue(
            ClassificationValidator.has_constraints(
                [
                    "TEST_CLASS_CONSTRAINTS",
                    "TEST_CLASS_CONSTRAINTS_EMPTY_VALUES",
                    "TEST_CLASS_CONSTRAINTS_NO_ERROR_MESSAGE",
                    "TEST_CLASS_EQUIVALENT_CONSTRAINT",
                ]
            )
        )

    def test_do_constraints_exist_multiple_classes_without_constraints(self):
        self.assertFalse(
            ClassificationValidator.has_constraints(
                [
                    "TEST_CLASS_AUTOMOTIVE",
                    "TEST_CLASS_COMPUTATION",
                    "TEST_CLASS_DATE_FORMULA",
                    "TEST_CLASS_RULES_MANDATORY",
                ]
            )
        )

    def test_int_conversion(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_INT_FORMULA"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_INT_FORMULA_TEST_PROP_FLOAT"
            class_data["values"][changed_property_code][0]["value"]["float_value"] = 88.0
            url = "/internal/classification/validate/"
            assigned_classes = ["TEST_CLASS_INT_FORMULA"]
            classes_for_validation = ClassificationClass.get_base_class_codes(
                class_codes=assigned_classes, include_given=True
            )
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(
                617,
                result["properties"]["TEST_CLASS_INT_FORMULA_TEST_PROP_INT"][0]["value"]
            )

            changed_property_code = "TEST_CLASS_INT_FORMULA_TEST_PROP_FLOAT"
            class_data["values"][changed_property_code][0]["value"]["float_value"] = None
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": assigned_classes,
                "classCodesForValidation": classes_for_validation,
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEqual(
                None,
                result["properties"]["TEST_CLASS_INT_FORMULA_TEST_PROP_INT"][0]["value"]
            )

    def test_zero_values(self):
        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_COMPUTATION_ZERO_VALUES"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "withDefaults": True,
                "activePropsOnly": True,
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            class_data = result.json

            changed_property_code = "TEST_CLASS_COMPUTATION_ZERO_VALUES_COMPUTER_TYPE"
            class_data["values"][changed_property_code][0]["value"] = "Tablet"
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": ["TEST_CLASS_COMPUTATION_ZERO_VALUES"],
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEquals(
                0,
                result["properties"]["TEST_CLASS_COMPUTATION_ZERO_VALUES_TEST_PROP_INT"][0]["value"]
            )
            self.assertEquals(
                0.0,
                result["properties"]["TEST_CLASS_COMPUTATION_ZERO_VALUES_TEST_PROP_FLOAT"][0]["value"]["float_value"]
            )

            class_data["values"][changed_property_code][0]["value"] = "Desktop"
            url = "/internal/classification/validate/"
            json_data = {
                "assigned_classes": ["TEST_CLASS_COMPUTATION_ZERO_VALUES"],
                "properties": class_data["values"],
                "changed_property_code": changed_property_code,
                "validation_mode": class_data["prop_codes_for_validation"][changed_property_code]
            }
            result = self.client.post_json(url, json_data).json
            self.assertEquals(
                None,
                result["properties"]["TEST_CLASS_COMPUTATION_ZERO_VALUES_TEST_PROP_INT"][0]["value"]
            )
            self.assertEquals(
                None,
                result["properties"]["TEST_CLASS_COMPUTATION_ZERO_VALUES_TEST_PROP_FLOAT"][0]["value"]["float_value"]
            )
