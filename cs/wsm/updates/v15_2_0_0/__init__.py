#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import six

from cdb import sqlapi
from cdb.comparch import modules, content


class SetObjektArtForWsmSettings(object):
    def run(self):
        # there is only one life cycle...
        # it must be filled; otherwise the attribute "joined_status_name" is null
        sqlapi.SQLupdate("wsm_settings SET cdb_objektart = 'wsm_settings'")


class InitIndexRuleDesignation(object):
    """
    Initialize the new multi-language attribute of index rules.
    (for the standard entries)
    """

    def run(self):
        self.reset_catalog(
            module_id="cs.wsm",
            classname="index_update_rule",
            attrs_to_update=["designation_de", "designation_en"],
        )

    def reset_catalog(self, module_id, classname, attrs_to_update):
        # load module content
        m = modules.Module.ByKeys(module_id)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in six.itervalues(mc.getItems(classname)):
            rec = item._getPersistentRecord()
            if rec:
                updates = dict(
                    [
                        (attr, item.getAttr(attr))
                        for attr in attrs_to_update
                        if not rec[attr]
                    ]
                )
                if updates:
                    rec.update(**updates)


class InitBomMethodDesignation(object):
    """
    Fills the new multi-language attribute 'designation'
     for standard catalog entries.
    """

    def run(self):
        self.reset_catalog(
            module_id="cs.vp.bomcreator",
            classname="bom_method",
            attrs_to_update=["designation_de", "designation_en"],
        )

    def reset_catalog(self, module_id, classname, attrs_to_update):
        # load module content
        m = modules.Module.ByKeys(module_id)
        content_filter = content.ModuleContentFilter([classname])
        mc = content.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

        # update data as defined by module content
        for item in six.itervalues(mc.getItems(classname)):
            rec = item._getPersistentRecord()
            if rec:
                updates = dict(
                    [
                        (attr, item.getAttr(attr))
                        for attr in attrs_to_update
                        if not rec[attr]
                    ]
                )
                if updates:
                    rec.update(**updates)


pre = []
post = [SetObjektArtForWsmSettings, InitIndexRuleDesignation, InitBomMethodDesignation]
