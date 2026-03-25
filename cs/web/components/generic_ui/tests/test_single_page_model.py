#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

import unittest

from cdb import testcase
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.web.components.configurable_ui import SinglePageModel


class MockSinglePageModel(SinglePageModel):
    """ Allows to provide the content of the files that will be read as a dict,
        whose keys are the filenames.
    """
    def __init__(self, page_name, mocked_config):
        super(MockSinglePageModel, self).__init__()
        self.page_name = page_name
        self.mocked_config = mocked_config

    def load_config(self, config_clname):
        return self.mocked_config


class TestSinglePageModel(testcase.PlatformTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    @run_with_roles(["public"])
    def test_minimal(self):
        config = [{"name": "pagename",
                   "roles": ["public"],
                   "component": "PageComponent",
                   "pageframe_id": "csweb_default_page_frame"}]
        mdl = MockSinglePageModel("pagename", config)
        self.assertEqual(mdl.app_conf,
                         {"pageRenderer": "cs-web-components-base-SinglePage",
                          "frameComponent": "cs-web-components-base-ApplicationFrame",
                          "pageContent": "PageComponent"})

# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
