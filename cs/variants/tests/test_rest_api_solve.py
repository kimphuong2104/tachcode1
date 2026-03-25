#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
# pylint: disable=too-many-lines
import mock
import webtest

from cs.classification.api import get_classification
from cs.classification.util import get_enum_values_with_labels
from cs.platform.web.root import root as RootApp
from cs.variants import VARIANT_STATUS_INVALID, VARIANT_STATUS_OK, api
from cs.variants.api.filter import (
    CsVariantsFilterContextPlugin,
    CsVariantsVariabilityModelContextPlugin,
)
from cs.variants.tests import common
from cs.variants.web.editor import STATUS_FILTER_DISCRIMINATOR


@mock.patch(
    "cs.classification.util.get_enum_values_with_labels",
    wraps=get_enum_values_with_labels,
)
class TestRestApiSolve(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp()
        self.client = webtest.TestApp(RootApp)

    def create_variants(self, only_have_saved_variants=True):
        variant_property_value_lookup = {}

        props = {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        variant_name = "SAVED1"
        self.variant_valid1 = common.generate_variant(
            self.variability_model, props, name=variant_name
        )
        variant_property_value_lookup[variant_name] = props

        props = {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        variant_name = "SAVED2"
        self.variant_valid2 = common.generate_variant(
            self.variability_model, props, name="SAVED2"
        )
        variant_property_value_lookup[variant_name] = props

        props = {self.prop1: "VALUE2", self.prop2: "VALUE2"}
        variant_name = "INVALID1"
        self.variant_invalid1 = common.generate_variant(
            self.variability_model, props, name="INVALID1"
        )
        variant_property_value_lookup[variant_name] = props
        api.exclude_variant(
            self.variability_model,
            get_classification(self.variant_invalid1)["properties"],
        )

        props = {self.prop1: "VALUE2", self.prop2: "VALUE1"}
        variant_name = "INVALID2"
        self.variant_invalid2 = common.generate_variant(
            self.variability_model, props, name="INVALID2"
        )
        variant_property_value_lookup[variant_name] = props
        api.exclude_variant(
            self.variability_model,
            get_classification(self.variant_invalid2)["properties"],
        )

        self.variant_ids = [
            self.variant_valid1.cdb_object_id,
            self.variant_valid2.cdb_object_id,
            self.variant_invalid1.cdb_object_id,
            self.variant_invalid2.cdb_object_id,
        ]

        if only_have_saved_variants:
            properties = self.variability_model.ClassificationClass.Properties

            for each in properties:
                each.is_enum_only = True

        return variant_property_value_lookup

    def setup_status(
        self, status, create_valid_variant=True, create_invalid_variant=True
    ):
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        if create_valid_variant:
            common.generate_variant(
                self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE1"}
            )

        if create_invalid_variant:
            common.generate_variant(
                self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE2"}
            )

        classification_class = self.variability_model.ClassificationClass
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s != 'VALUE1'" % prop2,
        )

        url = (
            "/api/cs.variants/v1/variability_model/%s/solve"
            % self.variability_model.cdb_object_id
        )
        response = self.client.post_json(
            url,
            params={"appliedFilterData": {STATUS_FILTER_DISCRIMINATOR: status}},
        )
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )
        return response

    def call_solve(
        self,
        mock_get_enum_values_with_labels=None,
        expected_mock_get_enum_values_with_labels_call_count=1,
        limit=None,
        filter_variant_id=None,
        filter_classification_properties=None,
        filter_status=None,
        expect_errors=False,
    ):
        url = (
            "/api/cs.variants/v1/variability_model/%s/solve"
            % self.variability_model.cdb_object_id
        )

        applied_filter_data = {}
        if filter_variant_id is not None:
            applied_filter_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                "variantData": {"object": {"id": filter_variant_id}},
            }
        if filter_classification_properties is not None:
            applied_filter_data[CsVariantsFilterContextPlugin.DISCRIMINATOR] = {
                "classificationProperties": filter_classification_properties,
            }
        if applied_filter_data:
            applied_filter_data[
                CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR
            ] = self.variability_model.cdb_object_id

        if filter_status is not None:
            applied_filter_data[STATUS_FILTER_DISCRIMINATOR] = filter_status

        params = {"appliedFilterData": applied_filter_data}
        if limit is not None:
            params.update({"limit": limit})

        response = self.client.post_json(
            url, params=params, expect_errors=expect_errors
        )
        if not expect_errors:
            self.assertEqual(
                200,
                response.status_code,
                "Unexpected response status %s" % response.status_code,
            )

        if mock_get_enum_values_with_labels is not None:
            self.assertEqual(
                expected_mock_get_enum_values_with_labels_call_count,
                mock_get_enum_values_with_labels.call_count,
            )
        return response

    def assert_variant_properties(
        self, variant_property_value_lookup, prop1, prop2, solution_variants
    ):
        for each in solution_variants:
            variant_name = each["variant"]["object"]["name"]
            property_value_lookup = variant_property_value_lookup[variant_name]
            expected_prop_dict = {
                prop1: common.get_text_property_entry(
                    prop1, property_value_lookup[self.prop1], use_mock_any_for_id=True
                ),
                prop2: common.get_text_property_entry(
                    prop2, property_value_lookup[self.prop2], use_mock_any_for_id=True
                ),
            }
            result_prop_dict = each["props"]
            self.assertDictEqual(
                expected_prop_dict,
                result_prop_dict,
            )  #

    def assert_variants(
        self, expected_variant_ids, variant_property_value_lookup, response
    ):
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        solution_variants = [
            solution for solution in response.json["solutions"] if "variant" in solution
        ]

        solution_variants_ids = [
            each["variant"]["object"]["cdb_object_id"] for each in solution_variants
        ]

        self.assertListEqual(
            sorted(solution_variants_ids),
            sorted(expected_variant_ids),
        )

        self.assert_variant_properties(
            variant_property_value_lookup, prop1, prop2, solution_variants
        )

    def assert_potential_variants(self, expected_potential_variants, response):
        solution_props_no_variant = [
            solution["props"]
            for solution in response.json["solutions"]
            if "variant" not in solution
        ]

        self.assertEqual(
            len(expected_potential_variants),
            len(solution_props_no_variant),
            "Expected # solved props {0} but got {1}".format(
                len(expected_potential_variants), len(solution_props_no_variant)
            ),
        )
        for expected_solution in expected_potential_variants:
            self.assertIn(
                expected_solution,
                solution_props_no_variant,
                "Cannot find solution %s in %s"
                % (
                    expected_solution,
                    solution_props_no_variant,
                ),
            )

    def assert_unique_ids(self, response):
        expected_unique_id_count = len(response.json["solutions"])
        got_unique_ids = {solution["id"] for solution in response.json["solutions"]}
        got_unique_ids_count = len(got_unique_ids)
        self.assertEqual(
            expected_unique_id_count,
            got_unique_ids_count,
            msg="Expected {0} unique ids but found: {1}".format(
                expected_unique_id_count, got_unique_ids_count
            ),
        )

    def test_solve(self, mock_get_enum_values_with_labels):
        """The solve API will generate all combinations"""
        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

        self.assert_unique_ids(response)

    def test_solve_one_prop(self, mock_get_enum_values_with_labels):
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1

        for each in self.variability_model.ClassificationClass.OwnProperties:
            if prop1 == each.code:
                continue

            each.Delete()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

        self.assert_unique_ids(response)

    def test_solve_with_valid_variant(self, mock_get_enum_values_with_labels):
        """The solve API will compute the status of a valid variant correctly"""
        variant_name = "VALID1"
        variant_props = {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        variant_property_value_lookup = {variant_name: variant_props}
        common.generate_variant(
            self.variability_model, variant_props, name=variant_name
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
        )

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        solutions = [
            solution
            for solution in response.json["solutions"]
            if common.is_classification_data_equal(
                solution["props"],
                {
                    prop1: common.get_text_property_entry(prop1, "VALUE1"),
                    prop2: common.get_text_property_entry(prop2, "VALUE1"),
                },
            )
        ]
        assert solutions, "Cannot find variant in the solution set"
        solution = solutions[0]

        assert "variant" in solution, "Cannot find variant in the solution set"
        got = solution["variant"]["status"]
        assert got == VARIANT_STATUS_OK, "Unexpected variant status %s" % got

        solution_variants = [
            each_solution
            for each_solution in response.json["solutions"]
            if "variant" in each_solution
        ]
        self.assert_variant_properties(
            variant_property_value_lookup, prop1, prop2, solution_variants
        )

        self.assert_unique_ids(response)

    def test_solve_with_invalid_variant(self, mock_get_enum_values_with_labels):
        """The solve API will compute the status of a invalid variant correctly"""
        variant_name = "INVALID1"
        variant_props = {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        variant_property_value_lookup = {variant_name: variant_props}
        common.generate_variant(
            self.variability_model, variant_props, name=variant_name
        )

        classification_class = self.variability_model.ClassificationClass
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s != 'VALUE1'" % prop2,
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
        )

        solutions = [
            solution
            for solution in response.json["solutions"]
            if common.is_classification_data_equal(
                solution["props"],
                {
                    prop1: common.get_text_property_entry(prop1, "VALUE1"),
                    prop2: common.get_text_property_entry(prop2, "VALUE1"),
                },
            )
        ]
        assert solutions, "Cannot find variant in the solution set"
        solution = solutions[0]

        assert "variant" in solution, "Cannot find variant in the solution set"
        got = solution["variant"]["status"]
        assert got == VARIANT_STATUS_INVALID, "Unexpected variant status %s" % got

        solution_variants = [
            each_solution
            for each_solution in response.json["solutions"]
            if "variant" in each_solution
        ]
        self.assert_variant_properties(
            variant_property_value_lookup, prop1, prop2, solution_variants
        )

        self.assert_unique_ids(response)

    def test_solve_with_presets(self, mock_get_enum_values_with_labels):
        """The solve API will restrict the solution space with presets"""
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        presets = {prop1: common.get_text_property_entry(prop1, "VALUE1")}
        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
            filter_classification_properties=presets,
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

        self.assert_unique_ids(response)

    def test_solve_incomplete(self, mock_get_enum_values_with_labels):
        """The solve API will restrict the solution space to incomplete variants"""
        # complete_variant
        common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        )

        # incomplete_variant
        common.generate_variant(self.variability_model, {self.prop1: "VALUE1"})

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"onlyIncomplete": True},
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
            }
        ]
        assert len(expected) == len(got), "Expected %s results but got %s" % (
            len(expected),
            len(got),
        )
        for index, expected_solution in enumerate(expected):
            for property_code, property_value in expected_solution.items():
                current_got = got[index]
                assert (
                    property_code in current_got
                ), "Property code not found in solution"
                assert (
                    property_value[0]["value"] == current_got[property_code][0]["value"]
                ), "Property values are not equal"

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of
        multiple valid and invalid saved variants with unsaved
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE1"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE2"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE1"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE2"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            self.variant_ids,
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_for_unsaved(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": True, "saved": False, "invalid": False},
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE1"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE2"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE1"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE2"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            [],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_except_unsaved(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": False, "saved": True, "invalid": True},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            self.variant_ids,
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_for_saved(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": False, "saved": True, "invalid": False},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid1.cdb_object_id, self.variant_valid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_except_saved(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": True, "saved": False, "invalid": True},
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE1"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE2"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE1"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE2"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            [self.variant_invalid1.cdb_object_id, self.variant_invalid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_for_invalid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": False, "saved": False, "invalid": True},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_invalid1.cdb_object_id, self.variant_invalid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_valid_and_invalid_variants_filtered_except_invalid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants with unsaved.
        But filtered to include only unsaved.
        """
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": True, "saved": True, "invalid": False},
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE1"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE2"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE1"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE2"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            [self.variant_valid1.cdb_object_id, self.variant_valid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_only_valid_and_invalid_variants(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of
        multiple valid and invalid saved variants without unsaved.
        """
        variant_property_value_lookup = self.create_variants()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            self.variant_ids,
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_only_valid_and_invalid_variants_filtered_for_valid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants without unsaved.
        But filtered to include only saved.
        """
        variant_property_value_lookup = self.create_variants()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": False, "saved": True, "invalid": False},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid1.cdb_object_id, self.variant_valid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_only_valid_and_invalid_variants_filtered_except_for_valid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants without unsaved.
        But filtered to exclude only saved.
        """
        variant_property_value_lookup = self.create_variants()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": True, "saved": False, "invalid": True},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_invalid1.cdb_object_id, self.variant_invalid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_only_valid_and_invalid_variants_filtered_for_invalid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants without unsaved.
        But filtered to include only invalid.
        """
        variant_property_value_lookup = self.create_variants()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": False, "saved": False, "invalid": True},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_invalid1.cdb_object_id, self.variant_invalid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_only_valid_and_invalid_variants_filtered_except_for_invalid(
        self, mock_get_enum_values_with_labels
    ):
        """
        The solve API will compute the status of a multiple valid and invalid saved variants without unsaved.
        But filtered to exclude only invalid.
        """
        variant_property_value_lookup = self.create_variants()

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_status={"notEvaluated": True, "saved": True, "invalid": False},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid1.cdb_object_id, self.variant_valid2.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_status_not_evaluated(self, _):
        """The solve API will restrict the solution space with invalid variants"""

        status = {"saved": False, "invalid": False, "notEvaluated": True}

        response = self.setup_status(status)

        solutions = response.json["solutions"]
        variants = [solution for solution in solutions if "variant" in solution]

        assert not variants, "Expected 0 variants but got %s" % len(variants)
        assert solutions, "The solution space is empty"

    def test_solve_with_status_valid(self, _):
        """The solve API will restrict the solution space with valid variants"""

        status = {"saved": True, "invalid": False, "notEvaluated": False}

        response = self.setup_status(status)

        solutions = response.json["solutions"]
        assert len(solutions) == 1, "Expected 1 variant but got %s" % len(solutions)

        solution = solutions[0]
        assert "variant" in solution, "Cannot find variant in the solution set"

        got = solution["variant"]["status"]
        assert got == VARIANT_STATUS_OK, "Unexpected variant status %s" % got

    def test_solve_with_status_invalid(self, _):
        """The solve API will restrict the solution space with not evaluated variants"""

        status = {"saved": False, "invalid": True, "notEvaluated": False}

        response = self.setup_status(status)
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )

        solutions = response.json["solutions"]
        assert len(solutions) == 1, "Expected 1 variant but got %s" % len(solutions)

        solution = solutions[0]
        assert "variant" in solution, "Cannot find variant in the solution set"

        got = solution["variant"]["status"]
        assert got != VARIANT_STATUS_OK, "Unexpected variant status %s" % got

    def test_solve_with_wrong_preset_prop(self, mock_get_enum_values_with_labels):
        """The solve API will answer with a bad request error if the preset property does not exist"""

        presets = {"wrong-prop": common.get_text_property_entry("wrong-prop", "VALUE1")}

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
            filter_classification_properties=presets,
            expect_errors=True,
        )
        assert response.status_code == 400, (
            "Unexpected response status %s" % response.status_code
        )

    def test_solve_with_limit(self, mock_get_enum_values_with_labels):
        """The solve API will restrict the solution space to the given limit"""

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
            limit=2,
        )

        got = [solution["props"] for solution in response.json["solutions"]]
        assert len(got) == 2, "Unexpected solution set"
        assert response.json["complete"] is False, "Unexpected complete flag"

    def test_solve_with_bigger_limit(self, mock_get_enum_values_with_labels):
        """The solve API will not restrict the solution space if the limit is bigger than the size"""

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            expected_mock_get_enum_values_with_labels_call_count=0,
            limit=200,
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        assert response.json["complete"] is True, "Unexpected complete flag"

        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

        self.assert_unique_ids(response)

    def test_solve_sort_variants_according_to_their_solver_status(
        self, mock_get_enum_values_with_labels
    ):
        """The solve API will sort the variants according to their status"""

        # valid_variant
        variant_name = "VALID1"
        variant_props = {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        variant_property_value_lookup = {variant_name: variant_props}
        common.generate_variant(
            self.variability_model, variant_props, name=variant_name
        )

        # invalid_variant
        variant_name = "INVALID1"
        variant_props = {self.prop1: "VALUE2", self.prop2: "VALUE2"}
        variant_property_value_lookup[variant_name] = variant_props
        common.generate_variant(
            self.variability_model, variant_props, name=variant_name
        )

        # valid_variant
        variant_name = "VALID2"
        variant_props = {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        variant_property_value_lookup[variant_name] = variant_props
        common.generate_variant(
            self.variability_model, variant_props, name=variant_name
        )

        classification_class = self.variability_model.ClassificationClass
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop1,
            expression="%s != 'VALUE2'" % prop2,
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
        )

        solutions = response.json["solutions"]

        for solution in solutions[:3]:
            assert "variant" in solution, "The saved variants do not come at the first"

        assert (
            solutions[0]["variant"]["status"] == VARIANT_STATUS_OK
        ), "The first variant is not valid"
        assert (
            solutions[1]["variant"]["status"] == VARIANT_STATUS_OK
        ), "The second variant is not valid"
        assert (
            solutions[2]["variant"]["status"] == VARIANT_STATUS_INVALID
        ), "The third variant is not valid"

        solution_variants = [
            solution for solution in response.json["solutions"] if "variant" in solution
        ]
        self.assert_variant_properties(
            variant_property_value_lookup, prop1, prop2, solution_variants
        )

        self.assert_unique_ids(response)

    def test_solve_with_variants_and_limit_1(self, mock_get_enum_values_with_labels):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            limit=1,
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid1.cdb_object_id], variant_property_value_lookup, response
        )

        self.assert_unique_ids(response)

    def test_solve_with_variants_and_limit_5(self, mock_get_enum_values_with_labels):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            limit=5,
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            [
                self.variant_valid1.cdb_object_id,
                self.variant_valid2.cdb_object_id,
                self.variant_invalid1.cdb_object_id,
                self.variant_invalid2.cdb_object_id,
            ],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_variants_and_limit_10(self, mock_get_enum_values_with_labels):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            limit=10,
        )

        self.assert_potential_variants(
            [
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE1"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, "VALUE2"
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE1"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, "VALUE2"
                    ),
                },
                {
                    self.class_prop1: common.get_text_property_entry(
                        self.class_prop1, None
                    ),
                    self.class_prop2: common.get_text_property_entry(
                        self.class_prop2, None
                    ),
                },
            ],
            response,
        )
        self.assert_variants(
            [
                self.variant_valid1.cdb_object_id,
                self.variant_valid2.cdb_object_id,
                self.variant_invalid1.cdb_object_id,
                self.variant_invalid2.cdb_object_id,
            ],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_variants_and_limit_1_with_filter(
        self, mock_get_enum_values_with_labels
    ):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            limit=1,
            filter_status={"notEvaluated": True, "saved": False, "invalid": True},
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_invalid1.cdb_object_id],
            variant_property_value_lookup,
            response,
        )

        self.assert_unique_ids(response)

    def test_solve_with_variants_and_limit_1_with_filter_presets(
        self, mock_get_enum_values_with_labels
    ):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=False
        )

        presets = {
            self.class_prop1: common.get_text_property_entry(
                self.class_prop1,
                variant_property_value_lookup[self.variant_valid2.name][self.prop1],
            ),
            self.class_prop2: common.get_text_property_entry(
                self.class_prop2,
                variant_property_value_lookup[self.variant_valid2.name][self.prop2],
            ),
        }

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            limit=1,
            filter_classification_properties=presets,
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid2.cdb_object_id], variant_property_value_lookup, response
        )

    def test_solve_with_variants_and_variant_id_filter(
        self, mock_get_enum_values_with_labels
    ):
        variant_property_value_lookup = self.create_variants(
            only_have_saved_variants=True
        )

        response = self.call_solve(
            mock_get_enum_values_with_labels=mock_get_enum_values_with_labels,
            filter_variant_id=self.variant_valid2.id,
        )

        self.assert_potential_variants([], response)
        self.assert_variants(
            [self.variant_valid2.cdb_object_id], variant_property_value_lookup, response
        )

        self.assert_unique_ids(response)
