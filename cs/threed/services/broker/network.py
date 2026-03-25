# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module network

This module provides network and server setup related utility for Broker Service.
This module is based on Uberserver Web UI setup from May 2019.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id:  pko $"

import logging
import socket
from twisted.internet import defer

from cdb.uberserver import secure
from cdb.uberserver import usutil
from cdb.twistedutil.tls import makeCertificateOptions
from cdb.twistedutil import use_default_dualstack

# Exported objects
__all__ = ["ServiceNetwork"]

LOG = logging.getLogger(__name__)


class ServiceNetwork(object):

    def __init__(self, no_http2=False, iface=""):
        super(ServiceNetwork, self).__init__()
        self.no_http2 = no_http2
        self.iface = iface
        self.ssl_opts = {}

    def attach_site(self, site, reactor, port):
        self.ssl_mode = secure.get_ssl_mode()
        self.ssl_opts = secure.merge_global_ssl_opts(secure.parse_ssl_opts({}))
        return self._setup_tcp_listener(reactor, port, site)

    def _setup_tcp_listener(self, reactor, listen_port, site):
        """
        Start to listen on the given port
        """
        ifaces4, ifaces6 = self._decode_iface(self.iface, listen_port)

        scheme, deferred = self._setup_endpoints(reactor, site, listen_port,
                                                 ifaces4, ifaces6)

        deferred.addCallback(self._set_port, scheme)
        deferred.addErrback(self._listen_error)
        return deferred

    def _set_port(self, listeners, scheme):
        if LOG.isEnabledFor(logging.INFO):
            for tcpport in listeners:
                iface, port = self._get_conn_infos(tcpport)
                url = "%s://%s:%s" % (scheme, self.normalize_iface(iface), port)
                LOG.info("Broker Service listening to url: %s", url)
        return listeners

    def _listen_error(self, fail):
        LOG.error("Failed to LISTEN on socket: %s" % fail)
        return

    def _setup_endpoints(self, reactor, site, listen_port, ifaces4, ifaces6):
        """
        Create twisted Endpoints for the interfaces and ports
        """
        scheme = "https" if self.ssl_mode else "http"
        # Handle dual stack sockets, only bind v6 for those
        if len(ifaces4) == 1 and len(ifaces6) == 1 and use_default_dualstack(ifaces4[0], ifaces6[0]):
            LOG.info("Binding to '%s' (IPv4) and '%s' (IPv6)", ifaces4[0], ifaces6[0])
            chain = [(scheme, ifaces6[0], 6)]
        else:
            # windows has dualstack, but needs a setsockopt we cannot
            # easily call here..
            chain = []
            for iface4 in ifaces4:
                LOG.info("Binding to %s", iface4)
                chain.append((scheme, iface4, 4))
            for iface6 in ifaces6:
                LOG.info("Binding to %s", iface6)
                chain.append((scheme, iface6, 6))

        if self.ssl_mode:
            kwargs = {}
            if self.no_http2:
                kwargs['acceptableProtocols'] = [b'http/1.1']
            kwargs['phrase'] = secure.make_callback(self.ssl_opts)
            ctx = makeCertificateOptions(self.ssl_opts, **kwargs)
        else:
            ctx = None

        deferred = self.setup_endpoint_chain(
            reactor, site, listen_port, chain, ctx)
        return scheme, deferred

    def _decode_iface(self, iface, port):
        """
        Decode the interface option into proper ifac4/iface6 options
        """
        iface4 = ['']
        iface6 = ['::']
        if iface:
            if usutil.Hostname.is_ip4_address(iface):
                # IPv4, only listen on v4
                iface4 = self.resolve_iface(iface, port, socket.AF_INET)
                iface6 = []
            elif usutil.Hostname.is_ip6_address(iface):
                # IPv6, only listen on v6
                iface4 = []
                iface6 = self.resolve_iface(iface, port, socket.AF_INET6)
            else:
                # Hostname, use hostname for binding
                iface4 = self.resolve_iface(iface, port, socket.AF_INET)
                iface6 = self.resolve_iface(iface, port, socket.AF_INET6)
        return iface4, iface6

    def resolve_iface(self, iface, port, family=socket.AF_INET):
        """Resolve our local interface names
        """
        try:
            addrs = socket.getaddrinfo(iface, port, family)
        except socket.gaierror:
            LOG.exception("Failed to resolve interface: %s", iface)
            return []
        # get sockadddress
        return list(set([addr[4][0] for addr in addrs]))

    def _get_conn_infos(self, conn):
        """Extract interface and port info from a connected endpoint"""
        name = conn.socket.getsockname()
        if len(name) == 4:
            # IPv6
            iface, port, flowinfo, scopeid = name
            iface = "[%s]" % iface
        else:
            iface, port = name
        return iface, port

    @defer.inlineCallbacks
    def setup_endpoint_chain(self, reactor, site, port, chain, ctxfac, *args):
        from twisted.internet.error import CannotListenError
        real_port = 0
        listeners = []
        exceptions = []
        for ifs in chain:
            ep = self.get_srv_endpoint(reactor, port, ctxfac, ifs)
            try:
                conn = yield ep.listen(site)
            except CannotListenError as exc:
                exceptions.append(exc)
            except Exception:
                raise
            else:
                iface, real_port = self._get_conn_infos(conn)
                listeners.append(conn)

            # Take the OS choosen port for all protocols
            if port == 0 and real_port:
                port = real_port

        # Hosts with disabled IPv6 often have totally broken DNS too,
        # e.g. they resolved localhost => ::1, but cannot bind it, or
        # similar issues.
        #
        # So we are graceful and only raise an exception if none of
        # our listeners could be set up, otherwise we just log the facts.
        if not listeners:
            for exc in exceptions:
                self.log_failed_listen(exc, logging.ERROR)
            raise RuntimeError("Failed to setup any TCP listeners")
        else:
            for exc in exceptions:
                self.log_failed_listen(exc, logging.WARNING)

        defer.returnValue(listeners)

    def get_srv_endpoint(self, reactor, port, ctxfac, ifs):
        """
        Turn a given network interface into the appropriate server endpoint
        """
        from twisted.internet.endpoints import (
            SSL4ServerEndpoint,
            TCP4ServerEndpoint,
            TCP6ServerEndpoint
        )
        if ifs[0] == "http" and ifs[2] == 4:
            return TCP4ServerEndpoint(reactor, port, interface=ifs[1])
        elif ifs[0] == "http" and ifs[2] == 6:
            return TCP6ServerEndpoint(reactor, port, interface=ifs[1])
        elif ifs[0] == "https":
            return SSL4ServerEndpoint(reactor, port, ctxfac, interface=ifs[1])
        else:
            raise RuntimeError("Cannot create Endpoint for interface", ifs)

    def log_failed_listen(self, exc, log_level):
        LOG.log(log_level, "Failed to listen on TCP interface "
                "{0.interface} port {0.port}: {0.socketError}".format(exc))

    def normalize_iface(self, iface):
        """Map INADDR_ANY to the fully qualified name"""
        iface_normalized = iface.strip('[]')
        if usutil.Hostname.is_inaddr_any(iface_normalized):
            return usutil.Hostname(usutil.getfqdn())
        if usutil.Hostname(iface_normalized).is_localhost():
            return 'localhost'
        else:
            return iface
