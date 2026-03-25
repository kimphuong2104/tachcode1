#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb.comparch import protocol


class EmptyNotesModuleId:
    def run(self):
        protocol.logMessage("Tyring to empty cdb_module_id from cdbpcs_notes_content.")
        try:
            table = sqlapi.SQLdescribe("select * from cdbpcs_notes_content")
            table.get_type("cdb_module_id")
        except KeyError:
            protocol.logMessage("cdb_module_id not found...")
            return
        sqlapi.SQLupdate("cdbpcs_notes_content set cdb_module_id = ''")
        protocol.logMessage("Done")


pre = []
post = [EmptyNotesModuleId]
