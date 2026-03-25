#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module reports

Reports of |cs.resources|
"""

import datetime
from collections import defaultdict

from cdb import ElementsError, sqlapi
from cdb.objects import Forward, Rule
from cdb.objects.org import User
from cdb.platform.gui import Label
from cs.pcs.resources.helpers import date_from_legacy_str
from cs.tools import powerreports as PowerReports

# Exported objects
__all__ = []

fCapaMatrix = Forward("cs.pcs.resources.calculation.CapaMatrix")

WEEK = Forward("cs.pcs.resources.WEEK").__resolve__()
MONTH = Forward("cs.pcs.resources.MONTH").__resolve__()


class PersonnelLoadHelper:
    """
    Helper class. Aggregates reusable data and provides methods.
    Holds the metadata and the methods which help compute the monthly and
    weekly statistics for the report. Is used by PersonnelLoadMetaData,
    PersonnelLoadMonthlyStatistics and PersonnelLoadWeeklyStatistics classes
    """

    # XSD field names in the XSD Schema plus format types
    nameDictionary = {
        # XML name for the month field
        "XSDMonthField": "persLoadM%.2d",
        # XML name for the week field
        "XSDWeekField": "persLoadW%.3d",
        # format of the month label: "<month>(2 digits) <year>(4 digits)"
        "MonthLabelFormat": "%.2d %d",
        # format of the week label: "KW <week>(2 digits) <year>(4 digits)"
        "WeekLabelFormat": {"en": "CW %.2d %d", "de": "KW %.2d %d"},
    }

    def getXSDMonthFields(self, total_months):
        fields = []
        for monthCount in range(1, total_months + 1):
            # XSD Schema header name for month
            fields.append(self.nameDictionary["XSDMonthField"] % (monthCount))
        return fields

    def getXSDWeekFields(self, total_weeks):
        fields = []
        for weekCount in range(1, total_weeks + 1):
            # XSD Schema header name for week
            fields.append(self.nameDictionary["XSDWeekField"] % (weekCount))
        return fields

    def getMonthLabelStrings(self, total_months, past_months, currentMDate):
        headers = []
        monthRange = list(range(-past_months, 0)) + list(
            range(total_months - past_months)
        )
        for monthCount in monthRange:
            if monthCount < 0:
                startDate = self.sub_months(currentMDate, -monthCount)
            elif monthCount > 0:
                startDate = self.add_months(currentMDate, monthCount)
            else:
                startDate = currentMDate
            # string to display as row header
            headers.append(
                self.nameDictionary["MonthLabelFormat"]
                % (startDate.month, startDate.year)
            )
        return headers

    def getWeekLabelStrings(self, total_weeks, past_weeks, currentWDate, language="en"):
        assert language in self.nameDictionary["WeekLabelFormat"], (  # nosec
            f"{language} needs to be added to the list of language formats"
        )
        headers = []
        weekRange = list(range(-past_weeks, 0)) + list(range(total_weeks - past_weeks))
        for weekCount in weekRange:
            startDate = currentWDate + datetime.timedelta(weeks=weekCount)
            startIsoCal = startDate.isocalendar()
            headers.append(
                self.nameDictionary["WeekLabelFormat"][language]
                % (
                    # iso week no, iso year no
                    startIsoCal[1],
                    startIsoCal[0],
                )
            )
        return headers

    def firstDayOfTheMonth(self, date):
        """First day of the current month as datetime.datetime object"""
        return date.replace(day=1)

    def firstDayOfTheWeek(self, date):
        """Monday of this week as datetime.datetime object"""
        return date - datetime.timedelta(days=date.weekday())

    def getMonthList(self, total_months, past_months, currentMDate):
        """
        Returns a list containing date information about total_months months,
        out of which, past_months months are in the past
        """
        monthList = []
        counter = 1
        monthRange = list(range(-past_months, 0)) + list(
            range(total_months - past_months)
        )
        for monthCount in monthRange:
            monthDict = {}
            monthDict["XSDFieldName"] = (
                self.nameDictionary["XSDMonthField"] % counter
            )  # XSD Schema field name
            # datetime.datetime object representing the start date computed by
            # adding/subtracting months from currentMDate
            if monthCount < 0:
                monthDict["startDate"] = self.sub_months(currentMDate, -monthCount)
            elif monthCount > 0:
                monthDict["startDate"] = self.add_months(currentMDate, monthCount)
            else:
                monthDict["startDate"] = currentMDate
            # datetime.datetime object representing the end date
            monthDict["endDate"] = self.add_months(
                monthDict["startDate"], 1
            ) - datetime.timedelta(days=1)
            monthList.append(monthDict)
            counter = counter + 1
        return monthList

    def getWeekList(self, total_weeks, past_weeks, currentWDate):
        """
        Returns a list containing date information about total_weeks weeks,
        out of which, past_weeks weeks are in the past
        """
        weekList = []
        counter = 1
        weekRange = list(range(-past_weeks, 0)) + list(range(total_weeks - past_weeks))
        for weekCount in weekRange:
            weekDict = {}
            weekDict["XSDFieldName"] = self.nameDictionary["XSDWeekField"] % counter
            weekDict["startDate"] = currentWDate + datetime.timedelta(weeks=weekCount)
            weekDict["endDate"] = weekDict["startDate"] + datetime.timedelta(days=6)
            weekList.append(weekDict)
            counter = counter + 1
        return weekList

    def add_months(self, date, n_mon):
        """Add n_mon months to date object. Adds months calendaristically only
        at the level of months, since a month is variable in length. If the end
        result is calendaristically invalid, the day is fixed but the month
        delta n_mon does not change"""
        month_loc = date.month
        year_loc = date.year
        day_loc = date.day
        while n_mon > 0:
            if month_loc + n_mon > 12:
                n_mon = n_mon - 13 + month_loc
                year_loc = year_loc + 1
                month_loc = 1
            else:
                month_loc = month_loc + n_mon
                n_mon = 0
        # Check that the date is valid. If not, it must be 29th, 30th or 31st.
        # Decrease the day until the date becomes valid, thus not losing months
        dateResult = None
        while dateResult is None:
            try:
                dateResult = datetime.datetime(year_loc, month_loc, day_loc)
            except ValueError:
                day_loc = day_loc - 1
        return datetime.datetime(year_loc, month_loc, day_loc)

    def sub_months(self, date, n_mon):
        """
        Subtract n_mon months from date object. Only at the level of months,
        since a month is variable in length. If the end result is
        calendaristically invalid, the day is fixed but the month
        delta n_mon does not change
        """
        month_loc = date.month
        year_loc = date.year
        day_loc = date.day
        while n_mon > 0:
            if month_loc - n_mon < 1:
                n_mon = n_mon - month_loc
                year_loc = year_loc - 1
                month_loc = 12
            else:
                month_loc = month_loc - n_mon
                n_mon = 0
        # Check that the date is valid. If not, it must be 29th, 30th or 31st
        # Decrease the day until the date becomes valid, thus not losing months
        dateResult = None
        while dateResult is None:
            try:
                dateResult = datetime.datetime(year_loc, month_loc, day_loc)
            except ValueError:
                day_loc = day_loc - 1
        return datetime.datetime(year_loc, month_loc, day_loc)

    @staticmethod
    def get_rule_of_project_applicability():
        """
        :rtype:
            cdb.objects.Rule
        :return:
            returns the instance of the object rule that defines whether a project
            is to be considered or not.
        """
        return Rule.ByKeys("cdbpcs: Active Project")

    @staticmethod
    def get_resources():
        """
        Provides all resources to be evaluated
        :rtype: list
        :return:
            list of cs.pcs.resources.pools.assignments.Resource
        """
        users = User.Query("capacity > 0 and is_resource = 1")
        return [user.Resource for user in users if user.Resource]


class PersonnelLoadMonthly(PowerReports.CustomDataProvider, PersonnelLoadHelper):
    """
    Custom Data Provider for personnel load (Mitarbeiterauslastung) with
    monthly statistics. Returns statistics per employee for current month (0),
    M months (-M) in the past and M months in the future (+M)
    """

    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_0
    total_months = 12
    past_months = 2

    def __init__(self):
        self.currentDate = self.firstDayOfTheMonth(datetime.datetime.today())

    def getData(self, parent_result, source_args, **kwargs):
        total = self.getParameter("monthsTotal")
        past = self.getParameter("monthsPast")
        if total:
            self.total_months = int(total)
        if past:
            self.past_months = int(past)
        startDate = kwargs.get("start_date", None)
        if startDate is not None:
            cdbDate = date_from_legacy_str(startDate)
            self.currentDate = self.firstDayOfTheMonth(cdbDate)

        rule = self.get_rule_of_project_applicability()
        if rule is None:
            raise ElementsError(
                "The object rule 'cdbpcs: Active Project' does not exist. "
                "Report can not be executed. Please contact your system administrator"
            )

        resources = self.get_resources()
        # list of dictionaries containing all the information
        # for each month of the report
        monthList = self.getMonthList(
            self.total_months, self.past_months, self.currentDate
        )
        pers_caps = fCapaMatrix(
            res_list=[x.cdb_object_id for x in resources],
            start_date=monthList[0]["startDate"],
            end_date=monthList[-1]["endDate"],
            prj_rule=rule,
            interval=MONTH,
        )
        result = PowerReports.ReportDataList(self)
        for resource in resources:
            rd = PowerReports.ReportData(self)
            rd["name"] = resource.name
            for monthD in monthList:
                rd[monthD["XSDFieldName"]] = pers_caps.getResourceFreeCapacities(
                    resource.cdb_object_id, monthD["startDate"]
                )
            result.append(rd)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("name", sqlapi.SQL_CHAR)
        # Add month headers to XSD Schema
        XSDMonthFields = self.getXSDMonthFields(self.total_months)
        if len(XSDMonthFields) != self.total_months:
            raise RuntimeError(
                "Number of header names doesn't match the"
                " number of months in report."
            )
        for field in XSDMonthFields:
            t.add_attr(field, sqlapi.SQL_FLOAT)
        return t

    def getArgumentDefinitions(self):
        return {"start_date": sqlapi.SQL_CHAR}


class PersonnelLoadMonthly_Labels(PowerReports.CustomDataProvider, PersonnelLoadHelper):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_0
    total_months = 12
    past_months = 2

    def __init__(self):
        self.currentDate = self.firstDayOfTheMonth(datetime.datetime.today())

    def getData(self, parent_result, source_args, **kwargs):
        total = self.getParameter("monthsTotal")
        past = self.getParameter("monthsPast")
        if total:
            self.total_months = int(total)
        if past:
            self.past_months = int(past)
        startDate = source_args.get("personnelloadmonthly-start_date", None)
        if startDate:
            cdbDate = date_from_legacy_str(startDate)
            self.currentDate = self.firstDayOfTheMonth(cdbDate)
        dataRD = PowerReports.ReportData(self)
        # User label
        language = source_args.get(
            "cdbxml_report_lang", ""
        )  # fallback to language selected by the logged in user
        dataRD["name"] = Label.ByKeys("cdbpcs_coworker").Text[language]
        # Monthly labels
        XSDMonthFields = self.getXSDMonthFields(self.total_months)
        MonthHeaderStrings = self.getMonthLabelStrings(
            self.total_months, self.past_months, self.currentDate
        )
        if len(MonthHeaderStrings) != self.total_months:
            raise RuntimeError(
                "Number of header names doesn't match the "
                "number of header strings for monthly report."
            )
        for count in range(self.total_months):
            dataRD[XSDMonthFields[count]] = MonthHeaderStrings[count]
        return dataRD

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("name", sqlapi.SQL_CHAR)
        # Add month headers to XSD Schema
        XSDMonthFields = self.getXSDMonthFields(self.total_months)
        if len(XSDMonthFields) != self.total_months:
            raise RuntimeError(
                "Number of header names doesn't match the "
                "number of months in report."
            )
        for field in XSDMonthFields:
            t.add_attr(field, sqlapi.SQL_CHAR)
        return t


class PersonnelLoadWeekly(PowerReports.CustomDataProvider, PersonnelLoadHelper):
    """
    Custom Data Provider for personnel load (Mitarbeiterauslastung) with
    weekly statistics. Returns statistics per employee for current week (0),
    W weeks (-W) in the past and W weeks in the future (+W)
    """

    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_0
    total_weeks = 52
    past_weeks = 8

    def __init__(self):
        self.currentDate = self.firstDayOfTheWeek(datetime.datetime.today())

    def getData(self, parent_result, source_args, **kwargs):
        total = self.getParameter("weeksTotal")
        past = self.getParameter("weeksPast")
        if total:
            self.total_weeks = int(total)
        if past:
            self.past_weeks = int(past)
        startDate = source_args.get("personnelloadmonthly-start_date", None)
        if startDate:
            cdbDate = date_from_legacy_str(startDate)
            self.currentDate = self.firstDayOfTheWeek(cdbDate)
        # list of dictionaries containing all the information
        # for each week of the report

        rule = self.get_rule_of_project_applicability()
        if rule is None:
            raise ElementsError(
                "The object rule 'cdbpcs: Active Project' does not exist. "
                "Report can not be executed. Please contact your system administrator"
            )

        resources = self.get_resources()
        weekList = self.getWeekList(self.total_weeks, self.past_weeks, self.currentDate)
        pers_caps = fCapaMatrix(
            res_list=[x.cdb_object_id for x in resources],
            start_date=weekList[0]["startDate"],
            end_date=weekList[-1]["endDate"],
            prj_rule=rule,
            interval=WEEK,
        )
        result = PowerReports.ReportDataList(self)
        for resource in resources:
            rd = PowerReports.ReportData(self)
            rd["name"] = resource.name
            for weekD in weekList:
                rd[weekD["XSDFieldName"]] = pers_caps.getResourceFreeCapacities(
                    resource.cdb_object_id, weekD["startDate"]
                )
            result.append(rd)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("name", sqlapi.SQL_CHAR)
        # Add week headers to XSD Schema
        XSDWeekFields = self.getXSDWeekFields(self.total_weeks)
        if len(XSDWeekFields) != self.total_weeks:
            raise RuntimeError(
                "Number of header names doesn't match the number of weeks in report."
            )
        for field in XSDWeekFields:
            t.add_attr(field, sqlapi.SQL_FLOAT)
        return t


class PersonnelLoadWeekly_Labels(PowerReports.CustomDataProvider, PersonnelLoadHelper):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_0
    total_weeks = 52
    past_weeks = 8

    def __init__(self):
        self.currentDate = self.firstDayOfTheWeek(datetime.datetime.today())

    def getData(self, pCDB_ShowObjectarent_result, source_args, **kwargs):
        total = self.getParameter("weeksTotal")
        past = self.getParameter("weeksPast")
        if total:
            self.total_weeks = int(total)
        if past:
            self.past_weeks = int(past)
        startDate = source_args.get("personnelloadmonthly-start_date", None)
        if startDate:
            cdbDate = date_from_legacy_str(startDate)
            self.currentDate = self.firstDayOfTheWeek(cdbDate)
        dataRD = PowerReports.ReportData(self)
        # User label
        language = source_args.get(
            "cdbxml_report_lang", ""
        )  # fallback to language selected by the logged in user
        dataRD["name"] = Label.ByKeys("cdbpcs_coworker").Text[language]
        # Weekly labels
        XSDWeekFields = self.getXSDWeekFields(self.total_weeks)
        WeekHeaderStrings = self.getWeekLabelStrings(
            self.total_weeks, self.past_weeks, self.currentDate, language=language
        )
        if len(WeekHeaderStrings) != self.total_weeks:
            raise RuntimeError(
                "Number of header names doesn't match the "
                "number of header strings for weekly report."
            )
        for count in range(self.total_weeks):
            dataRD[XSDWeekFields[count]] = WeekHeaderStrings[count]
        return dataRD

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("name", sqlapi.SQL_CHAR)
        # Add week headers to XSD Schema
        XSDWeekFields = self.getXSDWeekFields(self.total_weeks)
        if len(XSDWeekFields) != self.total_weeks:
            raise RuntimeError(
                "Number of header names doesn't match the number of weeks in report."
            )
        for field in XSDWeekFields:
            t.add_attr(field, sqlapi.SQL_CHAR)
        return t


class PortfolioResourceEvaluation(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def _getMonthList(self, mydate, months):
        mydate.replace(day=1)
        result = []
        for _ in range(months):
            mydate = mydate.replace(day=1)
            result.append(mydate)
            mydate += datetime.timedelta(days=31)
        return result

    def getData(self, parent_result, source_args, **kwargs):
        pool = parent_result.getObject()
        months = int(kwargs.get("months", 12))
        start = kwargs.get("start_date", None)
        if start:
            start = date_from_legacy_str(start)
        else:
            start = datetime.datetime.today()
        # remove time part but keep it as datetime to be comparable
        start = datetime.datetime(start.year, start.month, start.day)
        month_list = self._getMonthList(start, months)

        rule = Rule.ByKeys("cdbpcs: Active Project")
        objs = rule.getObjects()
        project_dict = defaultdict(list)
        for obj in objs:
            project_dict[obj.mapped_category_name] += [obj]

        result = PowerReports.ReportDataList(self)
        for month in month_list:
            matrix = fCapaMatrix(
                pool_list=[pool.cdb_object_id],
                start_date=month_list[0],
                end_date=month_list[-1],
                prj_rule=rule,
                interval=MONTH,
                eval_capacity=True,
            )
            rd = PowerReports.ReportData(self)
            rd["date"] = month
            rd["type"] = "Capacity"
            rd["value"] = matrix.getPoolCapacity(pool.cdb_object_id, month)
            result.append(rd)
        for category, projects in project_dict.items():
            p_ids = [x.cdb_project_id for x in projects]
            matrix = fCapaMatrix(
                pool_list=[pool.cdb_object_id],
                start_date=month_list[0],
                end_date=month_list[-1],
                with_prj_ids=p_ids,
                interval=MONTH,
                eval_capacity=True,
            )

            for month in month_list:
                rd = PowerReports.ReportData(self)
                rd["date"] = month
                rd["type"] = category
                rd["value"] = matrix.getPoolDemands(pool.cdb_object_id, month)
                result.append(rd)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("date", sqlapi.SQL_DATE)
        t.add_attr("type", sqlapi.SQL_CHAR)
        t.add_attr("value", sqlapi.SQL_FLOAT)
        return t

    def getArgumentDefinitions(self):
        return {"start_date": sqlapi.SQL_CHAR, "months": sqlapi.SQL_INTEGER}
