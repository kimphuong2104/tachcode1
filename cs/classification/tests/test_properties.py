# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module properties

This is the documentation for the properties module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import cdb

from cdb import constants
from cdb.objects import operations
from cs import documents

from cs.classification import api, applicability, catalog, classes
from cs.classification.tests import utils

class PropertyTests(utils.ClassificationTestCase):

    def setUp(self):
        super(PropertyTests, self).setUp()

        self.properties = {
            "editing": catalog.Property.ByKeys(code="TEST_PROP_TEXT"),
        }

    def test_all_folder_assignment(self):
        """Properties are automatically assigned to all folder."""

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.TextProperty,
            code="test_code",
            name_de="test_name_de"
        )
        self.assertIsNotNone(catalog_prop)

        all_folder_assignment = catalog.PropertyFolderAssignment.ByKeys(
            folder_id=catalog.PropertyFolder.ALL_PROPERTIES_FOLDER,
            property_id=catalog_prop.cdb_object_id
        )
        self.assertIsNotNone(
            all_folder_assignment, "Catalog property should be assigned to all folder"
        )

    def test_modify_editing_properties(self):
        """Properties with the status 'editing' can be modified"""
        prop = self.properties["editing"]

        self.assertIsNotNone(prop)
        self.assertTrue(prop.CheckAccess("save"))
        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            prop,
            name_de="MODIFIED NAME"
        )
        self.assertEqual(prop.name_de, "MODIFIED NAME")

    def test_property_code_invalid(self):
        """The property code cannot start with a number and cannot contain any spaces"""
        invalid_codes = [
            "123",
            "123Stella",
            "Once upon a time"
        ]

        for code in invalid_codes:
            with self.assertRaisesRegex(cdb.ElementsError, "Ungültiger Wert"):
                operations.operation(
                    constants.kOperationNew,  # @UndefinedVariable
                    catalog.TextProperty,
                    code=code
                )

    def test_multivalue_change(self):

        catalog_prop = operations.operation(
            cdb.constants.kOperationNew,  # @UndefinedVariable
            catalog.TextProperty,
            code="test_multivalue_change_catalog_prop",
            name_de="test_multivalue_change_catalog_prop_de"
        )
        self.assertEqual(None, catalog_prop.is_multivalued)

        clazz = operations.operation(
            constants.kOperationNew,  # @UndefinedVariable
            classes.ClassificationClass,
            code="test_multivalue_change_class",
        )
        class_prop = classes.ClassProperty.NewPropertyFromCatalog(catalog_prop, clazz.cdb_object_id)
        self.assertEqual(None, class_prop.is_multivalued)

        # check multivalue change with no property values
        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            is_multivalued=1
        )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(1, catalog_prop.is_multivalued)
        self.assertEqual(1, class_prop.is_multivalued)

        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            is_multivalued=0
        )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(0, catalog_prop.is_multivalued)
        self.assertEqual(0, class_prop.is_multivalued)

        doc = operations.operation(
            constants.kOperationNew,  # @UndefinedVariable
            documents.Document,
            titel="test doc",
            z_categ1="142",
            z_categ2="153"
        )
        operations.operation(
            constants.kOperationNew,  # @UndefinedVariable
            applicability.ClassificationApplicability,
            classification_class_id=clazz.cdb_object_id,
            dd_classname="document",
            is_active=1,
            write_access_obj="save"
        )

        # check multivalue change with class property values
        classification_data = api.get_new_classification([clazz.code])
        classification_data["properties"][class_prop.code][0]["value"] = "test text"
        api.update_classification(doc, classification_data, update_index=False)

        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            is_multivalued=1
        )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(1, catalog_prop.is_multivalued)
        self.assertEqual(1, class_prop.is_multivalued)

        with self.assertRaisesRegexp(cdb.ElementsError, "Mehrwertig kann nicht geändert werden, da bereits Merkmalwerte existieren."):
            operations.operation(
                constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                is_multivalued=0
            )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(1, catalog_prop.is_multivalued)
        self.assertEqual(1, class_prop.is_multivalued)

        classification_data = api.get_new_classification([])
        api.update_classification(doc, classification_data)

        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            is_multivalued=0
        )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(0, catalog_prop.is_multivalued)
        self.assertEqual(0, class_prop.is_multivalued)

        classification_data = api.create_additional_props([catalog_prop.code])
        classification_data["properties"][catalog_prop.code][0]["value"] = "test text"
        api.update_additional_props(doc, classification_data)

        operations.operation(
            constants.kOperationModify,  # @UndefinedVariable
            catalog_prop,
            is_multivalued=1
        )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(1, catalog_prop.is_multivalued)
        self.assertEqual(1, class_prop.is_multivalued)

        with self.assertRaisesRegexp(cdb.ElementsError, "Mehrwertig kann nicht geändert werden, da bereits Merkmalwerte existieren."):
            operations.operation(
                constants.kOperationModify,  # @UndefinedVariable
                catalog_prop,
                is_multivalued=0
            )
        catalog_prop.Reload()
        class_prop.Reload()
        self.assertEqual(1, catalog_prop.is_multivalued)
        self.assertEqual(1, class_prop.is_multivalued)
