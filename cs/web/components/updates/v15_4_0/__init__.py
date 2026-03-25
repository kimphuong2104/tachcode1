#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

import uuid
from cdb import sqlapi


_tb_stmt = "toolbar_id='webui_navigation' AND cdb_module_id NOT LIKE 'cs%'"


class MoveCustomerWebAppsNavEntries(object):
    def run(self):
        # Fetch all toolbar entries not defined by cs.* packages
        toolbar_cfgs = sqlapi.RecordSet2('cdb_toolbar_cfg', _tb_stmt)

        if not len(toolbar_cfgs):
            return

        # Iterate over each entry and move the configured URL to
        # csweb_primary_nav
        for cfg in toolbar_cfgs:
            op = sqlapi.RecordSet2('cdb_operations',
                                   "name='%s' AND classname='%s'" %
                                   (sqlapi.quote(cfg.op_name),
                                    sqlapi.quote(cfg.classdefname)))

            if not len(op):
                continue

            op = op[0]
            oid = "%s" % uuid.uuid4()
            op_url = op.url.replace('"', '').replace("'", "")
            sqlapi.SQLinsert("INTO csweb_primary_nav (pos, cdb_module_id,"
                             " app_link, cdb_icon_id, ausgabe_label, tooltip,"
                             " nav_section, cdb_object_id) VALUES ('%d', '%s',"
                             " '%s', '%s', '%s', '%s', '%s', '%s')" %
                             (cfg.ordering if cfg.ordering else 1000,
                              sqlapi.quote(cfg.cdb_module_id),
                              sqlapi.quote(op_url),
                              sqlapi.quote(cfg.icon_id),
                              sqlapi.quote(op.label),
                              sqlapi.quote(op.label),
                              "body", oid))

            # Fetch all related role_ids assigned to this operation
            role_set = sqlapi.RecordSet2('cdb_op_owner',
                                         "name='%s' AND classname='%s'" %
                                         (sqlapi.quote(cfg.op_name),
                                          sqlapi.quote(cfg.classdefname)))

            if not len(role_set):
                continue

            # Move all assigned role_ids to csweb_primary_nav_owner
            for op_role in role_set:
                sqlapi.SQLinsert("INTO csweb_primary_nav_owner (role_id,"
                                 " cdb_module_id, nav_object_id) VALUES"
                                 " ('%s', '%s', '%s')" %
                                 (sqlapi.quote(op_role.role_id),
                                  sqlapi.quote(op_role.cdb_module_id),
                                  sqlapi.quote(oid)))

pre = [MoveCustomerWebAppsNavEntries]
