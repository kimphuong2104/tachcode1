#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb.comparch import content, modules


class InstallStandardSettings(object):
    """
    Add the default settings of the module if not yet there.
    """

    def run(self):  # pylint: disable=no-self-use
        m = modules.Module.ByKeys("cs.documents")
        content_filter = content.ModuleContentFilter(["cdb_setting"])
        mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
        for item in mc.getItems("cdb_setting").values():
            if not item.exists():
                item.insertIntoDB()


pre = []
post = [InstallStandardSettings]
