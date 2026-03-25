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
from datetime import datetime, timedelta

from cdb import constants
from cdb.objects.operations import operation

from cdb.testcase import RollbackTestCase

from cs.vp import items
from cs.vp.utils import NEVER_VALID_DATE

# status numbers

DRAFT = 0
REVIEW = 100
RELEASED = 200
BLOCKED = 170
RELEASED_ERP = 300
OBSOLETE = 180


class TestEffectivity(RollbackTestCase):

    def _create_part(self, addtl_args=None):
        item_args = dict(
            benennung="Blech",
            t_kategorie="Baukasten",
            t_bereich="Engineering",
            mengeneinheit="qm"
        )
        if addtl_args:
            item_args.update(addtl_args)
        part = operation(
            constants.kOperationNew,
            items.Item,
            **item_args
        )
        self.assertIsNotNone(part, 'part could not be created!')
        return part

    def test_create_part(self):
        part = self._create_part()
        self.assertEqual(part.ce_valid_from, NEVER_VALID_DATE)
        self.assertIsNone(part.ce_valid_to)

    def test_create_part_with_valid_dates(self):
        valid_from = datetime.utcnow().replace(microsecond=0)
        valid_to = valid_from + timedelta(days=1)
        part = self._create_part({
            "ce_valid_from": valid_from,
            "ce_valid_to": valid_to
        })
        self.assertEqual(part.ce_valid_from, valid_from)
        self.assertEqual(part.ce_valid_to, valid_to)

    def test_released_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(REVIEW)
        part.ChangeState(RELEASED)
        part.Reload()
        released = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= part.ce_valid_from <= released)
        self.assertIsNone(part.ce_valid_to)

    def test_blocked_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(REVIEW)
        part.ChangeState(RELEASED)
        part.ChangeState(RELEASED_ERP)
        part.ChangeState(BLOCKED)
        part.Reload()
        blocked = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= part.ce_valid_from <= blocked)
        self.assertTrue(created <= part.ce_valid_to <= blocked)

    def test_obsolete_part(self):
        part = self._create_part()
        created = datetime.utcnow().replace(microsecond=0)
        part.ChangeState(REVIEW)
        part.ChangeState(RELEASED)
        part.ChangeState(OBSOLETE)
        part.Reload()
        obsolete = datetime.utcnow().replace(microsecond=0)
        self.assertTrue(created <= part.ce_valid_from <= obsolete)
        self.assertTrue(created <= part.ce_valid_to <= obsolete)
