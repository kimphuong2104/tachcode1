# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json

from mock import MagicMock

from cdb import constants
from cdb.objects import operations
from cs.classification import catalog, classes
from cs.variants import VariabilityModelPart, Variant, VariantPart, api
from cs.variants.tests import common
from cs.variants.tests.common import ReinstantiateCase, create_variability_model


class TestCsVariants(common.VariantsTestCaseWithFloat):
    def setUp(self):
        super().setUp()

        # the variant will match on the first component (for the subassembly)
        # but will not match on the on subassembly's component
        comp = self.maxbom.Components[0]
        expression = "CS_VARIANTS_TEST_CLASS_%s == 'VALUE1'" % self.prop1
        common.generate_selection_condition(self.variability_model, comp, expression)

        self.variant = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
                self.prop_float: common.get_float_value(
                    200, unit_label="mm", float_value_normalized=0.2
                ),
            },
        )

    def test_part_delete_also_deletes_variant_part(self):
        part = api.instantiate_part(self.variant, self.maxbom)
        teilenummer = part.teilenummer
        t_index = part.t_index

        variant_parts = VariantPart.KeywordQuery(
            teilenummer=teilenummer, t_index=t_index
        )
        assert len(variant_parts) == 1, "Exactly one variant part should exist"

        operations.operation(constants.kOperationDelete, part)
        variant_parts = VariantPart.KeywordQuery(
            teilenummer=teilenummer, t_index=t_index
        )
        assert not variant_parts, "Variant part should be deleted"

    def test_save_variants(self):
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

        variants_classification = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(float_prop, 2.71),
            }
        ]

        ctx_mock = MagicMock()
        ctx_mock.dialog = {
            "variability_model_id": self.variability_model.cdb_object_id,
            "params_list": json.dumps(variants_classification),
        }

        variants_ids_before = Variant.Query().cdb_object_id

        Variant.on_cs_variant_save_variants_now(ctx_mock)

        variants_after = Variant.Query().Execute()
        new_variants = [
            each
            for each in variants_after
            if each.cdb_object_id not in variants_ids_before
        ]

        self.assertEqual(1, len(new_variants))
        common.check_classification(new_variants[0], variants_classification[0])

    def test_save_two_variants(self):
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

        variants_classification = [
            {
                prop1: common.get_text_property_entry(prop1, "VALUE1"),
                prop2: common.get_text_property_entry(prop2, "VALUE1"),
                float_prop: common.get_float_property_entry(float_prop, 2.71),
            },
            {
                prop1: common.get_text_property_entry(prop1, "VALUE2"),
                prop2: common.get_text_property_entry(prop2, "VALUE2"),
                float_prop: common.get_float_property_entry(float_prop, 2.71),
            },
        ]

        ctx_mock = MagicMock()
        ctx_mock.dialog = {
            "variability_model_id": self.variability_model.cdb_object_id,
            "params_list": json.dumps(variants_classification),
        }

        variants_ids_before = Variant.Query().cdb_object_id

        Variant.on_cs_variant_save_variants_now(ctx_mock)

        variants_after = Variant.Query().Execute()
        new_variants = [
            each
            for each in variants_after
            if each.cdb_object_id not in variants_ids_before
        ]

        self.assertEqual(2, len(new_variants))
        common.check_classification(new_variants[0], variants_classification[0])
        common.check_classification(new_variants[1], variants_classification[1])


class TestVariabilityModelPart(ReinstantiateCase):
    def test_create_set_configurable(self):
        self.part1.Reload()
        self.assertEqual(0, self.part1.configurable)

        operations.operation(
            constants.kOperationNew,
            VariabilityModelPart,
            variability_model_object_id=self.variability_model.cdb_object_id,
            teilenummer=self.part1.teilenummer,
            t_index=self.part1.t_index,
        )

        self.part1.Reload()
        self.assertEqual(1, self.part1.configurable)

    def test_delete_single_entry_set_configurable(self):
        self.maxbom.Reload()
        self.assertEqual(1, self.maxbom.configurable)

        variability_model_part = VariabilityModelPart.ByKeys(
            variability_model_object_id=self.variability_model.cdb_object_id,
            teilenummer=self.maxbom.teilenummer,
            t_index=self.maxbom.t_index,
        )
        operations.operation(constants.kOperationDelete, variability_model_part)

        self.maxbom.Reload()
        self.assertEqual(0, self.maxbom.configurable)

    def test_delete_multiple_entry_set_configurable(self):
        self.maxbom.Reload()
        self.assertEqual(1, self.maxbom.configurable)

        variability_model = create_variability_model(self.product, {})

        operations.operation(
            constants.kOperationNew,
            VariabilityModelPart,
            variability_model_object_id=variability_model.cdb_object_id,
            teilenummer=self.maxbom.teilenummer,
            t_index=self.maxbom.t_index,
        )

        operations.operation(
            constants.kOperationDelete,
            VariabilityModelPart.ByKeys(
                variability_model_object_id=self.variability_model.cdb_object_id,
                teilenummer=self.maxbom.teilenummer,
                t_index=self.maxbom.t_index,
            ),
        )

        self.maxbom.Reload()
        self.assertEqual(1, self.maxbom.configurable)

        operations.operation(
            constants.kOperationDelete,
            VariabilityModelPart.ByKeys(
                variability_model_object_id=variability_model.cdb_object_id,
                teilenummer=self.maxbom.teilenummer,
                t_index=self.maxbom.t_index,
            ),
        )

        self.maxbom.Reload()
        self.assertEqual(0, self.maxbom.configurable)
