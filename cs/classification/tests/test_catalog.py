# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import constants, ElementsError
from cdb.objects import operations
from cdb.constants import kOperationNew, kOperationDelete
from cs.classification import api, ClassificationConstants, classes, catalog, units
from cs.classification.catalog import _activate_property_values, \
    TextProperty, TextPropertyValue, IntegerProperty, IntegerPropertyValue, MultilangProperty, MultilangPropertyValue, \
    FloatProperty, FloatPropertyValue, FloatRangeProperty, FloatRangePropertyValue, \
    DatetimeProperty, DatetimePropertyValue, ObjectReferenceProperty, ObjectRefPropertyValue
from cs.classification.tests import utils
from cs.documents import Document
from mock import MagicMock
import datetime


class TestCatalogPropertyValue(utils.ClassificationTestCase):
    def setUp(self):
        super(TestCatalogPropertyValue, self).setUp()

        self.test_class_property = classes.ClassProperty.ByKeys(code="TEST_CLASS_ENUM_LABELS_TEST_PROP_ENUM_LABELS")
        self.test_catalog_property = catalog.Property.ByKeys(code="TEST_PROP_ENUM_LABELS")

    def activate_for_variability(self):
        operations.operation(
            constants.kOperationModify,
            self.test_class_property,
            for_variants=1
        )

    def create_property_value_in_test_catalog_property(self, active=False):
        return operations.operation(
            constants.kOperationNew,
            catalog.value_type_map["text"],
            property_object_id=self.test_catalog_property.cdb_object_id,
            text_value="VALUE_NEW",
            is_active=active
        )

    def get_count_of_exclude_rules_for_test_catalog_property(self):
        return len(classes.ClassPropertyValueExclude.KeywordQuery(property_id=self.test_catalog_property.cdb_object_id))

    def test_disable_value_for_variability_class_properties_after_create__for_variants_false_and_active_creation(self):
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())
        self.create_property_value_in_test_catalog_property(active=True)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_create__for_variants_true_and_active_creation(self):
        self.activate_for_variability()

        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())
        self.create_property_value_in_test_catalog_property(active=True)
        self.assertEqual(1, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_create__for_variants_false_and_inactive_creation(
            self):
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())
        self.create_property_value_in_test_catalog_property(active=False)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_create__for_variants_true_and_inactive_creation(self):
        self.activate_for_variability()

        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())
        self.create_property_value_in_test_catalog_property(active=False)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_modify__for_variants_false_and_modify_inactive_to_active(
            self):
        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        operations.operation(
            constants.kOperationModify,
            property_value,
            is_active=1
        )
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_modify__for_variants_true_and_modify_inactive_to_active(
            self):
        self.activate_for_variability()

        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        operations.operation(
            constants.kOperationModify,
            property_value,
            is_active=1
        )
        self.assertEqual(1, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_modify__for_variants_false_and_modify_active_to_inactive(
            self):
        property_value = self.create_property_value_in_test_catalog_property(active=True)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        operations.operation(
            constants.kOperationModify,
            property_value,
            is_active=0
        )
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_disable_value_for_variability_class_properties_after_modify__for_variants_true_and_modify_active_to_inactive(
            self):
        self.activate_for_variability()

        property_value = self.create_property_value_in_test_catalog_property(active=True)
        self.assertEqual(1, self.get_count_of_exclude_rules_for_test_catalog_property())

        operations.operation(
            constants.kOperationModify,
            property_value,
            is_active=0
        )
        self.assertEqual(1, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_activate_property_values__for_variants_true_and_catalog_property(self):
        self.activate_for_variability()

        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        ctx_mock = MagicMock()
        ctx_mock.parent = self.test_catalog_property

        _activate_property_values([property_value], ctx_mock)
        self.assertEqual(1, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_activate_property_values__for_variants_false_and_catalog_property(self):
        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        ctx_mock = MagicMock()
        ctx_mock.parent = self.test_catalog_property

        _activate_property_values([property_value], ctx_mock)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_activate_property_values__for_variants_true_and_class_property(self):
        self.activate_for_variability()

        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        ctx_mock = MagicMock()
        ctx_mock.parent = self.test_class_property

        _activate_property_values([property_value], ctx_mock)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_activate_property_values__for_variants_false_and_class_property(self):
        property_value = self.create_property_value_in_test_catalog_property()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        ctx_mock = MagicMock()
        ctx_mock.parent = self.test_class_property

        _activate_property_values([property_value], ctx_mock)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

    def test_activate_property_values__for_variants_true_and_catalog_property_already_activated(self):
        self.activate_for_variability()

        property_value = self.create_property_value_in_test_catalog_property(active=True)
        # Remove rule
        classes.ClassPropertyValueExclude.KeywordQuery(property_id=self.test_catalog_property.cdb_object_id)[0].Delete()
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())

        ctx_mock = MagicMock()
        ctx_mock.parent = self.test_catalog_property

        _activate_property_values([property_value], ctx_mock)
        self.assertEqual(0, self.get_count_of_exclude_rules_for_test_catalog_property())


class TestCatalogPropertyValueUsageOnDeletion(utils.ClassificationTestCase):

    def _create_property_and_values(self, property_type, prop_values, clazz):
        prop_value_objs = {}

        if property_type == "text":
            prop = TextProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_TEXT_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_TEXT_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "text_value": prop_value
                }
                prop_value_objs[index] = TextPropertyValue.Create(**value_args)

        if property_type == "datetime":
            prop = DatetimeProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_DATETIME_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_DATETIME_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "datetime_value": prop_value
                }
                prop_value_objs[index] = DatetimePropertyValue.Create(**value_args)

        if property_type == "integer":
            prop = IntegerProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_INT_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_INT_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "integer_value": prop_value,
                }
                prop_value_objs[index] = IntegerPropertyValue.Create(**value_args)

        if property_type == "objref":
            prop = ObjectReferenceProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_OBJREF_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_OBJREF_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "object_reference_value": prop_value
                }
                prop_value_objs[index] = ObjectRefPropertyValue.Create(**value_args)

        if property_type == "float":
            prop = FloatProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_FLOAT_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_FLOAT_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "float_value": prop_value[0],
                    "unit_object_id": prop_value[1]
                }
                prop_value_objs[index] = FloatPropertyValue.Create(**value_args)

        if property_type == "float_range":
            prop = FloatRangeProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_FLOAT_RANGE_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_FLOAT_RANGE_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "min_float_value": prop_value[0],
                    "min_unit_object_id": prop_value[1],
                    "max_float_value": prop_value[2],
                    "max_unit_object_id": prop_value[3]
                }
                prop_value_objs[index] = FloatRangePropertyValue.Create(**value_args)

        if property_type == "multilang":
            prop = MultilangProperty.Create(
                cdb_objektart="cs_property",
                code="TEST_ENUM_MULTILANG_VALUE_PROP",
                has_enum_values=1,
                name_de="TEST_ENUM_MULTILANG_VALUE_PROP",
                status=200,
                cdb_status_txt="Released"
            )

            for index, prop_value in enumerate(prop_values):
                value_args = {
                    "property_object_id": prop.cdb_object_id,
                    "is_active": 1,
                    "multilang_value_de": prop_value[0],
                    "multilang_value_en": prop_value[1]
                }
                prop_value_objs[index] = MultilangPropertyValue.Create(**value_args)

        classes.ClassProperty.NewPropertyFromCatalog(prop, clazz.cdb_object_id)
        return prop_value_objs

    def _create_text_property_values(self, prop, prop_values, is_active, value_key):
        prop_value_objs = {}
        for index, prop_value in enumerate(prop_values):
            value_args = {
                "property_object_id": prop.cdb_object_id,
                "is_active": 1,
                "text_value": prop_value
            }
            prop_value_objs[index] = TextPropertyValue.Create(**value_args)
        return prop_value_objs

    def test_check_uses_for_delete_text_value(self):
        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_TEXT_ENUM_VALUE_CLASS",
            name_de="TEST_TEXT_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, text_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_TEXT_VALUE_PROP"][0][
                ClassificationConstants.VALUE] = text_value

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "text",
            [
                'Some text value 1',
                'Some text value 1',
                'Some text value 2'
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", 'Some text value 1')
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )

        operations.operation(
            kOperationDelete,
            prop_values[2]
        )

        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_datetime_value(self):
        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_DATETIME_ENUM_VALUE_CLASS",
            name_de="TEST_DATETIME_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, datetime_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_DATETIME_VALUE_PROP"][
                0][
                ClassificationConstants.VALUE] = datetime_value

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "datetime",
            [
                datetime.datetime(2002, 3, 11),
                datetime.datetime(2002, 3, 11),
                datetime.datetime(2002, 3, 12)
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", datetime.datetime(2002, 3, 11))
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_integer_value(self):
        cm = units.Unit.KeywordQuery(symbol="cm")[0]

        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_INT_ENUM_VALUE_CLASS",
            name_de="TEST_INT_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, integer_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_INT_VALUE_PROP"][0][
                ClassificationConstants.VALUE] = integer_value

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "integer",
            [5, 5, 10],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", 5)
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_objref_value(self):
        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_OBJREF_ENUM_VALUE_CLASS",
            name_de="TEST_OBJREF_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, objref_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_OBJREF_VALUE_PROP"][0][
                ClassificationConstants.VALUE] = objref_value

            api.update_classification(doc, classification)
            return doc

        prop_values = {}

        ref_doc1 = operations.operation(
            kOperationNew,
            Document,
            titel="ref_doc1",
            z_categ1="142",
            z_categ2="153"
        )

        ref_doc2 = operations.operation(
            kOperationNew,
            Document,
            titel="ref_doc2",
            z_categ1="142",
            z_categ2="153"
        )

        prop_values.update(self._create_property_and_values(
            "objref",
            [
                ref_doc1.cdb_object_id,
                ref_doc1.cdb_object_id,
                ref_doc2.cdb_object_id
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", ref_doc1.cdb_object_id)
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_float_value(self):
        cm = units.Unit.KeywordQuery(symbol="cm")[0]

        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_FLOAT_ENUM_VALUE_CLASS",
            name_de="TEST_FLOAT_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, float_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_FLOAT_VALUE_PROP"][0][
                "value"][ClassificationConstants.FLOAT_VALUE] = float_value[0]
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_FLOAT_VALUE_PROP"][0][
                "value"][ClassificationConstants.FLOAT_VALUE_UNIT_OID] = float_value[1]

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "float",
            [
                [5.0, cm.cdb_object_id],
                [5.0, cm.cdb_object_id],
                [10.0, cm.cdb_object_id]
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", [5.0, cm.cdb_object_id])
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_float_range_value(self):
        cm = units.Unit.KeywordQuery(symbol="cm")[0]

        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_FLOAT_RANGE_ENUM_VALUE_CLASS",
            name_de="TEST_FLOAT_RANGE_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, float_range_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification["properties"][clazz.code + "_TEST_ENUM_FLOAT_RANGE_VALUE_PROP"][0]["value"][
                "min"][ClassificationConstants.FLOAT_VALUE] = float_range_value[0]
            classification["properties"][clazz.code + "_TEST_ENUM_FLOAT_RANGE_VALUE_PROP"][0]["value"][
                "min"][ClassificationConstants.FLOAT_VALUE_UNIT_OID] = float_range_value[1]
            classification["properties"][clazz.code + "_TEST_ENUM_FLOAT_RANGE_VALUE_PROP"][0]["value"][
                "max"][ClassificationConstants.FLOAT_VALUE] = float_range_value[2]
            classification["properties"][clazz.code + "_TEST_ENUM_FLOAT_RANGE_VALUE_PROP"][0]["value"][
                "max"][ClassificationConstants.FLOAT_VALUE_UNIT_OID] = float_range_value[3]

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "float_range",
            [
                [5.0, cm.cdb_object_id, 10.0, cm.cdb_object_id],
                [5.0, cm.cdb_object_id, 10.0, cm.cdb_object_id],
                [10.0, cm.cdb_object_id, 20.0, cm.cdb_object_id]
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", [5.0, cm.cdb_object_id, 10.0, cm.cdb_object_id])
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )

    def test_check_uses_for_delete_multilang_value(self):
        clazz = classes.ClassificationClass.Create(
            cdb_objektart="cs_classification_class",
            parent_class_id="bb845380-19c6-11e7-a201-28d24433bf35",
            code="TEST_MULTILANG_ENUM_VALUE_CLASS",
            name_de="TEST_MULTILANG_ENUM_VALUE_CLASS",
            status=200,
            cdb_status_txt="Released"
        )

        def classify_object(title, multilang_value):
            doc = operations.operation(
                kOperationNew,
                Document,
                titel=title,
                z_categ1="142",
                z_categ2="153"
            )

            classes = [clazz.code]
            classification = api.get_new_classification(classes)
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_MULTILANG_VALUE_PROP"][
                0][
                ClassificationConstants.VALUE]["de"]["iso_language_code"] = "de"
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_MULTILANG_VALUE_PROP"][
                0][
                ClassificationConstants.VALUE]["de"][ClassificationConstants.MULTILANG_VALUE] = multilang_value[0]
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_MULTILANG_VALUE_PROP"][
                0][
                ClassificationConstants.VALUE]["en"]["iso_language_code"] = "en"
            classification[ClassificationConstants.PROPERTIES][clazz.code + "_TEST_ENUM_MULTILANG_VALUE_PROP"][
                0][
                ClassificationConstants.VALUE]["en"][ClassificationConstants.MULTILANG_VALUE] = multilang_value[1]

            api.update_classification(doc, classification)
            return doc

        prop_values = {}
        prop_values.update(self._create_property_and_values(
            "multilang",
            [
                ["Tisch", "table"],
                ["Tisch", "table"],
                ["Stuhl", "chair"]
            ],
            clazz
        ))
        doc_1 = classify_object("Document enum value test", ["Tisch", "table"])
        operations.operation(
            kOperationDelete,
            prop_values[0]
        )
        operations.operation(
            kOperationDelete,
            prop_values[2]
        )
        with self.assertRaisesRegex(ElementsError, "Der Merkmalswert*"):
            operations.operation(
                kOperationDelete,
                prop_values[1]
            )
