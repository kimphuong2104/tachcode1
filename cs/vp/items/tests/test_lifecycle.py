# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests lifecycle for parts
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import datetime
import unittest

from dateutil.relativedelta import relativedelta


from cdb import constants, ElementsError
from cdb.testcase import RollbackTestCase
from cdb.objects import operations

from cs.vp import items

from cs.vp.bom.tests import generateAssemblyComponent
from cs.vp.items.tests import generateItem


# def setup():
#     from cdb import testcase
#     testcase.run_level_setup()


# status numbers

BLOCKED = 170
DRAFT = 0
OBSOLETE = 180
RELEASED = 200
REVIEW = 100
REVISION = 190


class TestLifecycle(RollbackTestCase):
    def setUp(self):
        super(TestLifecycle, self).setUp()

        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        self.ebom = items.Item.ByKeys(teilenummer="9505947", t_index="")
        self.mbom = items.Item.ByKeys(teilenummer="9505945", t_index="")
        self.pure_mbom = items.Item.ByKeys(teilenummer="9505946", t_index="")

    def _new_index_released(self, part):
        part.ChangeState(RELEASED)

        index = operations.operation(
            constants.kOperationIndex,
            part
        )
        index.ChangeState(REVIEW)
        index.ChangeState(RELEASED)

        part.Reload()
        return index

    @classmethod
    def _create_part(cls, is_imprecise, benennung="part", assembly=None):
        part = generateItem(benennung=benennung)
        if assembly:
            generateAssemblyComponent(assembly, item=part, is_imprecise=is_imprecise)
        return part

    @classmethod
    def _create_draft_part(cls, is_imprecise, benennung="draft_part", assembly=None):
        return cls._create_part(is_imprecise, benennung=benennung, assembly=assembly)

    @classmethod
    def _create_released_part(cls, is_imprecise, benennung="released_part", assembly=None):
        part = cls._create_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part)
        return part

    @classmethod
    def _create_revision_part(cls, is_imprecise, benennung="revision_part", assembly=None):
        part = cls._create_released_part(is_imprecise, benennung=benennung, assembly=assembly)
        part_index = operations.operation(constants.kOperationIndex, part)
        return part, part_index

    @classmethod
    def _create_obsolete_part(cls, is_imprecise, benennung="obsolete_part", assembly=None):
        part, part_index = cls._create_revision_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part_index, part)
        return part, part_index

    @classmethod
    def _create_blocked_part(cls, is_imprecise, benennung="blocked_part", assembly=None):
        part, part_index = cls._create_revision_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part_index, part)
        part_index.ChangeState(180)
        part_index.ce_valid_to = part_index.ce_valid_from + relativedelta(years=1)
        return part, part_index

    @classmethod
    def _release_part(cls, part, prev_index=None):
        part.ChangeState(100)
        part.ChangeState(200)
        if prev_index:
            part.ce_valid_from = prev_index.ce_valid_from + relativedelta(years=1)
            prev_index.ce_valid_to = part.ce_valid_from
            part.Reload()
            prev_index.Reload()
        else:
            part.ce_valid_from = datetime.date(2000, 12, 31)
            part.Reload()

    def test_new_index_released(self):
        "when a new index of an ebom-part goes from review to released, the old index is set to obsolete"
        self._new_index_released(self.ebom)
        self.assertEqual(self.ebom.status, OBSOLETE)

    def test_new_pure_mbom_index_released(self):
        "when a new index of a pure mbom-part goes from review to released, the old index is set to obsolete"
        self._new_index_released(self.pure_mbom)
        self.assertEqual(self.pure_mbom.status, OBSOLETE)

    def _new_index_created(self, part):
        index = operations.operation(
            constants.kOperationIndex,
            part
        )
        part.Reload()
        return index

    def test_new_index_created(self):
        "when a new index of a released ebom-part is created, the old index is set to revision"
        self.ebom.ChangeState(RELEASED)
        self._new_index_created(self.ebom)
        self.assertEqual(self.ebom.status, REVISION)

    def test_new_pure_mbom_index_created(self):
        "when a new index of a released pure mbom-part is created, the old index is set to revision"
        self.pure_mbom.ChangeState(RELEASED)
        self._new_index_created(self.pure_mbom)
        self.assertEqual(self.pure_mbom.status, REVISION)

    def _new_index_deleted(self, part):
        index = operations.operation(constants.kOperationIndex, part)
        part.Reload()

        operations.operation(constants.kOperationDelete, part)
        part.Reload()

        return index

    def test_new_index_deleted(self):
        "when a new index of an ebom part is deleted, the old index is set to its original status"
        status = self.ebom.status
        self._new_index_deleted(self.ebom)

        self.assertEqual(self.ebom.status, status)

    def test_new_pure_mbom_index_deleted(self):
        "when a new index of an ebom part is deleted, the old index is set to its original status"
        status = self.pure_mbom.status
        self._new_index_deleted(self.pure_mbom)

        self.assertEqual(self.pure_mbom.status, status)

    def test_new_index_deleted(self):
        """
            when a new index of a part is deleted but the old part has no status_prev information,
            an error message is showed.
        """
        part = self.ebom

        part.ChangeState(RELEASED)
        index = self._new_index_created(self.ebom)

        self.assertEqual(part.status, REVISION)
        self.assertEqual(part.status_prev, RELEASED)
        part.status_prev = None

        with self.assertRaisesRegex(
            RuntimeError,
            "Fehler beim Zur.*cksetzen des Status"
        ):
            operations.operation(constants.kOperationDelete, index)

    def test_release_precise_assembly(self):
        bom = generateItem(benennung="bom")
        child_released = self._create_released_part(is_imprecise=0, assembly=bom)
        child_revision, _ = self._create_revision_part(is_imprecise=0, assembly=bom)
        self._release_part(bom)
        self.assertEqual(bom.status, 200)

    def test_release_error_precise_assembly(self):
        bom = generateItem(benennung="bom")
        child_draft = self._create_draft_part(is_imprecise=0, assembly=bom)
        self._create_released_part(is_imprecise=0, assembly=bom)
        self._create_revision_part(is_imprecise=0, assembly=bom)
        child_obsolete, _ = self._create_obsolete_part(is_imprecise=0, assembly=bom)
        child_blocked, _ = self._create_blocked_part(is_imprecise=0, assembly=bom)
        try:
            self._release_part(bom)
            parts = ', '.join([child_draft.teilenummer, child_obsolete.teilenummer, child_blocked.teilenummer])
            self.fail(
                f"Exception expected that parts {parts} are not released"
            )
        except ElementsError as ex:
            message = str(ex)
            self.assertIn(child_draft.teilenummer, message)
            self.assertIn(child_obsolete.teilenummer, message)
            self.assertIn(child_blocked.teilenummer, message)

    def test_release_imprecise_assembly(self):
        bom = generateItem(benennung="bom")
        self._create_released_part(is_imprecise=1, assembly=bom)
        self._create_revision_part(is_imprecise=1, assembly=bom)
        _, child_revision_index = self._create_revision_part(is_imprecise=1)
        generateAssemblyComponent(bom, item=child_revision_index, is_imprecise=1)
        self._create_obsolete_part(is_imprecise=1, assembly=bom)
        _, child_obsolete_index = self._create_obsolete_part(is_imprecise=1)
        generateAssemblyComponent(bom, item=child_revision_index, is_imprecise=1)
        self._release_part(bom)
        self.assertEqual(bom.status, 200)

    def test_release_imprecise_assembly_only_release(self):
        bom = generateItem(benennung="bom")
        child = self._create_draft_part(is_imprecise=1, assembly=bom)
        child.ChangeState(100)
        child.ChangeState(200)
        self._release_part(bom)

    def test_release_error_imprecise_assembly(self):
        bom = generateItem(benennung="bom")
        child_draft = self._create_draft_part(is_imprecise=1, assembly=bom)
        self._create_released_part(is_imprecise=1, assembly=bom)
        self._create_revision_part(is_imprecise=1, assembly=bom)
        _, child_revision_index = self._create_revision_part(is_imprecise=1)
        generateAssemblyComponent(bom, item=child_revision_index)
        self._create_obsolete_part(is_imprecise=1, assembly=bom)
        self._create_obsolete_part(is_imprecise=1, assembly=bom)
        _, child_obsolete_index = self._create_obsolete_part(is_imprecise=1)
        child_blocked, _ = self._create_blocked_part(is_imprecise=1, assembly=bom)
        try:
            self._release_part(bom)
            parts = ', '.join([child_draft.teilenummer, child_blocked.teilenummer])
            self.fail(
                f"Exception expected that parts {parts} are not released"
            )
        except ElementsError as ex:
            message = str(ex)
            self.assertIn(child_draft.teilenummer, message)
            self.assertIn(child_blocked.teilenummer, message)

    def test_release_error_imprecise_assembly_only_draft(self):
        bom = generateItem(benennung="bom")
        child = self._create_draft_part(is_imprecise=1, assembly=bom)
        try:
            self._release_part(bom)
            self.fail(f"Exception expected that part {child.teilenummer} is not released")
        except ElementsError as ex:
            message = str(ex)
            self.assertIn(child.teilenummer, message)

    def test_release_error_imprecise_assembly_only_check(self):
        bom = generateItem(benennung="bom")
        child = self._create_draft_part(is_imprecise=1, assembly=bom)
        child.ChangeState(100)
        try:
            self._release_part(bom)
            self.fail(f"Exception expected that part {child.teilenummer} is not released")
        except ElementsError as ex:
            message = str(ex)
            self.assertIn(child.teilenummer, message)
