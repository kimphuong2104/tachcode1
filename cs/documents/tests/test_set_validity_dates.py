# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.

__docformat__ = "restructuredtext en"


from datetime import datetime, timedelta

import cdbwrapc
from cdb import constants, sqlapi
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cs.documents import NEVER_VALID_DATE, Document
from cs.documents.scripts.set_validity_dates import set_validity_dates

# status numbers
DRAFT = 0
REVIEW = 100
BLOCKED = 170
OBSOLETE = 180
REVISION = 190
RELEASED = 200


class TestSetValidityDates(RollbackTestCase):
    def _clear_effectivity_dates(self, document):
        document.Update(ce_valid_from=None, ce_valid_to=None)
        document.Reload()
        self.assertEqual(document.ce_valid_from, None)
        self.assertEqual(document.ce_valid_to, None)
        return document

    def _create_document(self, title, addtl_args=None):
        item_args = {
            "titel": title,
            "z_nummer": Document.makeNumber(None),
            "z_index": "",
            "z_categ1": "142",
            "z_categ2": "153",
        }
        if addtl_args:
            item_args.update(addtl_args)
        document = operation(constants.kOperationNew, Document, **item_args)
        self.assertIsNotNone(document, "document could not be created!")
        return self._clear_effectivity_dates(document)

    def _set_validity_dates(self):  # pylint: disable=no-self-use
        return set_validity_dates(
            draft_state_numbers=[0, 100],
            valid_state_numbers=[190, 200],
            obsolete_state_numbers=[170, 180],
        )

    def test_blocked_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.ChangeState(BLOCKED)
        blocked = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(document)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertTrue(created <= document.ce_valid_from <= blocked)
        self.assertTrue(created <= document.ce_valid_to <= blocked)

    def test_new_document(self):
        document = self._create_document("TestDoc")
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertEqual(document.ce_valid_from, NEVER_VALID_DATE)
        self.assertEqual(document.ce_valid_to, None)

    def test_obsolete_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.ChangeState(REVISION)
        document.ChangeState(OBSOLETE)
        obsolete = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(document)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertTrue(created <= document.ce_valid_from <= obsolete)
        self.assertTrue(created <= document.ce_valid_to <= obsolete)

    def test_released_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        released = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(document)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertTrue(created <= document.ce_valid_from <= released)
        self.assertIsNone(document.ce_valid_to)

    def test_revision_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.ChangeState(REVISION)
        revision = datetime.utcnow().replace(microsecond=0)
        self._clear_effectivity_dates(document)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertTrue(created <= document.ce_valid_from <= revision)
        self.assertIsNone(document.ce_valid_to)

    def test_multiple_released_document(self):
        document = self._create_document("TestDoc")
        document.ChangeState(RELEASED)
        first_release_date = datetime.utcnow().replace(microsecond=0) - timedelta(
            days=1
        )
        stmt = """
            cdb_z_statiprot set cdbprot_zeit = {}
            where z_nummer = '{}' and z_index = '{}' and cdbprot_newstate = {}
        """.format(
            cdbwrapc.SQLdate_literal(first_release_date),
            document.z_nummer,
            document.z_index,
            RELEASED,
        )
        sqlapi.SQLupdate(stmt)
        document.ChangeState(REVISION)
        document.ChangeState(RELEASED)
        self._clear_effectivity_dates(document)
        dates_set = self._set_validity_dates()
        self.assertTrue(dates_set >= 1)
        document.Reload()
        self.assertEqual(document.ce_valid_from, first_release_date)
        self.assertIsNone(document.ce_valid_to)
