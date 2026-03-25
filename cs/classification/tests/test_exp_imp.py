# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import io
import os
from cdb import CADDOK
from cdb import sqlapi
from cdb import cdbuuid
from cs.classification.scripts import export_tool
from cs.classification.scripts import import_tool
from cs.classification.tests import utils
from cdb.comparch.content import ModuleContentItem
from cdb.comparch.tools import tojsonfile
from cdb.testcase import require_service


class TestExpImp(utils.ClassificationTestCase):

    checked_tables = ['cs_classification_class',
                      'cs_classification_applicabilit',
                      'cs_class_property_group',
                      'cs_property_group_assign',
                      'cs_class_property',
                      'cs_property',
                      'cs_unit',
                      'cs_classification_ref_appl',
                      'cs_block_prop_assign',
                      'cs_property_value',
                      'cs_classification_computation']

    tables_with_del = ['cs_class_property_group',
                       'cs_property_group_assign']

    # Note: 'cs_property_folder_assignment' and 'cs_property_folder' intentionally not listed because
    # cs.classificationtests doesn't contain data for these tables

    @classmethod
    def setUpClass(cls):
        super(TestExpImp, cls).setUpClass()
        require_service("cdb.uberserver.services.index.IndexService")

    def setUp(self):
        super(TestExpImp, self).setUp()

    def assert_all_types_exported(self, json_export_data, list_of_tables):
        for table in list_of_tables:
            self.assertIn(table, json_export_data, "Data of table %s is missing in json export" % table)

    def assert_rec_exists(self, rec):
        records = sqlapi.RecordSet2(rec.thead.tname, rec.sqlkey())
        self.assertEqual(len(records), 1, "Record not imported into DB: %s" % rec)

    def assert_modification_applied(self, rec):
        persistent_rec = sqlapi.RecordSet2(rec.thead.tname, rec.sqlkey())[0]
        self.assertNotEqual(persistent_rec["name_de"], "CHANGED BY UNIT TEST",
                            "Record not updated in DB: %s" % rec)

    def _create_db_diffs(self, json_export_data):
        # delete something (first element of each type)
        deleted = []
        for item_type, data_dict in json_export_data.items():
            content = data_dict["CONTENT"]
            item_dict = content[0]
            mc_item = ModuleContentItem(item_type, item_dict, import_tool.ModuleContentDummy())
            content_item = import_tool.ContentItem(mc_item)
            rec = content_item.mc_item._getPersistentRecord()
            rec.delete()
            deleted.append(rec)

        # modify something
        modified = []
        for item_type, data_dict in json_export_data.items():
            content = data_dict["CONTENT"]
            if len(content) >= 2:
                item_dict = content[1]
                mc_item = ModuleContentItem(item_type, item_dict, import_tool.ModuleContentDummy())
                content_item = import_tool.ContentItem(mc_item)
                attrs = content_item.mc_item.getAttrs()
                if "name_de" in attrs:
                    rec = content_item.mc_item._getPersistentRecord()
                    rec.update(name_de="CHANGED BY UNIT TEST")
                    modified.append(rec)

        return deleted, modified

    def test_exp_imp_all(self):
        # export all classes with export_tool
        exporter = export_tool.run(CADDOK.TMPDIR)

        # load json export for checks and further use
        with io.open(exporter.exp_filename, 'rb') as export_file:
            json_export_data = json.load(export_file)

        self.assert_all_types_exported(json_export_data, TestExpImp.checked_tables)

        # create some db modifications to check successfull import later
        deleted, modified = self._create_db_diffs(json_export_data)

        # reimport data. Previously applied modifications should be reverted.
        import_tool.run(exporter.exp_dir)

        # Check whether previously applied modifications have been reverted in db
        for deleted_rec in deleted:
            self.assert_rec_exists(deleted_rec)
        for modified_rec in modified:
            self.assert_modification_applied(modified_rec)

    def test_no_critical_deletes(self):
        exporter = export_tool.run(CADDOK.TMPDIR)
        with io.open(exporter.exp_filename, 'rb') as export_file:
            json_export_data = json.load(export_file)

        # Run Import with json file containing classes only
        # and check whether allowed data is deleted from db only.
        new_json_data = dict(json_export_data)
        for k in list(new_json_data):
            if k != "cs_classification_class":
                del new_json_data[k]
        fname = os.path.join(CADDOK.TMPDIR, "test_exp_imp_all_%s.json" % cdbuuid.create_uuid())
        tojsonfile(fname, new_json_data)
        imp = import_tool.Importer(exporter.exp_dir)
        imp.exp_filename = fname  # patch the json file to import
        imp.run()

        exporter = export_tool.run(CADDOK.TMPDIR)
        with io.open(exporter.exp_filename, 'rb') as export_file:
            json_export_data = json.load(export_file)
        self.assert_all_types_exported(json_export_data,
                                       set(TestExpImp.checked_tables) - set(TestExpImp.tables_with_del))
