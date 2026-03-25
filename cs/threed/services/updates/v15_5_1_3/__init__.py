# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# default maximum broker service worker count
# copied from module cs.threed.services.broker_service because of twisted:
# ReactorAlreadyInstalledError: reactor already installed
# See E050737 for details
DEFAULT_MAX_WORKER_COUNT = 16


class AddMaximumWorkerCountConfiguration(object):
    """ Add a new optional service option for the cs.threed broker service.
        This option will allow user to set maximum broker service worker/cpu cores.
    """

    def run(self):
        from cdb import sqlapi
        from cdb import transactions

        cdb_service = "cs.threed.services.ThreeDBrokerService"

        with transactions.Transaction():
            svcs = sqlapi.RecordSet2(
                "cdbus_svcs", "svcname='{}'".format(cdb_service)
            )
            for svc in svcs:
                rs = sqlapi.RecordSet2(
                    "cdbus_svcopts",
                    "svcid='%s' AND name='%s'" % (
                        sqlapi.quote(svc.svcid),
                        "--max_worker_count"
                    )
                )
                # if configuration doesn't exist, add the configuration in the DB
                if not rs:
                    sqlapi.Record(
                        "cdbus_svcopts",
                        svcid=svc.svcid,
                        name="--max_worker_count",
                        value="%d" % DEFAULT_MAX_WORKER_COUNT
                    ).insert()
                # if configuration exists, update the configuration conservatively in DB
                else:
                    rs[0].update(value="%d" % DEFAULT_MAX_WORKER_COUNT)


pre = []
post = [AddMaximumWorkerCountConfiguration]


if __name__ == "__main__":
    AddMaximumWorkerCountConfiguration().run()
