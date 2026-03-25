#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


class CleanupPreviewUserSettings(object):
    """
    Remove old Preview user settings
    """
    def run(self):
        from cdb import sqlapi
        sqlapi.SQLdelete("FROM cdb_usr_setting WHERE setting_id = 'cs.webcomponents.cs-vp-bom-web-bommanager-Settings' AND (setting_id2 ='threed_preview' OR setting_id2 = 'preview_tab_detached' OR setting_id2 = 'preview_tab_embedded')")


class RemoveXbimProperty(object):
    """
    Deletes the no longer needed property "xbim"
    """
    def run(self):
        from cdb import sqlapi
        sqlapi.SQLdelete("FROM cdb_prop WHERE attr = 'xbim'")
        sqlapi.SQLdelete("FROM cdb_prop_desc WHERE attr = 'xbim'")


class AddEbomBomType(object):
    def run(self):
        from cdb import sqlapi
        from cs.vp.bom import get_ebom_bom_type
        ebom_bom_type = get_ebom_bom_type()

        sqlapi.SQLupdate(
            "teile_stamm SET type_object_id = '%s' WHERE type_object_id = '' OR type_object_id IS NULL" %
            ebom_bom_type.cdb_object_id
        )


pre = []
post = [CleanupPreviewUserSettings, RemoveXbimProperty, AddEbomBomType]


if __name__ == "__main__":
    CleanupPreviewUserSettings().run()
    RemoveXbimProperty().run()
    AddEbomBomType().run()
