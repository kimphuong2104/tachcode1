#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

import pytest
from webtest import TestApp

from cdb import testcase
from cs.platform.web.root import root as RootApp

STANDARD_FORBIDDEN = ["delete", "post", "put"]
ALL_FORBIDDEN = ["get", "delete", "post", "put"]


@pytest.mark.integration
class RESTSmokeTestBase(testcase.RollbackTestCase):
    """
    Base class for Smoke Tests of rest API.
    The purpose is to call the rest routes GET, POST, PUT, DELETE
    and check if it is allowed or not and that no error is thrown
    """

    def setUp(self):
        testcase.RollbackTestCase.setUp(self)
        self.client = TestApp(RootApp)

    def _build_url(self, url_parts):
        return "/api/v1/collection/{0}".format("/".join(url_parts))

    def rest_get_only(self, rest_name, rest_key, class_name):
        """
        Performs the positive test for GET and a negative test for each of the other routes. This can be used
        as standard test for all classes, with only GET enabled.

        :param rest_name: The classes Rest Name.
        :type string:

        :param class_name: The classes Class Name.
        :type string:

        :param rest_key: The Objects Rest Key.
        :type string:
        """
        self._test_get_collection(rest_name, class_name)
        self._test_get_single_object(rest_name, rest_key)
        self.forbidden(STANDARD_FORBIDDEN, rest_name, rest_key)

    def rest_all_forbidden(self, rest_name, rest_key):
        """
        Performs a negative test for each route. This can be used
        as standard test for all rest-active classes, without any route enabled.

        :param rest_name: The classes Rest Name.
        :type string:

        :param class_name: The classes Class Name.
        :type string:

        :param rest_key: The Objects Rest Key.
        :type string:
        """
        self.forbidden(ALL_FORBIDDEN, rest_name, rest_key)

    def _test_get_collection(self, rest_name, classname):
        resp = self.client.get(self._build_url([rest_name]))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json["objects"], list)
        self.assertEqual(resp.json["objects"][0]["system:classname"], classname)
        return resp

    def _test_get_single_object(self, rest_name, rest_key):
        url = self._build_url([rest_name, rest_key])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse("objects" in resp.json.keys())
        self.assertEqual(resp.json["@id"], "http://localhost{0}".format(url))
        return resp

    def forbidden(self, methods, rest_name, rest_key):
        if "delete" in methods:
            self._test_delete_forbidden(rest_name, rest_key)
        if "post" in methods:
            self._test_post_forbidden(rest_name, rest_key)
        if "put" in methods:
            self._test_put_forbidden(rest_name, rest_key)

    def _test_delete_forbidden(self, rest_name, rest_key):
        url = self._build_url([rest_name, rest_key])
        with self.assertRaises(Exception) as error:
            self.client.delete(url)
        self.assertIn("403 Forbidden", str(error.exception))

    def _test_post_forbidden(self, rest_name, rest_key):
        url = self._build_url([rest_name, rest_key])
        with self.assertRaises(Exception) as error:
            self.client.post(url, json.dumps({}))
        self.assertIn("405 Method Not Allowed", str(error.exception))

    def _test_put_forbidden(self, rest_name, rest_key):
        url = self._build_url([rest_name, rest_key])
        with self.assertRaises(Exception) as error:
            self.client.put(url, json.dumps({}))
        self.assertIn("403 Forbidden", str(error.exception))
