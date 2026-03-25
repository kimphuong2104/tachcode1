#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import collections
import time

from webtest import TestApp as Client

from cs.platform.web.root import Root
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


class TestBomApp(common.VariantsTestCase):
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
            self.comp, occurrence_id="occurrence3"
        )
        self.occurrence4 = generate_assembly_component_occurrence(
            self.comp, occurrence_id="occurrence4"
        )
        self.occurrence5 = generate_assembly_component_occurrence(
            self.comp, occurrence_id="occurrence5"
        )
        self.comp.menge = 5

        self.selection_condition_comp = generate_selection_condition(
            variability_model, self.comp, expression
        )
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
        filter_classification_properties=None,
        expect_errors=False,
    ):
        variability_model_object_id = (
            self.variability_model.cdb_object_id
            if variability_model_oid is None
            else variability_model_oid
        )

        c = Client(Root())

        url = "/internal/bommanager/{lbom_oid}/+boms".format(
            lbom_oid=self.maxbom.cdb_object_id
        )

        bom_enhancement_data = {}
        if variability_model_object_id is not None:
            bom_enhancement_data[
                CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR
            ] = {"variability_model_id": variability_model_object_id}
            if variant_id is not None:
                bom_enhancement_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                    "variantData": {"object": {"id": variant_id}},
                }
            if filter_classification_properties is not None:
                bom_enhancement_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                    "classificationProperties": filter_classification_properties,
                }

        params = {
            "parents": [
                {
                    "teilenummer": self.maxbom.teilenummer,
                    "t_index": self.maxbom.t_index,
                    "cdb_object_id": self.maxbom.cdb_object_id,
                },
                {
                    "teilenummer": self.subassembly_comp.teilenummer,
                    "t_index": self.subassembly_comp.t_index,
                    "baugruppe": self.subassembly_comp.baugruppe,
                    "b_index": self.subassembly_comp.b_index,
                    "cdb_object_id": self.subassembly_comp.cdb_object_id,
                },
            ],
            "bomEnhancementData": bom_enhancement_data,
        }

        return c.post_json(url, params=params, expect_errors=expect_errors)

    # pylint: disable=too-many-arguments
    def assertBomItem(
        self,
        bom_item,
        in_variant=True,
        has_selection_condition=False,
        is_alternative=False,
        nr_occurrences_with_selection_condition=0,
        quantity=1,
        filtered_quantity=1,
    ):
        has_selection_condition = int(has_selection_condition)
        is_alternative = int(is_alternative)

        self.assertEqual(bom_item["in_variant"], in_variant)
        self.assertIsNone(bom_item["cdbvp_positionstyp"])

        # OLD VM Attributes
        self.assertIsNone(bom_item["cdbvp_has_condition"])
        # TODO: Do we really not need this?
        # self.assertEqual(bom_item["has_predicates"], 0)

        # NEW VM Attributes
        self.assertEqual(bom_item["has_sc_on_bom_item"], has_selection_condition)
        self.assertEqual(
            bom_item["cs_variants_has_selection_condition"], has_selection_condition
        )
        self.assertEqual(bom_item["cs_variants_is_alternative"], is_alternative)
        self.assertIn("selection_condition_icon", bom_item)

        self.assertEqual(
            bom_item["nr_of_selection_conditions_on_oc"],
            nr_occurrences_with_selection_condition,
        )

        self.assertEqual(int(bom_item["menge"]), quantity)
        self.assertEqual(
            int(bom_item["selection_condition_filtered_quantity"]), filtered_quantity
        )

    def test_boms_endpoint_with_variability_model(self):
        response = self.make_request()

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=1,
            quantity=2,
            filtered_quantity=2,
        )

    def test_boms_endpoint_with_variability_model_and_variant_which_filters(self):
        response = self.make_request(variant_id=self.variant.id)

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=1,
            quantity=2,
            filtered_quantity=1,
        )

    def test_boms_endpoint_with_variability_model_and_variant_which_filters_not(self):
        props = collections.OrderedDict(
            [
                (self.prop1, "VALUE2"),
                (self.prop2, "VALUE2"),
            ]
        )

        variant = common.generate_variant(self.variability_model, props)

        response = self.make_request(variant_id=variant.id)

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=1,
            quantity=2,
            filtered_quantity=2,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_not_filtered_all(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=5,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_all(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=0,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_text(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_float(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_float_with_unit(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_int(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_boolean(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=False,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_text_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
                self.text_prop: get_text_property_entry(self.text_prop, "VALUE2"),
            },
        )

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_float_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
                self.float_prop: get_float_property_entry(
                    self.float_prop, 4.56, unit_label=None
                ),
            },
        )

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_float_with_unit(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
                self.float_with_unit_prop: get_float_property_entry(
                    self.float_with_unit_prop, 4.56
                ),
            },
        )

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_int_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
                self.int_prop: get_int_property_entry(self.int_prop, 123),
            },
        )

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_variability_model_and_classification_prop_filtered_only_boolean_provided(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
                self.boolean_prop: get_bool_property_entry(self.boolean_prop, False),
            },
        )

        self.assertEqual(200, response.status_int)

        bom = response.json
        self.assertEqual(len(bom), 3)
        self.assertEqual(len(bom[1]), 1)
        self.assertEqual(len(bom[2]), 1)

        self.assertBomItem(
            bom[1][0],
            in_variant=True,
            has_selection_condition=False,
            is_alternative=False,
            nr_occurrences_with_selection_condition=0,
            quantity=1,
            filtered_quantity=1,
        )
        self.assertBomItem(
            bom[2][0],
            in_variant=True,
            has_selection_condition=True,
            is_alternative=False,
            nr_occurrences_with_selection_condition=5,
            quantity=5,
            filtered_quantity=4,
        )

    def test_boms_endpoint_with_selection_condition_with_syntax_error(
        self,
    ):
        variability_model = self.set_up_classification_prop_tests()

        self.selection_condition_comp.Update(
            expression='{prop} == "VALUE1'.format(prop=self.text_prop)
        )

        response = self.make_request(
            variability_model_oid=variability_model.cdb_object_id,
            filter_classification_properties={
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
            expect_errors=True,
        )

        self.assertEqual(422, response.status_code)
