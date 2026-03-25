#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


class UpdateDefaultSettings(object):
    """
    Update the default settings
    """
    def run(self):
        from cdb.comparch import modules
        from cdb.comparch import content
        m = modules.Module.ByKeys('cs.threed.hoops')
        content_filter = content.ModuleContentFilter(["cdb_setting"])
        mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
        for mod_content in mc.getItems("cdb_setting").values():
            if mod_content.getAttr("setting_id") in ["cs.webcomponents.cs-threed-hoops-web-cockpit-Settings"]:
                # if settings exist, update settings destructively in DB
                if mod_content.exists():
                    try:
                        mod_content.deleteFromDB()
                        mod_content.insertIntoDB()
                    except:
                        pass
                # if no default settings, insert into DB
                else:
                    try:
                        mod_content.insertIntoDB()
                    except:
                        # Already there
                        pass


class SetHealthAnalysisToolProperty(object):
    """
    Set Health Analysis Tool Property and Description
    """
    def run(self):
        from cdb.comparch import modules
        from cdb.comparch import content

        classes_to_update = ["cdb_prop", "cdb_prop_desc"]

        m = modules.Module.ByKeys('cs.threed.hoops')
        for classname in classes_to_update:
            content_filter = content.ModuleContentFilter([classname])
            mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
            for mod_content in mc.getItems(classname).values():
                if mod_content.getAttr("attr") in ["3dhc"]:
                    # if attr exists, update attr destructively in DB
                    if mod_content.exists():
                        try:
                            mod_content.deleteFromDB()
                            mod_content.insertIntoDB()
                        except:
                            pass
                    # if attr found, insert into DB
                    else:
                        try:
                            mod_content.insertIntoDB()
                        except:
                            # Already there
                            pass


pre = []
post = [UpdateDefaultSettings, SetHealthAnalysisToolProperty]


if __name__ == "__main__":
    UpdateDefaultSettings().run()
    SetHealthAnalysisToolProperty().run()
