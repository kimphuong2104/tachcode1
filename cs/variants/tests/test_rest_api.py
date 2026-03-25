# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
"""
Tests for the module cs.variants.rest
"""

import collections
import json
import time

import mock
import webtest

from cs.platform.web.root import root as RootApp
from cs.variants import Variant
from cs.variants.tests import common

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class TestRestAPI(common.VariantsTestCase):
    def setUp(self, with_occurrences=False):
        super().setUp()
        self.client = webtest.TestApp(RootApp)

    def test_exclude_variants(self):
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
        var_model = common.create_variability_model(
            self.product, props, class_code=clazz_code
        )

        prop1_varmodel = "%s_CLASS_%s" % (clazz_code, prop1)
        prop2_varmodel = "%s_CLASS_%s" % (clazz_code, prop2)
        prop3_varmodel = "%s_CLASS_%s" % (clazz_code, prop3)

        expected_excluded = [
            {
                prop1_varmodel: common.get_text_property_entry(
                    prop1_varmodel, "VALUE 2"
                ),
                prop2_varmodel: common.get_float_property_entry(
                    prop2_varmodel, 1.0, unit_label="m"
                ),
                prop3_varmodel: common.get_int_property_entry(prop3_varmodel, 7),
            }
        ]

        ctx_mock = mock.MagicMock()
        ctx_mock.dialog = {
            "variability_model_id": var_model.cdb_object_id,
            "params_list": json.dumps(expected_excluded),
        }
        Variant.on_cs_variant_exclude_variants_now(ctx_mock)

        url = "/api/cs.variants/v1/variability_model/%s/solve" % var_model.cdb_object_id
        response = self.client.post_json(url, params={})
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        assert response.json["complete"] is True, "Unexpected complete flag"

        for each in expected_excluded:
            assert each not in got, "%s is still in %s" % (expected_excluded, got)

    def test_exclude_two_variants(self):
        """The solver API will not return an excluded variant"""
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
        var_model = common.create_variability_model(
            self.product, props, class_code=clazz_code
        )

        prop1_varmodel = "%s_CLASS_%s" % (clazz_code, prop1)
        prop2_varmodel = "%s_CLASS_%s" % (clazz_code, prop2)
        prop3_varmodel = "%s_CLASS_%s" % (clazz_code, prop3)

        expected_excluded = [
            {
                prop1_varmodel: common.get_text_property_entry(
                    prop1_varmodel, "VALUE 2"
                ),
                prop2_varmodel: common.get_float_property_entry(
                    prop2_varmodel, 1.0, unit_label="m"
                ),
                prop3_varmodel: common.get_int_property_entry(prop3_varmodel, 7),
            },
            {
                prop1_varmodel: common.get_text_property_entry(
                    prop1_varmodel, "VALUE 1"
                ),
                prop2_varmodel: common.get_float_property_entry(
                    prop2_varmodel, 1.0, unit_label="m"
                ),
                prop3_varmodel: common.get_int_property_entry(prop3_varmodel, 7),
            },
        ]

        ctx_mock = mock.MagicMock()
        ctx_mock.dialog = {
            "variability_model_id": var_model.cdb_object_id,
            "params_list": json.dumps(expected_excluded),
        }
        Variant.on_cs_variant_exclude_variants_now(ctx_mock)

        url = "/api/cs.variants/v1/variability_model/%s/solve" % var_model.cdb_object_id
        response = self.client.post_json(url, params={})
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )

        got = [solution["props"] for solution in response.json["solutions"]]

        assert response.json["complete"] is True, "Unexpected complete flag"

        for each in expected_excluded:
            assert each not in got, "%s is still in %s" % (expected_excluded, got)

    def test_validate_variant(self):
        """Test constraint validation for a variant"""

        variant = common.generate_variant(
            self.variability_model, {self.prop1: "VALUE1", self.prop2: "VALUE1"}
        )
        url = "/api/cs.variants/v1/variant/%s/validate" % variant.cdb_object_id
        response = self.client.post_json(
            url, {"class_codes": [self.variability_model.class_code]}
        )
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )
        got = response.json.get("violated_constraints")
        assert not got, "No constraint violation expected."

        expression = "{} != {}".format(self.prop1, self.prop2)
        args = {
            "equivalent": 0,
            "error_message_de": "Errormessage",
            "name_de": "TEST_CONSTRAINT",
        }
        common.generate_constraint(
            self.variability_model.ClassificationClass,
            when_condition="",
            expression=expression,
            **args
        )

        response = self.client.post_json(
            url, {"class_codes": [self.variability_model.class_code]}
        )
        assert response.status_code == 200, (
            "Unexpected response status %s" % response.status_code
        )
        got = response.json.get("violated_constraints")
        assert len(got) == 1, "One constraint violation expected."

        expected_constraint = {
            "equivalent": args["equivalent"],
            "error_message": args["error_message_de"],
            "expression": expression,
            "name": args["name_de"],
            "when_condition": "",
        }
        self.assertDictEqual(expected_constraint, got[0])
