# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
# pylint: disable=too-many-lines

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections

import cs.variants.api.selection_condition
from cs.classification import ObjectClassification, catalog, classes
from cs.variants import api, exceptions
from cs.variants.tests import common


class TestAPI(common.VariantsTestCase):
    def call_solve(self, variability_model, **kwargs):
        result = []
        for each_solution, each_checksum in api.solve(variability_model, **kwargs):
            result.append(each_solution)
            self.assertIsNotNone(each_checksum)

        return result

    def call_solve_view(self, variability_model, **kwargs):
        result = []
        for each_solution, each_checksum in api.solve_view(variability_model, **kwargs):
            result.append(each_solution)
            self.assertIsNotNone(each_checksum)

        return result

    def test_solve(self):
        """The solve method will generate all combinations"""
        got = self.call_solve(self.variability_model)

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

    def test_solve_boolean(self):
        """The solve method will generate solutions for boolean properties"""
        class_code = "CS_VARIANTS_BOOLEAN_TEST"
        self.bool_prop1 = "BOOLPROP1_%s" % self.timestamp
        self.bool_prop2 = "BOOLPROP2_%s" % self.timestamp

        props = {
            self.bool_prop1: [True, False],
            self.bool_prop2: [True, False],
        }

        variability_model = common.create_variability_model(
            self.product, props, class_code=class_code
        )

        prop1 = "%s_CLASS_%s" % (class_code, self.bool_prop1)
        prop2 = "%s_CLASS_%s" % (class_code, self.bool_prop2)
        expected = [
            {
                prop1: common.get_bool_property_entry(prop1, True),
                prop2: common.get_bool_property_entry(prop2, True),
            },
            {
                prop1: common.get_bool_property_entry(prop1, True),
                prop2: common.get_bool_property_entry(prop2, False),
            },
            {
                prop1: common.get_bool_property_entry(prop1, False),
                prop2: common.get_bool_property_entry(prop2, True),
            },
            {
                prop1: common.get_bool_property_entry(prop1, False),
                prop2: common.get_bool_property_entry(prop2, False),
            },
        ]
        got = self.call_solve(variability_model)

        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

    def test_match(self):
        """The component will match a variant"""
        variant = common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        )
        assert cs.variants.api.selection_condition.match(
            self.comp, variant
        ), "The component did not match the variant"

    def test_not_match(self):
        """The match method will not match a variant"""
        variant = common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE2"}
        )
        assert not cs.variants.api.selection_condition.match(
            self.comp, variant
        ), "The component did match the variant"

    def test_solve_with_presets(self):
        """The solve method will restrict the solution space with presets"""
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        got = self.call_solve(
            self.variability_model,
            presets={prop1: common.get_text_property_entry(prop1, "VALUE1")},
        )

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

    def test_solve_with_wrong_preset_prop(self):
        """The solve method will raise an exception if the preset property code does not exist"""

        with self.assertRaises(exceptions.InvalidPropertyCode):
            self.call_solve(
                self.variability_model,
                presets={
                    "wrong-prop": common.get_text_property_entry("wrong-prop", "VALUE1")
                },
            )

    def test_solve_with_constraints(self):
        """The solve method will evaluate constraints"""
        classification_class = self.variability_model.ClassificationClass
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s == 'VALUE1'" % prop2,
        )

        got = self.call_solve(self.variability_model)
        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
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
        assert len(expected) == len(
            got
        ), "Unexpected solution set. " "Expected %s solutions, got %s" % (
            len(expected),
            len(got),
        )
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

    def test_solve_with_constraints_and_float_property(self):
        """The solve method will evaluate constraints correctly with float properties"""
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s == 2.71" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop1,
            expression="%s == 3.14" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop2,
            expression="%s == 3.14" % float_prop,
        )

        got = self.call_solve(self.variability_model)

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 2.71, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 2.71, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 2.71, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(float_prop, None),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 2.71, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )
        for got_solution in got:
            assert got_solution in expected, "Cannot find solution %s in %s" % (
                got_solution,
                expected,
            )

    def test_solve_with_constraints_and_float_property_with_preset(self):
        """The solve method will evaluate constraints correctly with float properties"""
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s == 2.71" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop1,
            expression="%s == 3.14" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop2,
            expression="%s == 3.14" % float_prop,
        )

        presets = {
            float_prop: common.get_float_property_entry(
                float_prop, 3.14, unit_label="m"
            )
        }
        got = self.call_solve(self.variability_model, presets=presets)

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

    def test_solve_with_constraints_and_float_property_with_preset_with_other_unit(
        self,
    ):
        """The solve method will evaluate constraints correctly with float properties"""
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "CS_VARIANTS_TEST_FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s == 2.71" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop1,
            expression="%s == 3.14" % float_prop,
        )
        common.generate_constraint(
            classification_class,
            when_condition="%s == 'VALUE2'" % prop2,
            expression="%s == 3.14" % float_prop,
        )

        presets = {
            float_prop: common.get_float_property_entry(
                float_prop, 3140, unit_label="mm", float_value_normalized=3.14
            )
        }
        got = self.call_solve(self.variability_model, presets=presets)

        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
            {
                prop1: common.get_text_property_entry(prop1, None),
                prop2: common.get_text_property_entry(prop2, None),
                float_prop: common.get_float_property_entry(
                    float_prop, 3.14, unit_label="m"
                ),
            },
        ]
        assert len(expected) == len(got), "Unexpected solution set"
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

    def test_solve_with_constraints_on_parent_class(self):
        """The solve method will evaluate constraints on the parent class"""
        parent_class = self.variability_model.ClassificationClass
        child_class = common.generate_class_with_props(
            {},
            code="CS_VARIANTS_TEST_CHILD_CLASS",
            name_de="CS_VARIANTS_TEST_CHILD_CLASS",
            name_en="CS_VARIANTS_TEST_CHILD_CLASS",
            parent_class_id=parent_class.cdb_object_id,
        )
        self.variability_model.class_object_id = child_class.cdb_object_id
        self.variability_model.Reload()

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        common.generate_constraint(
            parent_class,
            when_condition="%s == 'VALUE1'" % prop1,
            expression="%s == 'VALUE1'" % prop2,
        )

        got = self.call_solve(self.variability_model)
        expected = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
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
        assert len(expected) == len(
            got
        ), "Unexpected solution set. " "Expected %s solutions, got %s" % (
            len(expected),
            len(got),
        )
        for expected_solution in expected:
            assert expected_solution in got, "Cannot find solution %s in %s" % (
                expected_solution,
                got,
            )

    def test_solve_with_limit(self):
        """The solve method will restrict the solution space to the given limit"""
        got = self.call_solve(self.variability_model, limit=2)
        assert len(got) == 2, "Unexpected solution set"

    def test_solve_with_bigger_limit(self):
        """The solve method will not restrict the solution space if the limit is bigger than the size"""
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        got = self.call_solve(self.variability_model, limit=100)
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

    def test_solve_view(self):
        """The solve method will generate all combinations for a view"""
        got = self.call_solve_view(self.view)

        prop1 = "CS_VARIANTS_TEST_VIEW_0_CLASS_%s" % self.view_prop1
        prop2 = "CS_VARIANTS_TEST_VIEW_0_CLASS_%s" % self.view_prop2
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

    def test_solve_with_custom_value_presets(self):
        """The solve method will raise an exception if the preset property value does not exist"""

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1

        with self.assertRaises(exceptions.InvalidPresets):
            self.call_solve(
                self.variability_model,
                presets={prop1: common.get_text_property_entry(prop1, "VALUE3")},
            )

    def test_save_variant(self):
        """The save_variant method will generate a classified variant object"""

        # test with a float property because they have a special handling
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[2.71, 3.14], code=self.float_prop
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
            float_prop: common.get_float_property_entry(float_prop, 2.71),
        }
        variant = api.save_variant(self.variability_model, variant_classification)

        assert variant is not None, "Variant object has not been created"
        common.check_classification(variant, variant_classification)
        self.assertIsNotNone(variant.classification_checksum)

        objectClassification = ObjectClassification.ByKeys(
            ref_object_id=variant.cdb_object_id, class_code=classification_class.code
        )
        assert objectClassification is not None, "Variant has no classification"
        assert (
            objectClassification.not_deletable == 1
        ), "Classification should not be deletable"

    def test_save_variant_with_name(self):
        """The save_variant method will set attributes on the variant object"""

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
        }
        variant_name = "TEST_VARIANT_%s" % self.timestamp
        variant = api.save_variant(
            self.variability_model, variant_classification, name=variant_name
        )

        assert variant is not None, "Variant object has not been created"
        assert variant.name == variant_name, "The name of the variant has not been set"
        self.assertIsNotNone(variant.classification_checksum)

    def test_save_variant_without_catalog_values(self):
        """The save_variant method will accept custom values"""

        # test with a float property without catalog values
        classification_class = self.variability_model.ClassificationClass
        self.float_prop = "FLOAT_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_float_property(
            values=[], code=self.float_prop  # No values here
        )
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )
        assert class_prop.status == classes.ClassProperty.RELEASED.status

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        float_prop = "CS_VARIANTS_TEST_CLASS_%s" % self.float_prop

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
            float_prop: common.get_float_property_entry(float_prop, 2.71),
        }
        variant = api.save_variant(self.variability_model, variant_classification)

        assert variant is not None, "Variant object has not been created"
        common.check_classification(variant, variant_classification)
        self.assertIsNotNone(variant.classification_checksum)

        objectClassification = ObjectClassification.ByKeys(
            ref_object_id=variant.cdb_object_id, class_code=classification_class.code
        )
        assert objectClassification is not None, "Variant has no classification"
        assert (
            objectClassification.not_deletable == 1
        ), "Classification should not be deletable"

    def test_save_variant_id_generation_different_and_start_with_1(self):
        variability_model2_class_code = "CS_VARIANTS_TEST2"
        variability_model2_prop = "VAR2_PROP1_%s" % self.timestamp
        props = collections.OrderedDict(
            [(variability_model2_prop, ["VALUE1", "VALUE2"])]
        )
        variability_model2 = common.create_variability_model(
            self.product, props, class_code=variability_model2_class_code
        )
        variability_model2_class_prop = (
            variability_model2_class_code + "_CLASS_" + variability_model2_prop
        )

        variability_model_prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        variability_model_prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        variant_classification = {
            variability_model_prop1: common.get_text_property_entry(
                variability_model_prop1, "VALUE1"
            ),
            variability_model_prop2: common.get_text_property_entry(
                variability_model_prop2, "VALUE1"
            ),
        }
        variant_classification3 = {
            variability_model_prop1: common.get_text_property_entry(
                variability_model_prop1, "VALUE1"
            ),
            variability_model_prop2: common.get_text_property_entry(
                variability_model_prop2, "VALUE2"
            ),
        }

        variant = api.save_variant(self.variability_model, variant_classification)
        variant2 = api.save_variant(
            variability_model2,
            {
                variability_model2_class_prop: common.get_text_property_entry(
                    variability_model2_class_prop, "VALUE1"
                )
            },
        )

        variant3 = api.save_variant(self.variability_model, variant_classification3)
        variant4 = api.save_variant(
            variability_model2,
            {
                variability_model2_class_prop: common.get_text_property_entry(
                    variability_model2_class_prop, "VALUE2"
                )
            },
        )

        self.assertEqual(
            1, variant.id, "Variant one of variability model one should have id 1"
        )
        self.assertEqual(
            1, variant2.id, "Variant one of variability model two should have id 1"
        )

        self.assertEqual(
            2, variant3.id, "Variant two of variability model one should have id 2"
        )
        self.assertEqual(
            2, variant4.id, "Variant two of variability model two should have id 2"
        )
        self.assertIsNotNone(variant.classification_checksum)
        self.assertIsNotNone(variant2.classification_checksum)
        self.assertIsNotNone(variant3.classification_checksum)
        self.assertIsNotNone(variant4.classification_checksum)
