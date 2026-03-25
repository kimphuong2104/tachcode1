# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from cdb import constants

from cdb.objects.operations import operation

from cs.classification import api, ClassificationConstants
from cs.classification.tests import utils
from cs.classification.classes import ClassProperty, ClassificationClass
from cs.classification.applicability import ClassificationApplicability
from cs.classification.catalog import TextProperty


class TestApplicabilityChange(utils.ClassificationTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestApplicabilityChange, cls).setUpClass()

    def _create_test_class(self, code, parent_class_id):
        class_args = {
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "code": code,
            "name_de": code,
            "parent_class_id": parent_class_id,
            "status": 200
        }
        test_class = ClassificationClass.Create(**class_args)
        return test_class

    def _create_applicability(self, test_class):
        applicability_args = {
            "classification_class_id": test_class.cdb_object_id,
            "dd_classname": "document",
            "is_active": 1,
            "write_access_obj": "save"
        }
        return ClassificationApplicability.Create(**applicability_args)

    def _create_property(self, name):
        prop = TextProperty.Create(
            cdb_objektart="cs_property",
            code=name,
            is_multivalued=1,
            name_de=name,
            status=200,
            cdb_status_txt="Released"
        )
        return prop

    def test_change_in_applicability(self):
        # Create class
        parent_class = ClassificationClass.ByKeys(code="TEST_CLASS_APPLICABLE")
        test_class = self._create_test_class("TEST_APP_VALUE_CLASS", parent_class.cdb_object_id)
        # Create document
        test_doc = self.create_document("Test Document for applicability update")
        # Create property
        prop = self._create_property("TEST_TEXT_VALUE_PROP")
        class_prop = ClassProperty.NewPropertyFromCatalog(prop, test_class.cdb_object_id)

        # Add class to document and edit it
        classes = ["TEST_APP_VALUE_CLASS"]
        classification = api.get_new_classification(classes)
        classification[ClassificationConstants.PROPERTIES]["TEST_APP_VALUE_CLASS_TEST_TEXT_VALUE_PROP"][0][ClassificationConstants.VALUE] = "a value"
        api.update_classification(test_doc, classification)

        # Check if value was updated
        test_classification = api.get_classification(test_doc)
        assert test_classification[ClassificationConstants.PROPERTIES]["TEST_APP_VALUE_CLASS_TEST_TEXT_VALUE_PROP"][0][ClassificationConstants.VALUE] == "a value"

        # Prepare applicability with link to test class
        applicability_args = {
            "classification_class_id": test_class.cdb_object_id,
            "dd_classname": "document",
            "is_active": 1,
            "write_access_obj": "save",
            "write_access_objclassification": "save",
            "olc_objclassification": "cs_property"
        }

        # Link applicability
        ClassificationApplicability.Create(**applicability_args)

        # Update Classification value
        new_classification = api.get_classification(test_doc)
        new_classification[ClassificationConstants.PROPERTIES]["TEST_APP_VALUE_CLASS_TEST_TEXT_VALUE_PROP"][0][ClassificationConstants.VALUE] = "a new value"
        api.update_classification(test_doc, new_classification)

        # Check if we were able to update value
        check_classification = api.get_classification(test_doc)
        assert check_classification[ClassificationConstants.PROPERTIES]["TEST_APP_VALUE_CLASS_TEST_TEXT_VALUE_PROP"][0][ClassificationConstants.VALUE] == "a new value"

    def test_delete_applicability_without_class_assignments(self):
        base_class = self._create_test_class("TEST_APP_BASE_CLASS", None)
        base_class_applicability = self._create_applicability(base_class)
        derived_class = self._create_test_class("TEST_APP_DERIVED_CLASS", base_class.cdb_object_id)
        derived_class_applicability = self._create_applicability(derived_class)
        operation(
            constants.kOperationDelete,
            derived_class_applicability
        )
        operation(
            constants.kOperationDelete,
            base_class_applicability
        )

    def test_delete_applicability_with_class_assignments_1(self):
        base_class = self._create_test_class("TEST_APP_BASE_CLASS", None)
        base_class_applicability = self._create_applicability(base_class)
        derived_class = self._create_test_class("TEST_APP_DERIVED_CLASS", base_class.cdb_object_id)
        derived_class_applicability = self._create_applicability(derived_class)

        test_doc = self.create_document("Test Document for applicability update")
        classification = api.get_new_classification(["TEST_APP_DERIVED_CLASS"])
        api.update_classification(test_doc, classification)

        # delete should pe possible as base class has applicability
        operation(
            constants.kOperationDelete,
            derived_class_applicability
        )

        with self.assertRaisesRegex(RuntimeError, "Die Klassenzuordnung kann nicht gelöscht werden, da klassifizierte Objekte existieren."):
            operation(
                constants.kOperationDelete,
                base_class_applicability
            )

    def test_delete_applicability_with_class_assignments_2(self):
        base_class = self._create_test_class("TEST_APP_BASE_CLASS", None)
        base_class_applicability = self._create_applicability(base_class)
        derived_class_with_applicability = self._create_test_class("TEST_APP_DERIVED_CLASS", base_class.cdb_object_id)
        derived_class_applicability = self._create_applicability(derived_class_with_applicability)

        test_doc = self.create_document("Test Document for applicability update")
        classification = api.get_new_classification(["TEST_APP_DERIVED_CLASS"])
        api.update_classification(test_doc, classification)

        # delete should pe possible as derived class has applicability
        operation(
            constants.kOperationDelete,
            base_class_applicability
        )

        with self.assertRaisesRegex(RuntimeError, "Die Klassenzuordnung kann nicht gelöscht werden, da klassifizierte Objekte existieren."):
            operation(
                constants.kOperationDelete,
                derived_class_applicability
            )

    def test_delete_applicability_with_class_assignments_3(self):
        base_class = self._create_test_class("TEST_APP_BASE_CLASS", None)
        base_class_applicability = self._create_applicability(base_class)
        self._create_test_class("TEST_APP_DERIVED_CLASS", base_class.cdb_object_id)

        test_doc = self.create_document("Test Document for applicability update")
        classification = api.get_new_classification(["TEST_APP_DERIVED_CLASS"])
        api.update_classification(test_doc, classification)

        with self.assertRaisesRegex(RuntimeError, "Die Klassenzuordnung kann nicht gelöscht werden, da klassifizierte Objekte existieren."):
            operation(
                constants.kOperationDelete,
                base_class_applicability
            )
