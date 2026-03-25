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
from cs.web.components.generic_ui.detail_view import DetailViewModel


class MockDetailViewModel(DetailViewModel):
    """ Allows to provide the content of the files that will be read as a dict,
        whose keys are the filenames.
    """
    def __init__(self, rest_name, keys, viewname, mocked_file_content, mocked_config):
        super(MockDetailViewModel, self).__init__(rest_name, keys, viewname)
        self.mocked_file_content = mocked_file_content
        self.mocked_config = mocked_config

    def load_config_file(self, *path):
        fname = "/".join(path)
        return self.mocked_file_content[fname]

    def load_config(self, config_clname):
        return self.mocked_config


class TestDetailViewModel(testcase.PlatformTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    @run_with_roles(["public"])
    def test_minimal(self):
        config = [{"classname": "*",
                   "viewname": "default",
                   "roles": ["public"],
                   "pageframe_id": "csweb_default_page_frame",
                   "component": "DefaultComponent"}
                  ]
        mdl = MockDetailViewModel("person", "caddok", None, {}, config)
        self.assertEqual(mdl.app_conf,
                         {"pageRenderer": "cs-web-components-base-DetailPage",
                          "frameComponent": "cs-web-components-base-ApplicationFrame",
                          "detailView": "DefaultComponent"})

    @run_with_roles(["public"])
    def test_configuration_and_lib(self):
        config = [{"classname": "*",
                   "viewname": "default",
                   "roles": ["public"],
                   "pageframe_id": "csweb_default_page_frame",
                   "configuration": "default-config.json"}
                  ]
        file_data = {"default-config.json": {"configuration": {"name": "MyComponent",
                                                               "properties": {"abc": 42}},
                                             "libraries": [["libsomething", "1.2.3"],
                                                           ["libother", "3.2.1"]]}
                     }
        mdl = MockDetailViewModel("person", "caddok", None, file_data, config)
        self.assertEqual(mdl.app_conf,
                         {"pageRenderer": "cs-web-components-base-DetailPage",
                          "frameComponent": "cs-web-components-base-ApplicationFrame",
                          "detailView": {"name": "MyComponent",
                                         "properties": {"abc": 42}}})
        self.assertEqual(mdl.libraries,
                         [("libsomething", "1.2.3"),
                          ("libother", "3.2.1")])

# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
