# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import copy
import logging

from cdb import constants
from cdb.objects import operations

from cs.documents import Document

from cs.classification import api, tools
from cs.classification.tests import utils


LOG = logging.getLogger(__name__)


class TestBackendValidation(utils.ClassificationTestCase):

    def setUp(self):
        super(TestBackendValidation, self).setUp()

    def _execute_operation(self, source, classification_data):
        if source:
            doc_copy = operations.operation(
                constants.kOperationCopy,
                source,
                operations.system_args(
                    classification_web_ctrl=tools.preset_mask_data(classification_data)
                )
            )
            return doc_copy
        else:
            doc = operations.operation(
                constants.kOperationNew,
                Document,
                operations.system_args(
                    classification_web_ctrl=tools.preset_mask_data(classification_data)
                ),
                titel="test doc",
                z_categ1="142",
                z_categ2="153",
            )
            return doc

    def _test_backend_validation(self, source):
        class_codes = ["TEST_CLASS_BACKEND_VALIDATION"]
        classification_data = api.get_new_classification(class_codes)

        with self.assertRaisesRegex(Exception, ".*Pflichtfelder wurden nicht gefüllt\."):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_TEXT_MANDATORY"][0]["value"] = "test text"
        with self.assertRaisesRegex(Exception, ".*Pflichtfelder wurden nicht gefüllt\."):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS"][0]["value"][
            "child_props"]["TEST_PROP_TEXT_MANDATORY"][0]["value"] = "test text"
        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS"][0]["value"][
            "child_props"]["TEST_PROP_TEXT_MANDATORY_MULTIVALUE"][0]["value"] = "test text"
        doc = self._execute_operation(source, classification_data)
        self.assertIsNotNone(doc)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PATTERN_PROP_MULTI"][0]["value"] = "test text"
        with self.assertRaisesRegex(
            Exception, ".*Merkmalwerte stimmen nicht mit dem Format der Schablone überein\."
        ):
            self._execute_operation(source, classification_data)

        classification_data["properties"]["TEST_CLASS_BACKEND_VALIDATION_TEST_PATTERN_PROP_MULTI"].append(
            copy.deepcopy(
                classification_data["properties"]["TEST_CLASS_BACKEND_VALIDATION_TEST_PATTERN_PROP_MULTI"][0]
            )
        )
        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PATTERN_PROP_MULTI"][0]["value"] = "A11A"
        with self.assertRaisesRegex(
            Exception, ".*Merkmalwerte stimmen nicht mit dem Format der Schablone überein\."
        ):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PATTERN_PROP_MULTI"][1]["value"] = "B22B"
        self._execute_operation(source, classification_data)

        classification_data["properties"]["TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"].append(
            copy.deepcopy(
                classification_data["properties"]["TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]
            )
        )

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]["value"][
            "child_props"]["TEST_PATTERN_PROP"][0]["value"] = "test text"
        with self.assertRaisesRegex(
            Exception, ".*Merkmalwerte stimmen nicht mit dem Format der Schablone überein\."
        ):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]["value"][
            "child_props"]["TEST_PATTERN_PROP"].append(
            copy.deepcopy(
                classification_data["properties"][
                    "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]["value"][
                    "child_props"]["TEST_PATTERN_PROP"][0]
            )
        )
        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]["value"][
            "child_props"]["TEST_PATTERN_PROP"][0]["value"] = "A11A&A11A_A11A"
        with self.assertRaisesRegex(
            Exception, ".*Merkmalwerte stimmen nicht mit dem Format der Schablone überein\."
        ):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][0]["value"][
            "child_props"]["TEST_PATTERN_PROP"][1]["value"] = "B22B&B22B_B22B"
        self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][1]["value"][
            "child_props"]["TEST_PATTERN_PROP"][0]["value"] = "test text"
        with self.assertRaisesRegex(
            Exception, ".*Merkmalwerte stimmen nicht mit dem Format der Schablone überein\."
        ):
            self._execute_operation(source, classification_data)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_BLOCK_PATTERN_MULTI"][1]["value"][
            "child_props"]["TEST_PATTERN_PROP"][0]["value"] = "A11A&A11A_A11A"
        self._execute_operation(source, classification_data)


    def test_create(self):
        self._test_backend_validation(None)

    def test_copy(self):
        class_codes = ["TEST_CLASS_BACKEND_VALIDATION"]
        classification_data = api.get_new_classification(class_codes)

        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_TEXT_MANDATORY"][0]["value"] = "test text"
        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS"][0]["value"][
            "child_props"]["TEST_PROP_TEXT_MANDATORY"][0]["value"] = "test text"
        classification_data["properties"][
            "TEST_CLASS_BACKEND_VALIDATION_TEST_PROP_BLOCK_MULTIVALUE_WITH_MANDATORY_PROPS"][0]["value"][
            "child_props"]["TEST_PROP_TEXT_MANDATORY_MULTIVALUE"][0]["value"] = "test text"
        doc = self._execute_operation(None, classification_data)
        self.assertIsNotNone(doc)

        self._test_backend_validation(doc)

    def test_backend_validation_with_rules(self):
        class_codes = ["TEST_CLASS_RULES_MANDATORY"]
        classification_data = api.get_new_classification(class_codes)
        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_MANUAL"][0]["value"] = 0

        with self.assertRaisesRegex(Exception, ".*Pflichtfelder wurden nicht gefüllt\."):
            self._execute_operation(None, classification_data)

        # check mandatory properties as set
        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_INT"][0]["value"] = 0
        doc = self._execute_operation(None, classification_data)
        self.assertIsNotNone(doc)

        # overrule mandatory properties
        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_BOOL"][0]["value"] = 1
        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_INT"][0]["value"] = None
        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_INT_1"][0]["value"] = None

        with self.assertRaisesRegex(Exception, ".*Pflichtfelder wurden nicht gefüllt\."):
            self._execute_operation(None, classification_data)

        classification_data["properties"]["TEST_CLASS_RULES_MANDATORY_TEST_PROP_INT_1"][0]["value"] = 0
        doc = self._execute_operation(None, classification_data)
        self.assertIsNotNone(doc)
