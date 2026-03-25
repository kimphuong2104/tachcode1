#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cs.classification import catalog, classes
from cs.variants import api
from cs.variants.tests import common


class TestAPICheckClassification(common.VariantsTestCase):
    def test_prop_not_variant_driven(self):
        classification_class = self.variability_model.ClassificationClass
        free_prop = "FREE_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_property(values=[None, ""], code=free_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop,
            classification_class.cdb_object_id,
            for_variants=0,  # here non driven
        )

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
        }
        variant = api.save_variant(self.variability_model, variant_classification)
        result = api.check_classification_attributes(variant)

        self.assertTrue(result)

    def test_only_variant_driven_props(self):
        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
        }
        variant = api.save_variant(self.variability_model, variant_classification)
        result = api.check_classification_attributes(variant)
        self.assertTrue(result)

    def test_prop_variant_driven_empty_text_prop(self):
        classification_class = self.variability_model.ClassificationClass
        free_prop = "FREE_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_property(values=[""], code=free_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        prop3 = "CS_VARIANTS_TEST_CLASS_%s" % free_prop

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
            prop3: common.get_text_property_entry(prop3, ""),
        }
        variant = api.save_variant(self.variability_model, variant_classification)
        result = api.check_classification_attributes(variant)

        self.assertFalse(result)

    def test_prop_variant_driven_none_text_prop(self):
        classification_class = self.variability_model.ClassificationClass
        free_prop = "FREE_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_property(values=[""], code=free_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        prop3 = "CS_VARIANTS_TEST_CLASS_%s" % free_prop

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
            prop3: common.get_text_property_entry(prop3, None),
        }
        variant = api.save_variant(self.variability_model, variant_classification)
        result = api.check_classification_attributes(variant)

        self.assertFalse(result)

    def test_prop_variant_driven_empty_number_prop(self):
        classification_class = self.variability_model.ClassificationClass
        free_prop = "FREE_PROPERTY_%s" % self.timestamp
        catalog_prop = common.generate_property(values=[0], code=free_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED.status)

        classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id, for_variants=1
        )

        prop1 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop1
        prop2 = "CS_VARIANTS_TEST_CLASS_%s" % self.prop2
        prop3 = "CS_VARIANTS_TEST_CLASS_%s" % free_prop

        variant_classification = {
            prop1: common.get_text_property_entry(prop1, "VALUE1"),
            prop2: common.get_text_property_entry(prop2, "VALUE1"),
            prop3: common.get_text_property_entry(prop3, None),
        }
        variant = api.save_variant(self.variability_model, variant_classification)
        result = api.check_classification_attributes(variant)

        self.assertFalse(result)
