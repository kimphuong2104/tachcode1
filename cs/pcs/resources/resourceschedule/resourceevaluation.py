#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-instance-attributes

from collections import defaultdict
from datetime import timedelta

from cdb.objects import Forward, Rule
from cs.pcs.resources.constants import DAY, HALFYEAR, MONTH, QUARTER, WEEK

fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fCapaMatrix = Forward("cs.pcs.resources.calculation.CapaMatrix")
fCapaDetails = Forward("cs.pcs.resources.calculation.CapaDetails")

fResource = Forward("cs.pcs.resources.pools.assignments.Resource")


def next_monday(weekday):
    if weekday > 0:
        return (7 - weekday)
    return 0


def last_sunday(weekday):
    if weekday < 6:
        return -(weekday + 1)
    return 0


def sanitize_interval(interval, raw_start_date, raw_end_date):
    """
    :param interval: "day", "week", "month", "quarter" or "half-year"
    :type interval: str

    :param raw_start_date: First day to resolve interval for
    :type raw_start_date: datetime.date

    :param raw_end_date: Last day to resolve interval for
    :type raw_end_date: datetime.date

    :returns: Two dates, transformed as described below
    :rtype: tuple

    Depending on the value of ``interval``, the result is transformed as follows:

    day:
        No transformation

    week:
        Make sure dates represent full weeks only by shortening either end
        until the interval starts on a monday and ends on a sunday.

    month, quarter, half-year:
        Make sure dates represent full units by extending either end
        until the interval starts on the first and ends on the last day
        of a month, quarter or half-year.

    .. note::

        The resource schedule only queries for full quarters.
        Half-years are ignored, so "week" is the only interval that is no exact match.
        Because the schedule does not want to show extra data that is empty in other
        zoom levels, week intervals are shortened.
    """
    valid_months = None
    if interval == QUARTER:
        valid_months = [1, 4, 7, 10]
    elif interval == HALFYEAR:
        valid_months = [1, 7]

    start_date = raw_start_date
    end_date = raw_end_date

    if interval in [MONTH, QUARTER, HALFYEAR]:
        # Bei Monatsintervallen beginnt der Auswertungszeitraum mit
        # Monatsanfang und endet mit Monatsende.
        while start_date.day > 1 or (valid_months and start_date.month not in valid_months):
            start_date -= timedelta(days=start_date.day - 1)
            if valid_months and start_date.month not in valid_months:
                start_date -= timedelta(days=1)
        while end_date.day > 1 or (valid_months and end_date.month not in valid_months):
            end_date += timedelta(days=1)
        end_date -= timedelta(days=1)
    elif interval == WEEK:
        # Wochenintervall: Startet am Montag nach Start und endet Sonntag vor Ende
        start_date += timedelta(days=next_monday(start_date.weekday()))
        end_date += timedelta(days=last_sunday(end_date.weekday()))
    # else: Tagesintervall ist immer OK

    return start_date, end_date


# ***********************************************************************
# KAPAZITÄTSAUSWERTUNG
# ***********************************************************************
class ResourceEvaluation(object):
    def __init__(self, **kwargs):
        self.param = kwargs

        # Auswertungkontext bestimmen
        self.context = kwargs.get("context")
        self.cdb_project_ids = kwargs.get("cdb_project_ids", [])

        # Auswertungszeitraum bestimmen
        self.__initTimeInterval__()
        self.__initFilter__()

        # create list of resources dictionaries
        self.__initResources__()

        # Zeitintervalle fuer Wochen bestimmen
        self.__initDaysTemplate__()

        # Detailangaben zu einzelnen Ressourcen ermitteln
        self.__initAllocationDetails__()

    def __initTimeInterval__(self):
        # Intervallgröße bestimmen
        try:
            self.interval = self.param.get("interval")
        except Exception:  # pylint: disable=W0703
            self.interval = DAY

        self.start_date, self.end_date = sanitize_interval(
            self.interval, self.param.get("start"), self.param.get("end"))

        self.calendar_frame_start = self.start_date
        self.calendar_frame_end = self.end_date

    def __initFilter__(self):
        self.filter = eval(self.param.get("filter_list"))  # nosec

    def __initResources__(self):
        from cdb.objects.org import Organization
        from cs.pcs.resources.pools import ResourcePool

        self.resources = self.param.get("resources")
        self.pool_oids = []
        self.resources_oids = []
        for res in self.resources:
            if isinstance(res, (ResourcePool, Organization)):
                self.pool_oids.append(res.cdb_object_id)
            else:  # caller is responsible for resources matching given start and end dates
                self.resources_oids.append(res.cdb_object_id)

    def __initDaysTemplate__(self):
        """
        Berechnet die Anzahl an Tagen die sich innerhalb des gegebenen
        Zeitraums befinden und liefert eine entsprechend lange Liste bestehen
        aus Summenlisten zurück. Die Summenlisten bestehen jeweils aus drei
        Werten und beschreiben jeweils ein Zeitintervall:
        [capacity, demand, assignment]
        """
        self.days_template = []
        for i in range(  # pylint: disable=W0612
            (self.end_date - self.start_date).days + 1
        ):  # pylint: disable=W0612
            self.days_template.append([0, 0, 0])

    def __initAllocationDetails__(self):
        kwargs = {}
        kwargs["pool_list"] = self.pool_oids
        kwargs["res_list"] = self.resources_oids
        kwargs["start_date"] = self.calendar_frame_start
        kwargs["end_date"] = self.calendar_frame_end
        kwargs["prj_rule"] = self._getFilterRule()
        kwargs["interval"] = self.interval
        self.details = fCapaDetails(**kwargs)

    def excludePrj(self):
        return self.context != "resource"

    def _getFilterRule(self):
        if self.filter:
            return Rule.ByKeys(self.filter[0])
        return None

    def evaluatePrj(
        self,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        eval_capacity=False,
    ):
        self.matrix = fCapaMatrix(
            self.pool_oids,
            self.resources_oids,
            self.start_date,
            self.end_date,
            prj_rule,
            with_prj_ids,
            without_prj_ids,
            True,
            self.interval,
            eval_capacity,
        )

    def evaluateAll(self):
        without_prj_ids = None
        if self.excludePrj():
            without_prj_ids = self.cdb_project_ids
        prj_rule = self._getFilterRule()
        self.evaluatePrj(
            prj_rule=prj_rule, without_prj_ids=without_prj_ids, eval_capacity=True
        )

    def getCalculationDetails(self, include_capacity=True):
        result = {}
        for res in self.resources:
            days = self.matrix.getDetails(res.cdb_object_id)
            if days:
                result[res.cdb_object_id] = _writeEntries(
                    days, include_capacity=include_capacity
                )
        for res_oid in self.matrix.getPoolAssignmentOIDs():
            days = self.matrix.getDetails(res_oid)
            if days:
                result[res_oid] = _writeEntries(days, include_capacity=include_capacity)
        return result

    def getAllocationDetails(self):
        result = {}
        demands_assignments = {}
        for res in self.resources:
            demands, assignments = self.details.getDetails(res.cdb_object_id)
            for key, obj in demands.items():
                if key not in demands_assignments:
                    demands_assignments[key] = {}
                demands_assignments[key]["demand_oid"] = obj[0]["cdb_object_id"]
                demands_assignments[key]["demands"] = [float(x) for x in obj[1]]
            for key, obj in assignments.items():
                if key not in demands_assignments:
                    demands_assignments[key] = {}
                if "assignments" not in demands_assignments[key]:
                    demands_assignments[key]["assignments"] = {}
                demands_assignments[key]["assignments"][obj[0]["cdb_object_id"]] = [
                    float(x) for x in obj[1]
                ]
        for demand_assignment in demands_assignments.values():
            if "assignments" not in demand_assignment:
                result[demand_assignment["demand_oid"]] = [
                    (0.0, x, 0.0) for x in demand_assignment["demands"]
                ]
            else:
                for assignment_oid, values in demand_assignment["assignments"].items():
                    i = 0
                    combined_result = []
                    for value in values:
                        # use default demands if no demands found
                        demand_values = demand_assignment.get(
                            "demands", defaultdict(float)
                        )
                        combined_result.append((0.0, demand_values[i], value))
                        i += 1
                    result[assignment_oid] = combined_result
                    if "demand_oid" in demand_assignment:
                        result[demand_assignment["demand_oid"]] = combined_result
        return result


def _writeEntries(entries, include_capacity=False):
    out = []
    for entry in entries:
        out.append(_writeEntry(entry, include_capacity))
    return out


def _writeEntry(entry, include_capacity):
    if include_capacity:
        return (entry[0], entry[1], entry[2])
    return (entry[1], entry[2])
