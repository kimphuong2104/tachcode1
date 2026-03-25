#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import json

import unittest

from cdb.objects import OBJECT_STORE
from cdb.objects.operations import system_args
from cdb.sig import connect
from cdb.testcase import RollbackTestCase, error_logging_disabled

from cs.documents import Document
from cs.vp.items import Item

from cs.vp.bomcreator.bom import value_is_equal, UserHintList, GeneratedBOM, ReplaceDatetimeDecoder, ReplaceDatetimeEncoder
from cs.vp.bomcreator.bomreader import BOMContext, delete_unused_new_articles
from cs.vp.bomcreator.factory import Factory


#
#  NOTE: most tests use concrete BOM readers and are therefor not here, but in the package cs.workspaces
#

ITEM_CATEGORY = "Baukasten"


class Test_ArticleCreation(RollbackTestCase):
    """
    Tests concerned with the management of new articles that are created
    by BOMReaders.
    Tests the function delete_unused_new_articles (module bom_reader).
    """
    PREFIX = "TACR"

    def setUp(self):
        RollbackTestCase.setUp(self)
        with error_logging_disabled():
            self.item = Item.Create(teilenummer=self.PREFIX + "001", t_index="")
            self.existing_article_teilenummer = self.item.teilenummer

            self.part = Item.Create(teilenummer=self.PREFIX + "002", t_index="")
            self.part_teilenummer = self.part.teilenummer

            self.doc = Document.Create(z_nummer=self.PREFIX + "001", z_index="",
                                       teilenummer=self.item.teilenummer,
                                       t_index=self.item.t_index)
            self.userHints = UserHintList()
            context = BOMContext(self.doc.cdb_object_id,
                                 self.item.teilenummer, self.item.t_index,
                                 cadsource="", global_user_hints=self.userHints)
            self.factory = Factory(context)
            self.bom = self.factory.create_assembly_and_BOM(t_kategorie=ITEM_CATEGORY)
            self.bom = rebirth_bom(self.bom)
            self.new_article_teilenummer = self.bom.get_assembly().teilenummer

    def tearDown(self):
        RollbackTestCase.tearDown(self)

    def new_article_exists(self):
        return self.article_exists(self.new_article_teilenummer)

    def article_exists(self, teilenummer):
        OBJECT_STORE.clear()
        item = Item.ByKeys(teilenummer=teilenummer, t_index="")
        return item is not None

    def test_unusedNewArticle_isDeleted(self):
        delete_unused_new_articles([self.bom])
        assert not self.new_article_exists()

    def test_newArticleWithWrittenBOM_isNotDeleted(self):
        self.bom.write(self.userHints)
        delete_unused_new_articles([self.bom])
        assert self.new_article_exists()

    def test_newArticleThatIsUsedInWrittenBom_isNotDeleted(self):
        bom2 = self.factory.create_BOM()
        bom2.create_and_add_entry(teilenummer=self.new_article_teilenummer)
        bom2.synchronize()

        bom2.write(self.userHints)
        delete_unused_new_articles([self.bom, bom2])
        assert self.new_article_exists()

    def test_newArticleThatIsUsedInUnwrittenBom_isDeleted(self):
        bom2 = self.factory.create_BOM()
        bom2.create_and_add_entry(teilenummer=self.new_article_teilenummer)
        delete_unused_new_articles([self.bom, bom2])
        assert not self.new_article_exists()

    def test_newArticleThatIsModified_isNotDeleted(self):
        self.bom.mark_assembly_as_modified()
        delete_unused_new_articles([self.bom])
        assert self.new_article_exists()

    def test_existingArticle_isNotDeleted(self):
        bom2 = self.factory.create_BOM()
        delete_unused_new_articles([bom2])
        assert self.article_exists(self.existing_article_teilenummer)

    def test_create_item_with_system_args(self):
        result = {"success": False}

        @connect(Item, "create", "pre")
        def tester(item, ctx):
            result["success"] = ctx.get_active_integration() == "testing"

        self.factory.create_assembly_and_BOM(system_args(active_integration="testing"), t_kategorie=ITEM_CATEGORY)
        assert result["success"]

    def test_create_position_to_missing_item(self):
        # tests that there is no crash when trying to create a position referencing a non-existing item
        bom2 = self.factory.create_BOM()
        bom2.create_and_add_entry(teilenummer="cs.bomcreator-missing_teilenummer")
        bom2.synchronize()

    def test_create_position_to_assembly(self):
        # GIVEN: a BOM with an assembly item
        bom2 = self.factory.create_BOM()
        # WHEN: I add the assembly item as a component
        bom2.create_and_add_entry(teilenummer=self.existing_article_teilenummer)
        # THEN: the entry is ignored
        assert not bom2.entries()


class Test_value_is_equal(unittest.TestCase):
    def test_exact_equal(self):
        assert value_is_equal(0.0, 0.0)
        assert value_is_equal(-1.0, -1.0)
        assert value_is_equal(1.0, 1.0)
        assert value_is_equal(11.0, 11.0)
        assert value_is_equal(72.0, 72.0)
        assert value_is_equal(1.0e-20, 1.0e-20)
        assert value_is_equal(1.0e20, 1.0e20)

    def test_small_diff_equal(self):
        assert value_is_equal(1.12345678912, 1.12345678911)
        assert value_is_equal(1.123456789e-20, 1.123456788e-20)
        assert value_is_equal(1.12345678912e20, 1.12345678911e20)
        assert value_is_equal(-1.12345678912, -1.12345678911)
        assert value_is_equal(-1.123456789e-20, -1.123456788e-20)
        assert value_is_equal(-1.12345678912e20, -1.12345678911e20)

    def test_small_diff_unequal(self):
        assert not value_is_equal(1.1234567891, 1.1234567892)
        assert not value_is_equal(1.12345678e-20, 1.12345677e-20)
        assert not value_is_equal(1.1234567891e20, 1.1234567892e20)
        assert not value_is_equal(-1.1234567891, -1.1234567892)
        assert not value_is_equal(-1.12345678e-20, -1.12345677e-20)
        assert not value_is_equal(-1.1234567891e20, -1.1234567892e20)
        assert not value_is_equal(1.23456e-70, 1.23457e-70)

    def test_big_diff_unequal(self):
        assert not value_is_equal(1.0, 10.0)
        assert not value_is_equal(1.0, 100.0)
        assert not value_is_equal(10.0, 1.0)
        assert not value_is_equal(2.0, 20.0)
        assert not value_is_equal(0.0, 1.0)
        assert not value_is_equal(1.0, 2.0)
        assert not value_is_equal(1.23456789012e-20, 1.23456789012)
        assert not value_is_equal(1.23456789012e-20, 1.23456789012e20)
        assert not value_is_equal(0.0, -1.0)
        assert not value_is_equal(-1.0, -2.0)
        assert not value_is_equal(0.0, 1.0)
        assert not value_is_equal(-1.0, 0.0)
        assert not value_is_equal(2e-40, 3e-40)

    def test_diff_sign_unequal(self):
        assert not value_is_equal(-1.12345678912, 1.12345678911)
        assert not value_is_equal(1.123456789e-20, -1.123456788e-20)
        assert not value_is_equal(-1.12345678912e20, 1.12345678911e20)

    def test_non_float(self):
        assert value_is_equal("foo", "foo")
        assert not value_is_equal("foo", "bar")
        assert value_is_equal(42, 42)
        assert not value_is_equal(1, 2)


def rebirth_bom(bom, FactoryClass=None):
    js = json.dumps(bom.to_json(), cls=ReplaceDatetimeEncoder)
    bom2 = GeneratedBOM.from_json(json.loads(js, cls=ReplaceDatetimeDecoder), FactoryClass)
    return bom2


# Guard importing as main module
if __name__ == "__main__":
    import nose
    import sys
    nose.runmodule(argv=sys.argv)
