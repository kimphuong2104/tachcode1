#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import os
import time
from datetime import datetime, timedelta

from cdb.testcase import RollbackTestCase, error_logging_disabled

from cs.documents import Document
from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent

from cs.vp.bomcreator.bom import UserHintList, GeneratedBOM
from cs.vp.bomcreator.bomreader import BOMContext
from cs.vp.bomcreator.factory import Factory
from cs.vp.bomcreator.web.rest.bommodel import BOMModel
from cs.vp.bomcreator.web.rest.bomtreemodel import BOMTreeModel
from cs.vp.bomcreator.web.rest.savebomsmodel import SaveBOMsModel

ITEM_CATEGORY = "Baukasten"



class Test_RESTAPI(RollbackTestCase):
    PREFIX = "RAPI"

    def setUp(self):
        RollbackTestCase.setUp(self)
        with error_logging_disabled():
            self.item = Item.Create(teilenummer=self.PREFIX + "001", t_index="")
            self.existing_article_teilenummer = self.item.teilenummer

            self.part = Item.Create(teilenummer=self.PREFIX + "002", t_index="")
            self.part_teilenummer = self.part.teilenummer
            self.part2 = Item.Create(teilenummer=self.PREFIX + "003", t_index="")
            self.part2_teilenummer = self.part.teilenummer

            self.doc = Document.Create(z_nummer=self.PREFIX + "001", z_index="",
                                       teilenummer=self.item.teilenummer,
                                       t_index=self.item.t_index)
            self.userHints = UserHintList()
            context = BOMContext(self.doc.cdb_object_id,
                                 self.item.teilenummer, self.item.t_index,
                                 cadsource="", global_user_hints=self.userHints)
            self.factory = Factory(context)
            self.bom = self.factory.create_BOM_for_assembly(self.item)

    def tearDown(self):
        RollbackTestCase.tearDown(self)

    def test_create_bom_tree(self):
        # GIVEN: a structure of BOMs
        self.bom.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index)
        partBom = self.factory.create_BOM_for_assembly(self.part)
        partBom.create_and_add_entry(teilenummer=self.part2.teilenummer, t_index=self.part2.t_index)
        partBom2 = self.factory.create_BOM_for_assembly(self.part2)
        for b in [partBom, self.bom, partBom2]:
            b.synchronize()

        # WHEN: I create a tree REST model
        model = BOMTreeModel(self.doc.cdb_object_id)
        tree = model._create_tree([partBom, self.bom, partBom2])  # pylint: disable=protected-access

        # THEN: the tree structure is as expected
        self.assertEqual([{'id': self.bom.instance_id,
                           'children': [{'id': partBom.instance_id,
                                         'children': [{'id': partBom2.instance_id,
                                                       'children': []}],
                                         }]}],
                         tree)
        self.assertEqual(len(model._global_errors), 0)  # pylint: disable=protected-access

    def test_recursive_tree_error(self):
        # GIVEN: an illegal structure of BOMs with recursion
        self.bom.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index)
        partBom = self.factory.create_BOM_for_assembly(self.part)
        partBom.create_and_add_entry(teilenummer=self.item.teilenummer, t_index=self.item.t_index)
        # AND: the boms have an instance id
        partBom.synchronize()
        self.bom.synchronize()

        # WHEN: I create a tree REST model
        model = BOMTreeModel(self.doc.cdb_object_id)
        tree = model._create_tree([partBom, self.bom])  # pylint: disable=protected-access

        # THEN: the tree structure is empty and there is an error
        assert tree is None
        self.assertEqual(len(model._global_errors), 1)  # pylint: disable=protected-access

    def test_create_rows(self):
        # GIVEN: a structure of BOMs
        self.bom.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index)
        self.bom.user_hints.append("warning!")
        partBom = self.factory.create_BOM_for_assembly(self.part)
        partBom.create_and_add_entry(teilenummer=self.part2.teilenummer, t_index=self.part2.t_index)
        partBom.user_hints.append_error("error!")
        partBom2 = self.factory.create_BOM_for_assembly(self.part2)
        partBom2.is_writeable = False

        # WHEN: I create the rows of the REST model
        model = BOMTreeModel(self.doc.cdb_object_id)
        for b in [partBom, self.bom, partBom2]:
            b.synchronize()
        rows = model._create_rows([partBom, self.bom, partBom2])  # pylint: disable=protected-access

        # THEN: the rows are returned as expected
        rows.sort(key=lambda r: r['columns'][1])  # the real order is determined by the tree
        self.assertEqual([{'is_writable': True, 'is_changed': True, 'user_hints': [('warning!', 'warning')],
                           'columns': [True, u'RAPI001/  () ', False, False, [False, True], 1],
                           'id': self.bom.instance_id, 'assembly_is_temporary': False},
                          {'is_writable': True, 'is_changed': True, 'user_hints': [('error!', 'error')],
                           'columns': [False, u'RAPI002/  () ', False, False, [True, False], 1],
                           'id': partBom.instance_id, 'assembly_is_temporary': False},
                          {'is_writable': True, 'is_changed': False, 'user_hints': [],
                           'columns': [False, u'RAPI003/  () ', False, False, [False, False], 0],
                           'id': partBom2.instance_id, 'assembly_is_temporary': False}],
                         rows)

    def test_garbage_collect_old_tempfiles(self):
        # GIVEN: two files matching the pattern, one of them old enough to be GC'ed
        #        one file not matching the pattern
        pattern = GeneratedBOM.tempfile_pattern()
        file1 = pattern.replace("*", "test1")
        file2 = pattern.replace("*", "test2")
        not_matching = os.path.join(os.path.dirname(file1), "test_garbage_collect_old_tempfiles.json")
        for p in [file1, file2, not_matching]:
            with open(p, "w") as f:
                f.writelines(["content"])
        dt = datetime.now() - timedelta(days=7)
        dt_epoch = time.mktime(dt.timetuple())
        os.utime(file1, (dt_epoch, dt_epoch))

        # WHEN: I GC the files
        model = BOMTreeModel(self.doc.cdb_object_id)
        model._garbage_collect_old_tempfiles()  # pylint: disable=protected-access

        # THEN: only the older matching file is gone
        assert not os.path.exists(file1)
        assert os.path.exists(file2)
        assert os.path.exists(not_matching)

    def test_read_single_bom(self):
        # GIVEN: a structure of BOMs
        self.bom.create_and_add_entry(teilenummer=self.part.teilenummer, t_index=self.part.t_index)
        partBom = self.factory.create_BOM_for_assembly(self.part)
        partBom.create_and_add_entry(teilenummer=self.part2.teilenummer, t_index=self.part2.t_index)
        partBom2 = self.factory.create_BOM_for_assembly(self.part2)
        for b in [partBom, self.bom, partBom2]:
            b.synchronize()

        # WHEN: I create a BOM REST model for partBom
        model = BOMModel(partBom.instance_id)
        result = model.create_result(request=None)

        # THEN: the BOM info is as expected
        assert "columns" in result
        assert "rows" in result
        assert len(result["rows"]) == 1

    def test_cancel(self):
        # GIVEN: a temporary item with a bom
        partBom = self.factory.create_assembly_and_BOM(t_kategorie=ITEM_CATEGORY)
        partBom.synchronize()
        teilenummer = partBom.get_assembly().teilenummer
        t_index = partBom.get_assembly().t_index

        # WHEN: I cancel the BOM
        model = SaveBOMsModel()
        model.cancel({partBom.instance_id: {"itemIsModified": False, "selected": True, "changedValues": []}})

        #THEN: the BOM's JSON file and the temporary item are deleted
        assert not os.path.exists(partBom._temporary_json_path(partBom.instance_id))  # pylint: disable=protected-access
        item = Item.ByKeys(teilenummer=teilenummer, t_index=t_index)
        assert item is None

    def test_save(self):
        # GIVEN: a temporary item with a bom with a position
        partBom = self.factory.create_assembly_and_BOM(t_kategorie=ITEM_CATEGORY)
        partBom.create_and_add_entry(teilenummer=self.part2.teilenummer, t_index=self.part2.t_index)
        partBom.synchronize()
        teilenummer = partBom.get_assembly().teilenummer
        t_index = partBom.get_assembly().t_index

        # WHEN: I save the BOM
        model = SaveBOMsModel()
        model.save({partBom.instance_id: {"itemIsModified": False, "selected": True, "changedValues": []}})

        # THEN: the BOM's JSON file is deleted
        assert not os.path.exists(partBom._temporary_json_path(partBom.instance_id))  # pylint: disable=protected-access
        # AND: the BOM was actually saved
        components = AssemblyComponent.KeywordQuery(baugruppe=teilenummer, b_index=t_index)
        assert len(components) == 1


# Guard importing as main module
if __name__ == "__main__":
    import nose
    import sys
    nose.runmodule(argv=sys.argv)
