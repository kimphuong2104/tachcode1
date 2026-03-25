# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the bomqueries
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

from cdb import dberrors
from cdb.testcase import RollbackTestCase

from cs.vp import items
from cs.vp.bom import bomqueries
from cs.vp.bom.bomqueries import flat_bom
from cs.vp.bom.tests import generateItem, generateAssemblyComponent


class TestBomQueries(RollbackTestCase):

    def setUp(self):
        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        super(TestBomQueries, self).setUp()

        self.item = items.Item.ByKeys(teilenummer="9502659", t_index="")

    def raise_recursive_db_err_oracle(self, item):
        raise dberrors.DBError("error message", -32044, "stmt")

    def raise_recursive_db_err_mssql(self, item):
        raise dberrors.DBError("error message", 530, "stmt")

    def test_cyclic(self):
        root = generateItem(benennung="root")
        child = generateItem(benennung="child")
        generateAssemblyComponent(root, child)
        grand_child = generateItem(benennung="grand_child")
        generateAssemblyComponent(child, grand_child)
        generateAssemblyComponent(grand_child, root)

        expected_bom_items = set([
            (root.teilenummer, root.t_index, child.teilenummer, child.t_index),
            (child.teilenummer, child.t_index, grand_child.teilenummer, grand_child.t_index),
            (grand_child.teilenummer, grand_child.t_index, root.teilenummer, root.t_index)
        ])
        bom_items = flat_bom(root)
        self.assertEqual(len(expected_bom_items), len(bom_items))
        for bom_item in bom_items:
            self.assertIn(
                (bom_item.baugruppe, bom_item.b_index, bom_item.teilenummer, bom_item.t_index),
                expected_bom_items
            )

    def test_flat_bom(self):
        "The flat_bom method returns the correct result for a given part"

        result_dict = bomqueries.flat_bom_dict(self.item)
        parts = result_dict[('9502659', '')]

        result = []
        for item in parts:
            result.append(item['teilenummer'])

        expected = [
            ('9502664'),
            ('9502665'),
            ('9502666'),
            ]

        assert len(result) == len(expected), "Got %s results but expected %s" % (len(result), len(expected))
        for expected_tuple in expected:
            assert expected_tuple in result, "%s is not in the result %s" % (expected_tuple, result)

    def test_double_children(self):

        def check_count(parent, child, count):
            found = 0
            for bom_pos in flat_bom:
                if (
                    parent.teilenummer == bom_pos.baugruppe and parent.t_index == bom_pos.b_index and
                    child.teilenummer == bom_pos.teilenummer and child.t_index == bom_pos.t_index
                ):
                    found += 1
            self.assertEqual(count, found)

        root = generateItem(benennung="root")
        child = generateItem(benennung="child")
        generateAssemblyComponent(root, child)
        generateAssemblyComponent(root, child)
        child_assembly = generateItem(benennung="child_assembly")
        grand_child = generateItem(benennung="grand_child")
        generateAssemblyComponent(child_assembly, grand_child)
        generateAssemblyComponent(root, child_assembly)
        generateAssemblyComponent(root, child_assembly)

        flat_bom = bomqueries.flat_bom(root)

        check_count(root, child, 2)
        check_count(root, child_assembly, 2)
        check_count(child_assembly, grand_child, 1)

    def test_bom_item_record_dict(self):
        root = generateItem(benennung="root")
        child = generateItem(benennung="child")
        grand_child = generateItem(benennung="grand_child")

        bom_item_1 = generateAssemblyComponent(root, child)
        bom_item_2 = generateAssemblyComponent(child, grand_child)

        expected_records = bomqueries.bom_item_records(
            bom_item_1.cdb_object_id,
            bom_item_2.cdb_object_id
        )
        # Note: The expected_records are returned in arbitrary order, hence we sort them manually
        expected_records = sorted(expected_records, key=lambda rec: rec["teilenummer"])

        bom_item_record_dict = bomqueries.bom_item_record_dict(
            bom_item_1.cdb_object_id,
            bom_item_2.cdb_object_id
        )
        self.assertEqual(2, len(bom_item_record_dict))
        self.assertEqual(expected_records[0], bom_item_record_dict[bom_item_1.cdb_object_id])
        self.assertEqual(expected_records[1], bom_item_record_dict[bom_item_2.cdb_object_id])
