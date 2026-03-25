# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections
import time

from cdb import constants, testcase
from cdb.objects import operations
from cs.classification.classes import (
    ClassProperty,
    ClassPropertyGroup,
    PropertyGroupAssignment,
)
from cs.variants import VariabilityModel
from cs.variants.api.variants_classification import VariantsClassification
from cs.variants.tests import common


class TestVariantsClassification(common.VariantsTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVariantsClassification, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    def _check_property_order(self, properties, expected_property_codes):
        property_codes = []
        for prop in properties:
            property_codes.append(prop["code"])
        self.assertListEqual(property_codes, expected_property_codes)

    def _create_class(self, class_code, parent_class=None):
        timestamp = ("%s" % time.time()).replace(".", "")
        prop_codes = [
            "PROP_1_{}".format(timestamp),
            "PROP_2_{}".format(timestamp),
            "PROP_3_{}".format(timestamp),
        ]
        props = collections.OrderedDict(
            [
                (prop_codes[0], ["VALUE"]),
                (prop_codes[1], ["VALUE"]),
                (prop_codes[2], ["VALUE"]),
            ]
        )
        clazz_code = "{}_{}".format(class_code, timestamp)
        clazz_property_codes = [
            "{}_{}".format(clazz_code, prop_code) for prop_code in prop_codes
        ]
        parent_class_id = parent_class.cdb_object_id if parent_class else None
        clazz = common.generate_class_with_props(
            props, code=clazz_code, parent_class_id=parent_class_id
        )
        return clazz, clazz_property_codes

    def _create_group_assignment(self, group, property_code, position):
        class_prop = ClassProperty.KeywordQuery(code=property_code)[0]
        args = {
            "display_option": "New Line",
            "group_object_id": group.cdb_object_id,
            "property_object_id": class_prop.cdb_object_id,
            "position": position,
        }
        PropertyGroupAssignment.Create(**args)

    def test_all_class_codes(self):
        clazz, _ = self._create_class("CS_VARIANTS_TEST_CLASS")
        subclazz, _ = self._create_class("CS_VARIANTS_TEST_SUB_CLASS", clazz)

        variantsClassification = VariantsClassification([subclazz.code])
        class_codes = variantsClassification.get_all_class_codes()

        self.assertSetEqual(set(class_codes), set([subclazz.code, clazz.code]))

    def test_catalog_values(self):
        timestamp = ("%s" % time.time()).replace(".", "")
        prop1 = "PROP_TEXT_{}".format(timestamp)
        prop2 = "PROP_FLOAT_{}".format(timestamp)
        prop3 = "PROP_INT_{}".format(timestamp)
        props = collections.OrderedDict(
            [
                (prop1, ["VALUE 2", "VALUE 1", "VALUE 1"]),
                (prop2, [(100, "cm"), (1, "m"), (200, "mm")]),
                (prop3, [7, 4, 2, 7]),
            ]
        )
        clazz_code = "CS_VARIANTS_TEST_CLASS_%s" % timestamp
        common.generate_class_with_props(props, code=clazz_code)
        variants_classification = VariantsClassification([clazz_code])
        catalog_values = variants_classification.get_catalog_values()

        values = collections.defaultdict(list)
        for prop_code, property_values in catalog_values.items():
            for property_value in property_values:
                if property_value["type"] == "float":
                    values[prop_code].append(
                        property_value["value"]["float_value_normalized"]
                    )
                else:
                    values[prop_code].append(property_value["value"])

        self.assertListEqual(
            ["VALUE 1", "VALUE 2"], values["{}_{}".format(clazz_code, prop1)]
        )

        self.assertListEqual([0.2, 1.0], values["{}_{}".format(clazz_code, prop2)])
        self.assertListEqual([2, 4, 7], values["{}_{}".format(clazz_code, prop3)])

    def test_classification_data(self):
        clazz, clazz_prop_codes = self._create_class("CS_VARIANTS_TEST_CLASS")
        subclazz, sub_clazz_prop_codes = self._create_class(
            "CS_VARIANTS_TEST_SUB_CLASS", clazz
        )

        variantsClassification = VariantsClassification([subclazz.code])
        classification_data = variantsClassification.get_classification_data()

        self.assertSetEqual(
            set([subclazz.code]), classification_data["assigned_classes"]
        )
        self.assertSetEqual(
            set([clazz.code, subclazz.code]),
            set(classification_data["metadata"]["classes"].keys()),
        )
        self.assertSetEqual(
            set(clazz_prop_codes + sub_clazz_prop_codes),
            set(classification_data["properties"].keys()),
        )

    def test_property_values(self):
        clazz, clazz_prop_codes = self._create_class("CS_VARIANTS_TEST_CLASS")
        subclazz, sub_clazz_prop_codes = self._create_class(
            "CS_VARIANTS_TEST_SUB_CLASS", clazz
        )

        variantsClassification = VariantsClassification([subclazz.code])

        self.assertSetEqual(
            set(clazz_prop_codes + sub_clazz_prop_codes),
            set(variantsClassification.get_property_values().keys()),
        )

    def test_variant_driving_properties(self):
        clazz, clazz_prop_codes = self._create_class("CS_VARIANTS_TEST_CLASS")
        subclazz, sub_clazz_prop_codes = self._create_class(
            "CS_VARIANTS_TEST_SUB_CLASS", clazz
        )

        variantsClassification = VariantsClassification([subclazz.code, clazz.code])
        properties = variantsClassification.get_variant_driving_properties_by_class()

        self._check_property_order(properties[clazz.code], clazz_prop_codes)
        self._check_property_order(
            properties[subclazz.code], sub_clazz_prop_codes + clazz_prop_codes
        )
        self.assertSetEqual(
            set(sub_clazz_prop_codes + clazz_prop_codes),
            set(variantsClassification.get_variant_driving_properties().keys()),
        )
        args = {
            "classification_class_id": subclazz.cdb_object_id,
            "name_de": "Test Gruppe",
            "position": 10,
            "initial_expand": 1,
        }
        group = ClassPropertyGroup.Create(**args)
        self._create_group_assignment(group, clazz_prop_codes[1], 10)
        self._create_group_assignment(group, sub_clazz_prop_codes[2], 20)

        variantsClassification = VariantsClassification([subclazz.code])
        properties = variantsClassification.get_variant_driving_properties_by_class()
        self._check_property_order(
            properties[subclazz.code],
            [
                sub_clazz_prop_codes[0],
                sub_clazz_prop_codes[1],
                clazz_prop_codes[1],
                sub_clazz_prop_codes[2],
                clazz_prop_codes[0],
                clazz_prop_codes[2],
            ],
        )

        for each in properties[subclazz.code]:
            each_code = each["code"]
            if each_code in clazz_prop_codes:
                class_code = clazz.code
            elif each_code in sub_clazz_prop_codes:
                class_code = subclazz.code
            else:
                class_code = None

            self.assertEqual(class_code, each["class_code"])

        self.assertSetEqual(
            set(sub_clazz_prop_codes + clazz_prop_codes),
            set(variantsClassification.get_variant_driving_properties().keys()),
        )

    def test_variants_classification(self):
        timestamp = ("%s" % time.time()).replace(".", "")
        prop1 = "PROP_TEXT_{}".format(timestamp)
        prop2 = "PROP_FLOAT_{}".format(timestamp)
        prop3 = "PROP_INT_{}".format(timestamp)
        prop4 = "PROP_BOOL_{}".format(timestamp)
        props = collections.OrderedDict(
            [
                (prop1, ["VALUE 2", "VALUE 1", "VALUE 1"]),
                (prop2, [(100, "cm"), (1, "m"), (200, "mm")]),
                (prop3, [7, 4, 2, 7]),
                (prop4, []),
            ]
        )
        clazz_code = "CS_VARIANTS_TEST_CLASS_%s" % timestamp
        clazz = common.generate_class_with_props(props, code=clazz_code)

        variability_model = operations.operation(
            constants.kOperationNew,
            VariabilityModel,
            class_object_id=clazz.cdb_object_id,
            product_object_id=self.product.cdb_object_id,
        )

        empty_values = {
            prop1: common.get_text_property_entry(prop1, None),
            prop2: common.get_float_property_entry(prop2, None),
            prop3: common.get_int_property_entry(prop3, None),
            prop4: common.get_bool_property_entry(prop4, None),
        }
        variant_no_values = common.generate_variant(variability_model, {})

        values = {
            prop1: common.get_text_property_entry(prop1, "Testtext"),
            prop2: common.get_float_property_entry(
                prop2, 100.00, float_value_normalized=1.0, unit_label="cm"
            ),
            prop3: common.get_int_property_entry(prop3, 4711),
            prop4: common.get_bool_property_entry(prop4, False),
        }
        variant_with_values = common.generate_variant(
            variability_model, {key: value[0]["value"] for key, value in values.items()}
        )

        expected_values = {
            variant_no_values.id: {
                "{}_{}".format(clazz_code, prop_code): prop_value
                for prop_code, prop_value in empty_values.items()
            },
            variant_with_values.id: {
                "{}_{}".format(clazz_code, prop_code): prop_value
                for prop_code, prop_value in values.items()
            },
        }

        variants_classification = VariantsClassification([clazz_code])
        variants_properties = variants_classification.get_variants_classification(
            variability_model
        )

        for variant_properties in variants_properties:
            self.assertTrue(
                common.is_classification_data_equal(
                    variant_properties["classification"],
                    expected_values[variant_properties["variant"].id],
                )
            )
