#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import pytest
from cdb import ElementsError, testcase, util
from cdb.validationkit import generateUser

# This test suite does check if persons are generated under certain conditions.
# In some cases a creation is prevented by user exits.


@pytest.mark.integration
class ManagingPersonsIntegration(testcase.RollbackTestCase):
    def _create_person(self, isResource, capacity):
        # Create a person with given parameters
        presets = {
            "visibility_flag": True,
            "is_resource": isResource,
            "capacity": capacity,
            "mapped_calendar_profile": "*** mandatory stuff ***",
        }
        # sets up necessary parameters, uses operation to create user and gives
        # user public role common
        pers = generateUser(str(util.nextval("cs.pcs.person")), **presets)
        return pers

    def test_person_not_generated(self):
        """check person is not generated if it is tagged as resource,
        but has capacity of 0"""
        with self.assertRaises(ElementsError):
            pers = self._create_person(True, 0)
            self.assertIsNone(pers)

    def test_person_generated(self):
        """check person is generated if:
        (not tagged as resource, capacity of 0),
        (not tagged as resource, capacity of 8),
        (tagged as resource, capacity of 8)"""
        pers1 = self._create_person(False, 0)
        pers2 = self._create_person(False, 8)
        pers3 = self._create_person(True, 8)

        self.assertIsNotNone(pers1)
        self.assertIsNotNone(pers2)
        self.assertIsNotNone(pers3)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
