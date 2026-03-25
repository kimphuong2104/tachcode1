#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

from cdb.uberserver.mqsvc import MessageQueueService

__all__ = ["ShareObjectsServer"]


class ShareObjectsServer(MessageQueueService):
    def __init__(self, site):
        super(ShareObjectsServer, self).__init__(
            site, "Share Objects Server", None, "cs.sharing.share_objects_queue"
        )

    @classmethod
    def install(cls, svcname, host, site, arguments="", options=None, *args, **kwargs):
        if not svcname:
            svcname = cls.fqpyname()

        # Set User
        if not options:
            options = {}
        options.update({"--user": "caddok"})

        # Set autostart
        kwargs["autostart"] = True

        return super(ShareObjectsServer, cls).install(
            svcname, host, site, options, *args, **kwargs
        )

    @classmethod
    def get_service_option(cls, option):
        from cdb.platform.uberserver import Services

        svcs = Services.get_services(
            "%s.%s" % (cls.__module__, cls.__name__), site=None
        )
        if svcs:
            return svcs[0].get_option(option)
        return None

    @classmethod
    def get_service_user(cls):
        return cls.get_service_option("--user")

    @classmethod
    def get_service_language(cls):
        return cls.get_service_option("--language")
