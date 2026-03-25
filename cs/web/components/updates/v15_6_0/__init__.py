#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

import uuid

from cdb import comparch, ddl, sqlapi


class RemoveNotNullConstraint(object):
    """
    Remove the remaining ``NotNull`` constraint of the deleted attributes
    from ``csweb_outlet_position_owner`` in the DD
    """
    def run(self):
        table = ddl.Table("csweb_outlet_position_owner")
        if table:
            col = table.getColumn("pos")
            if col:
                col.notnull=0
                table.modifyAttributes(col)
            col = table.getColumn("priority")
            if col:
                col.notnull=0
                table.modifyAttributes(col)


class MoveOldWebuiNavigationEntries(object):
    def run(self):
        # Fetch all old webui_navigation toolbar entries
        toolbar_cfgs = sqlapi.RecordSet2('cdb_toolbar_cfg',
                                         "toolbar_id='webui_navigation'")

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

        sqlapi.SQLdelete("FROM cdb_toolbar_cfg WHERE toolbar_id='webui_navigation'")


class AdjustOutletPositionSetupFQPynames(object):
    def run(self):
        rs = sqlapi.RecordSet2('csweb_outlet_child')
        child_initializer = {r.outlet_child_name: r.setup_fqpyname for r in rs}
        outlet_pos = sqlapi.RecordSet2('csweb_outlet_position',
                                       ("cdb_module_id like '%s.%%'" % comparch.get_dev_namespace()))
        for pos in outlet_pos:
            if pos.setup_fqpyname and \
               pos.setup_fqpyname == child_initializer.get(pos.child_name):
                pos.update(setup_fqpyname="")


pre = [RemoveNotNullConstraint, MoveOldWebuiNavigationEntries]
post = [AdjustOutletPositionSetupFQPynames]
