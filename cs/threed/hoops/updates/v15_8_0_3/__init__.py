# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class MigrateJobParameters(object):
    """
    Migrate job parameters from acs paramDict to threed_hoops_job_params
    """

    def run(self):
        import json

        from cdb import acs
        from cdb import sqlapi
        from cdb import util

        from cdb.comparch import protocol
        from cdb.mq import NoPayloadDirectory

        job_recs = sqlapi.RecordSet2(table="mq_acs", condition="plugin='hoops'",
                          addtl="ORDER BY cdbmq_priority, cdbmq_id")

        acsqueue = acs.getQueue()
        all_existing_jobs = [acsqueue.job_by_id(job.cdbmq_id) for job in job_recs]

        for job in all_existing_jobs:
            params = None

            try:
                params = job.getParameters()
            except NoPayloadDirectory:
                protocol.logMessage("CDBMQ_PAYLOADDIR is not defined. Nothing to migrate.")
                return

            if params is None:
                params = {}

            params_str = json.dumps(params)
            util.text_write("threed_hoops_job_params", ['job_id'], [job.id()], params_str)

pre = []
post = [MigrateJobParameters]

if __name__ == "__main__":
    MigrateJobParameters().run()
