
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/import unittest

import unittest

from cdb import testcase
from cdb.testcase import RollbackTestCase

from cs.classification import api, ClassificationConstants, tools
from cs.classification.table_columns import ClassificationPropertiesProvider
from cs.documents import Document

class TestTableColumns(RollbackTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestTableColumns, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    def setUp(self):
        super(TestTableColumns, self).setUp()
        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.empty_addtl_props = {
            ClassificationConstants.METADATA: {},
            ClassificationConstants.PROPERTIES: {}
        }
        self.empty_classification = {
            ClassificationConstants.ASSIGNED_CLASSES: [],
            ClassificationConstants.PROPERTIES: {}
        }
        api.update_classification(self.document, self.empty_classification)


    def test_table_columns(self):

        with testcase.error_logging_disabled():
            assigned_classes = ["TEST_CLASS_SEARCH_RESULT"]
            classification_data = api.get_new_classification(assigned_classes)
            query_args = {
                'cdb::argument.classification_web_ctrl': tools.preset_mask_data(classification_data)
            }

            classification_data["properties"]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_ENUM_LABELS"][0][
                "value"] = "BT"
            classification_data["properties"]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_BLOCK_ENUM_LABELS"][0][
                "value"]["child_props"]["TEST_PROP_ENUM_LABELS"][0]["value"] = "LT"
            classification_data["properties"]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_IDENTIFYING_OBJ_REF"][0][
                "value"] = self.document.cdb_object_id
            classification_data["properties"]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_OBJREF_BLOCK"][0][
                "value"]["child_props"]["TEST_PROP_ENUM_LABELS"][0]["value"] = "BT"
            classification_data["properties"]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_OBJREF_BLOCK"][0][
                "value"]["child_props"]["TEST_PROP_IDENTIFYING_OBJ_REF"][0][
                "value"] = self.document.cdb_object_id

            api.update_classification(self.document, classification_data)

            column_definitions = ClassificationPropertiesProvider.getColumnDefinitions("document", query_args)
            table_data = [{
                'cdb_object_id': self.document.cdb_object_id
            }]
            column_data = ClassificationPropertiesProvider.getColumnData("document", table_data)
            self.assertEqual(
                "Betriebstemperatur (BT)",
                column_data[0]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_ENUM_LABELS"]
            )
            self.assertEqual(
                "Lagertemperatur (LT)",
                column_data[0]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_BLOCK_ENUM_LABELS"]
            )
            self.assertEqual(
                self.document.cdb_object_id,
                column_data[0]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_IDENTIFYING_OBJ_REF"]
            )
            self.assertEqual(
                "Betriebstemperatur (BT) - " + self.document.GetDescription(),
                column_data[0]["TEST_CLASS_SEARCH_RESULT_TEST_PROP_OBJREF_BLOCK"]
            )



# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
