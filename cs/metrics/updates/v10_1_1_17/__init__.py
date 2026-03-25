#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Some imports
from cdb import sqlapi


class AddQueueOptions(object):
    """
    Adds the new mandatory service options to the service
    cs.metrics.qc_engine.QCAggregationEngine
    """
    def run(self):
        svcs = sqlapi.RecordSet2("cdbus_svcs",
                                 "svcname='cs.metrics.qc_engine.QCAggregationEngine'")
        for svc in svcs:
            cond = "svcid='%s'" % sqlapi.quote(svc.svcid)
            opt_names = [svc_opt.name
                         for svc_opt in sqlapi.RecordSet2("cdbus_svcopts", cond)]

            new_opts = {
                "--buffer_size": "",
                "--description": "",
                "--poll_wait": "5",
                "--priority": "",
                "--timeout": "",
                "--user": "caddok"
            }
            for name, val in new_opts.items():
                if name not in opt_names:
                    sqlapi.Record("cdbus_svcopts",
                                  svcid=svc.svcid,
                                  name=name,
                                  value=val).insert()


pre = []
post = [AddQueueOptions]


if __name__ == "__main__":
    AddQueueOptions().run()
