#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module __init__.py

Update scripts of cs.pcs.msp 15.5.0
"""

from cdb import sqlapi
from cdb.comparch import content, modules, protocol


def revert_deleted_patch(module_id, table, **kwargs):
    m = modules.Module.ByKeys(module_id=module_id)
    content_filter = content.ModuleContentFilter([table])
    mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

    for mod_content in mc.getItems(table).values():
        mod_keys = {key: mod_content.getAttr(key) for key in list(kwargs)}
        if mod_keys == kwargs:
            try:
                # Effectively revert patch
                mod_content.insertIntoDB()
            except Exception as e:
                protocol.logError(
                    "could not revert DELETED patch "
                    f"(module {module_id}, table {table}, keys {kwargs})",
                    details_longtext=f"{e}",
                )


class InstallMSPTemplateDocument:
    """This script installs the Microsoft Project Template Document"""

    def run(self):
        # check for document
        doc = sqlapi.RecordSet2("zeichnung", "z_nummer = 'MSP_TEMPLATE'")
        if doc:
            protocol.logMessage("MSP template document already present skipping...")
            return

        protocol.logMessage("MSP template document not found trying to revert patch...")
        revert_deleted_patch(
            "cs.pcs.msp",
            "zeichnung",
            cdb_object_id="b5b7c1b3-1a68-11ea-bb02-dc4a3e92c6e8",
        )


pre = []
post = [InstallMSPTemplateDocument]
