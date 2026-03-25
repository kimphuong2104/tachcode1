# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module tests

This module provides tests for Broker Service and helper constructs for testing.
"""
# This picks a threaded reactor for nose tests to work
from nose.twistedtools import reactor  # noqa: F401

from twisted.internet.defer import succeed
from twisted.web import server
from twisted.web.test.test_web import DummyRequest


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []


def setup():
    from cdb import testcase
    testcase.run_level_setup()


# Testing helper classes for twisted resources borrowed from:
# http://findingscience.com/python/twisted/2012/02/20/testing-twisted-web-resources.html

class SmartDummyRequest(DummyRequest):
    def __init__(self, method, url, args=None, headers=None):
        DummyRequest.__init__(self, url.split('/'))
        self.method = method
        if headers:
            for k, v in headers.items():
                self.requestHeaders.addRawHeader(k, v)

        # set args
        args = args or {}
        for k, v in args.items():
            self.addArg(k, v)

    def value(self):
        return "".join(self.written)


class DummySite(server.Site):
    def get(self, url, args=None, headers=None):
        return self._request("GET", url, args, headers)

    def post(self, url, args=None, headers=None):
        return self._request("POST", url, args, headers)

    def _request(self, method, url, args, headers):
        request = SmartDummyRequest(method, url, args, headers)
        resource = self.getResourceFor(request)
        result = resource.render(request)
        return self._resolveResult(request, result)

    def _resolveResult(self, request, result):
        if isinstance(result, str):
            request.write(result)
            request.finish()
            return succeed(request)
        elif result is server.NOT_DONE_YET:
            if request.finished:
                return succeed(request)
            else:
                return request.notifyFinish().addCallback(lambda _: request)
        else:
            raise ValueError("Unexpected return value: %r" % (result,))
