#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

import unittest

import mock
from cdb import testcase
from cs.web.components.base.main import SettingDict

from cs.objectdashboard import widgets


class WidgetsTest(testcase.RollbackTestCase):
    def test_register_widget_url(self):

        app_setup = mock.MagicMock(spec=SettingDict)
        self.assertEqual(
            widgets.register_widget_url(app_setup, "CODE", "%24%7Burl%7D"), None
        )
        app_setup.merge_in.assert_called_once_with(
            ["cs-objectdashboard-widgets", "widgets", "CODE"], {"url": "${url}"}
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
