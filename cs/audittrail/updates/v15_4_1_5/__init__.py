# coding: utf-8
from __future__ import absolute_import
import json
from cdb import sqlapi
from cdb import transactions
from cdb import ddl
from cs.audittrail import AuditTrailObjects


class CreateAuditTrailObjects(object):
    def run(self):
        with transactions.Transaction():
            rs = sqlapi.RecordSet2("cdb_audittrail")
            for r in rs:
                AuditTrailObjects.Create(object_id=r.object_id,
                                         audittrail_id=r.audittrail_object_id)


class RemoveObjectId(object):
    def run(self):
        with transactions.Transaction():
            for table in ["cdb_audittrail", "cdb_audittrail_detail", "cdb_audittrail_longtext_new",
                          "cdb_audittrail_longtext_old"]:
                t = ddl.Table(table)
                if t.hasColumn('cdb_object_id'):
                    t.dropAttributes("cdb_object_id")


pre = []
post = [CreateAuditTrailObjects, RemoveObjectId]
