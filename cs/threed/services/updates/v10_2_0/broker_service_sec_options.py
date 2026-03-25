# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__all__ = ['AddBrokerServiceSecurityOptions']


class AddBrokerServiceSecurityOptions(object):
    """
    Add the missing service options to the broker service
    """
    def run(self):
        from cdb import sqlapi
        options = {
            "--tls_cert": '',
            "--tls_private_key": '',
        }
        cond = "svcname='cs.threed.services.ThreeDBrokerService'"
        for broker_svc in sqlapi.RecordSet2("cdbus_svcs", cond):
            db_opts = []
            opt_cond = "svcid='%s'" % (broker_svc.svcid,)
            for broker_option in sqlapi.RecordSet2("cdbus_svcopts", opt_cond):
                db_opts.append(broker_option.name)
            for opt in options:
                if opt not in db_opts:
                    sqlapi.Record("cdbus_svcopts", svcid=broker_svc.svcid,
                                  name=opt, value=options[opt]).insert()


if __name__ == "__main__":
    AddBrokerServiceSecurityOptions().run()
