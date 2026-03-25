#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import ast
import os
import shutil
from cdb import CADDOK
from cdb import sqlapi
from cdb.comparch import protocol
from cdb.platform.uberserver import Services


class UpdateWFServices(object):
    def run(self):
        wf_server = "cs.workflow.services.WFServer"
        wf_svcs = Services.KeywordQuery(svcname=wf_server)
        updated = 0

        for svc in wf_svcs:
            if svc.arguments.find("--language") == -1:
                new_args = u"{} --language de".format(svc.arguments)
                svc.Update(arguments=new_args)
                updated += 1

        protocol.logMessage("updated {} {} service configurations".format(
            updated, wf_server))


class InitWFQueueConfigFile(object):
    def run(self):
        conf = "wfqueue.conf"
        destination = os.path.join(CADDOK.BASE, "etc", conf)

        if os.path.exists(destination):
            protocol.logMessage(
                "Configuration file '{}' already exists".format(destination))
        else:
            source = os.path.join(os.path.dirname(__file__), conf)
            shutil.copyfile(source, destination)
            protocol.logMessage(
                "Configuration file '{}' successfully written".format(
                    destination))


class InitializeSuccessFlag(object):
    def run(self):
        records = len(sqlapi.RecordSet2(
            sql="SELECT 1 FROM cdbwf_process WHERE completing_ok IS NULL"))

        if records:
            for success, condition in [
                (1, "status NOT IN (30, 40)"),
                (0, "status IN (30, 40)"),
            ]:
                rows = sqlapi.SQLupdate(
                    "cdbwf_process "
                    "SET completing_ok={} "
                    "WHERE cdb_objektart='cdbwf_process' "
                    "AND {}".format(success, condition))

                protocol.logMessage(
                    "updated {} workflows: completing_ok={}".format(
                        rows, success))

            stats_stmt = (
                "SELECT COUNT(*) amount, status, completing_ok "
                "FROM cdbwf_process "
                "GROUP BY status, completing_ok")

            for stats in sqlapi.RecordSet2(sql=stats_stmt):
                protocol.logMessage((
                    "{0.amount}x\t"
                    "status {0.status}:\t"
                    "completing_ok {0.completing_ok}".format(stats)))


pre = []
post = [UpdateWFServices, InitWFQueueConfigFile, InitializeSuccessFlag]
