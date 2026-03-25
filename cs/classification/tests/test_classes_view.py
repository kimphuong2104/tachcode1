# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import unittest

from cs.classification import api
from cs.classification.tests import utils


class test_classification_classes_view(utils.ClassificationTestCase):

    def _get_classes_view(self, class_codes):
        doc = self.create_document("test_classes_view")
        classification_data = api.get_new_classification(class_codes)
        api.update_classification(doc, classification_data)
        classification_data = api.get_classification(
            doc, with_metadata=True, narrowed=False
        )
        return classification_data["metadata"]["classes_view"]

    def test_all_base_class_properties_in_sub_class_group(self):
        self.assertListEqual(
            ["TEST_CLASS_ORDER_SUB_2_2"], # no base classes should be displayed
            self._get_classes_view(["TEST_CLASS_ORDER_SUB_2_2"])
        )

    def test_assigned_class_without_own_properties(self):
        self.assertListEqual(
            [
                "TEST_CLASS_ORDER_SUB_3_3",
                "TEST_CLASS_ORDER_SUB_3",
                "TEST_CLASS_ORDER_BASE",
            ], # assigned class should be displayed
            self._get_classes_view(["TEST_CLASS_ORDER_SUB_3_3"])
        )

    def test_assigned_class_with_properties_on_all_levels(self):
        self.assertListEqual(
            [
                "TEST_CLASS_ORDER_SUB_1_1",
                "TEST_CLASS_ORDER_SUB_1",
                "TEST_CLASS_ORDER_BASE",
            ], # assigned class should be displayed
            self._get_classes_view(["TEST_CLASS_ORDER_SUB_1_1"])
        )

    def test_assigned_classes_with_properties_on_all_levels(self):
        self.assertListEqual(
            [
                "TEST_CLASS_ORDER_SUB_3_2",
                "TEST_CLASS_ORDER_SUB_3",
                "TEST_CLASS_ORDER_SUB_1_1",
                "TEST_CLASS_ORDER_SUB_1",
                "TEST_CLASS_ORDER_BASE",
            ], # assigned class should be displayed
            self._get_classes_view(["TEST_CLASS_ORDER_SUB_1_1", "TEST_CLASS_ORDER_SUB_3_2"])
        )

    def test_assigned_classes_with_groupde_base_class_properties(self):
        self.assertListEqual(
            [
                "TEST_CLASS_ORDER_SUB_3_3",
                "TEST_CLASS_ORDER_SUB_3",
                "TEST_CLASS_ORDER_SUB_1_1",
                "TEST_CLASS_ORDER_SUB_1",
                "TEST_CLASS_ORDER_SUB_2_2",
                "TEST_CLASS_ORDER_BASE",
            ], # assigned class should be displayed
            self._get_classes_view([
                "TEST_CLASS_ORDER_SUB_1_1", "TEST_CLASS_ORDER_SUB_2_2", "TEST_CLASS_ORDER_SUB_3_3"
            ])
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
