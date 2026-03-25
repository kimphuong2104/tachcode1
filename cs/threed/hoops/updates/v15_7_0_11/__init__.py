# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
from cdb import sqlapi
from cdb.comparch import protocol
from cdb.comparch import modules
from cdb.comparch import content

class DeleteConverterObjectRules(object):
    """
    Delete the 3DC Converter object rules Documents, Items, Product and Variant
    """
    def run(self):
        deprecated_rules = ["3DC Converter Documents", "3DC Converter Item", "3DC Converter Products", "3DC Converter Variant"]
        try:
            sqlapi.SQLdelete("FROM cdb_pyrule WHERE name IN ({0})".format(", ".join(["'%s'" % rule for rule in deprecated_rules])))
        except Exception as e:
            protocol.logError("Error while deleting object rules: {0}".format(e))

        deprecated_predicates = ["3DC Converter Documents"]
        try:
            sqlapi.SQLdelete("FROM cdb_pypredicate WHERE name IN ({0})".format(", ".join(["'%s'" % predicate for predicate in deprecated_predicates])))
        except Exception as e:
            protocol.logError("Error while deleting predicate: {0}".format(e))


class InsertUserSettings(object):
    """
    Insert the cutting plane edge color entry into the user settings
    """
    def run(self):
        SETTINGS_TO_INSERT = ["cuttingplaneEdgeColor"]

        usr_settings = sqlapi.RecordSet2("cdb_usr_setting_long_txt", "setting_id='cs.webcomponents.cs-threed-hoops-web-cockpit-Settings'")
        default_values = {}

        # retrieve the default settings from the module content
        m = modules.Module.ByKeys('cs.threed.hoops')
        content_filter = content.ModuleContentFilter(["cdb_setting"])
        mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
        for mod_content in mc.getItems("cdb_setting").values():
            if mod_content.getAttr("setting_id") in ["cs.webcomponents.cs-threed-hoops-web-cockpit-Settings"]:
                default_values = json.loads(mod_content.getAttr("default_val"))



        for setting in usr_settings:
            json_dict = json.loads(setting.text)
            
            for entry in SETTINGS_TO_INSERT:
                if entry not in json_dict:
                    json_dict[entry] = default_values[entry]
                    setting.update(text=json.dumps(json_dict))

pre = []
post = [DeleteConverterObjectRules, InsertUserSettings]

if __name__ == "__main__":
    DeleteConverterObjectRules().run()
    InsertUserSettings().run()
