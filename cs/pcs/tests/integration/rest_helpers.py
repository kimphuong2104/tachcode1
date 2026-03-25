#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

import pytest
from cdb import testcase
from cs.platform.web.root import root as RootApp
from webtest import TestApp

STANDARD_FORBIDDEN = ["delete", "post", "put"]


@pytest.mark.dependency(name="integration")
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
        return f"/api/v1/collection/{'/'.join(url_parts)}"

    def _build_rest_key(self, keys):
        return "@".join([str(k) for k in keys]).replace(" ", "~20").replace(":", "~3A")

    def complete_rest(self, rest_name, class_name, post_dict, rest_keys, put_dict):
        """
        Performs one test for each of the four rest routes. This should be used as
        standard test for all classes which have all rest types enabled.

        :param rest_name: The classes Rest Name.
        :type string:

        :param class_name: The classes Class Name.
        :type string:

        :param post_dict: Key value pairs of attributes for POST request.
        :type dict:

        :param rest_keys: Ordered list of all the attributes' names building the rest key.
        :type list:

        :param put_dict: Key value pairs of attributes for PUT request.
        :type dict:
        """
        obj = self._test_post(rest_name, class_name, post_dict)
        rest_key = "@".join([str(obj[k]) for k in rest_keys])
        self._test_get_collection(rest_name, class_name)
        self._test_put_single_object(rest_name, rest_key, put_dict)
        self._test_get_single_object(rest_name, rest_key)
        self._test_delete(rest_name, rest_key)

    def rest_get_only(self, rest_name, rest_key, class_name):
        """
        Performs the positive test for GET and a negative test for each of the other routes. This can be used
        as standard test for all classes, with only GET enabled.

        :param rest_name: The classes Rest Name.
        :type string:

        :param class_name: The classes Class Name.
        :type string:

        :param rest_keys: Ordered list of all the attributes' names building the rest key.
        :type list:
        """
        self._test_get_collection(rest_name, class_name)
        self._test_get_single_object(rest_name, rest_key)
        self.forbidden(STANDARD_FORBIDDEN, rest_name, rest_key)

    def _test_post(self, rest_name, classname, payload):
        resp = self.client.post(self._build_url([rest_name]), json.dumps(payload))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse("objects" in resp.json.keys())
        self.assertEqual(resp.json["system:classname"], classname)
        self.assertDictContainsSubset(payload, resp.json)
        return resp.json

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
        self.assertEqual(resp.json["@id"], f"http://localhost{url}")
        return resp

    def _test_put_single_object(self, rest_name, rest_key, payload):
        url = self._build_url([rest_name, rest_key])
        resp = self.client.put(url, json.dumps(payload))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse("objects" in resp.json.keys())
        self.assertEqual(resp.json["@id"], f"http://localhost{url}")
        self.assertDictContainsSubset(payload, resp.json)
        return resp

    def _test_delete(self, rest_name, rest_key):
        url = self._build_url([rest_name, rest_key])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)
        with self.assertRaises(Exception) as error:
            self.client.get(url)
        self.assertIn("The resource could not be found", str(error.exception))
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

    def no_rest(self, rest_name):
        url = self._build_url([rest_name])
        with self.assertRaises(Exception) as error:
            self.client.put(url, json.dumps({}))
        self.assertIn("404 Not Found", str(error.exception))
