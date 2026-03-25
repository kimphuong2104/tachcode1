#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from cdb.testcase import PlatformTestCase
from cs.web.components.library_config import Libraries, get_dependencies


class TestLibraryDependencies(PlatformTestCase):

    def test_get_dependencies(self):
        result = [lib.library_name for lib in get_dependencies(Libraries.ByKeys("cs-webtest-library"))]
        self.assertEquals(result, ["cs-webtest-library5", "cs-webtest-library3", "cs-webtest-library4", "cs-webtest-library"])

    def test_get_dependencies_with_cycles(self):
        result = []
        try:
            result = [lib.library_name for lib in get_dependencies(Libraries.ByKeys("cs-webtest-library6"))]
        except RuntimeError:
            pass
        self.assertEquals(len(result), 2)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
