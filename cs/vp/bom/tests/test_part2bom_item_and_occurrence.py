# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import constants, sig, ElementsError
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cdb.validationkit import run_with_roles

import cs.vp.bom.tests as common
from cs.vp.bom import (
    AssemblyComponent,
    AssemblyComponentOccurrence,
    ASSEMBLY_DELETE_POST,
)
from cs.vp.items import Item


class TestPart2BomItemAndOccurrenceBehaviour(RollbackTestCase):
    def setUp(self):
        super(TestPart2BomItemAndOccurrenceBehaviour, self).setUp()
        self.assembly_item = common.generateItem()
        self.part_item = common.generateItem()
        self.part_bom_item = common.generateAssemblyComponent(
            self.assembly_item, item=self.part_item
        )
        self.bom_item_occurrence = common.generateAssemblyComponentOccurrence(
            self.part_bom_item
        )

    @run_with_roles(["public", "Engineering"])
    def assert_access_right(
        self,
        access_identifier,
        expected_assembly_item=False,
        expected_part_item=False,
        expected_part_bom_item=False,
        expected_bom_item_occurrence=False,
    ):
        self.assertEqual(
            expected_assembly_item, self.assembly_item.CheckAccess(access_identifier)
        )
        self.assertEqual(
            expected_part_item, self.part_item.CheckAccess(access_identifier)
        )
        self.assertEqual(
            expected_part_bom_item, self.part_bom_item.CheckAccess(access_identifier)
        )
        self.assertEqual(
            expected_bom_item_occurrence,
            self.bom_item_occurrence.CheckAccess(access_identifier),
        )

    def test_access_right_create(self):
        self.assert_access_right(
            "create",
            expected_assembly_item=True,
            expected_part_item=True,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.part_item.ChangeState(200)
        self.assert_access_right(
            "create",
            expected_assembly_item=True,
            expected_part_item=False,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.assembly_item.ChangeState(200)
        self.assert_access_right(
            "create",
            expected_assembly_item=False,
            expected_part_item=False,
            expected_part_bom_item=False,
            expected_bom_item_occurrence=False,
        )

    def test_access_right_delete(self):
        self.assert_access_right(
            "delete",
            expected_assembly_item=True,
            expected_part_item=True,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.part_item.ChangeState(200)
        self.assert_access_right(
            "delete",
            expected_assembly_item=True,
            expected_part_item=False,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.assembly_item.ChangeState(200)
        self.assert_access_right(
            "delete",
            expected_assembly_item=False,
            expected_part_item=False,
            expected_part_bom_item=False,
            expected_bom_item_occurrence=False,
        )

    def test_access_right_save(self):
        self.assert_access_right(
            "save",
            expected_assembly_item=True,
            expected_part_item=True,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.part_item.ChangeState(200)
        self.assert_access_right(
            "save",
            expected_assembly_item=True,
            expected_part_item=False,
            expected_part_bom_item=True,
            expected_bom_item_occurrence=True,
        )
        self.assembly_item.ChangeState(200)
        self.assert_access_right(
            "save",
            expected_assembly_item=False,
            expected_part_item=False,
            expected_part_bom_item=False,
            expected_bom_item_occurrence=False,
        )

    def test_operation_copy_assembly(self):
        copied_assembly_item = operation(
            constants.kOperationCopy, self.assembly_item, teilenummer="#"
        )

        self.assertEqual(1, len(copied_assembly_item.Components))

        copied_part_bom_item = copied_assembly_item.Components[0]
        self.assertNotEqual(
            self.part_bom_item.cdb_object_id,
            copied_part_bom_item.cdb_object_id,
        )
        self.assertEqual(
            self.part_item.cdb_object_id,
            copied_part_bom_item.Item.cdb_object_id,
        )

        self.assertEqual(0, len(copied_part_bom_item.Occurrences))

    def test_operation_index_assembly(self):
        indexed_assembly_item = operation(constants.kOperationIndex, self.assembly_item)

        self.assertEqual(1, len(indexed_assembly_item.Components))

        copied_part_bom_item = indexed_assembly_item.Components[0]
        self.assertNotEqual(
            self.part_bom_item.cdb_object_id,
            copied_part_bom_item.cdb_object_id,
        )
        self.assertEqual(
            self.part_item.cdb_object_id,
            copied_part_bom_item.Item.cdb_object_id,
        )

        self.assertEqual(0, len(copied_part_bom_item.Occurrences))

    def test_operation_delete_assembly(self):

        call_count = 0

        @sig.connect(ASSEMBLY_DELETE_POST)
        def signal_ASSEMBLY_DELETE_POST(bom_item_cdb_object_ids, ctx):
            nonlocal call_count
            call_count += 1

            self.assertListEqual(
                [self.part_bom_item.cdb_object_id], bom_item_cdb_object_ids
            )
            self.assertIsNotNone(ctx)

        try:
            assembly_item_keys = self.assembly_item.GetRecord().keydict()
            part_item_keys = self.part_item.GetRecord().keydict()
            part_bom_item_keys = self.part_bom_item.GetRecord().keydict()
            bom_item_occurrence_keys = self.bom_item_occurrence.GetRecord().keydict()
            count_before_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())

            operation(constants.kOperationDelete, self.assembly_item)

            self.assertEqual(1, call_count)
            count_after_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())
            self.assertEqual(
                1, count_before_bom_item_occurrences - count_after_bom_item_occurrences
            )

            self.assertIsNone(Item.ByKeys(**assembly_item_keys))
            self.assertIsNotNone(Item.ByKeys(**part_item_keys))
            self.assertIsNone(AssemblyComponent.ByKeys(**part_bom_item_keys))
            self.assertIsNone(
                AssemblyComponentOccurrence.ByKeys(**bom_item_occurrence_keys)
            )
        finally:
            sig.disconnect(signal_ASSEMBLY_DELETE_POST)

    def test_operation_delete_part(self):
        call_count = 0

        @sig.connect(ASSEMBLY_DELETE_POST)
        def signal_ASSEMBLY_DELETE_POST(_, __):
            nonlocal call_count
            call_count += 1

        try:
            part_item_keys = self.part_item.GetRecord().keydict()
            part_bom_item_keys = self.part_bom_item.GetRecord().keydict()
            bom_item_occurrence_keys = self.bom_item_occurrence.GetRecord().keydict()
            count_before_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())


            operation(constants.kOperationDelete, self.part_bom_item)
            operation(constants.kOperationDelete, self.part_item)

            self.assertEqual(0, call_count)
            count_after_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())
            self.assertEqual(
                1, count_before_bom_item_occurrences - count_after_bom_item_occurrences
            )

            self.assertIsNone(Item.ByKeys(**part_item_keys))
            self.assertIsNone(AssemblyComponent.ByKeys(**part_bom_item_keys))
            self.assertIsNone(
                AssemblyComponentOccurrence.ByKeys(**bom_item_occurrence_keys)
            )
        finally:
            sig.disconnect(signal_ASSEMBLY_DELETE_POST)

    def test_operation_delete_part_referenced(self):
        with self.assertRaises(ElementsError):
            operation(constants.kOperationDelete, self.part_item)

    def test_operation_copy_bom_item(self):
        copied_part_bom_item = operation(constants.kOperationCopy, self.part_bom_item)

        self.assertNotEqual(
            self.part_bom_item.cdb_object_id,
            copied_part_bom_item.cdb_object_id,
        )
        self.assertEqual(
            self.part_item.cdb_object_id,
            copied_part_bom_item.Item.cdb_object_id,
        )

        self.assertEqual(1, len(copied_part_bom_item.Occurrences))
        self.assertNotEqual(
            self.bom_item_occurrence.cdb_object_id,
            copied_part_bom_item.Occurrences[0].cdb_object_id,
        )

    def test_operation_delete_bom_item(self):
        part_bom_item_keys = self.part_bom_item.GetRecord().keydict()
        bom_item_occurrence_keys = self.bom_item_occurrence.GetRecord().keydict()
        count_before_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())

        operation(constants.kOperationDelete, self.part_bom_item)

        count_after_bom_item_occurrences = len(AssemblyComponentOccurrence.Query())
        self.assertEqual(
            1, count_before_bom_item_occurrences - count_after_bom_item_occurrences
        )

        self.assertIsNone(AssemblyComponent.ByKeys(**part_bom_item_keys))
        self.assertIsNone(
            AssemblyComponentOccurrence.ByKeys(**bom_item_occurrence_keys)
        )
