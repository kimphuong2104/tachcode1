# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from copy import deepcopy

import cdb
from cdb.objects import operations
from cs import documents

from cs.classification import api, catalog, classes, units, FloatRangeObjectPropertyValue, ObjectPropertyValue
from cs.classification.tests import utils


class FloatRangePropertyTest(utils.ClassificationTestCase):

    def setUp(self):
        super(FloatRangePropertyTest, self).setUp()
        self.prop_code = "_" + cdb.cdbuuid.create_uuid().replace('-', '_')
        self.class_default_attrs = [
            "default_value_oid",
            "has_enum_values",
            "is_enum_only",
            "is_multivalued",
            "is_unit_changeable",
            "no_decimal_positions",
            "no_integer_positions",
            "unit_object_id"
        ]
        self.class_default_attrs.extend([
            field.name
            for field in catalog.Property.name.getLanguageFields().values()
        ])
        self.class_default_attrs.extend([
            field.name
            for field in catalog.Property.prop_description.getLanguageFields().values()
        ])

        self.document = operations.operation(
            cdb.constants.kOperationNew,
            documents.Document,
            titel="titel",
            z_categ1="142",
            z_categ2="153"
        )

    def test_base_unit_change(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            unit_object_id=m.cdb_object_id
        )

        self.assertEqual(m.cdb_object_id, catalog_prop.unit_object_id)

    def test_base_unit_change_with_block_properties(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        block_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.BlockProperty,
            code=self.prop_code + "_block",
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.BlockPropertyAssignment,
            block_property_code=block_prop.code,
            assigned_property_code=self.prop_code,
            assigned_property_object_id=catalog_prop.cdb_object_id,
            default_unit_object_id=cm.cdb_object_id
        )

        with self.assertRaisesRegex(cdb.ElementsError, "Die Basiseinheit kann nicht mehr geändert werden, da das Merkmal in Blockmerkmalen verwendet wird."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                unit_object_id=m.cdb_object_id
            )

    def test_base_unit_change_with_class_properties(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        classification_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_FOR_IMPORT")
        self.assertIsNotNone(classification_class)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id
        )
        self.assertIsNotNone(class_prop)

        with self.assertRaisesRegex(cdb.ElementsError, "Die Basiseinheit kann nicht mehr geändert werden, da das Merkmal in Klassen verwendet wird."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                unit_object_id=m.cdb_object_id
            )

    def test_base_unit_change_with_property_values(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=15,
            max_unit_object_id=cm.cdb_object_id
        )

        with self.assertRaisesRegex(cdb.ElementsError, "Die Basiseinheit kann nicht mehr geändert werden, da bereits Merkmalwerte als Wertevorrat definiert sind."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                unit_object_id=m.cdb_object_id
            )

    def test_base_unit_change_with_values(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        classification_data = api.get_classification(self.document)
        classification_data["properties"] = api.create_additional_props([self.prop_code])["properties"]
        classification_data["properties"][self.prop_code][0]["value"]["min"]["float_value"] = 10.10
        classification_data["properties"][self.prop_code][0]["value"]["max"]["float_value"] = 20.20
        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)
        self.assertTrue(self.prop_code in persistent_classification_data["properties"])

        with self.assertRaisesRegex(cdb.ElementsError, "Die Basiseinheit kann nicht mehr geändert werden, da bereits Objektbewertungen existieren."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                unit_object_id=m.cdb_object_id
            )

    def test_class_property(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]

        args = {
            "code": self.prop_code,
            "default_value_oid": None,
            "has_enum_values": 0,
            "is_enum_only": 1,
            "is_multivalued": 0,
            "is_unit_changeable": 1,
            "no_decimal_positions": 4,
            "no_integer_positions": 6,
            "unit_object_id": cm.cdb_object_id
        }
        for field in catalog.Property.prop_description.getLanguageFields().values():
            args[field.name] = field.name
        for field in catalog.Property.name.getLanguageFields().values():
            args[field.name] = field.name

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            **args
        )
        self.assertIsNotNone(catalog_prop)
        catalog_prop.ChangeState(catalog.Property.RELEASED)

        catalog_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=15,
            max_unit_object_id=cm.cdb_object_id
        )
        catalog_prop.default_value_oid = catalog_value.cdb_object_id

        classification_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_FOR_IMPORT")
        self.assertIsNotNone(classification_class)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id
        )
        self.assertIsNotNone(class_prop)

        # check attributes transfered from catalo property
        for attr in self.class_default_attrs:
            catalog_prop_attr_value = getattr(catalog_prop, attr)
            class_prop_attr_value = getattr(class_prop, attr)
            self.assertEqual(
                catalog_prop_attr_value,
                class_prop_attr_value,
                "Attribute {} should match {} != {}".format(
                    attr, str(catalog_prop_attr_value), str(class_prop_attr_value)
                )
            )

        # check db defaults
        for attr, value in {'is_editable': 1, 'is_visible': 1}.items():
            self.assertEqual(value, getattr(class_prop, attr))

    def test_class_property_values_with_units(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=1,
            max_unit_object_id=m.cdb_object_id
        )

        classification_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_FOR_IMPORT")
        self.assertIsNotNone(classification_class)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id
        )
        self.assertIsNotNone(class_prop)

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=class_prop.cdb_object_id,
            is_active=1,
            min_float_value=30,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=2,
            max_unit_object_id=m.cdb_object_id
        )

        catalog_values = api.get_catalog_values(
            class_code="TEST_CLASS_FOR_IMPORT", property_code=class_prop.code, active_only=False, request=None
        )

        catalog_value_pos = 0
        self.assertAlmostEqual(5.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value"])
        self.assertAlmostEqual(5.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value_normalized"])
        self.assertEqual(cm.cdb_object_id, catalog_values[catalog_value_pos]["value"]["min"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(cm.cdb_object_id), catalog_values[catalog_value_pos]["value"]["min"]["unit_label"])
        self.assertAlmostEqual(1.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value"])
        self.assertAlmostEqual(100.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value_normalized"])
        self.assertEqual(m.cdb_object_id, catalog_values[catalog_value_pos]["value"]["max"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(m.cdb_object_id), catalog_values[catalog_value_pos]["value"]["max"]["unit_label"])
        catalog_value_pos = 1
        self.assertAlmostEqual(30.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value"])
        self.assertAlmostEqual(30.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value_normalized"])
        self.assertEqual(cm.cdb_object_id, catalog_values[catalog_value_pos]["value"]["min"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(cm.cdb_object_id), catalog_values[catalog_value_pos]["value"]["min"]["unit_label"])
        self.assertAlmostEqual(2.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value"])
        self.assertAlmostEqual(200.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value_normalized"])
        self.assertEqual(m.cdb_object_id, catalog_values[catalog_value_pos]["value"]["max"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(m.cdb_object_id), catalog_values[catalog_value_pos]["value"]["max"]["unit_label"])

    def test_class_property_values_without_units(self):

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=None
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=None,
            max_float_value=10,
            max_unit_object_id=None
        )

        classification_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_FOR_IMPORT")
        self.assertIsNotNone(classification_class)

        class_prop = classes.ClassProperty.NewPropertyFromCatalog(
            catalog_prop, classification_class.cdb_object_id
        )
        self.assertIsNotNone(class_prop)

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=class_prop.cdb_object_id,
            is_active=1,
            min_float_value=30,
            min_unit_object_id=None,
            max_float_value=80,
            max_unit_object_id=None
        )

        catalog_values = api.get_catalog_values(
            class_code="TEST_CLASS_FOR_IMPORT", property_code=class_prop.code, active_only=False, request=None
        )

        catalog_value_pos = 0
        self.assertAlmostEqual(5.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value"])
        self.assertAlmostEqual(5.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value_normalized"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["min"]["unit_object_id"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["min"]["unit_label"])
        self.assertAlmostEqual(10.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value"])
        self.assertAlmostEqual(10.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value_normalized"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["max"]["unit_object_id"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["max"]["unit_label"])

        catalog_value_pos = 1
        self.assertAlmostEqual(30.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value"])
        self.assertAlmostEqual(30.0, catalog_values[catalog_value_pos]["value"]["min"]["float_value_normalized"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["min"]["unit_object_id"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["min"]["unit_label"])
        self.assertAlmostEqual(80.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value"])
        self.assertAlmostEqual(80.0, catalog_values[catalog_value_pos]["value"]["max"]["float_value_normalized"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["max"]["unit_object_id"])
        self.assertEqual("", catalog_values[catalog_value_pos]["value"]["max"]["unit_label"])

    def test_catalog_property_values_with_units(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=1,
            max_unit_object_id=m.cdb_object_id
        )

        catalog_value = api.get_catalog_values(
            class_code=None, property_code=catalog_prop.code, active_only=False, request=None
        )[0]
        self.assertAlmostEqual(5.0, catalog_value["value"]["min"]["float_value"])
        self.assertAlmostEqual(5.0, catalog_value["value"]["min"]["float_value_normalized"])
        self.assertEqual(cm.cdb_object_id, catalog_value["value"]["min"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(cm.cdb_object_id), catalog_value["value"]["min"]["unit_label"])
        self.assertAlmostEqual(1.0, catalog_value["value"]["max"]["float_value"])
        self.assertAlmostEqual(100.0, catalog_value["value"]["max"]["float_value_normalized"])
        self.assertEqual(m.cdb_object_id, catalog_value["value"]["max"]["unit_object_id"])
        self.assertEqual(units.UnitCache.get_unit_label(m.cdb_object_id), catalog_value["value"]["max"]["unit_label"])

    def test_catalog_property_values_without_units(self):

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=None
        )

        operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=None,
            max_float_value=10,
            max_unit_object_id=None
        )

        catalog_value = api.get_catalog_values(
            class_code=None, property_code=catalog_prop.code, active_only=False, request=None
        )

        catalog_value_pos = 0
        self.assertAlmostEqual(5.0, catalog_value[catalog_value_pos]["value"]["min"]["float_value"])
        self.assertAlmostEqual(5.0, catalog_value[catalog_value_pos]["value"]["min"]["float_value_normalized"])
        self.assertEqual("", catalog_value[catalog_value_pos]["value"]["min"]["unit_object_id"])
        self.assertEqual("", catalog_value[catalog_value_pos]["value"]["min"]["unit_label"])
        self.assertAlmostEqual(10.0, catalog_value[catalog_value_pos]["value"]["max"]["float_value"])
        self.assertAlmostEqual(10.0, catalog_value[catalog_value_pos]["value"]["max"]["float_value_normalized"])
        self.assertEqual("", catalog_value[catalog_value_pos]["value"]["max"]["unit_object_id"])
        self.assertEqual("", catalog_value[catalog_value_pos]["value"]["max"]["unit_label"])

    def test_property_values_min_max_check(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        m = units.Unit.KeywordQuery(symbol="m")[0]

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        prop_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=10,
            max_unit_object_id=cm.cdb_object_id
        )

        with self.assertRaisesRegex(cdb.ElementsError, "Bitte prüfen Sie die Eingabe für die Untergrenze. Diese darf nicht grösser als die Obergrenze sein."):
            operations.operation(
                cdb.constants.kOperationNew,  # @UndefinedVariable
                catalog.FloatRangePropertyValue,
                property_object_id=catalog_prop.cdb_object_id,
                is_active=1,
                min_float_value=5,
                min_unit_object_id=cm.cdb_object_id,
                max_float_value=1,
                max_unit_object_id=cm.cdb_object_id
            )

        with self.assertRaisesRegex(cdb.ElementsError, "Bitte prüfen Sie die Eingabe für die Untergrenze. Diese darf nicht grösser als die Obergrenze sein."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                prop_value,
                min_float_value=5,
                min_unit_object_id=cm.cdb_object_id,
                max_float_value=1,
                max_unit_object_id=cm.cdb_object_id
            )

        with self.assertRaisesRegex(cdb.ElementsError, "Bitte prüfen Sie die Eingabe für die Untergrenze. Diese darf nicht grösser als die Obergrenze sein."):
            operations.operation(
                cdb.constants.kOperationNew,  # @UndefinedVariable
                catalog.FloatRangePropertyValue,
                property_object_id=catalog_prop.cdb_object_id,
                is_active=1,
                min_float_value=1,
                min_unit_object_id=m.cdb_object_id,
                max_float_value=5,
                max_unit_object_id=cm.cdb_object_id
            )

        with self.assertRaisesRegex(cdb.ElementsError, "Bitte prüfen Sie die Eingabe für die Untergrenze. Diese darf nicht grösser als die Obergrenze sein."):
            operations.operation(
                cdb.constants.kOperationModify,  # @UndefinedVariable
                prop_value,
                min_float_value=1,
                min_unit_object_id=m.cdb_object_id,
                max_float_value=5,
                max_unit_object_id=cm.cdb_object_id
            )

    def test_property_values_single_value(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        prop_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id
        )

        self.assertAlmostEqual(prop_value.min_float_value, prop_value.max_float_value)
        self.assertEqual(prop_value.min_unit_object_id, prop_value.max_unit_object_id)

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            prop_value,
            min_float_value=15,
            min_unit_object_id=cm.cdb_object_id,
            max_float_value=None,
            max_unit_object_id=None
        )

        self.assertAlmostEqual(prop_value.min_float_value, prop_value.max_float_value)
        self.assertEqual(prop_value.min_unit_object_id, prop_value.max_unit_object_id)

        prop_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            max_float_value=5,
            max_unit_object_id=cm.cdb_object_id
        )

        self.assertAlmostEqual(prop_value.min_float_value, prop_value.max_float_value)
        self.assertEqual(prop_value.min_unit_object_id, prop_value.max_unit_object_id)

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            prop_value,
            min_float_value=None,
            min_unit_object_id=None,
            max_float_value=15,
            max_unit_object_id=cm.cdb_object_id
        )

        self.assertAlmostEqual(prop_value.min_float_value, prop_value.max_float_value)
        self.assertEqual(prop_value.min_unit_object_id, prop_value.max_unit_object_id)

    def test_property_values_unit(self):

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de",
            unit_object_id=cm.cdb_object_id
        )

        prop_value = operations.operation(
            cdb.constants.kOperationNew,
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=cm.cdb_object_id
        )

        for operation in [cdb.constants.kOperationCopy, cdb.constants.kOperationModify]:
            with self.assertRaisesRegex(cdb.ElementsError, "Sie müssen eine Einheit angeben."):
                operations.operation(
                    operation,
                    prop_value,
                    min_float_value=5,
                    min_unit_object_id=None
                )
            with self.assertRaisesRegex(cdb.ElementsError, "Sie müssen eine Einheit angeben."):
                operations.operation(
                    operation,
                    prop_value,
                    min_float_value=1,
                    min_unit_object_id=None,
                    max_float_value=5,
                    max_unit_object_id=None
                )

        with self.assertRaisesRegex(cdb.ElementsError, "Sie müssen eine Einheit angeben."):
            operations.operation(
                cdb.constants.kOperationNew,
                catalog.FloatRangePropertyValue,
                property_object_id=catalog_prop.cdb_object_id,
                is_active=1,
                min_float_value=5,
                min_unit_object_id=None
            )

        with self.assertRaisesRegex(cdb.ElementsError, "Sie müssen eine Einheit angeben."):
            operations.operation(
                cdb.constants.kOperationNew,
                catalog.FloatRangePropertyValue,
                property_object_id=catalog_prop.cdb_object_id,
                is_active=1,
                max_float_value=10,
                max_unit_object_id=None
            )

        with self.assertRaisesRegex(cdb.ElementsError, "Sie müssen eine Einheit angeben."):
            operations.operation(
                cdb.constants.kOperationNew,
                catalog.FloatRangePropertyValue,
                property_object_id=catalog_prop.cdb_object_id,
                is_active=1,
                min_float_value=1,
                min_unit_object_id=None,
                max_float_value=5,
                max_unit_object_id=None
            )

    def test_property_values_without_unit(self):

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,
            catalog.FloatRangeProperty,
            code=self.prop_code,
            name_de="name_de"
        )

        prop_value = operations.operation(
            cdb.constants.kOperationNew,
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=5,
            min_unit_object_id=None
        )

        self.assertAlmostEqual(5, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(5, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            prop_value,
            min_float_value=4,
            min_unit_object_id=None
        )

        self.assertAlmostEqual(4, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(5, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

        prop_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            max_float_value=5,
            max_unit_object_id=None
        )

        self.assertAlmostEqual(5, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(5, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            prop_value,
            min_float_value=4,
            min_unit_object_id=None
        )

        self.assertAlmostEqual(4, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(5, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

        prop_value = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.FloatRangePropertyValue,
            property_object_id=catalog_prop.cdb_object_id,
            is_active=1,
            min_float_value=1,
            min_unit_object_id=None,
            max_float_value=5,
            max_unit_object_id=None
        )

        self.assertAlmostEqual(1, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(5, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

        operations.operation(
            cdb.constants.kOperationModify,  # @UndefinedVariable
            prop_value,
            min_float_value=2,
            min_unit_object_id=None,
            max_float_value=4,
            max_unit_object_id=None
        )

        self.assertAlmostEqual(2, prop_value.min_float_value)
        self.assertEqual('', prop_value.min_unit_object_id)
        self.assertAlmostEqual(4, prop_value.max_float_value)
        self.assertEqual('', prop_value.max_unit_object_id)

    def test_float_range_property(self):
        prop_code = "TEST_PROP_FLOAT_RANGE"
        addtl_prop_data = api.create_additional_props([prop_code])

        self.assertTrue(prop_code in addtl_prop_data["metadata"])
        prop = addtl_prop_data["metadata"][prop_code]
        self.assertEqual("float_range", prop["type"])
        self.assertEqual("", prop["default_unit_object_id"])
        self.assertEqual("", prop["default_unit_symbol"])
        self.assertListEqual([6, 2], prop["float_format"])

        self.assertTrue(prop_code in addtl_prop_data["properties"])
        value = addtl_prop_data["properties"][prop_code][0]
        self.assertEqual("float_range", value["property_type"])
        self.assertIsNone(value["id"])
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            empty_value = {
                'float_value': None,
                'float_value_normalized': None,
                'id': None,
                'range_identifier': range_identifier,
                'unit_object_id': ''
            }
            self.assertDictEqual(empty_value, value["value"][range_identifier])

        classification_data = api.get_classification(self.document)

        classification_data["properties"] = addtl_prop_data["properties"]
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 10.10
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.20

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            input_value = classification_data["properties"][prop_code][0]["value"][range_identifier]
            persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"][range_identifier])
            self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
            self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value_normalized"])
            self.assertIsNotNone(persistent_value["id"])
            self.assertEqual(range_identifier, persistent_value["range_identifier"])
            self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

        classification_data = persistent_classification_data
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 11.11
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.20

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            input_value = classification_data["properties"][prop_code][0]["value"][range_identifier]
            persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"][range_identifier])
            self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
            self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value_normalized"])
            self.assertEqual(input_value["id"], persistent_value["id"])
            self.assertEqual(range_identifier, persistent_value["range_identifier"])
            self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

    def test_float_range_default_property(self):
        prop_code = "TEST_PROP_FLOAT_RANGE_DEFAULT"
        classification_data = api.create_additional_props([prop_code])

        self.assertTrue(prop_code in classification_data["metadata"])
        prop = classification_data["metadata"][prop_code]
        self.assertEqual("float_range", prop["type"])
        self.assertEqual("", prop["default_unit_object_id"])
        self.assertEqual("", prop["default_unit_symbol"])
        self.assertListEqual([6, 2], prop["float_format"])
        self.assertIsNotNone(prop["default_value_oid"])

        self.assertTrue(prop_code in classification_data["properties"])
        value = classification_data["properties"][prop_code][0]
        self.assertEqual("float_range", value["property_type"])
        self.assertIsNone(value["id"])
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            empty_value = {
                'float_value': None,
                'float_value_normalized': None,
                'id': None,
                'range_identifier': range_identifier,
                'unit_object_id': ''
            }
            self.assertDictEqual(empty_value, value["value"][range_identifier])

    def test_float_range_unit_property(self):
        prop_code = "TEST_PROP_FLOAT_RANGE_UNIT"
        unit_symbol = "cm"
        cm = units.Unit.KeywordQuery(symbol=unit_symbol)[0]
        mm = units.Unit.KeywordQuery(symbol="mm")[0]

        addtl_prop_data = api.create_additional_props([prop_code])

        self.assertTrue(prop_code in addtl_prop_data["metadata"])
        prop = addtl_prop_data["metadata"][prop_code]
        self.assertEqual("float_range", prop["type"])
        self.assertEqual(cm.cdb_object_id, prop["default_unit_object_id"])
        self.assertEqual(unit_symbol, prop["default_unit_symbol"])
        self.assertListEqual([6, 2], prop["float_format"])

        self.assertTrue(prop_code in addtl_prop_data["properties"])
        value = addtl_prop_data["properties"][prop_code][0]
        self.assertEqual("float_range", value["property_type"])
        self.assertIsNone(value["id"])
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            empty_value = {
                'float_value': None,
                'float_value_normalized': None,
                'id': None,
                'range_identifier': range_identifier,
                'unit_object_id': cm.cdb_object_id,
                'unit_label': unit_symbol
            }
            self.assertDictEqual(empty_value, value["value"][range_identifier])

        classification_data = api.get_classification(self.document)

        classification_data["properties"] = addtl_prop_data["properties"]
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 100.0
        classification_data["properties"][prop_code][0]["value"]["min"]["unit_object_id"] = mm.cdb_object_id
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.0

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            input_value = classification_data["properties"][prop_code][0]["value"][range_identifier]
            persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"][range_identifier])
            self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
            normalized_float_value = units.normalize_value(
                input_value["float_value"], input_value["unit_object_id"], prop["default_unit_object_id"], prop_code
            )
            self.assertAlmostEqual(normalized_float_value, persistent_value["float_value_normalized"])
            self.assertIsNotNone(persistent_value["id"])
            self.assertEqual(range_identifier, persistent_value["range_identifier"])
            self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

    def test_float_range_block_property(self):
        prop_code = "TEST_PROP_FLOAT_RANGE_BLOCK"
        unit_symbol = "cm"
        cm = units.Unit.KeywordQuery(symbol=unit_symbol)[0]
        mm = units.Unit.KeywordQuery(symbol="mm")[0]

        addtl_prop_data = api.create_additional_props([prop_code])
        self.assertTrue(prop_code in addtl_prop_data["metadata"])
        self.assertTrue(prop_code in addtl_prop_data["properties"])

        prop = addtl_prop_data["metadata"][prop_code]["child_props_data"]["TEST_PROP_FLOAT_RANGE"]
        self.assertEqual("float_range", prop["type"])
        self.assertEqual("", prop["default_unit_object_id"])
        self.assertEqual("", prop["default_unit_symbol"])
        self.assertListEqual([6, 2], prop["float_format"])

        value = addtl_prop_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE"][0]
        self.assertEqual("float_range", value["property_type"])
        self.assertIsNone(value["id"])
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            empty_value = {
                'float_value': None,
                'float_value_normalized': None,
                'id': None,
                'range_identifier': range_identifier,
                'unit_object_id': ''
            }
            self.assertDictEqual(empty_value, value["value"][range_identifier])

        prop = addtl_prop_data["metadata"][prop_code]["child_props_data"]["TEST_PROP_FLOAT_RANGE_UNIT"]
        self.assertEqual("float_range", prop["type"])
        self.assertEqual(cm.cdb_object_id, prop["default_unit_object_id"])
        self.assertEqual(unit_symbol, prop["default_unit_symbol"])
        self.assertListEqual([6, 2], prop["float_format"])

        value = addtl_prop_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE_UNIT"][0]
        self.assertEqual("float_range", value["property_type"])
        self.assertIsNone(value["id"])
        for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
            empty_value = {
                'float_value': None,
                'float_value_normalized': None,
                'id': None,
                'range_identifier': range_identifier,
                'unit_object_id': cm.cdb_object_id,
                'unit_label': unit_symbol
            }
            self.assertDictEqual(empty_value, value["value"][range_identifier])

        classification_data = api.get_classification(self.document)
        classification_data["properties"] = addtl_prop_data["properties"]

        value = classification_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE"][0]["value"]
        value["min"]["float_value"] = 10.0
        value["max"]["float_value"] = 20.0
        value = classification_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE_UNIT"][0]["value"]
        value["min"]["float_value"] = 100.0
        value["min"]["unit_object_id"] = mm.cdb_object_id
        value["max"]["float_value"] = 20.0

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        for child_prop_code in ["TEST_PROP_FLOAT_RANGE", "TEST_PROP_FLOAT_RANGE_UNIT"]:
            for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                input_value = classification_data["properties"][prop_code][0]["value"]["child_props"][child_prop_code][0]["value"][range_identifier]
                persistent_value = dict(persistent_classification_data["properties"][prop_code][0]["value"]["child_props"][child_prop_code][0]["value"][range_identifier])
                self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
                normalized_float_value = units.normalize_value(
                    input_value["float_value"], input_value["unit_object_id"], prop["default_unit_object_id"], prop_code
                ) if input_value["unit_object_id"] else input_value["float_value"]
                self.assertAlmostEqual(normalized_float_value, persistent_value["float_value_normalized"])
                self.assertIsNotNone(persistent_value["id"])
                self.assertEqual(range_identifier, persistent_value["range_identifier"])
                self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

    def test_default_values(self):
        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        mm = units.Unit.KeywordQuery(symbol="mm")[0]

        classification_data = api.get_new_classification(
            ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"], with_defaults=True, narrowed=False
        )

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT"
        value = classification_data["properties"][prop_code][0]["value"]
        self.assertAlmostEqual(30.0, value["min"]["float_value"])
        self.assertEqual("", value["min"]["unit_object_id"])
        self.assertAlmostEqual(40.0, value["max"]["float_value"])
        self.assertEqual("", value["max"]["unit_object_id"])

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT_UNIT"
        value = classification_data["properties"][prop_code][0]["value"]
        self.assertAlmostEqual(1.0, value["min"]["float_value"])
        self.assertEqual("cm", value["min"]["unit_label"])
        self.assertEqual(cm.cdb_object_id, value["min"]["unit_object_id"])
        self.assertAlmostEqual(30.0, value["max"]["float_value"])
        self.assertEqual("mm", value["max"]["unit_label"])
        self.assertEqual(mm.cdb_object_id, value["max"]["unit_object_id"])

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK"
        value = classification_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE_DEFAULT"][0]["value"]
        self.assertAlmostEqual(30.0, value["min"]["float_value"])
        self.assertEqual("", value["min"]["unit_object_id"])
        self.assertAlmostEqual(40.0, value["max"]["float_value"])
        self.assertEqual("", value["max"]["unit_object_id"])

        value = classification_data["properties"][prop_code][0]["value"]["child_props"]["TEST_PROP_FLOAT_RANGE_DEFAULT_UNIT"][0]["value"]
        self.assertAlmostEqual(1.0, value["min"]["float_value"])
        self.assertEqual("cm", value["min"]["unit_label"])
        self.assertEqual(cm.cdb_object_id, value["min"]["unit_object_id"])
        self.assertAlmostEqual(30.0, value["max"]["float_value"])
        self.assertEqual("mm", value["max"]["unit_label"])
        self.assertEqual(mm.cdb_object_id, value["max"]["unit_object_id"])

    def test_default_block_autocreate(self):

        def _check_block_values(identifying_prop_code, block_values, catalog_values):
            for block_value in block_values:
                found_match = False
                identifying_value = block_value["value"]["child_props"][identifying_prop_code][0]["value"]
                for catalog_value in catalog_values:
                    if identifying_value == catalog_value["value"]:
                        found_match = True
                self.assertTrue(found_match, "Missing catalog value for block {}".format(identifying_value))

        classification_data = api.get_new_classification(
            ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"], with_defaults=True, narrowed=False
        )

        identifying_prop_code = "TEST_PROP_FLOAT_RANGE_ENUM_ONLY"
        catalog_values = api.get_catalog_values(
            class_code=None, property_code=identifying_prop_code, active_only=False, request=None
        )

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_IDENTIFYING_CREATE"
        block_values = classification_data["properties"][prop_code]
        self.assertEqual(len(catalog_values), len(block_values))
        _check_block_values(identifying_prop_code, block_values, catalog_values)

        prop_code = "TEST_PROP_FLOAT_RANGE_BLOCK_IDENTIFYING_CREATE"
        block_prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_NESTED"

        block_values = classification_data["properties"][block_prop_code][0]["value"]["child_props"][prop_code]
        self.assertEqual(len(catalog_values), len(block_values))
        _check_block_values(identifying_prop_code, block_values, catalog_values)

        identifying_prop_code = "TEST_PROP_FLOAT_RANGE_UNIT_ENUM_ONLY"
        catalog_values = api.get_catalog_values(
            class_code=None, property_code=identifying_prop_code, active_only=False, request=None
        )

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT_BLOCK_IDENTIFYING_CREATE"
        block_values = classification_data["properties"][prop_code]
        self.assertEqual(len(catalog_values), len(block_values))
        _check_block_values(identifying_prop_code, block_values, catalog_values)

        prop_code = "TEST_PROP_FLOAT_RANGE_UNIT_BLOCK_IDENTIFYING_CREATE"
        block_prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_NESTED"

        block_values = classification_data["properties"][block_prop_code][0]["value"]["child_props"][prop_code]
        self.assertEqual(len(catalog_values), len(block_values))
        _check_block_values(identifying_prop_code, block_values, catalog_values)

    def test_class_default_and_autocreate(self):
        classification_data = api.get_new_classification(
            ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"], with_defaults=True, narrowed=False
        )
        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )

        persistent_classification_data = api.get_classification(self.document, pad_missing_properties=False, narrowed=False)

        expected_prop_codes = [
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_IDENTIFYING_CREATE",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_NESTED",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_BLOCK_NESTED_MULTIVALUE",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_DEFAULT_UNIT",
            "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT_BLOCK_IDENTIFYING_CREATE"
        ]

        for prop_code in persistent_classification_data["properties"]:
            self.assertIn(prop_code, expected_prop_codes)

    def test_class_edit_value(self):

        def _check_property_values():
            for prop_code in ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE",
                              "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT"]:
                prop = classes.FloatRangeClassProperty.KeywordQuery(code=prop_code)[0]
                for range_identifier in FloatRangeObjectPropertyValue.RANGE_IDENTIFIER:
                    input_value = classification_data["properties"][prop_code][0]["value"][range_identifier]
                    persistent_value = dict(
                        persistent_classification_data["properties"][prop_code][0]["value"][range_identifier])
                    self.assertAlmostEqual(input_value["float_value"], persistent_value["float_value"])
                    normalized_float_value = units.normalize_value(
                        input_value["float_value"], input_value["unit_object_id"],
                        prop["default_unit_object_id"], prop_code
                    ) if input_value["unit_object_id"] else input_value["float_value"]
                    self.assertAlmostEqual(normalized_float_value, persistent_value["float_value_normalized"])
                    self.assertIsNotNone(persistent_value["id"])
                    self.assertEqual(range_identifier, persistent_value["range_identifier"])
                    self.assertEqual(input_value["unit_object_id"], persistent_value["unit_object_id"])

        cm = units.Unit.KeywordQuery(symbol="cm")[0]
        mm = units.Unit.KeywordQuery(symbol="mm")[0]

        classification_data = api.get_new_classification(
            ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"], with_defaults=True, narrowed=False
        )

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE"
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 10.10
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.20

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT"
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 10.10
        classification_data["properties"][prop_code][0]["value"]["min"]["unit_object_id"] = mm.cdb_object_id
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.20

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        # check create values
        _check_property_values()

        classification_data = persistent_classification_data
        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE"
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 100.10
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 200.20

        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_UNIT"
        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 100.10
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 200.20
        classification_data["properties"][prop_code][0]["value"]["max"]["unit_object_id"] = mm.cdb_object_id

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        # check update values
        _check_property_values()

    def test_multivalue(self):
        classification_data = api.get_new_classification(
            ["TEST_CLASS_PROP_TYPE_FLOAT_RANGE"], with_defaults=True, narrowed=False
        )
        prop_code = "TEST_CLASS_PROP_TYPE_FLOAT_RANGE_TEST_PROP_FLOAT_RANGE_MULTIVALUE"
        classification_data["properties"][prop_code].append(
            deepcopy(classification_data["properties"][prop_code][0])
        )

        classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 10.10
        classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 20.20
        classification_data["properties"][prop_code][1]["value"]["min"]["float_value"] = 30.0
        classification_data["properties"][prop_code][1]["value"]["max"]["float_value"] = 50.0

        api.update_classification(
            self.document,
            classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        self.assertEqual(2, len(classification_data["properties"][prop_code]))
        for pos in [0, 1]:
            self.assertAlmostEqual(
                classification_data["properties"][prop_code][pos]["value"]["min"]["float_value"],
                persistent_classification_data["properties"][prop_code][pos]["value"]["min"]["float_value"]
            )
            self.assertAlmostEqual(
                classification_data["properties"][prop_code][pos]["value"]["max"]["float_value"],
                persistent_classification_data["properties"][prop_code][pos]["value"]["max"]["float_value"]
            )

        persistent_classification_data["properties"][prop_code][0]["value"]["min"]["float_value"] = 5.50
        persistent_classification_data["properties"][prop_code][0]["value"]["max"]["float_value"] = 10.10
        del persistent_classification_data["properties"][prop_code][-1]

        api.update_classification(
            self.document,
            persistent_classification_data,
            type_conversion=None,
            full_update_mode=True,
            check_access=True,
            update_index=False
        )
        persistent_classification_data = api.get_classification(self.document, narrowed=False)

        self.assertEqual(1, len(persistent_classification_data["properties"][prop_code]))
        self.assertAlmostEqual(
            5.5,
            persistent_classification_data["properties"][prop_code][0]["value"]["min"]["float_value"]
        )
        self.assertAlmostEqual(
            10.10,
            persistent_classification_data["properties"][prop_code][0]["value"]["max"]["float_value"]
        )
