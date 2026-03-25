# -*- mode: python; coding: utf-8 -*-

import logging

from datetime import datetime

from cdb import cdbuuid, sig, sqlapi

from cs.documents import Document

from cs.classification import api, ClassificationConstants, copy_classifications, delete_classifications, tools
from cs.classification.compare import ClassificationDataComparator
from cs.classification.tests import utils

LOG = logging.getLogger(__name__)


def set_persistent_flag(obj, data):
    data[ClassificationConstants.PERSISTENT_VALUES_CHECKSUM] = True


class TestLowLevelSQL(utils.ClassificationTestCase):

    @classmethod
    def setup_class(cls):
        sig.connect(Document, "classification_update", "pre")(set_persistent_flag)

        cls.CHUNK_SIZE_IN_STATEMENTS = tools.CHUNK_SIZE_IN_STATEMENTS
        cls.DELETE_ROW_MAX = tools.DELETE_ROW_MAX
        cls.INSERT_ROW_MAX = tools.INSERT_ROW_MAX
        cls.SELECT_ROW_MAX = tools.SELECT_ROW_MAX

        tools.CHUNK_SIZE_IN_STATEMENTS = 5
        tools.DELETE_ROW_MAX = 5
        tools.SELECT_ROW_MAX = 5
        tools.INSERT_ROW_MAX = 5

    @classmethod
    def teardown_class(cls):
        sig.disconnect(set_persistent_flag)

        tools.CHUNK_SIZE_IN_STATEMENTS = cls.CHUNK_SIZE_IN_STATEMENTS
        tools.DELETE_ROW_MAX = cls.DELETE_ROW_MAX
        tools.INSERT_ROW_MAX = cls.INSERT_ROW_MAX
        tools.SELECT_ROW_MAX = cls.SELECT_ROW_MAX

    def _test_checksums(self, ref_obj_ids):
        stmt = """SELECT * from cs_classification_checksum WHERE {}""".format(
            tools.format_in_condition("ref_object_id", list(ref_obj_ids.keys()) + list(ref_obj_ids.values()))
        )
        checksums = {}
        for checksum in sqlapi.RecordSet2(sql=stmt):
            checksums[checksum.ref_object_id] = checksum.checksum
        for src_obj_id, dest_object_id in ref_obj_ids.items():
            self.assertEqual(checksums[src_obj_id], checksums[dest_object_id])

    @classmethod
    def _create_uuids(cls, doc_ids):
        ref_obj_ids = {}
        copy_obj_ids = []
        for doc_id in doc_ids:
            copy_obj_id = cdbuuid.create_uuid()
            copy_obj_ids.append(copy_obj_id)
            ref_obj_ids[doc_id] = copy_obj_id
        return ref_obj_ids, copy_obj_ids

    def test_low_level_copy(self):
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        start = datetime.utcnow().replace(microsecond=0)

        doc_count = tools.SELECT_ROW_MAX + 1
        doc_ids = []
        for count in range(doc_count):
            doc = self.create_document("Test Copy {}".format(count))
            doc_ids.append(doc.cdb_object_id)
            classification_data = api.get_new_classification(assigned_classes)
            self.set_property_values(classification_data["properties"])
            api.update_classification(doc, classification_data, update_index=False)

        ref_obj_ids, copy_obj_ids = self._create_uuids(doc_ids)
        ref_object_ids_with_copied_classification_list = copy_classifications(ref_obj_ids)
        self.assertSetEqual(set(ref_object_ids_with_copied_classification_list), set(copy_obj_ids))

        for src_obj_id, dest_object_id in ref_obj_ids.items():
            comp = ClassificationDataComparator(
                src_obj_id, dest_object_id, with_metadata=False, narrowed=True, check_rights=False
            )
            compared_classification_data = comp.compare()
            self.assertTrue(compared_classification_data["classification_is_equal"])

        # test modification and index dates with solr update
        stmt = """SELECT * from cs_object_classification_log WHERE {}""".format(
            tools.format_in_condition("ref_object_id", copy_obj_ids)
        )
        count = 0
        for log_item in sqlapi.RecordSet2(sql=stmt):
            self.assertLessEqual(start, log_item.cdb_mdate)
            self.assertLessEqual(start, log_item.cdb_index_date)
            count += 1
        self.assertEqual(count, doc_count)

        self._test_checksums(ref_obj_ids)

        ref_obj_ids, copy_obj_ids = self._create_uuids(doc_ids)
        ref_object_ids_with_copied_classification_list = copy_classifications(ref_obj_ids, update_index=False)
        self.assertSetEqual(set(ref_object_ids_with_copied_classification_list), set(copy_obj_ids))

        for src_obj_id, dest_object_id in ref_obj_ids.items():
            comp = ClassificationDataComparator(
                src_obj_id, dest_object_id, with_metadata=False, narrowed=True, check_rights=False
            )
            compared_classification_data = comp.compare()
            self.assertTrue(compared_classification_data["classification_is_equal"])

        # test modification and index dates without solr update
        stmt = """SELECT * from cs_object_classification_log WHERE {}""".format(
            tools.format_in_condition("ref_object_id", copy_obj_ids)
        )
        count = 0
        for log_item in sqlapi.RecordSet2(sql=stmt):
            self.assertLessEqual(start, log_item.cdb_mdate)
            self.assertIsNone(log_item.cdb_index_date)
            count += 1
        self.assertEqual(count, doc_count)

        self._test_checksums(ref_obj_ids)

    def test_low_level_delete(self):
        assigned_classes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
        doc_count = tools.DELETE_ROW_MAX + 1
        doc_ids = []
        for count in range(doc_count):
            doc = self.create_document("Test Copy {}".format(count))
            doc_ids.append(doc.cdb_object_id)
            classification_data = api.get_new_classification(assigned_classes)
            self.set_property_values(classification_data["properties"])
            api.update_classification(doc, classification_data, update_index=False)

        ref_obj_ids, copy_obj_ids = self._create_uuids(doc_ids)
        ref_object_ids_with_copied_classification_list = copy_classifications(ref_obj_ids)
        self.assertSetEqual(set(ref_object_ids_with_copied_classification_list), set(copy_obj_ids))

        delete_classifications(copy_obj_ids)
        classification_tables = [
            "cs_object_classification",
            "cs_object_classification_log",
            "cs_object_property_value",
            "cs_classification_checksum"
        ]
        for table_name in classification_tables:
            stmt = """SELECT * FROM {} WHERE {}""".format(
                table_name,
                tools.format_in_condition("ref_object_id", copy_obj_ids)
            )
            rows = sqlapi.RecordSet2(sql=stmt)
            self.assertEqual(0, len(rows))
