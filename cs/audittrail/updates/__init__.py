#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb import sqlapi, cdbuuid, transactions, ddl
from cdb.comparch.pk_upgrade import PKUpgrade


class AuditTrailPKUpdate(PKUpgrade):
    def change_db_content(self):
        with transactions.Transaction():
            t = ddl.Table(self.table_name)
            if not t.hasColumn('audittrail_object_id'):
                # ensure that the table has the column
                col = ddl.Char('audittrail_object_id', 40)
                t.addAttributes(col)
            rs = sqlapi.RecordSet2(self.table_name)
            for r in rs:
                r.update(audittrail_object_id=r.cdb_object_id)

    def get_new_pk(self, old_pk, data, new_pk, module_id):
        if new_pk["audittrail_object_id"] is None:
            new_pk["audittrail_object_id"] = old_pk.get('cdb_object_id')
        return new_pk


class AuditTrailDetailPKUpdate(PKUpgrade):
    def change_db_content(self):
        with transactions.Transaction():
            t = ddl.Table(self.table_name)
            if not t.hasColumn('detail_object_id'):
                # ensure that the table has the column
                col = ddl.Char('detail_object_id', 40)
                t.addAttributes(col)
            rs = sqlapi.RecordSet2(self.table_name)
            for r in rs:
                r.update(detail_object_id=r.cdb_object_id)

    def get_new_pk(self, old_pk, data, new_pk, module_id):
        if new_pk["detail_object_id"] is None:
            new_pk["detail_object_id"] = old_pk.get('cdb_object_id')
        return new_pk


class AuditTrailDetailLongTextNewPKUpdate(PKUpgrade):
    def change_db_content(self):
        with transactions.Transaction():
            t = ddl.Table(self.table_name)
            if not t.hasColumn('detail_object_id'):
                # ensure that the table has the column
                col = ddl.Char('detail_object_id', 40)
                t.addAttributes(col)
            rs = sqlapi.RecordSet2(self.table_name)
            for r in rs:
                r.update(detail_object_id=r.cdb_object_id)

    def get_new_pk(self, old_pk, data, new_pk, module_id):
        if new_pk["detail_object_id"] is None:
            new_pk["detail_object_id"] = old_pk.get('cdb_object_id')
        return new_pk


class AuditTrailDetailLongTextOldPKUpdate(PKUpgrade):
    def change_db_content(self):
        with transactions.Transaction():
            t = ddl.Table(self.table_name)
            if not t.hasColumn('detail_object_id'):
                # ensure that the table has the column
                col = ddl.Char('detail_object_id', 40)
                t.addAttributes(col)
            rs = sqlapi.RecordSet2(self.table_name)
            for r in rs:
                r.update(detail_object_id=r.cdb_object_id)

    def get_new_pk(self, old_pk, data, new_pk, module_id):
        if new_pk["detail_object_id"] is None:
            new_pk["detail_object_id"] = old_pk.get('cdb_object_id')
        return new_pk


upgrades = [AuditTrailPKUpdate("cs.audittrail",
                               "cdb_audittrail",
                               "cdb_audittrail",
                               ["cdb_object_id"],
                               ["audittrail_object_id"]),
            AuditTrailDetailPKUpdate("cs.audittrail",
                                     "cdb_audittrail_detail",
                                     "cdb_audittrail_detail",
                                     ["cdb_object_id"],
                                     ["detail_object_id"]),
            AuditTrailDetailLongTextNewPKUpdate("cs.audittrail",
                                                "cdb_audittrail_detail",
                                                "cdb_audittrail_longtext_new",
                                                ["cdb_object_id", "zeile"],
                                                ["detail_object_id", "zeile"]),
            AuditTrailDetailLongTextOldPKUpdate("cs.audittrail",
                                                "cdb_audittrail_detail",
                                                "cdb_audittrail_longtext_old",
                                                ["cdb_object_id", "zeile"],
                                                ["detail_object_id", "zeile"]),
            ]
