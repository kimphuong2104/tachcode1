#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module test_app

This is the documentation for the tests.
"""

from __future__ import absolute_import

import unittest

from cdb.testcase import PlatformTestCase
from cs.licdashboard.app.dashboard import LicenseInfoModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Tests
class Test_dashboard_app(PlatformTestCase):
    def test_get_info(self):
        # Just a smoke test because there are no licenses installed
        d = LicenseInfoModel().get_info()
        self.assertTrue(isinstance(d, dict))
        for key in [
            "sites",
            "user_info",
            "lics_installed",
            "soed_msg",
            "licenses",
            "soed_active",
            "slots",
            "slot_table",
            "chart_info",
        ]:
            self.assertTrue(key in d, "%s missing in info" % key)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
