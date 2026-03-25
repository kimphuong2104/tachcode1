#!/usr/bin/env python
# -*- python -*- coding: UTF-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     powerreportsqueue.py
# Author:   js
# Creation: 13.01.10
# Purpose:

"""
Module powerreportsqueue.py

This is the documentation for the powerreportsqueue.py module.
"""

__docformat__ = "restructuredtext en"

from cdb.uberserver.mqsvc import MessageQueueService
from cs.tools.powerreports.reportserver.report_queue_arg import (
    cleanup_orphaned_job_params,
)


class PowerReportQueue(MessageQueueService):
    """PowerReport Queue service implementation"""

    def __init__(self, site):
        cleanup_orphaned_job_params()
        super(PowerReportQueue, self).__init__(
            site,
            "Power Reports Queue",
            None,
            "cs.tools.powerreports.reportserver.report_queue",
        )

    def check_config(self):
        """Check whether given configuration is valid from point of this
        service. Raise an Exception in case of error"""
        from cdb.platform.uberserver import Services

        my_name = self.fqpyname()
        my_services = Services.get_services(my_name, None)
        if len(my_services) > 1:
            raise RuntimeError(
                "There is more than one %s"
                " configured in this instance.:\n%s"
                % (my_name, "\n".join([str(svc) for svc in my_services]))
            )

    @classmethod
    def install(cls, svcname, host, site, arguments="", options=None, *args, **kwargs):
        """Install basic default configuration for this service"""
        if not svcname:
            svcname = cls.fqpyname()
        defopts = {"--user": "powerreports_service"}
        if options:
            defopts.update(options)
        from cdb.platform.uberserver import Services

        # Nur einmal pro Instanz
        if not Services.get_services(svcname, None):
            return super(PowerReportQueue, cls).install(
                svcname, host, site, arguments, defopts, *args, **kwargs
            )
