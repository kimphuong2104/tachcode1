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

from cdb import constants, ElementsError, sqlapi
from cdb.objects import operations

from cs.classification import api, catalog, classes
from cs.classification.tests import utils


class ClassPropertyTests(utils.ClassificationTestCase):

    def _create_test_class(self, code, parent_class_id, external_class_type=''):
        class_args = {
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "code": code,
            "external_class_type": external_class_type,
            "name_de": code,
            "parent_class_id": parent_class_id,
            "status": 200
        }
        test_class = classes.ClassificationClass.Create(**class_args)
        return test_class

    def _create_property(self, name):
        prop = catalog.TextProperty.Create(
            cdb_objektart="cs_property",
            code=name,
            is_multivalued=1,
            name_de=name,
            status=200,
            cdb_status_txt="Released"
        )
        return prop

    def test_enum_excludes(self):
        class_property = classes.ClassProperty.ByKeys(
            code="TEST_CLASS_ENUM_TEST_MANY_ENUM_VALUES"
        )
        class_property.change_active_flag_for_all_catalog_property_values(False)
        exclude_records = sqlapi.RecordSet2(
            "cs_property_value_exclude",
            "classification_class_id='{class_id}' AND class_property_id='{prop_id}'".format(
                class_id=class_property.classification_class_id,
                prop_id=class_property.cdb_object_id
            )
        )
        self.assertGreater(len(exclude_records), 0, "Excludes expected.")

        class_property.change_active_flag_for_all_catalog_property_values(True)

        exclude_records = sqlapi.RecordSet2(
            "cs_property_value_exclude",
            "classification_class_id='{class_id}' AND class_property_id='{prop_id}'".format(
                class_id=class_property.classification_class_id,
                prop_id=class_property.cdb_object_id
            )
        )
        self.assertEqual(len(exclude_records), 0, "Not excludes expected")

    def test_delete_without_object_classification(self):
        parent_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_APPLICABLE")
        test_class = self._create_test_class(
            "TEST_APP_CLASS_TEST_DELETE_CLASS_PROPERTIES_1",
            parent_class.cdb_object_id,
            external_class_type="DELETE_TEST"
        )
        prop = self._create_property("TEST_TEXT_VALUE_PROP")
        class_prop_1 = classes.ClassProperty.NewPropertyFromCatalog(prop, test_class.cdb_object_id)
        test_doc = self.create_document()
        assigned_classes = ["TEST_APP_CLASS_TEST_DELETE_CLASS_PROPERTIES_1"]
        classification = api.get_new_classification(assigned_classes)
        classification["properties"]["_DELETE_TEST_TEST_TEXT_VALUE_PROP"][0]["value"] = "a value"
        api.update_classification(test_doc, classification)

        parent_class = classes.ClassificationClass.ByKeys(code="TEST_CLASS_APPLICABLE")
        test_class = self._create_test_class(
            "TEST_APP_CLASS_TEST_DELETE_CLASS_PROPERTIES_2",
            parent_class.cdb_object_id,
            external_class_type="DELETE_TEST"
        )
        class_prop_2 = classes.ClassProperty.NewPropertyFromCatalog(prop, test_class.cdb_object_id)
        self.assertEqual(class_prop_1.code, class_prop_2.code)

        with self.assertRaisesRegex(ElementsError, "Das Merkmal kann nicht gelöscht werden, da Objektbewertungen existieren."):
            operations.operation(
                constants.kOperationDelete,
                class_prop_1
            )

        operations.operation(
            constants.kOperationDelete,
            class_prop_2
        )
