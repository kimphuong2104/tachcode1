#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com


from cdb.comparch import content, modules, protocol
from cdb.platform.uberserver import Services


class UpdateWFServices(object):
    "Remove svcuser argument from service arguments."
    def run(self):
        svcuser_arg = "--svcuser"
        wf_server = "cs.workflow.services.WFServer"
        wf_svcs = Services.KeywordQuery(svcname=wf_server)

        updated = 0
        for svc in wf_svcs:
            if not svc.arguments:
                continue

            args = svc.arguments.split()

            if svcuser_arg in args:
                user_arg_index = args.index(svcuser_arg)
                svc.Update(arguments=" ".join(
                    args[0:user_arg_index] + args[user_arg_index + 2:]))
                updated += 1

        protocol.logMessage("updated {} {} service configurations".format(
            updated, wf_server))


class EnsureTaskContexts(object):
    """Always re-insert new cs.taskmanager contexts"""

    __tables__ = [
        "cs_tasks_context_tree",
        "cs_tasks_context_tree_relships",
    ]

    def run(self):
        protocol.logMessage("reverting patches in {}".format(self.__tables__))

        module = modules.Module.ByKeys("cs.workflow")
        for table_name in self.__tables__:
            content_filter = content.ModuleContentFilter([table_name])
            mc = modules.ModuleContent(
                module.module_id,
                module.std_conf_exp_dir,
                content_filter,
            )
            reverted = 0

            for mod_content in mc.getItems(table_name).values():
                try:
                    mod_content.insertIntoDB()  # Effectively revert patch
                    reverted += 1
                except:  # nosec # noqa: E722
                    pass  # Already there

            if reverted:
                protocol.logMessage(
                    "  {}: reverted {} patches".format(
                        module.module_id, reverted))


pre = []
post = [UpdateWFServices, EnsureTaskContexts]
