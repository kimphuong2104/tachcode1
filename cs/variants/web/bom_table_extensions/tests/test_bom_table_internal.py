#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import collections
import json
import time

from webtest import TestApp as Client

from cs.platform.web.rest.support import get_restlink_by_keys
from cs.platform.web.root import Root
from cs.platform.web.root.main import _get_dummy_request
from cs.variants.api.filter import (
    CsVariantsFilterContextPlugin,
    CsVariantsVariabilityModelContextPlugin,
)
from cs.variants.tests import common
from cs.variants.tests.common import (
    create_variability_model,
    generate_assembly_component_occurrence,
    generate_selection_condition,
    get_bool_property_entry,
    get_float_property_entry,
    get_int_property_entry,
    get_text_property_entry,
)


class TestInternal(common.VariantsTestCase):
    def setUp(self, with_occurrences=True):
        super().setUp(with_occurrences=True)

        self.props = collections.OrderedDict(
            [
                (self.prop1, "VALUE1"),
                (self.prop2, "VALUE2"),
            ]
        )

        self.variant = common.generate_variant(self.variability_model, self.props)

    def set_up_classification_prop_tests(self):
        timestamp = ("%s" % time.time()).replace(".", "")

        class_code = "CS_VARIANTS_PROP_TEST"

        text_prop = "text_prop_%s" % timestamp
        float_prop = "float_prop_%s" % timestamp
        float_with_unit_prop = "float_with_unit_prop_%s" % timestamp
        int_prop = "int_prop_%s" % timestamp
        boolean_prop = "boolean_prop_%s" % timestamp

        props = collections.OrderedDict(
            [
                (text_prop, ["VALUE1", "VALUE2"]),
                (float_prop, [1.23, 4.56]),
                (float_with_unit_prop, [(1.23, "m"), (4.56, "m")]),
                (int_prop, [42, 123]),
                (boolean_prop, [True, False]),
            ]
        )

        variability_model = create_variability_model(
            self.product,
            props,
            class_code=class_code,
        )

        self.text_prop = "{class_code}_CLASS_{text_prop}".format(
            class_code=class_code,
            text_prop=text_prop,
        )
        self.float_prop = "{class_code}_CLASS_{float_prop}".format(
            class_code=class_code,
            float_prop=float_prop,
        )
        self.float_with_unit_prop = "{class_code}_CLASS_{float_with_unit_prop}".format(
            class_code=class_code,
            float_with_unit_prop=float_with_unit_prop,
        )
        self.int_prop = "{class_code}_CLASS_{int_prop}".format(
            class_code=class_code,
            int_prop=int_prop,
        )
        self.boolean_prop = "{class_code}_CLASS_{boolean_prop}".format(
            class_code=class_code,
            boolean_prop=boolean_prop,
        )

        expression_parts = [
            '{prop} == "VALUE1"'.format(prop=self.text_prop),
            "{prop} == 1.23".format(prop=self.float_prop),
            "{prop} == 1.23".format(prop=self.float_with_unit_prop),
            "{prop} == 42".format(prop=self.int_prop),
            "{prop}".format(prop=self.boolean_prop),
        ]
        expression = " and ".join(expression_parts)

        self.occurrence3 = generate_assembly_component_occurrence(
            self.comp,
            occurrence_id="occurrence3",
            relative_transformation="occurrence3",
        )
        self.occurrence4 = generate_assembly_component_occurrence(
            self.comp,
            occurrence_id="occurrence4",
            relative_transformation="occurrence4",
        )
        self.occurrence5 = generate_assembly_component_occurrence(
            self.comp,
            occurrence_id="occurrence5",
            relative_transformation="occurrence5",
        )
        self.comp.menge = 5

        generate_selection_condition(variability_model, self.comp, expression)
        generate_selection_condition(
            variability_model, self.occurrence1, expression_parts[0]
        )
        generate_selection_condition(
            variability_model, self.occurrence2, expression_parts[1]
        )
        generate_selection_condition(
            variability_model, self.occurrence3, expression_parts[2]
        )
        generate_selection_condition(
            variability_model, self.occurrence4, expression_parts[3]
        )
        generate_selection_condition(
            variability_model, self.occurrence5, expression_parts[4]
        )

        return variability_model

    def make_request(
        self,
        variability_model_oid=None,
        variant_id=None,
        classification_properties=None,
    ):
        variability_model_object_id = (
            self.variability_model.cdb_object_id
            if variability_model_oid is None
            else variability_model_oid
        )

        c = Client(Root())

        bom_enhancement_data = {}
        if variability_model_object_id is not None:
            bom_enhancement_data[
                CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR
            ] = {"variability_model_id": variability_model_object_id}
            if variant_id is not None:
                bom_enhancement_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                    "variantData": {"object": {"id": variant_id}},
                }
            if classification_properties is not None:
                bom_enhancement_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                    "classificationProperties": classification_properties,
                }

        params = {
            "bom_item_keys": {"cdb_object_id": self.comp["cdb_object_id"]},
            "bomEnhancementData": bom_enhancement_data,
        }

        url = "/internal/bomtable/bom_item_occurrences/cs.variants"
        return c.post_json(
            url,
            params=params,
        )

    def assert_row(self, all_rows, obj, has_selection_condition=False):
        has_selection_condition = int(has_selection_condition)
        rest_link = get_restlink_by_keys(
            "bom_item_occurrence", objargs=obj, request=_get_dummy_request()
        )
        # rows are not sorted - find the correct row
        found_row = [row for row in all_rows if row["@id"] == rest_link]
        self.assertTrue(found_row)
        row_data = found_row[0]

        self.assertEqual(row_data["@id"], rest_link)
        self.assertEqual(row_data["persistent_id"], rest_link)

        columns_data = row_data["columns"]
        self.assertEqual(columns_data[0], obj.occurrence_id)

        columns_data_1 = json.loads(columns_data[1])
        self.assertEqual(columns_data_1["cdb_object_id"], obj.cdb_object_id)
        self.assertEqual(
            columns_data_1["cs_variants_has_selection_condition"],
            has_selection_condition,
        )
        self.assertIn("selection_condition_icon", columns_data_1)

        self.assertEqual(columns_data[2], obj.reference_path)
        self.assertEqual(columns_data[3], obj.assembly_path)
        self.assertEqual(columns_data[4], obj.relative_transformation)

    def test_bom_item_occurrences_endpoint_with_variability_model(self):
        response = self.make_request()

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 2)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=False)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_variant_which_filters(
        self,
    ):
        response = self.make_request(variant_id=self.variant.id)

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 1)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=False)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_variant_which_filters_not(
        self,
    ):
        props = collections.OrderedDict(
            [
                (self.prop1, "VALUE2"),
                (self.prop2, "VALUE2"),
            ]
        )

        variant = common.generate_variant(self.variability_model, props)

        response = self.make_request(variant_id=variant.id)

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 2)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=False)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_no_filter(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE1"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 1.23, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 1.23
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 42),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, True),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 5)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_all_filter(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE2"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 4.56, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 4.56
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 123),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, False),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 0)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_text(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE2"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 1.23, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 1.23
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 42),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, True),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_float(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE1"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 4.56, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 1.23
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 42),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, True),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_float_with_unit(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE1"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 1.23, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 4.56
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 42),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, True),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_int(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE1"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 1.23, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 1.23
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 123),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, True),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_boolean(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE1"),
                self.float_prop: get_float_property_entry(
                    self.float_prop, 1.23, unit_label=None
                ),
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 1.23
                ),
                self.int_prop: get_int_property_entry(self.int_prop, 42),
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, False),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_text_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE2"),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_float_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.float_prop: get_float_property_entry(
                    self.float_prop, 4.56, unit_label=None
                ),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_float_with_unit_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 4.56
                ),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_int_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.int_prop: get_int_property_entry(self.int_prop, 123),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence5, has_selection_condition=True)

    def test_bom_item_occurrences_endpoint_with_variability_model_and_props_filter_boolean_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            classification_properties={
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, False),
            },
        )

        self.assertEqual(200, response.status_int)

        response_rows = response.json["rows"]

        self.assertEqual(len(response_rows), 4)
        self.assert_row(response_rows, self.occurrence1, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence2, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence3, has_selection_condition=True)
        self.assert_row(response_rows, self.occurrence4, has_selection_condition=True)
