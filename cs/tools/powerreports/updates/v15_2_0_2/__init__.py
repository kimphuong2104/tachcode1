# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


class AddServiceUser(object):
    """
    Add the powerreports_service user with his standard assignments. We have to use
    an update script because role assignments are usually not updated automatically.
    """

    def run(self):
        # Add the new service user
        from cdb.comparch import content, modules

        m = modules.Module.ByKeys("cs.tools.powerreports")
        for rel, key in [
            ("angestellter", "personalnummer"),
            ("cdb_global_subj", "subject_id"),
        ]:
            content_filter = content.ModuleContentFilter([rel])
            mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
            for mod_content in list(mc.getItems(rel).values()):
                if mod_content.getAttr(key) == "powerreports_service":
                    try:
                        mod_content.insertIntoDB()
                    except:  # noqa  # pylint: disable=W0702 # nosec
                        pass  # already exists

        # Now associate all "default" report services with the new service user. We don't know
        # the names of derived services, possibly created by the customer. Their options have to
        # be manually corrected.
        from cdb.platform.uberserver import Services

        for default_svcname in [
            "cs.tools.powerreports.powerreports_queue.PowerReportQueue",
            "cs.tools.powerreports.powerreports_server.PowerReportsServer",
        ]:
            for svc in Services.KeywordQuery(svcname=default_svcname):
                svc.set_option("--user", "powerreports_service")


pre = [AddServiceUser]
post = []


if __name__ == "__main__":
    AddServiceUser().run()
