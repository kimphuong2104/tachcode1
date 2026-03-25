#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
"""
Module services

Service for the workflow message queue.
"""

from cdb.platform.uberserver import Services
from cdb.uberserver.mqsvc import MessageQueueService

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

__all__ = [
    'WFServer',
]


class WFServer(MessageQueueService):
    """WFServer service implementation"""
    def __init__(self, site):
        super(WFServer, self).__init__(
            site, "Workflow Server", None, "cs.workflow.wfqueue")

    @classmethod
    def install(cls, svcname, host, site, arguments="", options=None, *args, **kwargs):
        if not svcname:
            svcname = cls.fqpyname()

        # Set User
        if not options:
            options = "--language en"

        # Set autostart
        kwargs["autostart"] = True

        return super(WFServer, cls).install(svcname, host, site, options, *args, **kwargs)

    @classmethod
    def get_service_user(cls):
        svcs = Services.get_services("%s.%s" % (cls.__module__, cls.__name__), site=None)
        if svcs:
            return svcs[0].get_option("--user")
        return None
