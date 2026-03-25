#!/usr/bin/env powerscript
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


__revision__ = "$Id: __init__.py 154332 2017-02-21 14:43:33Z khi $"

from cdb import transactions


class AddServiceUser(object):
    """
    Add the cs.threed.service user with his standard assignments.
    """
    def run(self):
        from cdb.comparch import modules
        mod = modules.Module.ByKeys('cs.threed.hoops')
        mc = mod.getMasterContent()
        usr = mc.findItem('angestellter', personalnummer='cs.threed.service')
        roles = mc.KeywordQuery('cdb_global_subj', subject_id='cs.threed.service')
        if usr and not usr.exists():
            usr.insertIntoDB()
        for role in roles:
            if not role.exists():
                role.insertIntoDB()


class AddServiceUserOptions(object):
    """
    Add the new mandatory service options for the cs.threed services
    """
    def run(self):
        from cdb import sqlapi

        login = "cs_threed_service"
        cdb_services = [
            "cs.threed.services.ThreeDBrokerService",
            "cs.threed.services.threedcs.ThreedConversionServer",
            "cs.threed.services.threedcs.ThreedConversionServer2",
            "cs.threed.services.threedcs.ThreedConversionServer3",
            "cs.threed.services.threedcs.ThreedConversionServer4",
        ]

        with transactions.Transaction():
            for svcname in cdb_services:
                svcs = sqlapi.RecordSet2(
                    "cdbus_svcs", "svcname='{}'".format(svcname)
                )
                for svc in svcs:
                    rs = sqlapi.RecordSet2(
                        "cdbus_svcopts",
                        "svcid='%s' AND name='%s'" % (
                            sqlapi.quote(svc.svcid),
                            "--user"
                        )
                    )
                    if rs:
                        for r in rs:
                            r.update(value=login)
                    else:
                        sqlapi.Record(
                            "cdbus_svcopts",
                            svcid=svc.svcid,
                            name="--user",
                            value=login
                        ).insert()


pre = []
post = [AddServiceUserOptions, AddServiceUser]


if __name__ == "__main__":
    AddServiceUserOptions().run()
    AddServiceUser().run()
