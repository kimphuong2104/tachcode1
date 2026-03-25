# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from datetime import date, datetime, timedelta

import cdbwrapc

from cdb import constants, sqlapi
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase

from cs.vp import items
from cs.vp.utils import NEVER_VALID_DATE
from cs.vp.items.scripts.set_validity_dates import set_validity_dates

# status numbers
DRAFT = 0
REVIEW = 100
BLOCKED = 170
OBSOLETE = 180
REVISION = 190
RELEASED = 200
RELEASED_ERP = 300


class TestSetValidityDates(RollbackTestCase):

    def _clear_effectivity_dates(self, part):
        part.Update(
            ce_valid_from = None,
            ce_valid_to = None
        )
        part.Reload()
        self.assertEqual(part.ce_valid_from, None)
        self.assertEqual(part.ce_valid_to, None)
        return part

    def _create_part(self):
        item_args = dict(
            benennung="Blech",
            t_kategorie="Baukasten",
            t_bereich="Engineering",
            mengeneinheit="qm"
        )
        part = operation(
            constants.kOperationNew,
            items.Item,
            **item_args
        )
        self.assertIsNotNone(part, 'part could not be created!')
        return self._clear_effectivity_dates(part)

    def _set_validity_dates(self):
        return set_validity_dates(
            draft_state_numbers=[0, 100],
            valid_state_numbers=[190, 200, 300],
            obsolete_state_numbers=[170, 180]
        )

    def test_blocked_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(RELEASED)
        part.ChangeState(RELEASED_ERP)
        part.ChangeState(BLOCKED)
        blocked = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertTrue(created <= part.ce_valid_from <= blocked)
        self.assertTrue(created <= part.ce_valid_to <= blocked)

    def test_new_part(self):
        part = self._create_part()
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertEqual(part.ce_valid_from, NEVER_VALID_DATE)
        self.assertIsNone(part.ce_valid_to)

    def test_obsolete_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(RELEASED)
        part.ChangeState(OBSOLETE)
        obsolete = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertTrue(created <= part.ce_valid_from <= obsolete)
        self.assertTrue(created <= part.ce_valid_to <= obsolete)

    def test_review_part(self):
        part = self._create_part()
        part.ChangeState(REVIEW)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertEqual(part.ce_valid_from, NEVER_VALID_DATE)
        self.assertIsNone(part.ce_valid_to)

    def test_released_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(RELEASED)
        released = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertTrue(created <= part.ce_valid_from <= released)
        self.assertIsNone(part.ce_valid_to)

    def test_released_erp_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(RELEASED)
        part.ChangeState(RELEASED_ERP)
        released = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertTrue(created <= part.ce_valid_from <= released)
        self.assertIsNone(part.ce_valid_to)

    def test_revision_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(RELEASED)
        part.ChangeState(REVISION)
        revision = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertTrue(created <= part.ce_valid_from <= revision)
        self.assertIsNone(part.ce_valid_to)

    def test_multiple_released_part(self):
        part = self._create_part()
        part.ChangeState(RELEASED)
        first_release_date = datetime.utcnow().replace(microsecond=0) - timedelta(days=1)
        stmt = """
            cdb_t_statiprot set cdbprot_zeit = {}
            where teilenummer = '{}' and t_index = '{}' and cdbprot_newstate = {}
        """.format(cdbwrapc.SQLdate_literal(first_release_date), part.teilenummer, part.t_index, RELEASED)
        sqlapi.SQLupdate(stmt)
        part.ChangeState(REVISION)
        part.ChangeState(RELEASED)
        self._clear_effectivity_dates(part)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        part.Reload()
        self.assertEqual(part.ce_valid_from, first_release_date)
        self.assertIsNone(part.ce_valid_to)
