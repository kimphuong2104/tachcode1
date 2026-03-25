# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module authentication

This module contains tests for authentication system used by the Broker Service.
"""
import unittest
import sys

from jwkest import jws
from nose.twistedtools import deferred as nose_deferred
from twisted.internet.defer import inlineCallbacks
from twisted.web import resource

from cdb import testcase

from cs.threed.services.broker import util as brokerUtil
from cs.threed.services.broker import authentication

from . import DummySite
from cs.threed.services import auth

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


class MockRegistrationResource(resource.Resource):
    isLeaf = True

    def render_POST(self, request):
        brokerUtil.default_head_response(request)
        request.setResponseCode(200)

        scope = "threed/broker/%s" % ("/".join(request.postpath[0:3]),)
        if not authentication.validate_request(request, scope):
            return "fail"
        return "ok"


class TestBrokerAuthentication(testcase.PlatformTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBrokerAuthentication, cls).setUpClass()

    def setUp(self):
        super(TestBrokerAuthentication, self).setUp()
        self.longMessage = True
        register_resource = MockRegistrationResource()
        root = resource.ForbiddenResource()
        root.putChild(b"register", register_resource)
        self.web = DummySite(root)
        # clear old keys
        auth.WebKey.Query().Delete()

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_unauthenticated_request(self):
        response = yield self.web.post("register/test_resource")
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_empty_request(self):
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": ""
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_invalid_request(self):
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "garbage"
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_invalid_request2(self):
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer garbage"
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertIn("error=\"invalid_token\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_unshared_key(self):
        keys = auth.WebKeySet()
        keys.append(keys.make_rsakey(kid="testkey"))
        jwt = keys.sign("https://localhost/test/auth", "threed/broker/test_resource")
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt,)
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertIn("error=\"invalid_token\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error")
        self.assertIn("error_description=\"The access token expired\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error description")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_shared_key(self):
        jwt = auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt["access_token"],)
        })
        self.assertEqual(response.value(), "ok", "Should not fail")
        self.assertEqual(response.responseCode, 200, "Should be 200 (OK)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_forbidden_resource(self):
        jwt = auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        response = yield self.web.post("register/forbidden_resource", None, {
            "Authorization": "Bearer %s" % (jwt["access_token"],)
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 403, "Should be 403 (Forbidden)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertIn("error=\"insufficient_scope\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_wrong_exp_timestamp(self):
        auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        keys = auth.WebKey.get_active_keyset()
        payload = {
            "iss": "Test",
            "iat": "wrong",
            "exp": "wrong",
            "scope": "threed/broker/test_resource"
        }
        jws_token = jws.JWS(payload, alg=auth.WEB_KEY_ALG)
        jwt = jws_token.sign_compact(keys=keys._keys)
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt,)
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertIn("error=\"invalid_token\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error")
        self.assertIn("error_description=\"Expiration date missing\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error description")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_missing_exp_timestamp(self):
        auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        keys = auth.WebKey.get_active_keyset()
        payload = {
            "iss": "Test",
            "iat": "wrong",
            "scope": "threed/broker/test_resource"
        }
        jws_token = jws.JWS(payload, alg=auth.WEB_KEY_ALG)
        jwt = jws_token.sign_compact(keys=keys._keys)
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt,)
        })
        self.assertEqual(response.value(), "fail", "Should fail")
        self.assertEqual(response.responseCode, 401, "Should be 401 (Unauthorized)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertIn("error=\"invalid_token\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error")
        self.assertIn("error_description=\"Expiration date missing\"", www_auth_header[0],
                      "WWW-Authenticate header should contain an error description")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_missing_iap_timestamp(self):
        auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        keys = auth.WebKey.get_active_keyset()
        payload = {
            "iss": "Test",
            "exp": sys.maxsize,
            "scope": "threed/broker/test_resource"
        }
        jws_token = jws.JWS(payload, alg=auth.WEB_KEY_ALG)
        jwt = jws_token.sign_compact(keys=keys._keys)
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt,)
        })
        self.assertEqual(response.value(), "ok", "Should work")
        self.assertEqual(response.responseCode, 200, "Should be 200 (OK)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

    @nose_deferred(timeout=60.0)
    @inlineCallbacks
    def test_wrong_iap_timestamp(self):
        auth.WebKey.gen_bearer_token("https://localhost/test/auth", "threed/broker/test_resource")
        keys = auth.WebKey.get_active_keyset()
        payload = {
            "iss": "Test",
            "iap": "wrong",
            "exp": sys.maxsize,
            "scope": "threed/broker/test_resource"
        }
        jws_token = jws.JWS(payload, alg=auth.WEB_KEY_ALG)
        jwt = jws_token.sign_compact(keys=keys._keys)
        response = yield self.web.post("register/test_resource", None, {
            "Authorization": "Bearer %s" % (jwt,)
        })
        self.assertEqual(response.value(), "ok", "Should work")
        self.assertEqual(response.responseCode, 200, "Should be 200 (OK)")
        www_auth_header = response.responseHeaders.getRawHeaders("www-authenticate")
        self.assertIsNotNone(www_auth_header,
                             "There should be a WWW-Authenticate header")
        self.assertEqual(len(www_auth_header), 1,
                         "There should be only one WWW-Authenticate header")
        self.assertEqual(www_auth_header[0], "Bearer",
                         "WWW-Authenticate header should be \"Bearer\"")

if __name__ == "__main__":
    unittest.main()
