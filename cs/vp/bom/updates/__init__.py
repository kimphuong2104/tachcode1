#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#



__revision__ = "$Id$"

from cdb.comparch.cdbpkg_upgrade import Upgrade
from cdb import util
from cdb import ddl
from cdb.progress import ProgressBar
from cdb.platform.tools import CDBObjectIDFixer

class AddCDBObjectIDToBOMItem(Upgrade):

    def need_upgrade(self):
        try:
            util.tables["einzelteile"]
        except KeyError:
            # initial installation case
            return False
        return True if self.module_id == "cs.vp.bom" and not self.bom_item_has_object_id() else False

    def need_std_upgrade(self):
       return False

    def need_master_upgrade(self):
       return False

    def run(self):
        if self.bom_item_has_object_id():
            return
        table_name = "einzelteile"
        print("Adding cdb_object_id attribute to table 'einzelteile' (class bom_item)")
        table = ddl.Table(table_name)
        table.addAttributes(ddl.Char("cdb_object_id", 40, 0))
        # init cdb_object_id
        fixer = CDBObjectIDFixer(self.log, ProgressBar)
        fixer.repair_object_ids(table_name)

    def bom_item_has_object_id(self):
        return util.column_exists("einzelteile", "cdb_object_id")

    def log(self, msg):
        print(msg)

upgrades = [AddCDBObjectIDToBOMItem]
