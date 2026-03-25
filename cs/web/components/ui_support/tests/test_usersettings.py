# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from webtest import TestApp as Client
from cs.platform.web.root import Root
from cdb.testcase import RollbackTestCase
from cs.web.components.ui_support.user_settings import SettingsModel


class TestUserSettings(RollbackTestCase):

    def setUp(self):
        """
        Set up the test case
        """
        super(TestUserSettings, self).setUp()

        SettingsModel("test1", "test2").set_value('{"key":"value"}')

        app = Root()
        self.c = Client(app)
        self.maxDiff = None

    def test_usersetting_get(self):
        response = self.c.get(u'/internal/uisupport/user_settings/test1/test2')
        self.assertEqual(response.json['key'], 'value')

    def test_usersetting_post(self):
        json = {
            u'key1': 123,
            u'key2': '456',
        }
        response = self.c.post_json(u'/internal/uisupport/user_settings/post/json', json)
        self.assertEqual(response.json['key1'], 123)
        self.assertEqual(response.json['key2'], '456')

        response = self.c.get(u'/internal/uisupport/user_settings/post/json')
        self.assertEqual(response.json['key1'], 123)
        self.assertEqual(response.json['key2'], '456')

    def test_usersetting_delete(self):
        response = self.c.get(u'/internal/uisupport/user_settings/test1/test2')
        self.assertEqual(response.json['key'], 'value')
        response = self.c.delete(u'/internal/uisupport/user_settings/test1/test2')
        response = self.c.get(u'/internal/uisupport/user_settings/test1/test2')
        self.assertEqual(response.json, '')
