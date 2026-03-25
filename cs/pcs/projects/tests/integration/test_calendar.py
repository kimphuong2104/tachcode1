#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime
import unittest

import pytest
from cdb import testcase

from cs.pcs.projects import calendar


@pytest.mark.integration
class CalendarIntegrationTestCase(testcase.RollbackTestCase):
    calendar_profile_id = "0116cc53-f3fe-11e9-8350-d0577b2793bc"
    day = datetime.date(2020, 0o1, 0o1)

    def test_getCalendarIndex(self):
        "Test get Calendar Index return date values and not datetime"
        dict_by_day, _ = calendar.getCalendarIndex(self.calendar_profile_id)
        self.assertEqual(dict_by_day.get(self.day), (1, 1))


if __name__ == "__main__":
    unittest.main()
