
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/import unittest

import datetime
import unittest

from cdb import constants, sig
from cdb.objects.operations import operation

from cs.classification import api, ClassificationChecksum, ClassificationConstants, ObjectPropertyValue
from cs.classification.object_classification import ClassificationUpdater
from cs.classification.classification_data import ClassificationData
from cs.classification.scripts import udpate_persistent_checksums
from cs.documents import Document

from cs.classification.tests import utils

def set_persistent_flag(obj, data):
    data[ClassificationConstants.PERSISTENT_VALUES_CHECKSUM] = True


class TestChecksum(utils.ClassificationTestCase):

    def setUp(self):
        super(TestChecksum, self).setUp()
        sig.connect(Document, "classification_update", "pre")(set_persistent_flag)

    def tearDown(self):
        super(TestChecksum, self).tearDown()
        sig.disconnect(set_persistent_flag)

    def _check_checksum(self, obj):
        checksum = ClassificationData.calc_persistent_checksum(
            ObjectPropertyValue.KeywordQuery(ref_object_id=obj.cdb_object_id)
        )
        classification_checksum = ClassificationChecksum.ByKeys(ref_object_id=obj.cdb_object_id)
        self.assertIsNotNone(classification_checksum)
        self.assertEqual(checksum, classification_checksum.checksum)

    def test_checksum_empty_classification(self):
        doc = self.create_document("test_checksum_empty_classification")
        classification_data = api.get_new_classification([])
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)

    def test_checksum_values(self):
        doc = self.create_document("test_checksum_values")
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification_data = api.get_new_classification(assigned_classes)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2003, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2004, 3, 11)
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)
        classification_data = api.get_classification(doc)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext update"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2103, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2104, 3, 11)
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)
        classification_data = api.get_new_classification([])
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)

    def test_compare_checksums_for_different_objects(self):
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        doc_1 = self.create_document("test_checksum 1")
        classification_data = api.get_new_classification(assigned_classes)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2003, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2004, 3, 11)
        api.update_classification(doc_1, classification_data)

        doc_2 = self.create_document("test_checksum 2")
        classification_data = api.get_new_classification(assigned_classes)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2003, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2004, 3, 11)
        api.update_classification(doc_2, classification_data)

        checksum_1 = ClassificationChecksum.ByKeys(ref_object_id=doc_1.cdb_object_id).checksum
        checksum_2 = ClassificationChecksum.ByKeys(ref_object_id=doc_2.cdb_object_id).checksum
        self.assertEqual(checksum_1, checksum_2)

        classification_data = api.get_classification(doc_2)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext updated"
        api.update_classification(doc_2, classification_data)

        checksum_1 = ClassificationChecksum.ByKeys(ref_object_id=doc_1.cdb_object_id).checksum
        checksum_2 = ClassificationChecksum.ByKeys(ref_object_id=doc_2.cdb_object_id).checksum
        self.assertNotEqual(checksum_1, checksum_2)

    def test_checksum_multi_values(self):
        doc = self.create_document("test_checksum_multi_values")
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification_data = api.get_new_classification(assigned_classes)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0]["value"] = "testtext 1"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"].append(
            dict(classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0])
        )
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][1]["value"] = "testtext 2"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"].append(
            dict(classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][0])
        )
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][2]["value"] = "testtext 3"
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)
        classification_data = api.get_classification(doc)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"][2]["value"] = "testtext 3 update"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"].pop(1)
        api.update_classification(doc, classification_data)
        self._check_checksum(doc)

    def test_checksum_multi_operation(self):
        doc_1 = self.create_document("test_checksum_multi_operation 1")
        doc_2 = self.create_document("test_checksum_multi_operation 2")
        docs = [doc_1, doc_2]

        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification_data = api.get_new_classification(assigned_classes, with_defaults=False)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2003, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2004, 3, 11)

        ClassificationUpdater.multiple_update(docs, classification_data)
        for doc in docs:
            self._check_checksum(doc)

        classification_data = api.get_new_classification(assigned_classes, with_defaults=False)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext update"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2103, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2104, 3, 11)
        ClassificationUpdater.multiple_update(docs, classification_data)
        for doc in docs:
            self._check_checksum(doc)

    def test_checksum(self):
        doc = self.create_document("test_checksum_values")
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        classification_data = api.get_new_classification(assigned_classes)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2003, 3, 11)
        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_BLOCK_WITH_MULTILEVEL_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_WITH_SUB_BLOCK"][0]["value"]["child_props"]["TEST_PROP_BLOCK_MULTIVALUE_WITH_DATE"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"] = datetime.date(2004, 3, 11)
        api.update_classification(doc, classification_data)
        classification_checksum_1 = ClassificationChecksum.ByKeys(ref_object_id=doc.cdb_object_id)
        classification_data = api.get_classification(doc)
        api.update_classification(doc, classification_data)
        ClassificationUpdater.update_persistent_checksum(doc)
        classification_checksum_2 = ClassificationChecksum.ByKeys(ref_object_id=doc.cdb_object_id)
        self.assertEqual(classification_checksum_1.checksum, classification_checksum_2.checksum)

        classification_checksum_2.checksum = ""
        udpate_persistent_checksums.update_existing_checksums()
        classification_checksum_2 = ClassificationChecksum.ByKeys(ref_object_id=doc.cdb_object_id)
        self.assertEqual(classification_checksum_1.checksum, classification_checksum_2.checksum)

        operation(
            constants.kOperationDelete,
            doc
        )
        classification_checksum = ClassificationChecksum.ByKeys(ref_object_id=doc.cdb_object_id)
        self.assertIsNone(classification_checksum)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
