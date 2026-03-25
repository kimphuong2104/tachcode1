#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Custom data providers
"""

__revision__ = "$Id$"

from operator import itemgetter

from cdb import sqlapi
from cs.tools import powerreports as PowerReports

from cs.pcs.checklists import Checklist, ChecklistItem


class QualityGates(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        qualityGate = kwargs["checklist_id"]
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()

        for i in p.Checklists:
            if i.type == "QualityGate" and (
                not qualityGate or qualityGate == f"{i.checklist_id}"
            ):
                data = PowerReports.ReportData(self, i)
                result.append(data)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, Checklist)
        return t

    def getClass(self):
        return Checklist


class QualityGatesItems(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        ko_criterion = kwargs["ko_criterion"]
        my_list = []

        for i in p.ChecklistItems:
            if (
                (ko_criterion == "0")
                or (ko_criterion == "1" == f"{i.ko_criterion}")
                or (not ko_criterion)
            ):
                my_list.append(i)

        my_list = sorted(my_list, key=itemgetter("ko_criterion"), reverse=True)

        for i in my_list:
            data = PowerReports.ReportData(self, i, ["cdbpcs_cli_txt"])
            mapping = {
                "rot": 49,
                "gelb": 51,
                "gruen": 101,
                "nicht_relevant": 19,
                "clear": "",
            }
            if data["rating_id"] in mapping:
                data["rating_xml"] = mapping[data["rating_id"]]
            result.append(data)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, ChecklistItem)
        t.add_attr("rating_xml", sqlapi.SQL_INTEGER)
        t.add_attr("cdbpcs_cli_txt", sqlapi.SQL_CHAR)
        return t

    def getClass(self):
        return ChecklistItem
