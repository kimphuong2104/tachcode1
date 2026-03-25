# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
This module tests the functionality specific to the "Replace by Copy" operation for the BOM Item.

Due to the implementation of the cdb_copy_and_replace_bom_item operation, the backend never touches the
initiating operation. So we only need to test the AssemblyComponent 'Copy' operation with a passed
bom_item_to_replace parameter.
"""
from cdb import constants, ElementsError
from cdb.objects.operations import operation, system_args
from cdb.testcase import RollbackTestCase

from cs.vp.items import Part
from cs.vp.bom.tests import generateItem, generateAssemblyComponent
from cs.vp.bom import AssemblyComponent


class TestCopyAndReplaceBomItem(RollbackTestCase):

    @staticmethod
    def _find_copied_parts():
        return Part.KeywordQuery(benennung="after_copy")

    def assert_exception_for_id(self, bom_item_id):
        with self.assertRaisesRegex(ElementsError, "BOM item with id {} not found".format(bom_item_id)):
            operation(
                constants.kOperationCopy,
                self.child,
                system_args(bom_item_to_replace=bom_item_id),
                teilenummer='#',
                benennung='after_copy'
            )

    def assert_no_copies(self):
        self.assertEqual(len(self._find_copied_parts()), 0)

    def assert_one_copy(self):
        self.assertEqual(len(self._find_copied_parts()), 1)

    def setUp(self):
        super(TestCopyAndReplaceBomItem, self).setUp()
        self.bom = generateItem(
            benennung="bom"
        )
        self.child = generateItem(benennung="child")
        self.bom_item = generateAssemblyComponent(self.bom, self.child, benennung="bom_item")

    def test_when_no_bom_item_id_then_only_copy(self):
        self.bom.cdb_m2persno = None
        self.bom.cdb_m2date = None

        # This should be a regular Item copy.
        copy = operation(
            constants.kOperationCopy,
            self.child,
            teilenummer='#',
            benennung='after_copy',
            cdb_mpersno='New Testuser'
        )

        self.assert_one_copy()

        replacement = AssemblyComponent.KeywordQuery(
            teilenummer=copy.teilenummer,
            t_index=copy.t_index
        )
        # No BOM Item should have been created by the copy operation.
        self.assertFalse(replacement)

        # BOM Item should still refer to child.
        self.assertEqual(self.bom_item.teilenummer, self.child.teilenummer)
        self.assertEqual(self.bom_item.t_index, self.child.t_index)

    def test_when_invalid_uuid_then_raise_error(self):
        bom_item_id = "0"

        self.assert_exception_for_id(bom_item_id)
        self.assert_no_copies()

    def test_when_unassigned_uuid_then_raise_error(self):
        from uuid import UUID
        zero_uuid = str(UUID(int=0))

        self.assert_exception_for_id(zero_uuid)
        self.assert_no_copies()

    def test_when_wrong_uuid_then_raise_error(self):
        temp_item = generateItem()

        # Case: Passed UUID is not from a BOM Item.
        self.assert_exception_for_id(temp_item.cdb_object_id)
        self.assert_no_copies()

    def test_when_wrong_bom_item_then_raise_error(self):
        child_2 = generateItem()

        # Case: BOM Item references self.child, but operation is executed on child_2.
        bom_item_id = self.bom_item.cdb_object_id
        with self.assertRaisesRegex(ElementsError, "BOM item with id {} not found".format(bom_item_id)):
            operation(
                constants.kOperationCopy,
                child_2,
                system_args(bom_item_to_replace=bom_item_id),
                teilenummer='#',
                benennung='after_copy'
            )

    def test_replacement_success(self):
        self.bom.cdb_m2persno = None
        self.bom.cdb_m2date = None

        copy = operation(
            constants.kOperationCopy,
            self.child,
            system_args(bom_item_to_replace=self.bom_item.cdb_object_id),
            teilenummer='#',
            benennung='after_copy'
        )

        self.bom_item.Reload()
        self.assertEqual(copy.teilenummer, self.bom_item.teilenummer)
        self.assertEqual(copy.t_index, self.bom_item.t_index)
        self.assert_one_copy()
