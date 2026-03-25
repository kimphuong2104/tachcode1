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

from cdb import sqlapi, typeconversion
from cs.tools import powerreports as PowerReports

from cs.pcs.issues import Issue


def _get_date_from_legacy_format(date_str):
    if date_str == "":
        return None
    return typeconversion.from_legacy_date_format(date_str).date()


class ProjectIssues(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        t_id = kwargs["task_id"]
        prio = kwargs["priority"]
        cf = kwargs["close_flag"]
        fd = kwargs["fromdate"]
        cdbDateFrom = _get_date_from_legacy_format(fd)
        td = kwargs["to"]
        cdbDateTo = _get_date_from_legacy_format(td)
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        for i in p.Issues:
            cdbDateIssue = i.reported_at
            if (  # pylint: disable=too-many-boolean-expressions
                (not t_id or t_id == i.task_id)
                and (not prio or prio == i.priority)
                and (not cf or cf == i.close_flag)
                and (
                    not i.reported_at
                    or (fd == "" or cdbDateFrom <= cdbDateIssue)
                    and (td == "" or cdbDateIssue <= cdbDateTo)
                )
            ):
                result += PowerReports.ReportData(self, i)
        return result

    def getSchema(self):
        return PowerReports.XSDType(self.CARD, Issue, provider=self)

    def getArgumentDefinitions(self):
        return {
            "task_id": sqlapi.SQL_CHAR,
            "fromdate": sqlapi.SQL_CHAR,
            "to": sqlapi.SQL_CHAR,
            "priority": sqlapi.SQL_CHAR,
            "close_flag": sqlapi.SQL_CHAR,
        }

    def getClass(self):
        return Issue


class TaskIssues(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        prio = kwargs["priority"]
        cf = kwargs["close_flag"]
        fd = kwargs["fromdate"]
        cdbDateFrom = _get_date_from_legacy_format(fd)
        td = kwargs["to"]
        cdbDateTo = _get_date_from_legacy_format(td)
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        for i in p.Issues:
            cdbDateIssue = i.reported_at
            if (  # pylint: disable=too-many-boolean-expressions
                (not prio or prio == i.priority)
                and (not cf or cf == i.close_flag)
                and (
                    not i.reported_at
                    or (fd == "" or cdbDateFrom <= cdbDateIssue)
                    and (td == "" or cdbDateIssue <= cdbDateTo)
                )
            ):
                result += PowerReports.ReportData(self, i)
        return result

    def getSchema(self):
        return PowerReports.XSDType(self.CARD, Issue, provider=self)

    def getArgumentDefinitions(self):
        return {
            "fromdate": sqlapi.SQL_CHAR,
            "to": sqlapi.SQL_CHAR,
            "priority": sqlapi.SQL_CHAR,
            "close_flag": sqlapi.SQL_CHAR,
        }

    def getClass(self):
        return Issue
