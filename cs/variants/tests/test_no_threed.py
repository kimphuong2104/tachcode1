# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import testcase
from cdb.comparch import packages


class TestNoThreed(testcase.RollbackTestCase):
    def test_threed_not_installed(self):
        threed_package = packages.Package.ByKeys("cs.threed")
        self.assertIsNone(threed_package)
