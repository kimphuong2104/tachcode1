#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
from __future__ import unicode_literals
__revision__ = "$Id$"


class AddServiceUsers(object):
    """
    Add the qcaggregationengine and qccomputationengine users with his standard assignments. We have
    to use an update script because role assignments are usually not
    updated automatically.
    """
    def run(self):
        from cdb.comparch import modules
        from cdb.comparch import content
        from cdb import sqlapi
        for login, password in [('qcaggregationengine', '$pbkdf2-sha256$29000$0hqDkNJaS4nxvrd2LsVYyw$ydktQewvlXlJbIKuVfGSxbqqVBfrgKkTMMODNYeWHbc'),
                                ('qccomputationengine', '$pbkdf2-sha256$29000$LiUk5HyPUWrtPcfYO.d8rw$s9lNyEJ8IA9sS4ANySTZiICx.w1jmI6Eyim2zl4gf9s')]:
            user = sqlapi.RecordSet2("angestellter",
                                     "personalnummer='%s'" % login)
            if not user:
                m = modules.Module.ByKeys('cs.metrics')
                for rel, key in [('angestellter', 'personalnummer'),
                                 ('cdb_global_subj', 'subject_id')]:
                    content_filter = content.ModuleContentFilter([rel])
                    mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
                    for mod_content in mc.getItems(rel).values():
                        if mod_content.getAttr(key) == login:
                            try:
                                mod_content.insertIntoDB()
                                user = sqlapi.RecordSet2("angestellter",
                                                         "personalnummer='%s'" % login)
                            except Exception:
                                # Already there
                                pass
            # The component architecture does not transport the password
            if user and (not user[0].password or user[0].password == password):
                import cdbwrapc
                import os
                new_pw = cdbwrapc.get_crypted_password(login, os.urandom(32))
                user[0].update(password=new_pw)


class AddServiceUserOptions(object):
    """
    Add the new mandatory service options for the service
    cs.metrics.qc_engine.QCAggregationEngine and cs.metrics.qc_engine.QCComputationEngine
    """
    def run(self):
        from cdb import sqlapi
        svc_names_and_login_pairs = [("cs.metrics.qc_engine.QCAggregationEngine",
                                      "qcaggregationengine"),
                                     ("cs.metrics.qc_engine.QCComputationEngine",
                                      "qccomputationengine")]
        for svcname, login in svc_names_and_login_pairs:
            svcs = sqlapi.RecordSet2("cdbus_svcs", "svcname='{}'".format(svcname))
            for svc in svcs:
                cond = "svcid='%s'" % sqlapi.quote(svc.svcid)
                opt_names = [svc_opt.name
                             for svc_opt in sqlapi.RecordSet2("cdbus_svcopts", cond)]
                new_opts = {
                    "--user": login
                }
                for name, val in new_opts.items():
                    if name not in opt_names:
                        sqlapi.Record("cdbus_svcopts",
                                      svcid=svc.svcid,
                                      name=name,
                                      value=val).insert()


pre = []
post = [AddServiceUsers, AddServiceUserOptions]


if __name__ == "__main__":
    AddServiceUsers().run()
    AddServiceUserOptions().run()
