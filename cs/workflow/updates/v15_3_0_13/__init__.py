#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import ast
from cdb import sqlapi
from cdb.comparch import content
from cdb.comparch import modules
from cdb.comparch import protocol

WF_SVCUSER = "cs.workflow.svcuser"

class UpdateWFServices(object):
    def run(self):
        try:
            from cdb.platform.uberserver import Services
        except ImportError:
            # Skip Update-Task - we seem to run with CE 16
            protocol.logMessage("Skip UpdateWFServices - no uberserver")
            return
        wf_server = "cs.workflow.services.WFServer"
        wf_svcs = Services.KeywordQuery(svcname=wf_server)

        for svc in wf_svcs:
            try:
                args = ast.literal_eval(svc.arguments)
            except (ValueError, SyntaxError):
                continue

            new_args = u"--svcuser {}".format(
                args.get("--svcuser", WF_SVCUSER))
            svc.Update(arguments=new_args)

        protocol.logMessage("updated {} {} service configurations".format(
            len(wf_svcs), wf_server))


class EnsureServiceUser(object):
    "Always re-insert workflow service user and role assignments"
    def run(self):
        m = modules.Module.ByKeys("cs.workflow")
        for rel, key in [("angestellter", "personalnummer"),
                         ("cdb_global_subj", "subject_id")]:
            content_filter = content.ModuleContentFilter([rel])
            mc = modules.ModuleContent(
                m.module_id, m.std_conf_exp_dir, content_filter)

            for mod_content in mc.getItems(rel).values():
                if mod_content.getAttr(key) == "cs.workflow.svcuser":
                    try:
                        # Effectively revert patch
                        mod_content.insertIntoDB()
                    except:
                        pass  # Already there


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
                protocol.logMessage(("{0.amount}x\t"
                      "status {0.status}:\t"
                      "completing_ok {0.completing_ok}".format(stats)))


pre = []
post = [UpdateWFServices, EnsureServiceUser, InitializeSuccessFlag]
