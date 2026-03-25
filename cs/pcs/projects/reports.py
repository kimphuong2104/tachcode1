#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=too-many-statements,too-many-branches,too-many-locals
# pylint: disable=too-many-nested-blocks,too-many-return-statements

"""
Custom data providers
"""

import calendar  # calendar from the std. lib, not from cs.pcs.projects
import datetime

from cdb import sqlapi, ue
from cdb.objects import Rule
from cdb.objects.org import Organization
from cdb.platform import gui
from cdb.platform.gui import I18nCatalogEntry
from cs.metrics.computationrules import UpdateClock
from cs.metrics.qualitycharacteristics import (
    ClassAssociation,
    History,
    ObjectQualityCharacteristic,
    QCDefinition,
)
from cs.tools import powerreports as PowerReports

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


class ProjectEvaluationProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_N

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        for pr in parent_result:
            p = pr.getObject()
            rule = self.__class__.__name__
            if not Rule.ByKeys(name=rule):
                raise ue.Exception("cdb_pyrule_err8", rule)
            if p.MatchRule(rule):
                r = PowerReports.ReportData(self, p)
                # Hyperlink übernehmen
                r["cdbxml_hyperlink"] = pr["cdbxml_hyperlink"]

                # Kundenname
                if p.customer:
                    myOrg = Organization.ByKeys(org_id=p.customer)
                    if myOrg:
                        r["eval_customer"] = myOrg.name

                # Projektdauer
                r["eval_duration"] = p.days if p.days else 0

                # Existieren kritische offene Punkte
                criticals = len(p.getCriticalIssues())
                if criticals:
                    r["eval_critical"] = criticals

                # Zeit- und Kosteneffizienz berechnen
                (ev, pv) = p.get_ev_pv_for_project()
                cost_state = p.get_cost_state(ev)
                schedule_state = p.get_schedule_state(ev, pv)
                plan_time = p.getPlanTimeCompletion2()
                r["eval_completed"] = int(round(plan_time, 2) * 100)
                r["eval_earned_value"] = schedule_state[4]
                r["eval_planned_value"] = schedule_state[5]
                r["eval_time"] = spi = schedule_state[3]
                r["eval_cost"] = cpi = cost_state[3]
                r["eval_total"] = min(spi, cpi)

                # multilang fields
                r["mapped_category_name_de"] = p.mapped_category_name_de
                r["mapped_category_name_en"] = p.mapped_category_name_en

                result += r

        result.sort(cmpData)
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, "cdbpcs_project")
        t.add_attr("eval_earned_value", sqlapi.SQL_FLOAT)
        t.add_attr("eval_planned_value", sqlapi.SQL_FLOAT)
        t.add_attr("eval_critical", sqlapi.SQL_INTEGER)
        t.add_attr("eval_total", sqlapi.SQL_FLOAT)
        t.add_attr("eval_completed", sqlapi.SQL_INTEGER)
        t.add_attr("eval_time", sqlapi.SQL_FLOAT)
        t.add_attr("eval_cost", sqlapi.SQL_FLOAT)
        t.add_attr("eval_duration", sqlapi.SQL_INTEGER)
        t.add_attr("eval_customer", sqlapi.SQL_CHAR)
        t.add_attr("cdbxml_hyperlink", sqlapi.SQL_CHAR)
        t.add_attr("mapped_category_name_de", sqlapi.SQL_CHAR)
        t.add_attr("mapped_category_name_en", sqlapi.SQL_CHAR)
        return t

    def getClass(self):
        return Project


class ProjectMTA(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    _clock_daily = "täglich"
    _clock_weekly = "wöchentlich"
    _clock_monthly = "monatlich"
    _clock_yearly = "jährlich"
    _clock_quarterly = "vierteljährlich"
    _clock_half_yearly = "halbjährlich"
    _date_format = "%d.%m.%Y"
    _map_to_start = 1
    _map_to_end = 0
    _map_to_milestones = 1
    _map_to_project = 0

    def __init__(self):
        """get the actual possible clock update_clock values, set the default mapping mode"""
        ucs = UpdateClock.Query()
        self.ucs = {}
        self.map_mode = None
        for uc in ucs:
            self.ucs[uc.name_de] = uc.position

    def getWeekStartDate(self, date):
        """
        calculates the start date of the week in year of the given date
        """
        return date - datetime.timedelta(days=date.weekday())

    def getWeekEndDate(self, date):
        """
        calculates the end date of the week in year of the given date
        """
        return date + datetime.timedelta(days=6 - date.weekday())

    def getBorderMilestoneDates(self, milestones):
        """returns a tuple of the first/last date
        of a given list of tasks/milestones and None if there
        is no planed start/end date in all given milestones"""
        tmpDateFirst = None
        tmpDateLast = None
        for milestone in milestones:
            if milestone.start_time_fcast:
                start_time_fcast_date = milestone.start_time_fcast
                if (tmpDateFirst and start_time_fcast_date < tmpDateFirst) or (
                    not tmpDateFirst
                ):
                    tmpDateFirst = start_time_fcast_date
            if milestone.end_time_fcast:
                end_time_fcast_date = milestone.end_time_fcast
                if (tmpDateLast and end_time_fcast_date > tmpDateLast) or (
                    not tmpDateLast
                ):
                    tmpDateLast = end_time_fcast_date

        return (tmpDateFirst, tmpDateLast)

    def getIntervalMatchingDate(self, basedate, clock=_clock_daily):
        """returns the corresponding start/end basedate of the given interval, basedate and map mode"""

        def resolve(x):
            return self.ucs[x] if x in self.ucs else None

        clock = int(clock)
        if clock == resolve(self._clock_daily):
            # daily
            return basedate
        elif clock == resolve(self._clock_weekly):
            # weekly
            if self.map_mode == self._map_to_start:
                return self.getWeekStartDate(basedate)
            else:
                return self.getWeekEndDate(basedate)
        elif clock == resolve(self._clock_monthly):
            # monthly
            if self.map_mode == self._map_to_start:
                return datetime.date(basedate.year, basedate.month, 1)
            else:
                return datetime.date(
                    basedate.year,
                    basedate.month,
                    calendar.monthrange(basedate.year, basedate.month)[1],
                )
        elif clock == resolve(self._clock_quarterly):
            # quarterly
            if basedate.month > 0 and basedate.month < 4:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=1, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=3, day=31)
            elif basedate.month >= 4 and basedate.month < 7:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=4, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=6, day=30)
            elif basedate.month >= 7 and basedate.month < 10:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=7, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=9, day=30)
            else:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=10, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=12, day=31)
        elif clock == resolve(self._clock_half_yearly):
            # half yearly
            if basedate.month <= 6:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=1, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=6, day=30)
            else:
                if self.map_mode == self._map_to_start:
                    return datetime.date(day=1, month=7, year=basedate.year)
                else:
                    return datetime.date(year=basedate.year, month=12, day=31)
        elif clock == resolve(self._clock_yearly):
            # yearly
            if self.map_mode == self._map_to_start:
                return datetime.date(day=1, month=1, year=basedate.year)
            else:
                return datetime.date(year=basedate.year, month=12, day=31)

    def getData(self, parent_result, source_args, **kwargs):
        from cs.metrics.services import get_next_computation

        result = PowerReports.ReportDataList(self)
        milestone_result = []
        firstDate = None
        lastDate = None
        qc = None
        qc_id = None
        resultdata = {}

        update_clock = source_args.get("update_clock", None)
        map_mode = int(source_args.get("map_mode", None))
        time_window_mode = int(source_args.get("time_window_mode", None))

        # set interval map mode
        if map_mode in (self._map_to_end, self._map_to_start):
            self.map_mode = map_mode
        else:
            self.map_mode = self._map_to_end

        # set time_window_mode
        if time_window_mode in (self._map_to_project, self._map_to_milestones):
            self.time_window_mode = time_window_mode
        else:
            self.time_window_mode = self._map_to_project

        # get project information
        context_project = parent_result.getObject()
        milestones = context_project.Milestones
        projectFirstDate = context_project.start_time_fcast
        projectLastDate = context_project.end_time_fcast
        milestoneBorderDates = self.getBorderMilestoneDates(milestones)

        # start/end date can be set by start_time_plan/end_time_plan
        # of project, milestone, dialogue (later on)

        if not firstDate:
            if time_window_mode == self._map_to_milestones and milestoneBorderDates[0]:
                firstDate = milestoneBorderDates[0]
            else:
                firstDate = projectFirstDate
        if not lastDate:
            if time_window_mode == self._map_to_milestones and milestoneBorderDates[1]:
                lastDate = milestoneBorderDates[1]
            else:
                lastDate = projectLastDate

        if firstDate is None or lastDate is None:
            return result

        today = datetime.date.today()

        # get qc definition information - only set update_clock if not set
        qc_id_list = QCDefinition.KeywordQuery(name_de="Meilensteintermine Wöchentlich")
        if qc_id_list and len(qc_id_list) == 1:
            qc_id = qc_id_list[0]
        interval_list = ClassAssociation.KeywordQuery(
            cdbqc_def_object_id=qc_id.cdb_object_id
        )
        if not update_clock and interval_list and len(interval_list) == 1:
            update_clock = interval_list[0].update_clock

        # traverse the tree of qc information: milestone->qc->qc_hist->value
        if qc_id and update_clock:
            # if operation is on mapped dates - start/end also have to be mapped
            firstDate = self.getIntervalMatchingDate(firstDate, update_clock)
            lastDate = self.getIntervalMatchingDate(lastDate, update_clock)
            todayDate = self.getIntervalMatchingDate(today, update_clock)
            for milestone in milestones:
                milestoneFinished = False
                milestone_end_date = None
                if milestone.end_time_act:
                    milestone_end_date = self.getIntervalMatchingDate(
                        milestone.end_time_act, update_clock
                    )
                # get the corresponding qc
                qc = ObjectQualityCharacteristic.KeywordQuery(
                    cdbqc_def_object_id=qc_id.cdb_object_id,
                    cdbf_object_id=milestone.cdb_object_id,
                )
                if qc and len(qc) == 1:
                    # get the corresponding qc history - do not fetch history entries before viewing window
                    qc_hist_list = History.Query(
                        ((History.cdbqc_object_id == qc[0].cdb_object_id)),
                        order_by="cdb_cdate",
                    )
                    qchli = 0
                    # go over the defined timedelta and insert points
                    # make sure not to interpolate points into future
                    tmpDate = firstDate
                    while (
                        len(qc_hist_list) > qchli
                        and tmpDate <= lastDate
                        and not milestoneFinished
                        and tmpDate <= todayDate
                    ):
                        # increase qchl index if measurement date is lower
                        # than last actual measurement in interval date
                        if (
                            self.getIntervalMatchingDate(
                                qc_hist_list[qchli].cdb_cdate.date(), update_clock
                            )
                            < tmpDate
                        ):
                            tmp_qchli = qchli
                            while (tmp_qchli + 1 < len(qc_hist_list)) and (
                                self.getIntervalMatchingDate(
                                    qc_hist_list[tmp_qchli + 1].cdb_cdate.date(),
                                    update_clock,
                                )
                                <= tmpDate
                            ):
                                tmp_qchli += 1
                            qchli = tmp_qchli
                        # get measured planed milestone date and save into distinct dict
                        # indexed by the tmpDate which is mapped to the selected interval and the milestones
                        # this makes sure that there is only one y-value per x-value even if the granularity
                        # of the measurement is much higher than the visualisation granularity
                        ms_date = datetime.date.fromordinal(
                            int(qc_hist_list[qchli].value)
                        )
                        if tmpDate not in resultdata:
                            resultdata[tmpDate] = {}
                        resultdata[tmpDate][
                            milestone.task_name
                        ] = self.getIntervalMatchingDate(
                            ms_date, update_clock
                        ).strftime(
                            self._date_format
                        )

                        # check finished milestones in next iteration - if last point - reset
                        # ms_date to end date of milestone
                        str_next_interval_date = get_next_computation(
                            update_clock, tmpDate
                        )
                        nidt = datetime.datetime.combine(
                            str_next_interval_date, datetime.datetime.min.time()
                        )
                        checkDate = self.getIntervalMatchingDate(
                            datetime.date(nidt.year, nidt.month, nidt.day), update_clock
                        )
                        if (
                            milestone.status >= Task.FINISHED.status
                            and milestone_end_date
                            and milestone_end_date < checkDate
                        ):
                            resultdata[tmpDate][
                                milestone.task_name
                            ] = milestone_end_date.strftime(self._date_format)
                            milestoneFinished = True

                        # increase measurement interval date with update_clock interval
                        str_next_interval_date = get_next_computation(
                            update_clock, tmpDate
                        )
                        nidt = datetime.datetime.combine(
                            str_next_interval_date, datetime.datetime.min.time()
                        )
                        tmpDate = self.getIntervalMatchingDate(
                            datetime.date(nidt.year, nidt.month, nidt.day), update_clock
                        )

            # generate diagonal line
            if qc and len(qc) == 1:
                tmpDate = firstDate
                while tmpDate <= lastDate:
                    data = PowerReports.ReportData(self)
                    data["ms_date"] = tmpDate.strftime(self._date_format)
                    data["ms_name"] = "Verlauf"
                    data["report_date"] = tmpDate.strftime(self._date_format)

                    # increase tmpDate with update_clock interval
                    str_next_interval_date = get_next_computation(update_clock, tmpDate)
                    nidt = datetime.datetime.combine(
                        str_next_interval_date, datetime.datetime.min.time()
                    )
                    tmpDate = self.getIntervalMatchingDate(
                        datetime.date(nidt.year, nidt.month, nidt.day), update_clock
                    )
                    result.append(data)

        # insert measured milestone dates

        measurementDates = list(resultdata)
        measurementDates.sort()

        for measurementDate in measurementDates:
            milestoneDict = list(resultdata[measurementDate])
            milestoneDict.sort()
            for milestoneName in milestoneDict:
                data = PowerReports.ReportData(self)
                data["ms_date"] = resultdata[measurementDate][milestoneName]
                data["ms_name"] = milestoneName
                data["report_date"] = measurementDate.strftime(self._date_format)
                milestone_result.append(data)

        final_result = result + milestone_result
        return final_result

    def getSchema(self):
        qc = PowerReports.XSDType(self.CARD, ObjectQualityCharacteristic)
        qc.add_attr("ms_date", sqlapi.SQL_DATE)
        qc.add_attr("ms_name", sqlapi.SQL_CHAR)
        qc.add_attr("report_date", sqlapi.SQL_DATE)
        return qc

    def getClass(self):
        return ObjectQualityCharacteristic


class MTAUpdateClockCatalog(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        return [
            I18nCatalogEntry(f"{uc.position}", uc.Name[""])
            for uc in UpdateClock.Query(
                UpdateClock.name_de != "manuell", order_by="position"
            )
        ]


def cmpData(o1, o2):
    try:
        res = int(o1["end_time_fcast"] > o2["end_time_fcast"]) - int(
            o1["end_time_fcast"] < o2["end_time_fcast"]
        )
        if res:
            return res
        for a in ["category", "status"]:
            res = int(o1[a] > o2[a]) - int(o1[a] < o2[a])
            if res:
                return res
        return 0
    except Exception:
        return 0
