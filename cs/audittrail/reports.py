# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
powerreport_available = False
try:
    from cs.tools import powerreports as PowerReports
    from cdb import sqlapi
    from cs.audittrail import AuditTrailObjects
    powerreport_available = True
except ImportError:
    pass


if powerreport_available:
    class AuditTrailOverview(PowerReports.CustomDataProvider):
        """ Data provider for the Audit Trail of a generic object"""
        CARD = PowerReports.N
        CALL_CARD = PowerReports.CARD_1

        def getSchema(self):
            schema = PowerReports.XSDType(self.CARD, 'cdb_audittrail_view')
            schema.add_attr('cdbxml_level', sqlapi.SQL_INTEGER)
            return schema

        def getData(self, parent_result, source_args, **kwargs):
            obj = parent_result.getObject()
            data = PowerReports.ReportDataList(self)
            auos = AuditTrailObjects.KeywordQuery(object_id=obj.cdb_object_id)
            for auo in auos:
                for auv in auo.Entries:
                    d = PowerReports.ReportData(self, auv)
                    if auv.parent:
                        d["cdbxml_level"] = 1
                    else:
                        d["cdbxml_level"] = 0
                    data += d
            return data
