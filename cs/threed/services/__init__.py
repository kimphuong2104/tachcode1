#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import os
import random
import tempfile
from urllib.parse import urlparse

from cdb import rte
from cdb import CADDOK

from cdb.platform.uberserver import Services
from cdb.uberserver.process import Process
from cdb.uberserver.iservice import ISSL
from cdb.uberserver import usutil

# Exported objects
__all__ = ['ThreeDBrokerService']


LOG = logging.getLogger(__name__)


class ProcessDead(RuntimeError):
    """The process died."""
    pass


class InvalidPortError(RuntimeError):
    """An invalid port number was written to the port file."""
    pass


_SERVICES = []
_ENDPOINTS = None
_USER_ENDPOINT = None


def get_services(refresh=False):
    """Return all active and inactive threed broker services on all sites."""
    global _SERVICES
    if _SERVICES and not refresh:
        return _SERVICES
    svcprefix = ThreeDBrokerService.fqpyname()
    svcs = Services.get_all_services(None)
    _SERVICES = [svc for svc in svcs
                 if svc.svcname and svc.svcname.startswith(svcprefix) and svc.get_url() is not None]
    return _SERVICES


def get_broker_endpoint(same_site_only=False, refresh=False):
    """Choose one single available 3DC Broker Service and return its endpoint data."""
    global _USER_ENDPOINT
    if _USER_ENDPOINT and not refresh:
        return _USER_ENDPOINT
    endpoints = get_broker_endpoints(same_site_only, refresh)
    _USER_ENDPOINT = random.choice(endpoints) if endpoints else None
    return _USER_ENDPOINT


def get_broker_endpoints(same_site_only=False, refresh=False):
    """Return endpoint data from all available 3DC Broker Services.

    It will prefer the Broker Service on the same site and if not found, it will
    take all available on other sites.
    Only active broker services will be considered.

    Note: It is not the url of the hoops broker server, but of the 3DC Broker Service.

    :param same_site_only: Limit the result list to services on the same site
                           as the callee.
    :param refresh: Disables caching and enforces new DB requests

    :return: Empty list if there is no active threed broker services to be found.
             Otherwise it is the list of matched broker services each in
             form of a dictionary with keys 'hostname', 'port' and 'url'.
    """
    global _ENDPOINTS
    if _ENDPOINTS and not refresh:
        return _ENDPOINTS
    result = []
    found_svcs = None
    services = get_services(refresh)
    if services:
        svc = None
        # take broker svc on current site
        mysite = Services.get_current_site()
        mysite_svcs = [s for s in services if s.active and s.site == mysite
                       and s.port > 0]
        if mysite_svcs:
            found_svcs = mysite_svcs
        elif not same_site_only:
            # or take the first available if none on the same site found
            active_svcs = [s for s in services if s.active and s.port > 0]
            found_svcs = active_svcs
        if found_svcs:
            for svc in found_svcs:
                svc_data = {}
                svc_data["hostname"] = svc.hostname
                svc_data["port"] = svc.port
                svc_data["url"] = _get_external_service_url(svc)
                result.append(svc_data)
            _ENDPOINTS = result
    return result


def _get_external_service_url(svc):
    external_url = svc.Options.KeywordQuery(name='--external_url')
    if len(external_url) == 0 or external_url[0].value == '':
        return svc.get_url()
    return external_url[0].value


class ThreeDBrokerService(Process, ISSL):
    __servicename__ = "3D Viewer Streaming Broker"
    counter = 1

    def __init__(self, site):
        super(ThreeDBrokerService, self).__init__(
            site, self.__servicename__, None, rte.runtime_tool("powerscript"))
        self.modulename = "cs.threed.services.broker_service"
        self.program_name = "threed_broker_service"

    def get_args(self, *args, **kwargs):
        args = ["--program-name", self.program_name,
                "-m", self.modulename,
                '-q']
        user_args = super(ThreeDBrokerService, self).get_args()
        hostname = usutil.getfqdn()

        pairs = zip(user_args[::2], user_args[1::2])
        for arg, value in pairs:
            if arg == "--authentication":
                if ("%s" % value).lower() in ["true", "1"]:
                    LOG.error("3DC Broker Service parameter '--authentication' "
                              "is now replaced by an always on solution. "
                              "(see release notes for 3D Connect)")
            elif arg == "--user":
                args = ["--user", value] + args
            elif arg in ["--disable_http2"]:
                if ("%s" % value).lower() in ["true", "1"]:
                    args.append(arg)
            elif arg == '--external_url':
                continue
            else:
                args.append(arg)
                args.append(value)

        args.extend(["--hostname", hostname])
        args.extend(["--interface", self.node.interface])
        args.extend(["--statusfile", self.portfile.name])
        args.extend(["--id", "%d" % (self.counter, )])
        return args

    def check_config(self):
        """Check whether given configuration is valid from point of this
        service. Raise an Exception in case of error"""
        my_name = self.fqpyname()
        my_site = Services.get_current_site()
        my_services = Services.get_services(my_name, my_site)
        if len(my_services) > 1:
            raise RuntimeError("There is more than one active %s"
                               " configured in this instance." % (my_name,))

    @classmethod
    def install(cls, svcname, host, site, *args, **kwargs):
        """ Install configuration for this service.
        """
        if not svcname:
            svcname = cls.fqpyname()
        if not Services.get_services(svcname, None):
            super(ThreeDBrokerService, cls).install(svcname, host, site,
                                                    *args, **kwargs)
            return cls._create_basic_configuration(
                svcname,
                host,
                site,
                arguments="",
                autostart=True,
                options={
                    "--port": '11179',
                    "--max_spawn_count": "200",
                    "--spawn_start_port": "11200",
                    "--csr_enabled": "1",
                    "--ssr_enabled": "0",
                    "--user": "cs_threed_service",
                    "--disable_http2": "1",
                    "--max_worker_count": "16",
                    "--external_url": ""
                })

    def start(self):
        self.portfile = tempfile.NamedTemporaryFile(suffix=".port",
                                                    prefix="threed_broker",
                                                    dir=CADDOK.TMPDIR,
                                                    delete=False)

        try:
            deferred = super(ThreeDBrokerService, self).start()
        except Exception:
            self._remove_portfile(None)
            LOG.exception("Failed starting ThreeDBrokerService")
            return None

        deferred.addCallback(self._check_portfile)
        deferred.addErrback(self._remove_portfile)
        return deferred

    def stop(self):
        # If the service is not alive, it is already stopped
        if not super(ThreeDBrokerService, self).is_alive():
            return None

        result = super(ThreeDBrokerService, self).stop()
        self.set_port(0)
        self._remove_portfile(None)
        return result

    def _remove_portfile(self, failure):
        if not self.portfile:
            return
        try:
            self.portfile.close()
        except (IOError, ValueError):
            pass
        try:
            os.unlink(self.portfile.name)
        except OSError:
            pass
        self.portfile = None

    def _check_portfile(self, svc):
        """Poll the portfile for a valid port number of the service"""
        TIMEOUT = 300.0

        def matcher(content):
            if not super(ThreeDBrokerService, self).is_alive():
                raise ProcessDead()

            if content:
                try:
                    port = int(content)
                except ValueError:
                    raise InvalidPortError("Invalid Port received or "
                                           "portfile corrupt: %s" % content)
                if 0 < port < 65536:
                    return True
                else:
                    raise InvalidPortError("Port out of valid range 1-65535 "
                                           "received: %s" % content)
            return False

        poller = usutil.FilePoller(poll_file_fd=self.portfile,
                                   poll_timeout=TIMEOUT,
                                   matchfunc=matcher,
                                   delete_file=False)

        poll_deferred = poller.run()
        poll_deferred.addCallback(self._setup_port)
        poll_deferred.addErrback(self._port_error)
        return poll_deferred

    def _setup_port(self, content):
        """Set the port in the database"""
        try:
            port = int(content)
            # check is performaned by matcher, so assert here
            assert 0 < port < 65536, "Invalid Port passed"
            self.set_port(port)
        except ValueError:
            pass
        finally:
            self._remove_portfile(None)

        # The next callback expects a svc instance, so return self
        return self

    def _port_error(self, failure):
        """No port number found, handle error cases."""
        # stop the server first
        self.stop()

        # check what failed and re-raise all other exceptions
        ex = failure.check(usutil.Timeout, InvalidPortError, ProcessDead)
        if ex == usutil.Timeout:
            LOG.error("Timeout occurred while waiting for "
                      "ThreeDBrokerService to start")
        elif ex == InvalidPortError:
            LOG.error(failure.getErrorMessage())
        elif ex == ProcessDead:
            LOG.error("ThreeDBrokerService died.")
        return failure

    @staticmethod
    def get_endpoints(svc):
        endpts = list()
        url_comps = ThreeDBrokerService._get_svc_url_comps(svc)
        if url_comps.port is None:
            endpts.append("%s://%s" % (url_comps.scheme, url_comps.hostname))
        else:
            endpts.append("%s://%s:%s" % (
                url_comps.scheme, url_comps.hostname, url_comps.port))
        endpts.append("%s://%s:*" % (
            "wss" if url_comps.scheme == "https" else "ws",
            url_comps.hostname))
        return endpts

    @staticmethod
    def _get_svc_url_comps(svc):
        url = _get_external_service_url(svc)
        return urlparse(url)


class ThreeDBrokerService2(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #2"
    counter = 2


class ThreeDBrokerService3(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #3"
    counter = 3


class ThreeDBrokerService4(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #4"
    counter = 4


class ThreeDBrokerService5(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #5"
    counter = 5


class ThreeDBrokerService6(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #6"
    counter = 6


class ThreeDBrokerService7(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #7"
    counter = 7


class ThreeDBrokerService8(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #8"
    counter = 8


class ThreeDBrokerService9(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #9"
    counter = 9


class ThreeDBrokerService10(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #10"
    counter = 10


class ThreeDBrokerService11(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #11"
    counter = 11


class ThreeDBrokerService12(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #12"
    counter = 12


class ThreeDBrokerService13(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #13"
    counter = 13


class ThreeDBrokerService14(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #14"
    counter = 14


class ThreeDBrokerService15(ThreeDBrokerService):
    __servicename__ = "3D Viewer Streaming Broker #15"
    counter = 15
