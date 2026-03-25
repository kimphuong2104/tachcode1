#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging
import os

from cdb import rte
from cdb.platform.uberserver import Services
from cdb.uberserver.process import Process

__docformat__ = "restructuredtext en"


class DailyMailService(Process):
    __servicename__ = "Daily Activities Mailer"

    def __init__(self, site):
        toolname = rte.runtime_tool("powerscript")
        super(DailyMailService, self).__init__(
            site, self.__servicename__, None, toolname
        )

    def get_args(self):
        from cdb.comparch import modules

        mod_dir = modules.get_module_dir("cs.activitystream")
        script = os.path.join(mod_dir, u"services.py")
        args = ["--nologin", script]
        args.extend(super(DailyMailService, self).get_args())
        return args

    @classmethod
    def install(cls, svcname, host, site, *args, **kwargs):
        """Install configuration for this service."""
        if Services.get_services(svcname, None):
            return None  # Install me only once.
        super(DailyMailService, cls).install(svcname, host, site, *args, **kwargs)
        logging.getLogger(__name__).info(
            "%s: cls._create_basic_configuration(%s, autostart=True, " "options={})",
            cls.__servicename__,
            svcname,
        )
        return cls._create_basic_configuration(
            svcname, host, site, arguments="", autostart=True, options={}
        )

    def start(self):
        super(DailyMailService, self).start()
        return self

    def __str__(self):
        return "%s is %s running" % (
            self.__servicename__,
            "" if self.is_alive() else "*NOT*",
        )
