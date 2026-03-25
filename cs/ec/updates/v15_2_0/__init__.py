#!/usr/bin/env powerscript
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.comparch import modules
from cdb.comparch import content

MODULE_ID = "cs.ec"


class UpdateCatalogs(object):
    def run(self):
        self.update_catalogs()

    def update_catalogs(self):
        self.reset_catalog(classname='cdbecm_ec_categ', attrs_to_update=['name_de', 'name_en'])
        self.reset_catalog(classname='cdbecm_maturity', attrs_to_update=['name_de', 'name_en'])

    def reset_catalog(self, classname, attrs_to_update):
        # load module content
        m = modules.Module.ByKeys(MODULE_ID)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m. std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in mc.getItems(classname).values():
            rec = item._getPersistentRecord()
            if rec:
                updates = dict([(attr, item.getAttr(attr)) for attr in attrs_to_update if not rec[attr]])
                if updates:
                    rec.update(**updates)


pre = []
post = [UpdateCatalogs]
