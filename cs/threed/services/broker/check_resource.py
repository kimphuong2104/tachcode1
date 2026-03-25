# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module check_resource

This module contains twisted classes and other utility to provide Broker Service
information to the health analysis tool.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import json
import logging
import sys

from twisted.web import resource
from twisted.web import server

from cs.threed.services.broker import util as brokerUtil
from cs.threed.services.broker import authentication

from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource

# Exported objects
__all__ = ["CheckResource"]


LOG = logging.getLogger(__name__)


def has_valid_jwt_token(request):
    scope = "threed/broker/health_tool"
    return authentication.validate_request(request, scope)


class UnsupportedResource(resource.Resource):
    isLeaf = True

    def render_HEAD(self, request):
        return brokerUtil.default_head_response(request)

    def render_OPTIONS(self, request):
        return brokerUtil.default_options_response(request)

    def render_GET(self, request):
        origin = brokerUtil.get_last_header(request, 'origin', '*')
        request.setHeader("content-type", "text/plain; charset=utf-8")
        request.setHeader('Access-Control-Allow-Origin', origin)

        if not has_valid_jwt_token(request):
            return ""
        return "unsupported"

class EchoServerProtocol(WebSocketServerProtocol):
    def onMessage(self, payload, isBinary):
        self.sendMessage(payload, isBinary)


class CheckStatsResource(resource.Resource):
    isLeaf = True

    def __init__(self, broker_state_manager):
        resource.Resource.__init__(self)
        self.sm = broker_state_manager
        from cdb.platform.uberserver import Services
        self.cdb_site = Services.get_current_site()

    def render_HEAD(self, request):
        return brokerUtil.default_head_response(request)

    def render_OPTIONS(self, request):
        return brokerUtil.default_options_response(request)

    def render_GET(self, request):
        brokerUtil.default_head_response(request)

        if not has_valid_jwt_token(request):
            return ""

        def send_response(server_status, req, cdb_site, worker_count):
            data = {
                "cdb_site": cdb_site,
                "worker_count": worker_count,
                "server_status": server_status,
            }
            if sys.platform.startswith("win"):
                from cdb.plattools import winservice
                data["running_inside_service"] = winservice.running_as_service()
            req.write(json.dumps(data))
            req.finish()

        def send_error(err, req, cdb_site, worker_count):
            try:
                errMsg = "%s" % (err.value)
            except AttributeError:
                errMsg = "%s" % (err)
            data = {
                "cdb_site": cdb_site,
                "worker_count": worker_count,
                "server_status": {"error": errMsg}
            }
            req.write(json.dumps(data))
            req.finish()
            LOG.warning("Failed service check with error: %s", errMsg)

        def _response_failed(err, deferred_call):
            deferred_call.cancel()

        resp_site = self.cdb_site
        resp_wc = self.sm.worker_count()
        call = self.sm.get_hoops_server_status()
        call.addCallback(send_response, request, resp_site, resp_wc)
        call.addErrback(send_error, request, resp_site, resp_wc)
        request.notifyFinish().addErrback(_response_failed, call)
        return server.NOT_DONE_YET


class CheckResource(resource.Resource):
    isLeaf = False

    def __init__(self, broker_state_manager, openHandshakeTimeout,
                 closeHandshakeTimeout):
        resource.Resource.__init__(self)
        unsupportedResource = UnsupportedResource()
        wsFactory = WebSocketServerFactory()
        wsFactory.protocol = EchoServerProtocol
        wsFactory.setProtocolOptions(
            webStatus=False,
            openHandshakeTimeout=openHandshakeTimeout,
            closeHandshakeTimeout=closeHandshakeTimeout)
        self.putChild(b"pongws", WebSocketResource(wsFactory))
        self.putChild(b"stats", CheckStatsResource(broker_state_manager))

    def render_HEAD(self, request):
        return brokerUtil.default_head_response(request)

    def render_OPTIONS(self, request):
        return brokerUtil.default_options_response(request)

    def render_GET(self, request):
        origin = brokerUtil.get_last_header(request, 'origin', '*')
        request.setHeader("content-type", "text/plain; charset=utf-8")
        request.setHeader('Access-Control-Allow-Origin', origin)
        if not has_valid_jwt_token(request):
            return ""
        return "ok"


# Guard importing as main module
if __name__ == "__main__":
    pass
