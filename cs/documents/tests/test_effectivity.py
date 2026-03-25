# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"


# Some imports
from datetime import datetime, timedelta

from cdb import constants
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cs.documents import NEVER_VALID_DATE, Document

# status numbers
DRAFT = 0
REVIEW = 100
BLOCKED = 170
OBSOLETE = 180
REVISION = 190
RELEASED = 200


class TestEffectivity(RollbackTestCase):
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
        return document

    def test_create_document(self):
        document = self._create_document("TestDoc")
        self.assertEqual(document.ce_valid_from, NEVER_VALID_DATE)
        self.assertIsNone(document.ce_valid_to)

    def test_create_document_with_valid_dates(self):
        valid_from = datetime.utcnow().replace(microsecond=0)
        valid_to = valid_from + timedelta(days=1)
        document = self._create_document(
            "TestDoc", {"ce_valid_from": valid_from, "ce_valid_to": valid_to}
        )
        self.assertEqual(document.ce_valid_from, valid_from)
        self.assertEqual(document.ce_valid_to, valid_to)

    def test_released_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.Reload()
        released = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= document.ce_valid_from <= released)
        self.assertIsNone(document.ce_valid_to)

    def test_blocked_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.ChangeState(BLOCKED)
        document.Reload()
        blocked = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= document.ce_valid_from <= blocked)
        self.assertTrue(created <= document.ce_valid_to <= blocked)

    def test_obsolete_document(self):
        document = self._create_document("TestDoc")
        created = datetime.utcnow().replace(microsecond=0)
        document.ChangeState(RELEASED)
        document.ChangeState(REVISION)
        document.ChangeState(OBSOLETE)
        document.Reload()
        obsolete = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= document.ce_valid_from <= obsolete)
        self.assertTrue(created <= document.ce_valid_to <= obsolete)
