#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=C0200,C0201,R1702,W0703,R0912,R0913,R0914,too-many-statements

import datetime
import logging
from copy import deepcopy

from cdb import sqlapi
from cdb.objects import Forward
from cs.pcs.resources import SCHEDULE_VIEWS
from cs.pcs.resources.helpers import to_legacy_str

DAY = Forward("cs.pcs.resources.DAY").__resolve__()
WEEK = Forward("cs.pcs.resources.WEEK").__resolve__()
MONTH = Forward("cs.pcs.resources.MONTH").__resolve__()
QUARTER = Forward("cs.pcs.resources.QUARTER").__resolve__()
HALFYEAR = Forward("cs.pcs.resources.HALFYEAR").__resolve__()

fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fResourceSchedule = Forward(__name__ + ".ResourceSchedule")
fResourceScheduleObject = Forward(__name__ + ".ResourceScheduleObject")
fProject2ResourceSchedule = Forward(__name__ + ".Project2ResourceSchedule")
fTimeSchedule = Forward("cs.pcs.timeschedule.TimeSchedule")
fCombinedResourceSchedule = Forward(__name__ + ".CombinedResourceSchedule")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignmentPerson = Forward(
    "cs.pcs.resources.pools.assignments.person.ResourcePoolAssignmentPerson"
)

dStartTimeField = fTask.getDemandStartTimeFieldName()
dEndTimeField = fTask.getDemandEndTimeFieldName()
aStartTimeField = fTask.getAssignmentStartTimeFieldName()
aEndTimeField = fTask.getAssignmentEndTimeFieldName()

DEFAULT_RESOURCE_TYPE = "%"


def __log__(txt):
    logging.debug(txt)


##########################################
# capacity and resource calculations
##########################################
class CapaMatrix:
    pool_list = []
    resource_list = []
    resource_matrix = {}
    pool_matrix = {}
    resource_oid_map = {}
    pool_day_matrix = {}
    resource_day_matrix = {}

    def __init__(
        self,
        pool_list=None,
        res_list=None,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        sum_up=True,
        interval=DAY,
        eval_capacity=True,
        resource_type=DEFAULT_RESOURCE_TYPE,
    ):
        """
        liefert zwei Kapazitätsmatrizen (Dictionaries), in denen alle angefragten
        Organisationseinheiten (pool_list) bzw. Ressourcen (res_list) als Schlüssel
        enthalten sind.
        Diesen Schlüsseln sind jeweils ihre Kapazitäten, Ressourcenbedarfe und -zuweisungen
        in Form eines Tupels aus Listen zugeordnet.
        Die Listen enthalten je einen Wert pro angegebenem Zeitintervall (interval) über die
        angeforderten Zeitspanne (start_date bis end_date).
        Wird das Summierungsflag gesetzt (sum_up=True), so werden für alle Organisationseinheiten
        alle resultierenden Werte untergeordneter Org-Einheiten hinzuaddiert.
        Wird das Summierungsflag nicht gesetzt, so beinhalten die Listen einer Organisationeinheit
        nur genau die Werte, die der Org-Einheit selbst und den zugehoerigen Ressourcen
        zugeordnet wurden.
        Die Menge der ausgewerteten Bedarfe und Zuweisungen aus auf ausgewählte Projekte
        beschränkt werden, die als Objektregel (prj_rule) bestimmt werden können.
        Ergänzend zur Regel (oder falls keine Regel verwendet werden soll) können
        Projekt-IDs angegeben werden, die zur Auswertung hinzugefügt (with_prj_ids)
        bzw. ignoriert (without_prj_ids) werden sollen.
        .
        """
        if not pool_list and not res_list or not start_date or not end_date:
            return
        if not pool_list:
            pool_list = []
        if not res_list:
            res_list = []
        __log__("Ressources.CapaMatrix (Initiierung)")
        self.start_date = self.frame_start = start_date
        self.end_date = self.frame_end = end_date
        self.interval = interval

        # always take the complete interval frames
        if self.interval in list(SCHEDULE_VIEWS):
            self.frame_start, self.frame_end = SCHEDULE_VIEWS[self.interval][2](
                start_date, end_date
            )

        __log__("Ressources.CapaMatrix (Gemeinsames Dictionary erstellen)")
        # create a dictionary
        pool_dict = {}
        pool_matrix = {}
        res_matrix = {}
        for pool_oid in pool_list:
            if pool_oid not in pool_dict:
                # pool dictionary, resource list, pool list
                (pd, _, pl) = fResourcePool.getPoolBreakdown(
                    pool_oid, self.frame_start, self.frame_end
                )
                for id2 in pl:
                    pool_dict[id2] = pd[id2]

        # enter all pools and resources in those pools into matrix
        __log__("Ressources.CapaMatrix (Ressourcenlisten erstellen):")
        for pool_oid, resources in pool_dict.items():
            res = resources[0]
            pool_matrix[pool_oid] = ""
            for r in res:
                res_matrix[r] = ""
        res_list = [x for x in res_list if x not in list(res_matrix)]
        for r in res_list:
            res_matrix[r] = ""

        if res_matrix.keys():
            # add still missing resources into matrix
            for res in fResource.KeywordQuery(referenced_oid=list(res_matrix)):
                res_matrix[res.cdb_object_id] = ""

            # add missing pool assignments within the given time frame
            start_frame = sqlapi.SQLdate_literal(self.frame_start)
            end_frame = sqlapi.SQLdate_literal(self.frame_end)
            res_str = ",".join(["'%s'" % sqlapi.quote(x) for x in res_matrix.keys()])
            condition = f"""(
                    resource_oid IN ({res_str})
                    OR cdb_object_id IN ({res_str})
                )
                AND (
                    COALESCE(start_date, {start_frame}) <= {end_frame}
                    OR assign_start_date <= {end_frame}
                )
                AND (
                    COALESCE(end_date, {end_frame}) >= {start_frame}
                    OR assign_end_date >= {start_frame}
                )
            """
            for res in sqlapi.RecordSet2(
                "cdbpcs_pool_assignment",
                condition,
                columns=["cdb_object_id", "resource_oid"],
            ):
                res_matrix[res.cdb_object_id] = ""
                res_matrix[res.resource_oid] = ""

        # daymap: the interval mapping
        # for interval in [MONTH, QUARTER, HALFYEAR]:
        #         key is "MM.YYYY", value is index of months/quarters/halfyears
        #     interval == DAY: key is "DD.MM.YYYY", value is index of days
        #     interval == WEEK: key is "DD.MM.YYYY", value is index of weeks
        self.daymap = {}
        empty_template = []
        if self.interval in SCHEDULE_VIEWS.keys():
            viewfunc = SCHEDULE_VIEWS[self.interval][1]
            # generate the intervals without counting days
            ivals = viewfunc(self.frame_start, self.frame_end, False)
            ival_keys = list(ivals)
            ival_keys.sort()
            for i in range(len(ival_keys)):
                self.daymap[to_legacy_str(ival_keys[i])] = i
                empty_template.append(0)
        else:
            for i in range((end_date - start_date).days + 1):
                self.daymap[to_legacy_str(start_date + datetime.timedelta(days=i))] = i
                empty_template.append(0)

        # set empty template lists for organizations and resources
        __log__("Ressources.CapaMatrix (leere Ergebnislisten eintragen)")
        for rid in list(pool_matrix):
            pool_matrix[rid] = [
                list(empty_template),
                list(empty_template),
                list(empty_template),
            ]
        for rid in list(res_matrix):
            res_matrix[rid] = [
                list(empty_template),
                list(empty_template),
                list(empty_template),
            ]

        start_date_sql = sqlapi.SQLdate_literal(self.frame_start)
        end_date_sql = sqlapi.SQLdate_literal(self.frame_end)

        # split the person list and organization list into pieces to fit the SQL-statement
        res_list_tmp = list(res_matrix)
        pool_list_tmp = list(pool_dict)

        MAX_ELEMS_IN_CLAUSE = 500
        reslen = len(res_list_tmp)
        lidxs = list(range((reslen + len(pool_list_tmp)) // MAX_ELEMS_IN_CLAUSE + 1))
        for lidx in lidxs:
            startidx = MAX_ELEMS_IN_CLAUSE * lidx
            endidx = startidx + MAX_ELEMS_IN_CLAUSE
            res_temp = res_list_tmp[startidx:endidx]
            pool_temp = []
            if reslen < endidx:
                endidx = endidx - reslen
                if startidx > reslen:
                    startidx = startidx - reslen
                else:
                    startidx = 0
                pool_temp = pool_list_tmp[startidx:endidx]
            if not res_temp and not pool_temp:
                break

            res_str = pool_str = "''"
            if res_temp:
                res_str = ",".join(["'%s'" % sqlapi.quote(x) for x in res_temp])
            # Table alias would be set later
            sql_res = " %s." + "resource_oid in ( %s ) " % res_str

            if pool_temp:
                pool_str = ",".join(["'%s'" % sqlapi.quote(x) for x in pool_temp])
            sql_pool = " %s." + "pool_oid in ( %s ) " % pool_str

            sqlPrjRule = sqlWithPrj = "1=0"
            sqlWithoutPrj = "1=1"
            if prj_rule:
                project_stmt = prj_rule.stmt(prj_rule.getClasses()[0])
                project_stmt = project_stmt.replace(
                    "*", "cdb_project_id cdb_project_id"
                )
                sqlPrjRule1 = " t." + "cdb_project_id IN (%s)" % project_stmt

                task_stmt = f"""SELECT cdbpcs_task.task_id
                    FROM cdbpcs_task
                    WHERE cdbpcs_task.status != 180
                        AND cdbpcs_task.cdb_project_id IN ({project_stmt})
                        AND cdbpcs_task.ce_baseline_id = ''
                """
                sqlPrjRule2 = " t." + "task_id IN (%s)" % task_stmt
                sqlPrjRule = sqlPrjRule1 + " AND " + sqlPrjRule2

            if with_prj_ids:
                sqlWithPrj = " t." + "cdb_project_id in (%s)" % (
                    ",".join(["'%s'" % sqlapi.quote(x) for x in with_prj_ids])
                )
            elif not prj_rule:
                # ? all projects should be calculated
                sqlWithPrj = "1=1"

            if without_prj_ids:
                sqlWithoutPrj = " t." + "cdb_project_id not in (%s)" % (
                    ",".join(["'%s'" % sqlapi.quote(x) for x in without_prj_ids])
                )
            # sqlWhere = " (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

            # all calculations (capacity, demand, assignment) for days, week, month, quarter or half year
            if self.interval in SCHEDULE_VIEWS.keys():
                viewtable = SCHEDULE_VIEWS[self.interval][0]
                sql_res = sql_res % "t"
                sql_pool = sql_pool % "t"

                # calculation of demand and assignment for days, week, month, quarter or half year
                # - determine all entries in the table and sum up by person
                # 'day' is a keyword in postgres, hence requires the use of AS for aliasing
                sqlStatement = f"""SELECT
                    t.resource_oid resource_oid, t.start_date AS day,
                    t.pool_oid pool_oid, t.assignment_oid assignment_oid,
                    SUM(t.d_value) dvalue, SUM(t.a_value) avalue
                FROM {viewtable} t
                WHERE ({sql_res} OR {sql_pool})
                    AND {start_date_sql} <= t.start_date
                    AND t.start_date <= {end_date_sql}
                    AND t.resource_type LIKE '{resource_type}'
                    AND ({sqlPrjRule} OR {sqlWithPrj})
                    AND {sqlWithoutPrj}
                GROUP BY t.assignment_oid, t.resource_oid, t.pool_oid, t.start_date
                """

                perdata = sqlapi.RecordSet2(sql=sqlStatement)
                for perd in perdata:
                    perd_day = to_legacy_str(perd.day)
                    didx = self.daymap.get(perd_day, -1)
                    if didx >= 0:
                        if perd.assignment_oid:
                            if perd.assignment_oid in res_matrix.keys():
                                res_matrix[perd.assignment_oid][1][
                                    didx
                                ] += self._resetNull(perd.dvalue)
                                res_matrix[perd.assignment_oid][2][
                                    didx
                                ] += self._resetNull(perd.avalue)
                        if perd.resource_oid:
                            if perd.resource_oid in res_matrix.keys():
                                res_matrix[perd.resource_oid][1][
                                    didx
                                ] += self._resetNull(perd.dvalue)
                                res_matrix[perd.resource_oid][2][
                                    didx
                                ] += self._resetNull(perd.avalue)
                        elif perd.pool_oid in pool_matrix:
                            pool_matrix[perd.pool_oid][1][didx] += self._resetNull(
                                perd.dvalue
                            )
                            pool_matrix[perd.pool_oid][2][didx] += self._resetNull(
                                perd.avalue
                            )

                # determine capacity for each relevant person and
                # combine sum up the values in the matrix
                # 'day' is a keyword in postgres, hence requires the use of AS for aliasing
                sqlStatement = f"""SELECT
                    t.resource_oid resource_oid, t.pool_oid pool_oid, t.assignment_oid assignment_oid,
                    t.capacity capacity, t.day AS day
                FROM {SCHEDULE_VIEWS[self.interval][3]} t
                WHERE ({sql_res} OR {sql_pool})
                    AND {start_date_sql} <= t.day
                    AND t.day <= {end_date_sql}
                """
                perdata = sqlapi.RecordSet2(sql=sqlStatement)
                framefunc = SCHEDULE_VIEWS[self.interval][2]
                for perd in perdata:
                    didx = self.daymap.get(perd.day, -1)
                    if didx == -1:
                        framestart = framefunc(perd.day.date())[0]
                        didx = self.daymap.get(to_legacy_str(framestart), -1)
                    if didx >= 0:
                        if (
                            perd.assignment_oid
                            and perd.assignment_oid in res_matrix.keys()
                        ):
                            res_matrix[perd.assignment_oid][0][didx] += self._resetNull(
                                perd.capacity
                            )
                        if perd.resource_oid and perd.resource_oid in res_matrix.keys():
                            res_matrix[perd.resource_oid][0][didx] += self._resetNull(
                                perd.capacity
                            )

        __log__(
            "Ressources.CapaMatrix (Ergebnis von Ressourcen analog bei Personen eintragen)"
        )

        self._createOIDMapping(list(res_matrix))
        if res_matrix.keys():
            ids = ", ".join(["'%s'" % x for x in res_matrix])
            sql = f"""SELECT DISTINCT
                    resource_oid,
                    original_resource_oid
                FROM cdbpcs_pool_assignment_v
                WHERE original_resource_oid IN ({ids})
            """
            for r in sqlapi.RecordSet2(sql=sql):
                if r.resource_oid in res_matrix.keys():
                    res_matrix[r.original_resource_oid] = res_matrix[r.resource_oid]

        __log__("Ressources.CapaMatrix (Matrizen aufsummieren)")

        # iterate organizations and sum up the values of all sub elements
        if sum_up:
            done = []

            def poolAggr(oid):
                if oid not in done:
                    for res in pool_dict.get(oid, [[], []])[0]:
                        for i in range(3):
                            hlist = pool_matrix[oid][i]
                            slist = res_matrix[res][i]
                            for x in range(len(slist)):
                                hlist[x] += slist[x]
                    for subpool in pool_dict.get(oid, [[], []])[1]:
                        poolAggr(subpool)
                        for i in range(3):
                            hlist = pool_matrix[oid][i]
                            slist = pool_matrix[subpool][i]
                            for x in range(len(slist)):
                                hlist[x] += slist[x]
                    done.append(oid)

            for oid in pool_list:
                poolAggr(oid)

        self.pool_list = pool_list
        self.resource_list = res_list
        self.pool_matrix = pool_matrix
        self.resource_matrix = res_matrix
        self.pool_day_matrix = self._toDayDict(self.pool_matrix)
        self.resource_day_matrix = self._toDayDict(self.resource_matrix)
        __log__("Ressources.CapaMatrix (fertig erstellt)")

    def _createOIDMapping(self, res_list):
        if not res_list:
            return
        oids = ", ".join(["'%s'" % x for x in res_list])
        sqlStatement = f"""SELECT
                cdb_object_id, original_resource_oid, resource_oid
            FROM cdbpcs_pool_assignment_v
            WHERE resource_oid IN ({oids})
        """
        for r in sqlapi.RecordSet2(sql=sqlStatement):
            self.resource_oid_map[r["original_resource_oid"]] = r["resource_oid"]

    def getPoolAssignmentOIDs(self):
        return list(self.resource_oid_map)

    def getPoolCapacity(self, pool_oid, myDate=None):
        return self.__getValues(self.pool_matrix, pool_oid, 0, myDate)

    def getResourceCapacity(self, resource_oid, myDate=None):
        return self.__getValues(self.resource_matrix, resource_oid, 0, myDate)

    def getPoolUncoveredDemands(self, pool_oid, myDate=None):
        return self.__getValues(self.pool_matrix, pool_oid, 1, myDate)

    def getResourceUncoveredDemands(self, resource_oid, myDate=None):
        return self.__getValues(self.resource_matrix, resource_oid, 1, myDate)

    def getPoolAssignments(self, pool_oid, myDate=None):
        return self.__getValues(self.pool_matrix, pool_oid, 2, myDate)

    def getResourceAssignments(self, resource_oid, myDate=None):
        return self.__getValues(self.resource_matrix, resource_oid, 2, myDate)

    def getPoolDemands(self, pool_oid, myDate=None):
        demand = self.getPoolUncoveredDemands(pool_oid, myDate)
        assign = self.getPoolAssignments(pool_oid, myDate)
        if myDate:
            return demand + assign
        return [demand[x] + assign[x] for x in range(len(demand))]

    def getResourceDemands(self, resource_oid, myDate=None):
        demand = self.getRessourceUncoveredDemands(resource_oid, myDate)
        assign = self.getResourceAssignments(resource_oid, myDate)
        return [demand[x] + assign[x] for x in range(len(demand))]

    def getPoolFreeCapacities(self, pool_oid, myDate=None):
        if myDate:
            i = self._getIndexByDate(myDate)
            return (
                self.pool_matrix[pool_oid][0][i]
                - self.pool_matrix[pool_oid][1][i]
                - self.pool_matrix[pool_oid][2][i]
            )
        values = []
        for i in range(len(self.pool_matrix[pool_oid][0])):
            values.append(
                self.pool_matrix[pool_oid][0][i]
                - self.pool_matrix[pool_oid][1][i]
                - self.pool_matrix[pool_oid][2][i]
            )
        return values

    def getResourceFreeCapacities(self, resource_oid, myDate=None):
        if myDate:
            i = self._getIndexByDate(myDate)
            if i == -1:
                return []
            return (
                self.resource_matrix[resource_oid][0][i]
                - self.resource_matrix[resource_oid][1][i]
                - self.resource_matrix[resource_oid][2][i]
            )
        values = []
        for i in range(len(self.resource_matrix[resource_oid][0])):
            values.append(
                self.resource_matrix[resource_oid][0][i]
                - self.resource_matrix[resource_oid][1][i]
                - self.resource_matrix[resource_oid][2][i]
            )
        return values

    def __getValues(self, matrix, rid, index=None, myDate=None):
        if myDate:
            return matrix[rid][index][self._getIndexByDate(myDate)]
        return deepcopy(matrix[rid][index])

    def _getIndexByDate(self, myDate):
        if self.interval in SCHEDULE_VIEWS.keys():
            framefunc = SCHEDULE_VIEWS[self.interval][2]
            framestart = framefunc(myDate)[0]
            return self.daymap.get(to_legacy_str(framestart), -1)
        return self.daymap.get(to_legacy_str(myDate), -1)

    def _toDayDict(self, matrix):
        dayDict = {}
        for rid in matrix.keys():
            m = matrix[rid]
            days = []
            for i in range(len(m[0])):
                days.append([m[0][i], m[1][i], m[2][i]])
            dayDict[rid] = days
        return dayDict

    def _resetNull(self, val):
        try:
            return float(val)
        except Exception:  # nosec
            pass
        return 0.0

    def getDetails(self, oid):
        oid = self.resource_oid_map.get(oid, oid)
        if oid in self.pool_day_matrix:
            return self.pool_day_matrix.get(oid, None)
        return self.resource_day_matrix.get(oid, None)


class CapaDetails:

    pool_list = []
    resource_list = []
    resource_matrix = {}
    pool_matrix = {}

    def __init__(
        self,
        pool_list=None,
        res_list=None,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        sum_up=True,
        interval=DAY,
        resource_type=DEFAULT_RESOURCE_TYPE,
    ):
        """
        liefert zwei Kapazitätsmatrizen (Dictionaries), in denen alle angefragten
        Organisationseinheiten (pool_list) bzw. Ressourcen (res_list) als Schlüssel
        enthalten sind.
        Diesen Schlüsseln sind jeweils ihre Kapazitäten, Ressourcenbedarfe und -zuweisungen
        in Form eines Tupels aus Listen zugeordnet.
        Die Listen enthalten je einen Wert pro angegebenem Zeitintervall (interval) über die
        angeforderten Zeitspanne (start_date bis end_date).
        Wird das Summierungsflag gesetzt (sum_up=True), so werden für alle Organisationseinheiten
        alle resultierenden Werte untergeordneter Org-Einheiten hinzuaddiert.
        Wird das Summierungsflag nicht gesetzt, so beinhalten die Listen einer Organisationeinheit
        nur genau die Werte, die der Org-Einheit selbst und den zugehoerigen Ressourcen
        zugeordnet wurden.
        Die Menge der ausgewerteten Bedarfe und Zuweisungen aus auf ausgewählte Projekte
        beschränkt werden, die als Objektregel (prj_rule) bestimmt werden können.
        Ergänzend zur Regel (oder falls keine Regel verwendet werden soll) können
        Projekt-IDs angegeben werden, die zur Auswertung hinzugefügt (with_prj_ids)
        bzw. ignoriert (without_prj_ids) werden sollen.
        .
        """
        if not pool_list and not res_list or not start_date or not end_date:
            return
        if not pool_list:
            pool_list = []
        if not res_list:
            res_list = []
        __log__("Ressources.CapaDetails (Initiierung)")
        self.start_date = self.frame_start = start_date
        self.end_date = self.frame_end = end_date
        self.interval = interval

        # always take the complete interval frames
        if self.interval in list(SCHEDULE_VIEWS):
            self.frame_start, self.frame_end = SCHEDULE_VIEWS[self.interval][2](
                start_date, end_date
            )

        __log__("Ressources.CapaDetails (Gemeinsames Dictionary erstellen)")
        # create a dictionary
        pool_dict = {}
        pool_matrix = {}
        res_matrix = {}
        for pool_oid in pool_list:
            if pool_oid not in pool_dict:
                # pool dictionary, resource list, pool list
                (pd, _, pl) = fResourcePool.getPoolBreakdown(
                    pool_oid, self.frame_start, self.frame_end
                )
                for id2 in pl:
                    pool_dict[id2] = pd[id2]

        # enter all pools and resources into matrix
        __log__("Ressources.CapaDetails (Ressourcenlisten erstellen)")
        for pool_oid, resources in pool_dict.items():
            res = resources[0]
            pool_matrix[pool_oid] = ""
            for r in res:
                res_matrix[r] = ""
        res_list = [x for x in res_list if x not in res_matrix.keys()]
        for r in res_list:
            res_matrix[r] = ""

        # daymap: the interval mapping
        # for interval in [MONTH, QUARTER, HALFYEAR]:
        #         key is "MM.YYYY", value is index of months/quarters/halfyears
        #     interval == DAY: key is "DD.MM.YYYY", value is index of days
        #     interval == WEEK: key is "DD.MM.YYYY", value is index of weeks
        self.daymap = {}
        empty_template = []
        if self.interval in SCHEDULE_VIEWS.keys():
            viewfunc = SCHEDULE_VIEWS[self.interval][1]
            # generate the intervals without counting days
            ivals = viewfunc(self.frame_start, self.frame_end, False)
            ival_keys = list(ivals)
            ival_keys.sort()
            for i in range(len(ival_keys)):
                self.daymap[to_legacy_str(ival_keys[i])] = i
                empty_template.append(0)
        else:
            for i in range((end_date - start_date).days + 1):
                self.daymap[to_legacy_str(start_date + datetime.timedelta(days=i))] = i
                empty_template.append(0)

        # set empty template lists for organizations and resources
        __log__("Ressources.CapaDetails (leere Ergebnislisten eintragen)")
        for rid in list(pool_matrix):
            pool_matrix[rid] = [{}, {}]
        for rid in list(res_matrix):
            res_matrix[rid] = [{}, {}]

        start_date_sql = sqlapi.SQLdate_literal(self.frame_start)
        end_date_sql = sqlapi.SQLdate_literal(self.frame_end)

        # split the person list and organization list into pieces to fit the SQL-statement
        res_list_tmp = list(res_matrix)
        pool_list_tmp = list(pool_dict)
        MAX_ELEMS_IN_CLAUSE = 500
        reslen = len(res_list_tmp)
        lidxs = list(range((reslen + len(pool_list_tmp)) // MAX_ELEMS_IN_CLAUSE + 1))
        for lidx in lidxs:
            startidx = MAX_ELEMS_IN_CLAUSE * lidx
            endidx = startidx + MAX_ELEMS_IN_CLAUSE
            res_temp = res_list_tmp[startidx:endidx]
            pool_temp = []
            if reslen < endidx:
                endidx = endidx - reslen
                if startidx > reslen:
                    startidx = startidx - reslen
                else:
                    startidx = 0
                pool_temp = pool_list_tmp[startidx:endidx]
            if not res_temp and not pool_temp:
                break

            res_str = pool_str = "''"
            if res_temp:
                res_str = ",".join(["'%s'" % sqlapi.quote(x) for x in res_temp])
            # Table alias would be set later
            sql_res = " %s." + "resource_oid in ( %s ) " % res_str

            if pool_temp:
                pool_str = ",".join(["'%s'" % sqlapi.quote(x) for x in pool_temp])
            sql_pool = " %s." + "pool_oid in ( %s ) " % pool_str

            sqlPrjRule = sqlWithPrj = "1=0"
            sqlWithoutPrj = "1=1"
            if prj_rule:
                sqlPrjRule = prj_rule.stmt(prj_rule.getClasses()[0])
                sqlPrjRule = sqlPrjRule.replace("*", "cdb_project_id cdb_project_id")
                sqlPrjRule = " t." + "cdb_project_id in (%s)" % sqlPrjRule

            if with_prj_ids:
                sqlWithPrj = " t." + "cdb_project_id in (%s)" % (
                    ",".join(["'%s'" % sqlapi.quote(x) for x in with_prj_ids])
                )
            elif not prj_rule:
                # ? all projects should be calculated
                sqlWithPrj = "1=1"

            if without_prj_ids:
                sqlWithoutPrj = " t." + "cdb_project_id not in (%s)" % (
                    ",".join(["'%s'" % sqlapi.quote(x) for x in without_prj_ids])
                )
            # sqlWhere = " (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

            # all calculations (demand, assignment) for week, month, quarter or half year
            if self.interval in SCHEDULE_VIEWS.keys():
                viewtable = SCHEDULE_VIEWS[self.interval][0]
                sql_res = sql_res % "t"
                sql_pool = sql_pool % "t"

                # Demands
                # 'day' is a keyword in postgres, hence requires the use of AS for aliasing
                dsqlStatement = f"""SELECT
                    t.resource_oid resource_oid, t.pool_oid pool_oid, t.start_date AS day,
                    t.d_value svalue, t.cdb_project_id cdb_project_id,
                    t.task_id task_id, t.cdb_demand_id cdb_demand_id,
                    p.project_name project_name, t1.task_name task_name,
                    t1.{dStartTimeField} start_time_fcast, t1.{dEndTimeField} end_time_fcast,
                    t1.status task_status, t1.cdb_status_txt task_status_txt, t1.position task_position,
                    d1.resource_type resource_type,
                    d1.hours hours, d1.hours_per_day hours_per_day, d1.cdb_object_id demand_oid
                FROM {viewtable} t, cdbpcs_project p, cdbpcs_task t1, cdbpcs_prj_demand d1
                WHERE ({sql_res} OR {sql_pool})
                    AND t1.status != 180
                    AND {start_date_sql} <= t.start_date
                    AND t.start_date <= {end_date_sql}
                    AND t.resource_type LIKE '{resource_type}'
                    AND ({sqlPrjRule} OR {sqlWithPrj})
                    AND {sqlWithoutPrj}
                    AND t.cdb_project_id=p.cdb_project_id
                    AND t.cdb_project_id=t1.cdb_project_id AND t.task_id=t1.task_id
                    AND t.cdb_project_id=d1.cdb_project_id AND t.task_id=d1.task_id
                    AND t.cdb_demand_id=d1.cdb_demand_id
                    AND p.ce_baseline_id = ''
                    AND t1.ce_baseline_id = ''
                """

                drsets = sqlapi.RecordSet2(sql=dsqlStatement)
                for drset in drsets:
                    drset_day = to_legacy_str(drset.day)
                    didx = self.daymap.get(drset_day, -1)
                    if didx >= 0:
                        dkey = (
                            drset.cdb_project_id,
                            drset.task_id,
                            drset.cdb_demand_id,
                        )
                        if drset.resource_oid:
                            if drset.resource_oid in list(res_matrix):
                                if dkey not in res_matrix[drset.resource_oid][0]:
                                    res_matrix[drset.resource_oid][0][dkey] = [
                                        self.getDemandDataFromRecordSet(drset),
                                        list(empty_template),
                                    ]
                                res_matrix[drset.resource_oid][0][dkey][1][
                                    didx
                                ] += self._resetNull(drset.svalue)
                        elif drset.pool_oid in pool_matrix:
                            if dkey not in pool_matrix[drset.pool_oid][0]:
                                pool_matrix[drset.pool_oid][0][dkey] = [
                                    self.getDemandDataFromRecordSet(drset),
                                    list(empty_template),
                                ]
                            pool_matrix[drset.pool_oid][0][dkey][1][
                                didx
                            ] += self._resetNull(drset.svalue)

                # Assignments
                # 'day' is a keyword in postgres, hence requires the use of AS for aliasing
                asqlStatement = f"""SELECT
                    t.resource_oid resource_oid, t.pool_oid pool_oid, t.start_date AS day,
                    t.a_value svalue, t.cdb_project_id cdb_project_id,
                    t.task_id task_id, t.cdb_alloc_id cdb_alloc_id,
                    p.project_name project_name, t1.task_name task_name,
                    t1.{aStartTimeField} start_time_fcast, t1.{aEndTimeField} end_time_fcast,
                    t1.status task_status, t1.cdb_status_txt task_status_txt, t1.position task_position,
                    d1.cdb_demand_id cdb_demand_id, d1.resource_type resource_type,
                    a1.hours hours, a1.hours_per_day hours_per_day, a1.cdb_object_id alloc_oid
                FROM {viewtable} t, cdbpcs_project p, cdbpcs_task t1, cdbpcs_prj_alloc a1, cdbpcs_prj_demand d1
                WHERE ({sql_res} OR {sql_pool})
                    AND t1.status != 180
                    AND {start_date_sql} <= t.start_date
                    AND t.start_date <= {end_date_sql}
                    AND t.resource_type LIKE '{resource_type}'
                    AND ({sqlPrjRule} OR {sqlWithPrj})
                    AND {sqlWithoutPrj}
                    AND t.cdb_project_id=p.cdb_project_id
                    AND t.cdb_project_id=t1.cdb_project_id AND t.task_id=t1.task_id
                    AND t.cdb_project_id=a1.cdb_project_id AND t.task_id=a1.task_id
                    AND t.cdb_alloc_id=a1.cdb_alloc_id
                    AND a1.cdb_project_id=d1.cdb_project_id
                    AND a1.cdb_demand_id=d1.cdb_demand_id
                    AND p.ce_baseline_id = ''
                    AND t1.ce_baseline_id = ''
                """

                drsets = sqlapi.RecordSet2(sql=asqlStatement)
                for drset in drsets:
                    drset_day = to_legacy_str(drset.day)
                    didx = self.daymap.get(drset_day, -1)
                    if didx >= 0:
                        dkey = (
                            drset.cdb_project_id,
                            drset.task_id,
                            drset.cdb_demand_id,
                        )
                        if drset.resource_oid:
                            if drset.resource_oid in list(res_matrix):
                                if dkey not in res_matrix[drset.resource_oid][1]:
                                    res_matrix[drset.resource_oid][1][dkey] = [
                                        self.getAssignmentDataFromRecordSet(drset),
                                        list(empty_template),
                                    ]
                                res_matrix[drset.resource_oid][1][dkey][1][
                                    didx
                                ] += self._resetNull(drset.svalue)
                        elif drset.pool_oid in pool_matrix:
                            if dkey not in pool_matrix[drset.pool_oid][1]:
                                pool_matrix[drset.pool_oid][1][dkey] = [
                                    self.getAssignmentDataFromRecordSet(drset),
                                    list(empty_template),
                                ]
                            pool_matrix[drset.pool_oid][1][dkey][1][
                                didx
                            ] += self._resetNull(drset.svalue)

        self.pool_list = pool_list
        self.resource_list = res_list
        self.pool_matrix = pool_matrix
        self.resource_matrix = res_matrix
        __log__("Ressources.CapaDetails (fertig erstellt)")

    def getDemandDataFromRecordSet(self, drset):
        return {
            "cdb_project_id": drset.cdb_project_id,
            "task_id": drset.task_id,
            "cdb_demand_id": drset.cdb_demand_id,
            "cdb_object_id": drset.demand_oid,
            "project_name": drset.project_name,
            "task_name": drset.task_name,
            "start_time_fcast": drset.start_time_fcast,
            "end_time_fcast": drset.end_time_fcast,
            "task_status": drset.task_status,
            "task_status_txt": drset.task_status_txt,
            "task_position": drset.task_position,
            "hours": drset.hours,
            "hours_per_day": drset.hours_per_day,
        }

    def getAssignmentDataFromRecordSet(self, drset):
        return {
            "cdb_project_id": drset.cdb_project_id,
            "task_id": drset.task_id,
            "cdb_alloc_id": drset.cdb_alloc_id,
            "cdb_object_id": drset.alloc_oid,
            "project_name": drset.project_name,
            "task_name": drset.task_name,
            "start_time_fcast": drset.start_time_fcast,
            "end_time_fcast": drset.end_time_fcast,
            "task_status": drset.task_status,
            "task_status_txt": drset.task_status_txt,
            "task_position": drset.task_position,
            "cdb_demand_id": drset.cdb_demand_id,
            "hours": drset.hours,
            "hours_per_day": drset.hours_per_day,
        }

    def _getIndexByDate(self, myDate):
        if self.interval in SCHEDULE_VIEWS.keys():
            framefunc = SCHEDULE_VIEWS[self.interval][2]
            framestart = framefunc(myDate)[0]
            return self.daymap.get(to_legacy_str(framestart), -1)
        return self.daymap.get(to_legacy_str(myDate), -1)

    def _resetNull(self, val):
        try:
            return float(val)
        except Exception:  # nosec
            pass
        return 0.0

    def getDetails(self, oid):
        if oid in self.pool_matrix:
            return self.pool_matrix.get(oid, None)
        return self.resource_matrix.get(oid, None)
