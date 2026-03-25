#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import


class Updater(object):
    """
    Add the aspostingqueue user with his standard assignments. We have
    to use an update script because role assignments are usually not
    updated automatically.
    """

    def run(self):
        from cdb import sqlapi
        from cdb.comparch import content, modules

        user = sqlapi.RecordSet2("angestellter", "personalnummer='aspostingqueue'")
        if not user:
            m = modules.Module.ByKeys("cs.activitystream")
            for rel, key in [
                ("angestellter", "personalnummer"),
                ("cdb_global_subj", "subject_id"),
            ]:
                content_filter = content.ModuleContentFilter([rel])
                mc = modules.ModuleContent(
                    m.module_id, m.std_conf_exp_dir, content_filter
                )
                for mod_content in mc.getItems(rel).values():
                    if mod_content.getAttr(key) == "aspostingqueue":
                        try:
                            mod_content.insertIntoDB()
                            user = sqlapi.RecordSet2(
                                "angestellter", "personalnummer='aspostingqueue'"
                            )
                        except Exception:  # nosec # pylint: disable=W0703
                            pass  # Already there
        # The component architecture does not transport the password
        if user and not user[0].password:
            user[0].update(  # nosec
                password=u"$pbkdf2-sha256$29000$A6CUUsqZE4KwFgIgBA"
                "CgFA$TCjnSFL5LMCd8ZrXwHbAom9U2LTzfAKMP221fF01WDo"
            )
