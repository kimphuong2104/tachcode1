#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Custom data providers
"""

__revision__ = "$Id$"

from operator import itemgetter

from cdb import sqlapi, typeconversion
from cs.tools import powerreports as PowerReports

from cs.pcs.efforts import TimeSheet


def _get_date_from_legacy_format(date_str):
    if date_str == "":
        return None
    return typeconversion.from_legacy_date_format(date_str).date()


class ProjectEfforts(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        t_id = kwargs["task_id"]
        fd = kwargs["fromdate"]
        cdbDateFrom = _get_date_from_legacy_format(fd)
        td = kwargs["to"]
        cdbDateTo = _get_date_from_legacy_format(td)

        p_id = kwargs["person_id"]
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        order = kwargs["ordercode"]

        if not order:
            order = "effort_id"
        myList = []
        for i in p.TimeSheets:
            cdbDateTs = i.day
            if (  # pylint: disable=too-many-boolean-expressions
                (not t_id or t_id == i.task_id)
                and (not i.day or fd == "" or cdbDateFrom <= cdbDateTs)
                and (td == "" or cdbDateTs <= cdbDateTo)
                and (not p_id or p_id == i.person_id)
            ):
                myList.append(i)

        if order != "day":
            myList = sorted(myList, key=itemgetter(order))
        else:
            myList.sort(cmpDateRep)

        for i in myList:
            data = PowerReports.ReportData(self, i)
            for t in p.Tasks:
                if t.task_id == i.task_id:
                    data["task_name"] = t.task_name
                    data["task_hyperlink"] = PowerReports.MakeReportURL(
                        t, "CDB_Modify", "task_name"
                    )
            result.append(data)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, TimeSheet)
        t.add_attr("task_name", sqlapi.SQL_CHAR)
        t.add_attr("task_hyperlink", sqlapi.SQL_CHAR)
        return t

    def getArgumentDefinitions(self):
        return {
            "task_id": sqlapi.SQL_CHAR,
            "fromdate": sqlapi.SQL_CHAR,
            "to": sqlapi.SQL_CHAR,
            "person_id": sqlapi.SQL_CHAR,
            "ordercode": sqlapi.SQL_CHAR,
        }

    def getClass(self):
        return TimeSheet


class TaskEfforts(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        fd = kwargs["fromdate"]
        cdbDateFrom = _get_date_from_legacy_format(fd)
        td = kwargs["to"]
        cdbDateTo = _get_date_from_legacy_format(td)
        p_id = kwargs["person_id"]
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        order = kwargs["ordercode"]

        if not order:
            order = "effort_id"

        myList = []
        for i in p.TimeSheets:
            cdbDateTs = i.day
            if (  # pylint: disable=too-many-boolean-expressions
                (not i.day or fd == "" or cdbDateFrom <= cdbDateTs)
                and (td == "" or cdbDateTs <= cdbDateTo)
                and (not p_id or p_id == i.person_id)
            ):
                myList.append(i)

        if order != "day":
            myList = sorted(myList, key=itemgetter(order))
        else:
            myList.sort(cmpDateRep)

        for i in myList:
            data = PowerReports.ReportData(self, i)
            data["task_name"] = p.task_name
            data["task_hyperlink"] = PowerReports.MakeReportURL(
                p, "CDB_Modify", "task_name"
            )
            result.append(data)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, TimeSheet)
        t.add_attr("task_name", sqlapi.SQL_CHAR)
        t.add_attr("task_hyperlink", sqlapi.SQL_CHAR)
        return t

    def getArgumentDefinitions(self):
        return {
            "fromdate": sqlapi.SQL_CHAR,
            "to": sqlapi.SQL_CHAR,
            "person_id": sqlapi.SQL_CHAR,
            "ordercode": sqlapi.SQL_CHAR,
        }

    def getClass(self):
        return TimeSheet


def cmpDateRep(d1, d2):
    return int(d1["day"] > d2["day"]) - int(d1["day"] < d2["day"])
