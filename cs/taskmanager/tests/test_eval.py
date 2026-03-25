#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime
import unittest

from cdb import testcase
from cdb.objects.org import Organization
from cs.taskmanager.eval import evaluate


def setUpModule():
    testcase.run_level_setup()


class Evaluate(testcase.RollbackTestCase):
    def setUp(self):
        super(Evaluate, self).setUp()
        self.ORG = Organization.Create(
            org_id="test_eval",
            name="Test Eval",
            org_type="foo",
            org_id_head="131",
            cdb_cdate=datetime.datetime(2021, 10, 4, 13, 22, 11),
        )

    def test_simpleAttribute(self):
        self.assertEqual(
            evaluate(self.ORG, "name"),
            "Test Eval",
        )

    def test_objectMethod(self):
        self.assertEqual(
            evaluate(self.ORG, "GetDescription"),
            "Test Eval ()",
        )
        self.assertFalse(evaluate(self.ORG, "MatchRule", rule="WEBUI Files"))

    def test_chainedReference_1(self):
        self.assertEqual(evaluate(self.ORG, "HeadOrganization.org_id"), "131")

    def test_reference_n(self):
        self.assertEqual(evaluate(self.ORG, "SubOrganizations"), 0)

    def test_nonExistingAttribute(self):
        self.assertIsNone(evaluate(self.ORG, "SubOrganizations.missing"))
        self.assertIsNone(evaluate(self.ORG, "missing"))
        self.assertIsNone(evaluate(self.ORG, None))
        self.assertIsNone(evaluate(self.ORG, 1))
        self.assertIsNone(evaluate(self.ORG, ""))
        self.assertIsNone(evaluate(self.ORG, "."))
        self.assertIsNone(evaluate(None, ""))
        self.assertIsNone(evaluate(0, ""))
        self.assertIsNone(evaluate(1, ""))
        self.assertIsNone(evaluate("?", ""))

    def test_privateAttribute(self):
        self.assertIsNone(evaluate(self.ORG, "__dict__"))

    def test_datetime(self):
        self.assertEqual(evaluate(self.ORG, "cdb_cdate"), "2021-10-04T13:22:11")


if __name__ == "__main__":
    unittest.main()
