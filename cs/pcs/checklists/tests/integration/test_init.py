#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import testcase

from cs.pcs import checklists


@pytest.mark.integration
class ChecklistIntegrationTestCase(testcase.RollbackTestCase):
    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_set_frozen_in_event_map(self):
        "Checklist event map contains 'set_frozen'"
        self.assertIn(
            "set_frozen",
            checklists.Checklist.GetEventMap()[(("create", "copy"), "pre")],
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_derived_from_WithFrozen(self):
        "Checklist is derived from WithFrozen"
        self.assertIn(checklists.WithFrozen, checklists.Checklist.mro())


@pytest.mark.integration
class ChecklistItemIntegrationTestCase(testcase.RollbackTestCase):
    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_set_frozen_in_event_map(self):
        "ChecklistItem event map contains 'set_frozen'"
        self.assertIn(
            "set_frozen",
            checklists.ChecklistItem.GetEventMap()[(("create", "copy"), "pre")],
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_derived_from_WithFrozen(self):
        "ChecklistItem is derived from WithFrozen"
        self.assertIn(checklists.WithFrozen, checklists.ChecklistItem.mro())


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
