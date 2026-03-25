#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
SystemPostingQueue Service for Activity Stream.
"""

from __future__ import absolute_import

from cdb.uberserver.mqsvc import MessageQueueService

__all__ = ["SystemPostingQueue"]
__docformat__ = "restructuredtext en"


class SystemPostingQueue(MessageQueueService):
    """
    Queue to generate system postings
    """

    def __init__(self, site):
        super(SystemPostingQueue, self).__init__(
            site, "System Posting Queue", None, "cs.activitystream.posting_queue"
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
                " configured in this instance.:\n%s" % (my_name, "\n".join(my_services))
            )

    @classmethod
    def install(cls, svcname, host, site, arguments="", options=None, *args, **kwargs):
        """Install basic default configuration for this service"""
        if not svcname:
            svcname = cls.fqpyname()

        defopts = {"--user": "aspostingqueue"}
        if options:
            defopts.update(options)

        from cdb.platform.uberserver import Services

        # Remove deprecated service if available
        depr_services = Services.get_services(
            "cdb.uberserver.services.blog.SystemPostingQueue", None
        )
        if depr_services:
            for depr_svc in depr_services:
                depr_svc.Delete()
        # Nur einmal pro Instanz
        if not Services.get_services(svcname, None):
            kwargs["autostart"] = kwargs.get("autostart", True)
            return super(SystemPostingQueue, cls).install(
                svcname, host, site, arguments, defopts, *args, **kwargs
            )
        return None
