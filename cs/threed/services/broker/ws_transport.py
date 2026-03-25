# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ws_transport

This module provides twisted constructs for WebSocket Transport.
"""

import logging

from twisted.internet import defer
from twisted.internet import reactor

from cs.threed.services.broker import authentication
from cs.threed.services.broker import util as brokerUtil

from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.twisted.websocket import WebSocketClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.resource import WebSocketResource
from autobahn.websocket import types

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ["WebsocketTransportProtocol"]

LOG = logging.getLogger(__name__)


class WebSocketTransportServerFactory(WebSocketServerFactory):
    def __init__(self, sm):
        super(WebSocketTransportServerFactory, self).__init__()
        self.sm = sm
    def buildProtocol(self, *args, **kwargs):
        prot = super(WebSocketTransportServerFactory, self).buildProtocol(*args, **kwargs)
        prot.sm = self.sm
        return prot
class WebSocketTransportResource(WebSocketResource):
    pass
class DestEndpointForwardingProtocol(WebSocketClientProtocol):
    def onConnect(self, response):
        LOG.debug("Established websocket connection with hoops "
                  "endpoint: %s (headers=%s, extensions=%s)",
                  self.transport.getPeer(), response.headers,
                  response.extensions)
        LOG.debug("Endpoint connected: %s", self.transport.getPeer())
        if self.factory._sourceProtocol._destConnection:
            self.factory._sourceProtocol._destConnection.callback(True)
    def onMessage(self, payload, isBinary):
        if self.factory._sourceProtocol:
            self.factory._sourceProtocol.sendMessage(payload, isBinary)
        else:
            LOG.warning("sending websocket data into void (%s)",
                        self.transport.getPeer())
    def onClose(self, wasClean, code, reason):
        if self.factory._sourceProtocol:
            LOG.info("Dropping websocket connection with endpoint: %s. Reason: %s",
                 self.transport.getPeer(), reason)
            self.factory._sourceProtocol.dropConnection()
class DestEndpointForwardingFactory(WebSocketClientFactory):
    def __init__(self, sourceProtocol):
        super(DestEndpointForwardingFactory, self).__init__()
        self._sourceProtocol = sourceProtocol
        self._proto = None
    def buildProtocol(self, addr):
        self._proto = DestEndpointForwardingProtocol()
        self._proto.factory = self
        return self._proto
class WebsocketTransportProtocol(WebSocketServerProtocol):
    def __init__(self):
        super(WebSocketServerProtocol, self).__init__()
        openHandshakeTimeout = brokerUtil.read_env_param(
        "THREED_WS_OPEN_ENDPOINT_TIMEOUT", 60.0)
        closeHandshakeTimeout = brokerUtil.read_env_param(
        "THREED_WS_CLOSE_ENDPOINT_TIMEOUT", 60.0)
        self._destConnection = defer.Deferred()
        self._destFactory = DestEndpointForwardingFactory(self)
        self._destFactory.setProtocolOptions(
            openHandshakeTimeout=openHandshakeTimeout,
            closeHandshakeTimeout=closeHandshakeTimeout)
    @defer.inlineCallbacks
    def onConnect(self, request):
        postpath = request.path.split("/")[2:]
        LOG.debug("Established websocket connection with client: %s, "
                  "(protocols=%s, headers=%s, extensions=%s)",
                  self.transport.getPeer(), request.protocols,
                  request.headers, request.extensions)
        access_token = request.params.get("access_token")
        if postpath:
            self.forwarded_port = int(postpath[0])
            scope = self.sm.pop_endpoint_scope(self.forwarded_port)
            if not access_token or not access_token[0] or \
                    not authentication.validate_token(access_token[0], scope):
                raise types.ConnectionDeny(types.ConnectionDeny.FORBIDDEN, "Forbidden")
            self._destFactory.setSessionParameters(protocols=request.protocols)
            yield reactor.connectTCP("localhost", self.forwarded_port, self._destFactory)
            LOG.debug("Waiting for endpoint connection (%s)", self.forwarded_port)
            yield self._destConnection
            LOG.debug("Waiting for endpoint connection (%s): Done", self.forwarded_port)
            defer.returnValue(request.protocols[0] if request.protocols else None)
        else:
            raise Exception("Unspecified resource")
    def onMessage(self, payload, isBinary):
        if self._destFactory._proto:
            self._destFactory._proto.sendMessage(payload, isBinary)
        else:
            LOG.warning("sending websocket data into void (%s)",
                        self.forwarded_port)
    def onClose(self, wasClean, code, reason):
        LOG.info("Dropping websocket connection with client: %s. Reason: %s",
                 self.transport.getPeer(), reason)
        if self._destFactory._proto:
            self._destFactory._proto.dropConnection()



# Guard importing as main module
if __name__ == "__main__":
    pass
