# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from datetime import datetime, timedelta
import logging

from cdb import cdbuuid, sqlapi
from cs.classification import api, solr, tools, ObjectClassificationLog
from cs.classification.scripts.solr_resync import reindex_objects

from cs.classification.tests import utils

LOG = logging.getLogger(__name__)


class TestIndex(utils.ClassificationTestCase):

    def test_log(self):
        doc = self.create_document("Test Index")

        mdate, idate = ObjectClassificationLog.get_dates(doc.cdb_object_id)
        self.assertIsNone(mdate)
        self.assertIsNone(idate)

        classification_data = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
        api.update_classification(doc, classification_data, update_index=False)

        mdate, idate = ObjectClassificationLog.get_dates(doc.cdb_object_id)
        self.assertIsNotNone(mdate)
        self.assertLess(mdate, datetime.utcnow())
        self.assertIsNone(idate)

        classification_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "Test Text"
        api.update_classification(doc, classification_data)

        mdate, idate = ObjectClassificationLog.get_dates(doc.cdb_object_id)
        self.assertIsNotNone(mdate)
        self.assertIsNotNone(idate)
        self.assertLessEqual(mdate, idate)

        idate = datetime.utcnow().replace(microsecond=0)
        ObjectClassificationLog.update_log(doc.cdb_object_id, cdb_index_date=idate)
        mdate_2, idate_2 = ObjectClassificationLog.get_dates(doc.cdb_object_id)
        self.assertEqual(mdate, mdate_2)
        self.assertEqual(idate, idate_2)

    def test_ref_object_ids_for_reindex(self):
        doc = self.create_document("Test Index")
        classification_data = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
        self.set_property_values(classification_data["properties"])
        api.update_classification(doc, classification_data)
        doc_log = ObjectClassificationLog.ByKeys(ref_object_id=doc.cdb_object_id)

        # mdate and index_date set => no reindex needed
        self.assertNotIn(doc.cdb_object_id, ObjectClassificationLog.get_ref_object_ids_for_reindex())

        # mdate later than index_date set => reindex needed
        doc_log.cdb_index_date = doc_log.cdb_index_date - timedelta(hours = 1)
        self.assertIn(doc.cdb_object_id, ObjectClassificationLog.get_ref_object_ids_for_reindex())

        # no mdate but index_date set => no reindex needed
        doc_log.cdb_mdate = None
        self.assertNotIn(doc.cdb_object_id, ObjectClassificationLog.get_ref_object_ids_for_reindex())

        # no mdate and no index_date set => reindex needed
        doc_log.cdb_index_date = None
        self.assertIn(doc.cdb_object_id, ObjectClassificationLog.get_ref_object_ids_for_reindex())

    def test_ref_object_ids_for_reindex_with_modified_from_date(self):
        doc = self.create_document("Test Index")
        classification_data = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
        self.set_property_values(classification_data["properties"])
        api.update_classification(doc, classification_data)
        doc_log = ObjectClassificationLog.ByKeys(ref_object_id=doc.cdb_object_id)

        # mdate and modified_from identical => reindex needed
        modified_from = doc_log.cdb_mdate
        self.assertIn(
            doc.cdb_object_id,
            ObjectClassificationLog.get_ref_object_ids_for_reindex(modified_from=modified_from)
        )

        # mdate later than modified_from  => reindex needed
        modified_from = doc_log.cdb_mdate - timedelta(hours=1)
        self.assertIn(
            doc.cdb_object_id,
            ObjectClassificationLog.get_ref_object_ids_for_reindex(modified_from=modified_from)
        )

        # mdate earlier than modified_from  => no reindex needed
        modified_from = doc_log.cdb_mdate + timedelta(hours = 1)
        self.assertNotIn(
            doc.cdb_object_id,
            ObjectClassificationLog.get_ref_object_ids_for_reindex(modified_from=modified_from)
        )

        # no mdate set  => no reindex needed
        modified_from = doc_log.cdb_mdate
        doc_log.cdb_mdate = None
        self.assertNotIn(
            doc.cdb_object_id,
            ObjectClassificationLog.get_ref_object_ids_for_reindex(modified_from=modified_from)
        )

    def test_reindex(self):
        start = datetime.utcnow()
        doc_ids = []
        for count in range(solr.SOLR_CHUNK_SIZE + 1):
            doc = self.create_document("Test Reindex {}".format(count))
            doc_ids.append(doc.cdb_object_id)
            classification_data = api.get_new_classification(["TEST_CLASS_ALL_PROPERTY_TYPES"])
            self.set_property_values(classification_data["properties"])
            api.update_classification(doc, classification_data, update_index=False)
        self.assertTrue(set(doc_ids).issubset(set(ObjectClassificationLog.get_ref_object_ids_for_reindex())))
        reindex_objects(LOG.info)
        self.assertListEqual([], ObjectClassificationLog.get_ref_object_ids_for_reindex())
        stmt = """SELECT * from cs_object_classification_log WHERE {}""".format(
            tools.format_in_condition("ref_object_id", doc_ids)
        )
        for log_item in sqlapi.RecordSet2(sql=stmt):
            self.assertLessEqual(start, log_item.cdb_index_date)

    def test_log_inserts(self):
        ref_obj_ids = []
        for _ in range(tools.INSERT_ROW_MAX +1):
            ref_obj_ids.append(cdbuuid.create_uuid())
        index_date = datetime.utcnow().replace(microsecond=0)
        ObjectClassificationLog.update_logs(ref_obj_ids, index_date)
        classification_logs = ObjectClassificationLog.Query(
            ObjectClassificationLog.ref_object_id.one_of(*ref_obj_ids)
        )
        self.assertEqual(len(ref_obj_ids), len(classification_logs))
        for classification_log in classification_logs:
            self.assertIn(classification_log.ref_object_id, ref_obj_ids)
            self.assertEqual(index_date, classification_log.cdb_index_date)
