# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb.comparch.pk_upgrade import PKUpgrade

class OutletPositionPKUpdate(PKUpgrade):

        def change_db_content(self):
            from cdb import ddl, sqlapi
            from cdb.ddl import Char
            t = ddl.Table(self.table_name)
            if not t.hasColumn('outlet_position_identifier'):
                # ensure that the table has the column
                col = Char('outlet_position_identifier', 40)
                t.addAttributes(col)

            for r in sqlapi.RecordSet2(self.table_name):
                r.update(outlet_position_identifier = "%s_%s" % (r.pos, r.priority))

        def get_new_pk(self, old_pk, data, new_pk, module_id):
            if new_pk["outlet_position_identifier"] is None:
                new_pk["outlet_position_identifier"] = "%s_%s" % (old_pk.get('pos'), old_pk.get('priority'))

            return new_pk

class OutletPositionOwnerPKUpdate(PKUpgrade):

        def change_db_content(self):
            from cdb import ddl, sqlapi
            from cdb.ddl import Char
            t = ddl.Table(self.table_name)
            if not t.hasColumn('outlet_position_identifier'):
                # ensure that the table has the column
                col = Char('outlet_position_identifier', 40)
                t.addAttributes(col)

            for r in sqlapi.RecordSet2(self.table_name):
                r.update(outlet_position_identifier = "%s_%s" % (r.pos, r.priority))

        def get_new_pk(self, old_pk, data, new_pk, module_id):
            if new_pk["outlet_position_identifier"] is None:
                new_pk["outlet_position_identifier"] = "%s_%s" % (old_pk.get('pos'), old_pk.get('priority'))

            return new_pk


upgrades = [PKUpgrade("cs.web.components",
                      "csweb_dialog_hook",
                      "csweb_dialog_hook",
                      ["dialog_name", "hook_name"],
                      ["dialog_name", "hook_name", "attribut"]),
            OutletPositionPKUpdate("cs.web.components",
                                   "csweb_outlet_position",
                                   "csweb_outlet_position",
                                   ["outlet_name", "classname", "pos", "priority"],
                                   ["outlet_name", "classname", "outlet_position_identifier"]),
            OutletPositionOwnerPKUpdate("cs.web.components",
                                        "csweb_outlet_position_owner",
                                        "csweb_outlet_position_owner",
                                        ["outlet_name", "classname", "pos", "priority", "role_id"],
                                        ["outlet_name", "classname", "outlet_position_identifier", "role_id"])
            ]
