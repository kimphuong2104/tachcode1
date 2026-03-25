# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from mock import MagicMock

from cdb import testcase
from cdb.uberserver import secure

from cs.threed.services.broker import proxy


class MockHost(object):
    def __init__(self, port):
        self.port = port


class MockRequest(object):
    def __init__(self, headers, host_port=80):
        self.headers = headers
        self.host = MockHost(host_port)

    def getHeader(self, name):
        return self.headers.get(name)

    def getHost(self):
        return self.host


class TestGetClientRequestPort(testcase.PlatformTestCase):
    def test_get_port_in_forwarded_header(self):
        """ The port can be extracted from the 'Forwarded' header """
        request = MockRequest({
            "Forwarded": "host=plm.example.com:8443;proto=https"
        })

        port = proxy._get_client_request_port(request)

        self.assertEqual(port, 8443)

    def test_get_port_in_x_forwarded_host_header(self):
        """ The port can be extracted from the 'X-Forwarded-Host' header """
        request = MockRequest({
            "X-Forwarded-Host": "plm.example.com:8443"
        })

        port = proxy._get_client_request_port(request)

        self.assertEqual(port, 8443)

    def test_get_port_in_host(self):
        """ Fall back to the port defined in the host if no *Forwarded* header is present """
        request = MockRequest({}, 1337)

        port = proxy._get_client_request_port(request)

        self.assertEqual(port, 1337)

    def test_get_url_scheme_in_forwarded_header(self):
        """ The url scheme can be extracted from the 'Forwarded' header """
        request = MockRequest({
            "Forwarded": "host=plm.example.com:8443;proto=https"
        })

        scheme = proxy._get_client_url_scheme(request)

        self.assertEqual(scheme, "https")

    def test_get_url_scheme_in_x_forwarded_proto_header(self):
        """ The url scheme can be extracted from the 'X-Forwarded-Proto' header """
        request = MockRequest({
            "X-Forwarded-Proto": "https"
        })

        scheme = proxy._get_client_url_scheme(request)

        self.assertEqual(scheme, "https")

    def test_get_url_base_with_forwarded_header(self):
        """ The WebSocket url gets generated correctly for the 'Forwarded' header """
        request = MockRequest({
            "Forwarded": "host=plm.example.com:8443;proto=https"
        })

        base = proxy.get_ws_scheme_and_host(request)

        self.assertEqual(base, "wss://plm.example.com:8443")

    def test_get_url_base_with_x_forwarded_header(self):
        """ The WebSocket url gets generated correctly for the 'X-Forwarded-*' headers """
        request = MockRequest({
            "X-Forwarded-Host": "plm.example.com:8443",
            "X-Forwarded-Proto": "https",
        })

        base = proxy.get_ws_scheme_and_host(request)

        self.assertEqual(base, "wss://plm.example.com:8443")

    def test_get_url_base_without_forwarded_headers(self):
        """ The WebSocket url gets generated correctly if no *Forwarded* headers are present """
        request = MockRequest({
            "Host": "plm.example.com"
        }, 1337)

        secure.get_ssl_mode = MagicMock(return_value=secure.USESSL)
        base = proxy.get_ws_scheme_and_host(request)

        self.assertEqual(base, "wss://plm.example.com:1337")

    def test_get_client_request_port_with_default_ports_https(self):
        """ The port can be determined if it is the default port for the https scheme """
        request = MockRequest({
            "X-Forwarded-Host": "plm.example.com",
            "X-Forwarded-Proto": "https"
        })

        port = proxy._get_client_request_port(request)

        self.assertEqual(port, 443)

    def test_get_client_request_port_with_default_ports_http(self):
        """ The port can be determined if it is the default port for the http scheme """
        request = MockRequest({
            "X-Forwarded-Host": "plm.example.com",
            "X-Forwarded-Proto": "http"
        })

        port = proxy._get_client_request_port(request)

        self.assertEqual(port, 80)
