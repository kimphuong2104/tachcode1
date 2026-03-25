# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
The CDBService starting up and exposing the documentation portal
when running inside a CDB environment (e.g. platform)
"""

from cdb import rte
from cdb.platform.uberserver import Services
from cdb.uberserver.process import Process

from cs.docportal.cdb import CADDOK_BASE

__all__ = ['DocPortalService']

service_path_prefix = 'doc'
service_port = 11111

HTTPD_CONF = '''ProxyPass "/{base_uri}" "http://localhost:{port}"
ProxyPassReverse "/{base_uri}" "http://localhost:{port}"'''


class DocPortalService(Process):
    """The CDB Service running the DocPortal"""

    def __init__(self, site):
        super().__init__(
            site=site,
            servicename='DocPortal',
            depends=[],
            executable=rte.runtime_tool('powerscript'),
        )
        self.main_module = 'cs.docportal.app'

    @classmethod
    def install(cls, svcname, host, site, *args, **kwargs):
        """Install configuration for this service"""
        if not svcname:
            svcname = cls.fqpyname()
        with open(
            CADDOK_BASE / 'etc' / 'docportal.httpd.conf', 'w', encoding='utf-8'
        ) as f:
            f.write(HTTPD_CONF.format(base_uri=service_path_prefix, port=service_port))
        if not Services.get_services(svcname, None):
            super(DocPortalService, cls).install(svcname, host, site, *args, **kwargs)
        return cls._create_basic_configuration(
            svcname=svcname,
            host=host,
            site=site,
            arguments='',
            autostart=True,
            options={'--port': service_port},
        )

    def get_args(self, replace_opts=None):
        """Get launch arguments for the `DocPortalService`"""
        args = []
        super_args = super(DocPortalService, self).get_args()

        # extract port info from super
        for i, arg in enumerate(super_args):
            if arg == '--port':
                args += ['-p', super_args[i + 1]]
                break

        # prepend out start module in front of the options
        return ['-m', self.main_module, '-q'] + args

    def start(self):
        deferred = super(DocPortalService, self).start()
        deferred.addCallback(lambda svc: self.set_port(int(self.options()['--port'])))
        return deferred

    def set_port(self, port):
        self.node.port = port

    def stop(self):
        self.set_port(port=0)
        super(DocPortalService, self).stop()

    def is_alive(self):
        alive = super(DocPortalService, self).is_alive()
        if alive:
            # we could try to ping the service here, but that's optional
            pass
        return alive

    def get_service_url(self):
        return f'http://{self.node.hostname}/doc'
