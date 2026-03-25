#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=too-many-lines,too-many-arguments,expression-not-assigned
# pylint: disable=too-many-locals,too-many-nested-blocks,too-many-branches
# pylint: disable=protected-access,broad-except,len-as-condition
# pylint: disable=redefined-builtin,too-many-instance-attributes

import datetime
import functools
import logging

from cdb import misc, sqlapi, transactions, ue, util
from cdb.comparch.packages import Package
from cdb.constants import kOperationModify, kOperationNew
from cdb.objects import Forward, N, Object, Reference, ReferenceMethods_1, unique
from cdb.platform.gui import CDBCatalog, CDBCatalogContent, Message
from cs.pcs.projects import calendar as Calendar
from cs.pcs.resources.constants import DAY, HALFYEAR, MONTH, QUARTER, WEEK
from cs.pcs.resources.db_tools import is_oracle, is_postgres, load_pattern
from cs.pcs.resources.helpers import to_legacy_str
from cs.web.components.ui_support.dialog_hooks import DialogHook

__all__ = ["RessourceDemand", "RessourceAssignment"]

# Forward declarations
fProject = Forward("cs.pcs.projects.Project")
fRole = Forward("cs.pcs.projects.Role")
fTask = Forward("cs.pcs.projects.tasks.Task")
fRessourceDemand = Forward("cs.pcs.resources.RessourceDemand")
fRessourceAssignment = Forward("cs.pcs.resources.RessourceAssignment")
fOrganization = Forward("cdb.objects.org.Organization")
fPerson = Forward("cdb.objects.org.Person")
fAssignmentSchedule = Forward("cs.pcs.resources.AssignmentSchedule")
fDemandSchedule = Forward("cs.pcs.resources.DemandSchedule")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignment = Forward(
    "cs.pcs.resources.pools.assignments.ResourcePoolAssignment"
)
fSCHEDULE_CALCULATOR = Forward("cs.pcs.resources.schedule.SCHEDULE_CALCULATOR")

dStartTimeField = fTask.getDemandStartTimeFieldName()
dEndTimeField = fTask.getDemandEndTimeFieldName()
aStartTimeField = fTask.getAssignmentStartTimeFieldName()
aEndTimeField = fTask.getAssignmentEndTimeFieldName()

logger = logging.getLogger(__name__)


def partition(values, chunksize):
    if not (isinstance(chunksize, int) and chunksize > 1):
        raise ValueError("chunksize must be a positive integer")

    for index in range(0, len(values), chunksize):
        yield values[index : index + chunksize]


def format_in_condition(col_name, values, max_inlist_value=1000):
    """
    :param col_name: Name of the column to generate an "in" clause for
    :type col_name: string

    :param values: Values to use in "in" clause
    :type values: list - will break if a set is used

    :returns: "or"-joined SQL "in" clauses including ``values`` in batches of
        up to 1000 each to respect DBMS-specific limits (ORA: 1K, MS SQL 10K).
        NOTE: If values is empty "1=0" is returned, so no value should be
              returned for the SQL statement.
    :rtype: string
    """

    def _convert(values):
        return "{} IN ({})".format(
            col_name, ",".join([sqlapi.make_literals(v) for v in values])
        )

    if not values:
        return "1=0"

    conditions = [_convert(chunk) for chunk in partition(values, max_inlist_value)]
    return " OR ".join(conditions)


def adjust_pool_assignments(assignment_oids):
    if not assignment_oids:
        return
    oids = ",".join(["'%s'" % sqlapi.quote(x) for x in assignment_oids])
    sql_sd = (
        """ cdbpcs_pool_assignment
    SET assign_start_date =
        (SELECT MIN(tmp.start_time_fcast) FROM
            (SELECT start_time_fcast, assignment_oid FROM cdbpcs_prj_demand_v
             UNION
             SELECT start_time_fcast, assignment_oid FROM cdbpcs_prj_alloc_v
            ) tmp
            WHERE tmp.assignment_oid = cdbpcs_pool_assignment.cdb_object_id
            AND tmp.start_time_fcast IS NOT NULL
        )
    WHERE cdb_object_id IN (%s)"""
        % oids
    )
    sqlapi.SQLupdate(sql_sd)

    sql_ed = (
        """ cdbpcs_pool_assignment
    SET assign_end_date =
        (SELECT MIN(tmp.end_time_fcast) FROM
            (SELECT end_time_fcast, assignment_oid FROM cdbpcs_prj_demand_v
             UNION
             SELECT end_time_fcast, assignment_oid FROM cdbpcs_prj_alloc_v
            ) tmp
            WHERE tmp.assignment_oid = cdbpcs_pool_assignment.cdb_object_id
            AND tmp.end_time_fcast IS NOT NULL
        )
    WHERE cdb_object_id IN (%s)"""
        % oids
    )
    sqlapi.SQLupdate(sql_ed)


def get_package_version(as_tupel=False):
    package = Package.ByKeys(name="cs.resources")
    if not package:
        return None
    result = package.version
    if not as_tupel:
        return result
    if result.count(".") < 3:
        logger.error("Package version can not be determined\n:")
        return None
    (major, minor, release, service_level) = result.split(".")
    try:
        (major, minor, release) = (int(major), int(minor), int(release))
    except ValueError:
        logger.error("Package version can not be determined\n:")
        return None
    return major, minor, release, service_level


def getIntervalDays(frame_start, frame_end, start_date, end_date):
    cstart = frame_start if frame_start > start_date else start_date
    cend = frame_end if frame_end < end_date else end_date
    return (cend - cstart).days + 1


def getDayFrame(start_date, end_date=None):
    if not end_date:
        end_date = start_date
    return start_date, end_date


def getDayIntervals(start_date, end_date, eval_days=True):
    tempdate = start_date
    result = {}
    while tempdate <= end_date:
        frame_start, frame_end = getDayFrame(tempdate, tempdate)
        if eval_days:
            result[frame_start] = getIntervalDays(
                frame_start, frame_end, start_date, end_date
            )
        else:
            result[frame_start] = 0
        tempdate = frame_end + datetime.timedelta(days=1)
    return result


def getWeekFrame(start_date, end_date=None):
    if not end_date:
        end_date = start_date
    frame_start = start_date - datetime.timedelta(days=start_date.weekday())
    frame_end = end_date + datetime.timedelta(days=(6 - end_date.weekday()))
    return frame_start, frame_end


def getWeekIntervals(start_date, end_date, eval_days=True):
    tempdate = start_date
    result = {}
    while tempdate <= end_date:
        frame_start, frame_end = getWeekFrame(tempdate, tempdate)
        if eval_days:
            result[frame_start] = getIntervalDays(
                frame_start, frame_end, start_date, end_date
            )
        else:
            result[frame_start] = 0
        tempdate = frame_end + datetime.timedelta(days=1)
    return result


def getMonthFrame(start_date, end_date=None):
    if not end_date:
        end_date = start_date
    frame_start = start_date.replace(day=1)
    frame_end = None
    if end_date.month == 12:
        frame_end = end_date.replace(day=31)
    else:
        frame_end = end_date.replace(
            day=1, month=end_date.month + 1
        ) - datetime.timedelta(days=1)
    return frame_start, frame_end


def getMonthIntervals(start_date, end_date, eval_days=True):
    tempdate = start_date
    result = {}
    while tempdate <= end_date:
        frame_start, frame_end = getMonthFrame(tempdate, tempdate)
        if eval_days:
            result[frame_start] = getIntervalDays(
                frame_start, frame_end, start_date, end_date
            )
        else:
            result[frame_start] = 0
        tempdate = frame_end + datetime.timedelta(days=1)
    return result


def getQuarterFrame(start_date, end_date=None):
    if not end_date:
        end_date = start_date
    mstart = (start_date.month - 1) // 3 * 3 + 1
    frame_start = start_date.replace(day=1, month=mstart)
    if end_date.month > 9:
        frame_end = end_date.replace(day=31, month=12)
    else:
        mend = (end_date.month + 2) // 3 * 3 + 1
        frame_end = end_date.replace(day=1, month=mend) - datetime.timedelta(days=1)
    return frame_start, frame_end


def getQuarterIntervals(start_date, end_date, eval_days=True):
    tempdate = start_date
    result = {}
    while tempdate <= end_date:
        frame_start, frame_end = getQuarterFrame(tempdate, tempdate)
        if eval_days:
            result[frame_start] = getIntervalDays(
                frame_start, frame_end, start_date, end_date
            )
        else:
            result[frame_start] = 0
        tempdate = frame_end + datetime.timedelta(days=1)
    return result


def getHalfYearFrame(start_date, end_date=None):
    if not end_date:
        end_date = start_date
    mstart = 1
    if start_date.month > 6:
        mstart = 7
    frame_start = start_date.replace(day=1, month=mstart)
    if end_date.month > 6:
        frame_end = end_date.replace(day=31, month=12)
    else:
        frame_end = end_date.replace(day=30, month=6)
    return frame_start, frame_end


def getHalfYearIntervals(start_date, end_date, eval_days=True):
    tempdate = start_date
    result = {}
    while tempdate <= end_date:
        frame_start, frame_end = getHalfYearFrame(tempdate, tempdate)
        if eval_days:
            result[frame_start] = getIntervalDays(
                frame_start, frame_end, start_date, end_date
            )
        else:
            result[frame_start] = 0
        tempdate = frame_end + datetime.timedelta(days=1)
    return result


def deleteScheduleViews(data, all=False):
    if not data:
        return
    sterms = ["%s='%s'" % (k, v) for (k, v) in data.items()]
    sqld = " and ".join(sterms)
    for viewkey in list(SCHEDULE_VIEWS):
        viewtable = SCHEDULE_VIEWS[viewkey][0]
        dsql = " from %s where %s" % (viewtable, sqld)
        sqlapi.SQLdelete(dsql)
    if all:
        dsql = " from cdbpcs_res_schedule where %s" % (sqld)
        sqlapi.SQLdelete(dsql)


def update_workdays(pattern_name, table, condition):
    if is_oracle():
        pattern = load_pattern(f"{pattern_name}_ora")
    elif is_postgres():
        pattern = load_pattern(f"{pattern_name}_postgres")
    else:
        pattern = load_pattern(pattern_name)

    sqlapi.SQLupdate(pattern.format(
        table=table,
        condition=condition,
    ))


def adjust_values_many(table, task_uuids):
    from cs.pcs.resources import db_tools

    if not task_uuids:
        return

    view = f"{table}_v"
    assigned = []
    unassigned = []

    oor = db_tools.OneOfReduced(table_name=view)
    query = oor.get_expression(
        column_name="task_object_id",
        values=task_uuids,
    )
    records = sqlapi.RecordSet2(
        sql=f"""
        SELECT cdb_object_id, assignment_oid
        FROM {view}
        WHERE {query}"""
    )

    for rec in records:
        if rec.assignment_oid:
            assigned.append(rec.cdb_object_id)
        else:
            unassigned.append(rec.cdb_object_id)

    query_assigned = oor.get_expression(
        column_name="cdb_object_id",
        values=assigned,
        table_alias=table,
    )
    query_unassigned = oor.get_expression(
        column_name="cdb_object_id",
        values=unassigned,
        table_alias=table,
    )

    with transactions.Transaction():
        # entries without tasks -> no workdays/daily hours
        # (should not happen; this is only called with task context)

        update_workdays("update_workdays_pool_assignment", table, query_assigned)
        update_workdays("update_workdays_no_pool_assignment", table, query_unassigned)

        hours = "CAST(hours AS NUMERIC)" if is_postgres() else "hours"

        # set daily hours
        sqlapi.SQLupdate(
            f"""{table} SET hours_per_day = CASE
            WHEN workdays > 0 THEN ROUND({hours} / workdays, 2)
            ELSE 0.0 END
            WHERE {query_assigned}
                OR {query_unassigned}"""
        )


SCHEDULE_VIEWS = {
    DAY: (
        "cdbpcs_res_schedule",
        getDayIntervals,
        getDayFrame,
        "cdbpcs_capa_sched_pd",
    ),
    WEEK: (
        "cdbpcs_res_sched_pw",
        getWeekIntervals,
        getWeekFrame,
        "cdbpcs_capa_sched_pw",
    ),
    MONTH: (
        "cdbpcs_res_sched_pm",
        getMonthIntervals,
        getMonthFrame,
        "cdbpcs_capa_sched_pm",
    ),
    QUARTER: (
        "cdbpcs_res_sched_pq",
        getQuarterIntervals,
        getQuarterFrame,
        "cdbpcs_capa_sched_pq",
    ),
    HALFYEAR: (
        "cdbpcs_res_sched_ph",
        getHalfYearIntervals,
        getHalfYearFrame,
        "cdbpcs_capa_sched_ph",
    ),
}


class RessourceDemand(Object):
    __classname__ = "cdbpcs_prj_demand"
    __maps_to__ = "cdbpcs_prj_demand"

    Project = Reference(1, fProject, fRessourceAssignment.cdb_project_id)
    Task = Reference(
        1, fTask, fRessourceAssignment.cdb_project_id, fRessourceAssignment.task_id
    )
    Assignments = Reference(
        N,
        fRessourceAssignment,
        fRessourceAssignment.cdb_project_id == fRessourceDemand.cdb_project_id,
        fRessourceAssignment.cdb_demand_id == fRessourceDemand.cdb_demand_id,
    )

    ResourcePool = Reference(1, fResourcePool, fRessourceDemand.pool_oid)
    ResourcePoolAssignment = Reference(
        1,
        fResourcePoolAssignment,
        fResourcePoolAssignment.cdb_object_id == fRessourceDemand.assignment_oid,
    )
    Resource = Reference(1, fResource, fRessourceDemand.resource_oid)

    DemandSchedules = Reference(
        N,
        fDemandSchedule,
        fDemandSchedule.cdb_project_id == fRessourceDemand.cdb_project_id,
        fDemandSchedule.task_id == fRessourceDemand.task_id,
        fDemandSchedule.cdb_demand_id == fRessourceDemand.cdb_demand_id,
    )

    # tolerance for calculations
    Tolerance = 0.01

    # Flags to disallow the break down structure of demands, which means:
    #     resource demands can be created for a task if:
    #     - there is no demand entry of the same type attached to the ancestors of current task and
    #     - there is no demand entry of the same type attached to the descendants of current task.
    #     - there is no demand entry of the same type from same task attached to the ancestors of org./person and
    #     - there is no demand entry of the same type from same task attached to the descendants of this org.
    __NO_TASK_BREAK_DOWN__ = True
    __NO_ORG_BREAK_DOWN__ = False
    # Flag to allow the missing target deadlines to be automatically set using plan values while creating
    # demand/assignment
    __AUTO_SET_DEADLINE__ = True

    @classmethod
    def getDemands(
        cls,
        pool_list,
        res_list,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        all_status=False,
    ):
        if not pool_list and not res_list or not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = (
            "SELECT cdbpcs_prj_demand.*"
            ", (cdbpcs_prj_demand.hours - cdbpcs_prj_demand.hours_assigned) AS hours_open"
            ", ((cdbpcs_prj_demand.hours - cdbpcs_prj_demand.hours_assigned)"
            " / (cdbpcs_task.duration_fcast/8)) AS hpd_open"
            ", cdbpcs_task.%s AS start_time_fcast"
            ", cdbpcs_task.%s AS end_time_fcast" % (dStartTimeField, dEndTimeField)
        )
        sqlFrom = " FROM cdbpcs_prj_demand, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_task.milestone != 1"
            " AND cdbpcs_task.duration_fcast > 0"
            " AND cdbpcs_prj_demand.coverage = 0"
            " AND cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        # evaluate time frame
        if start_date and end_date:
            sd = sqlapi.SQLdbms_date(start_date)
            ed = sqlapi.SQLdbms_date(end_date)
            sqlWhere += (
                " AND (%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "cdbpcs_task.%s <= %s AND %s <= cdbpcs_task.%s)"
                % (
                    sd,
                    dStartTimeField,
                    dStartTimeField,
                    ed,
                    sd,
                    dEndTimeField,
                    dEndTimeField,
                    ed,
                    dStartTimeField,
                    sd,
                    ed,
                    dEndTimeField,
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            rule_cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(rule_cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_demand.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, (prj_rule.expr(rule_cls)))
            )
        if with_prj_ids:
            sqlWithPrj = "cdbpcs_prj_demand.cdb_project_id IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in with_prj_ids]
            )
        if without_prj_ids:
            sqlWithoutPrj = "cdbpcs_prj_demand.cdb_project_id NOT IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in without_prj_ids]
            )
        sqlWhere += " AND (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

        # evaluate pool and resource parameters
        sqlOrg = sqlRes = "1=0"
        if pool_list:
            pool_list_str = ",".join(["'%s'" % sqlapi.quote(x) for x in pool_list])
            subSelect = (
                "SELECT resource_oid FROM cdbpcs_pool_assignment WHERE pool_oid IN (%s)"
                % pool_list_str
            )
            sqlOrg = (
                "(cdbpcs_prj_demand.pool_oid IN (%s)"
                " OR cdbpcs_prj_demand.resource_oid IN (%s))"
                % (pool_list_str, subSelect)
            )
        if res_list:
            res_list_str = ",".join(["'%s'" % sqlapi.quote(x) for x in res_list])
            sqlRes = "cdbpcs_prj_demand.resource_oid IN (%s)" % res_list_str
        sqlWhere += " AND (%s OR %s)" % (sqlOrg, sqlRes)

        # send statement
        return sqlapi.RecordSet2(sql=sqlSelect + sqlFrom + sqlWhere)

    @classmethod
    def on_cdbpcs_demand_open_now(cls, ctx):
        mysql = "SELECT cdb_demand_id FROM cdbpcs_prj_demand_v WHERE 1=1"
        args = {}
        prj_id = ""
        if ctx.dialog["cdb_project_id"]:
            prj_id = ctx.dialog["cdb_project_id"]
            args["cdb_project_id"] = ctx.dialog["cdb_project_id"]
            mysql += " AND cdb_project_id = '%(cdb_project_id)s'" % ctx.dialog
        if ctx.dialog["task_id"]:
            args["task_id"] = ctx.dialog["task_id"]
            mysql += " AND task_id = '%(task_id)s'" % ctx.dialog
        if ctx.dialog["pool_oid"]:
            args["pool_oid"] = ctx.dialog["pool_oid"]
            mysql += " AND org_id = '%(pool_oid)s'" % ctx.dialog
        if ctx.dialog["pool_oid"]:
            args["resource_oid"] = ctx.dialog["resource_oid"]
            mysql += " AND resource_oid = '%(resource_oid)s'" % ctx.dialog
        if ctx.dialog["start_time_fcast"]:
            args["end_time_fcast"] = ">=" + ctx.dialog["start_time_fcast"]
            mysql += " AND end_time_fcast >= %s" % sqlapi.SQLdbms_date(
                ctx.dialog["start_time_fcast"]
            )
        if ctx.dialog["end_time_fcast"]:
            args["start_time_fcast"] = "<=" + ctx.dialog["end_time_fcast"]
            mysql += " AND start_time_fcast <= %s" % sqlapi.SQLdbms_date(
                ctx.dialog["end_time_fcast"]
            )

        sqlWhere = "cdb_project_id = '%s' AND cdb_demand_id IN (%s)" % (prj_id, mysql)
        result = RessourceDemand.Query(sqlWhere)
        if len(result) > 1:
            link = result[0].MakeURL("CDB_Search", **args)
            ctx.url(link)
        elif len(result):
            obj = result[0]
            args = {}
            for k, v in list(obj.items()):
                args[k] = v
            link = obj.MakeURL("CDB_Modify")
            ctx.url(link)
        else:
            arg_names = [x.name for x in RessourceDemand.GetFields()]
            arg_names = [x for x in arg_names if x in ctx.dialog.get_attribute_names()]
            args = [(x, ctx.dialog[x]) for x in arg_names]
            ctx.set_followUpOperation(
                "CDB_Create", keep_rship_context=True, predefined=args
            )

    def MakeCopy(self, new_project, new_task):
        from cdb import cdbuuid

        new_resource_demand_check = RessourceDemand(**self._record)
        if new_resource_demand_check.HasField("cdb_object_id"):
            new_resource_demand_check.cdb_object_id = cdbuuid.create_uuid()
        new_resource_demand_check.cdb_project_id = new_project.cdb_project_id
        new_resource_demand_check.task_id = new_task.task_id

        # Important! No duplicate demand_id any more.
        # Remove cdb_demand_id, it will be regenerated in _create_from_pre_check()
        new_resource_demand_check.cdb_demand_id = "#"
        # Check resource demand before cdbpcs_create_from operation
        new_resource_demand_check._create_from_pre_check()
        new_resource_demand_check.Update(
            **RessourceDemand.MakeChangeControlAttributes()
        )

        # Copy resource demand
        new_resource_demand = fRessourceDemand.Create(**new_resource_demand_check)
        # Check copied resource demand
        new_resource_demand.Reload()
        new_resource_demand._create_from_post_check()

        return new_resource_demand

    def _generate_id(self):
        return "D" + ("%s" % util.nextval("cdbpcs_prj_demand")).zfill(9)

    @classmethod
    def adjust_values_many(cls, task_uuids):
        adjust_values_many(cls.__maps_to__, task_uuids)

    def adjust_values(self, createSchedules=True):
        obj = self.getPersistentObject()
        obj.setWorkdays()
        obj.hours_changed()
        if not obj.hours_per_day:
            obj.Task.work_uncovered = 1
        if createSchedules:
            obj.createSchedules()

    def hours_changed(self, ctx=None):
        if self.hours and self.Task:
            self.hours = max(self.hours, 0.0)
            myDays = float(self.workdays)
            if myDays:
                self.hours_per_day = round(self.hours / myDays, 2)
                ctx and ctx.set("cdbpcs_prj_demand.hours_per_day", self.hours_per_day)
            else:
                self.hours_per_day = ""
                ctx and ctx.set("cdbpcs_prj_demand.hours_per_day", 0.00)
        else:
            self.hours_per_day = ""
            ctx and ctx.set("cdbpcs_prj_demand.hours_per_day", 0.00)

    def hours_per_day_changed(self, ctx=None):
        if self.workdays and self.hours_per_day and self.Task:
            self.hours = self.hours_per_day * self.workdays
            ctx and ctx.set("cdbpcs_prj_demand.hours", self.hours)
        self.hours_changed(ctx)

    def getWorkdays(self, task=None):
        if not task:
            task = fTask.ByKeys(self.cdb_project_id, self.task_id)
        if task:
            if self.ResourcePoolAssignment:
                return task.getWorkdays(
                    assignment_oid=self.ResourcePoolAssignment.cdb_object_id
                )
            return task.getWorkdays()
        return 0

    # === new class methods to optimize the calendar logic ===
    @classmethod
    def clsHoursChanged(cls, task, demand):
        result = {}
        if demand["hours"] and task:
            if demand["hours"] < 0.0:
                result["hours"] = 0.0
                result["hours_per_day"] = 0.0
            else:
                myDays = float(cls.clsGetWorkdays(task, demand))
                if myDays:
                    result["hours_per_day"] = round(demand["hours"] / myDays, 2)
                else:
                    result["hours_per_day"] = ""
        else:
            result["hours_per_day"] = ""
        return result

    @classmethod
    def clsGetWorkdays(cls, task, obj):
        if task:
            if obj.ResourcePoolAssignment:
                return fTask.clsGetWorkdays(task, obj.ResourcePoolAssignment.person_id)
            return fTask.clsGetWorkdays(task)
        return 0

    @classmethod
    def clsCheckDemandCoverage(cls, demand, assigned_hours):
        # sum all assignments to compare it to demand
        result = {"hours_assigned": assigned_hours}
        if demand["hours"] > assigned_hours + cls.Tolerance:
            # not enough capacity scheduled...
            result["coverage"] = 0
        else:
            # demand is covered...
            result["coverage"] = 1
        return result

    def demandRemainderInHours(self):
        if self.hours:
            return float(self.hours - self.assigned("hours"))
        return -self.assigned("hours")

    def demandRemainderInHoursPerDay(self):
        if self.hours and self.hours_per_day:
            return self.hours_per_day * float(
                self.demandRemainderInHours() / self.hours
            )
        return -self.assigned("hours_per_day")

    def assigned(self, attr):
        return functools.reduce(
            lambda a, b: a + b, [x for x in [x[attr] for x in self.Assignments] if x], 0
        )

    def check_demand_coverage(self, ctx=None):
        if ctx and ctx.action == "create":
            return
        asgnhours = self.assigned("hours")
        dem = self.getPersistentObject()
        if dem and dem.hours_assigned != asgnhours:
            dem.hours_assigned = asgnhours
            dem.createSchedules()
        elif dem and ctx and ctx.action == "modify":
            sqlstr = (
                "select sum(value) sum_value from %s "
                "where cdb_project_id='%s' and task_id='%s' "
                " and cdb_demand_id='%s'"
                % (
                    fDemandSchedule.GetTableName(),
                    dem.cdb_project_id,
                    dem.task_id,
                    dem.cdb_demand_id,
                )
            )
            ssum = sqlapi.RecordSet2(sql=sqlstr)
            value = 0
            try:
                value = float(ssum[0].sum_value)
            except Exception:  # nosec
                pass
            if abs(dem.hours - asgnhours - value) > dem.Tolerance:
                dem.createSchedules()
        if dem and dem.hours > dem.hours_assigned + dem.Tolerance:
            # not enough capacity scheduled...
            dem.coverage = 0
        else:
            # demand is covered...
            dem.coverage = 1
        self.Reload()
        if self.Task:
            self.Task.validateSchedule_many([self.Task])

    def dialog_item_change(self, ctx):
        self.setWorkdays(ctx)
        if ctx.changed_item == "pool_oid":
            self.hours_changed(ctx)
        elif ctx.changed_item == "original_resource_oid":
            self.hours_changed(ctx)
        elif ctx.changed_item == "hours":
            self.hours_changed(ctx)
        elif ctx.changed_item == "hours_per_day":
            self.hours_per_day_changed(ctx)
        elif ctx.changed_item in {"task_name", "task_id"}:
            self.propose_demand(ctx)
        elif self.subject_id == "" and self.org_id == "":
            self.demand_type = ""

        # do some checks
        self.set_demand_type()
        # self.check_demand_coverage()

    def set_id(self, ctx):
        if not self.cdb_demand_id or self.cdb_demand_id == "#":
            self.cdb_demand_id = self._generate_id()

    def setWorkdays(self, ctx=None):
        days = self.getWorkdays()
        if self.workdays != days:
            self.workdays = days
        ctx and ctx.set("cdbpcs_prj_demand.workdays", days)
        return days

    def set_task_name(self, ctx):
        if self.Task:
            ctx.set("task_name", self.Task.task_name)
            if ctx and ctx.action != "copy":
                ctx.set_readonly("task_name")

    def getHoursPerDay(self, hours=0.0):
        days = float(self.workdays)
        if not days:
            return ""
        if not hours:
            hours = self.hours or 0
        return round(hours / days, 2)

    def propose_demand(self, ctx):
        days = self.setWorkdays()
        hours = 0.0
        task = fTask.ByKeys(self.cdb_project_id, self.task_id)
        if task:
            hours = task.demandRemainderInHours()

        if not days:
            self.hours_per_day = ""
        elif ctx or self.hours is None and hours and task:
            if hasattr(ctx, "action") and ctx.action == "create":
                self.hours = max(0.0, hours)
                self.hours_per_day = self.getHoursPerDay()
            if (
                hasattr(ctx, "get_operation_name")
                and ctx.get_operation_name() == kOperationNew
            ):
                ctx.set("cdbpcs_prj_demand.hours", max(0.0, hours))
                ctx.set("cdbpcs_prj_demand.hours_per_day", self.getHoursPerDay(hours))
        elif not self.hours:
            self.hours = 0.0
            ctx.set("cdbpcs_prj_demand.hours", max(0.0, self.hours))
            self.hours_per_day = 0.0
            ctx.set("cdbpcs_prj_demand.hours_per_day", 0.0)
        if ctx:
            if (
                (hasattr(ctx, "action") and ctx.action == "modify")
                or (
                    hasattr(ctx, "get_operation_name")
                    and ctx.get_operation_name() == kOperationModify
                )
                and self.task_id == ctx.object.task_id
                and self.hours
            ):
                hours += self.hours
            ctx.set("hours_max", max(0.0, hours))
            ctx.set(".hours_max", max(0.0, hours))

            if task:
                ctx.set("cdbpcs_task.start_time_fcast", task.start_time_fcast)
                ctx.set("cdbpcs_task.end_time_fcast", task.end_time_fcast)

    def adjust_hours(self):
        self.check_demand_coverage()

    def set_demand_type(self, ctx=None):
        if self.subject_type == "Person":
            self.demand_type = 5
        elif self.subject_type == "PCS Role":
            self.demand_type = 2
        elif not self.org_id:
            self.demand_type = 3
        else:
            self.demand_type = ""

    def check_subject(self, ctx=None, hook=None):
        myPool = fResourcePool.ByKeys(self.pool_oid) if self.pool_oid else None
        if not myPool:
            if hook:
                hook.set_error("", Message.GetMessage("cdb_capa_err_012"))
            else:
                raise ue.Exception("cdb_capa_err_012")
        myResAssign = (
            fResourcePoolAssignment.ByKeys(cdb_object_id=self.assignment_oid)
            if self.assignment_oid
            else None
        )

        # Resource demands can be attached to a org./person if:
        # (- there is no demand entry of the same type from same task attached to the ancestors of org./person and)
        # (- there is no demand entry of the same type from same task attached to the descendants of this org.)
        if self.__NO_ORG_BREAK_DOWN__:
            errmsg = ""
            if myResAssign:
                errmsg = RessourceDemand.noHeadOrgDemand(
                    self.cdb_project_id,
                    self.task_id,
                    myResAssign.pool_oid,
                    self.resource_type,
                )
            elif myPool.parent_oid:
                errmsg = RessourceDemand.noHeadOrgDemand(
                    self.cdb_project_id,
                    self.task_id,
                    myPool.parent_oid,
                    self.resource_type,
                )
            if not errmsg:
                errmsg = RessourceDemand.noSubOrgDemand(
                    self.cdb_project_id, self.task_id, self.pool_oid, self.resource_type
                )
            if errmsg:
                raise ue.Exception("pcs_capa_err_017", errmsg)
            demands = RessourceDemand.Query(
                "cdb_project_id = '%(cdb_project_id)s' AND "
                "task_id = '%(task_id)s' AND "
                "pool_oid = '%(pool_oid)s' AND "
                "resource_oid = '%(resource_oid)s' AND "
                "resource_type LIKE '%(resource_type)s' AND "
                "cdb_demand_id <> '%(cdb_demand_id)s'" % self
            )
            if len(demands) > 0:
                raise ue.Exception("pcs_capa_err_019", demands[0].GetDescription())

    def check_task(self, ctx=None, hook=None):
        # Resource demands can be created for a task if:
        # - target start/end dates are set
        # (- there is no demand entry of the same type attached to the ancestors of this task and)
        # (- there is no demand entry of the same type attached to the descendants of this task.)
        if self.Task:
            if self.Task.milestone:
                if hook:
                    hook.set_error("", Message.GetMessage("cdb_capa_err_009"))
                else:
                    raise ue.Exception("cdb_capa_err_009")
            if not self.Task.getDemandStartTime() or not self.Task.getDemandEndTime():
                if self.__AUTO_SET_DEADLINE__ and self.Task.acceptAllocation():
                    if (ctx and ctx.mode == "post_mask") or hook:
                        # auto adjust task deadlines
                        self.Task.autoSetDemandTime(ctx)
                else:
                    if hook:
                        hook.set_error("", Message.GetMessage("pcs_capa_err_024"))
                    else:
                        raise ue.Exception("pcs_capa_err_024")
            if (
                (ctx and ctx.mode == "post_mask") or hook
            ) and self.__NO_TASK_BREAK_DOWN__:
                task_id = RessourceDemand.noParentTaskDemand(
                    self.cdb_project_id, self.Task.parent_task, self.resource_type
                )
                if not task_id:
                    task_id = RessourceDemand.noSubTaskDemand(
                        self.cdb_project_id, self.task_id, self.resource_type
                    )
                if task_id:
                    task = fTask.ByKeys(self.cdb_project_id, task_id)
                    if task:
                        if hook:
                            msg = Message.GetMessage(
                                "pcs_capa_err_015", task.GetDescription()
                            )
                            hook.set_error("", msg)
                        else:
                            raise ue.Exception(
                                "pcs_capa_err_015", task.GetDescription()
                            )

    @classmethod
    def noParentTaskDemand(cls, cdb_project_id, parent_id, resource_type):
        if not parent_id:
            return ""
        cond1 = "cdb_project_id='%s' AND task_id='%s' AND resource_type LIKE '%s'" % (
            cdb_project_id,
            parent_id,
            resource_type,
        )
        cond2 = "cdb_project_id='%s' AND task_id='%s' AND ce_baseline_id = ''" % (
            cdb_project_id,
            parent_id,
        )
        demands = RessourceDemand.Query(cond1)
        if len(demands) > 0:
            return demands[0].task_id
        else:
            parents = sqlapi.RecordSet2(fTask.GetTableName(), cond2, ["parent_task"])
            if len(parents) > 0:
                return cls.noParentTaskDemand(
                    cdb_project_id, parents[0].parent_task, resource_type
                )
            else:
                return ""

    @classmethod
    def noSubTaskDemand(cls, cdb_project_id, parent_id, resource_type):
        cond1 = (
            "resource_type LIKE '%s' AND cdb_project_id='%s' AND task_id IN "
            "(SELECT tt1.task_id FROM %s tt1 "
            "WHERE tt1.cdb_project_id='%s' AND tt1.parent_task='%s' AND tt1.ce_baseline_id = '')"
            % (
                resource_type,
                cdb_project_id,
                fTask.GetTableName(),
                cdb_project_id,
                parent_id,
            )
        )
        cond2 = "cdb_project_id='%s' AND parent_task='%s' AND ce_baseline_id = ''" % (
            cdb_project_id,
            parent_id,
        )
        demands = RessourceDemand.Query(cond1)
        if len(demands) > 0:
            return demands[0].task_id
        else:
            children = sqlapi.RecordSet2(fTask.GetTableName(), cond2, ["task_id"])
            if len(children) > 0:
                for cld in children:
                    tid = cls.noSubTaskDemand(
                        cdb_project_id, cld.task_id, resource_type
                    )
                    if tid:
                        return tid
            return ""

    @classmethod
    def noHeadOrgDemand(cls, cdb_project_id, task_id, pool_oid, resource_type):
        cond1 = (
            "cdb_project_id='%s' AND task_id='%s' AND pool_oid='%s' AND resource_type LIKE '%s'"
            % (cdb_project_id, task_id, pool_oid, resource_type)
        )
        cond2 = "pool_oid='%s'" % (pool_oid)
        if len(cls.Query(cond1)) > 0:
            mypool = fResourcePool.ByKeys(pool_oid)
            if mypool:
                return mypool.GetDescription()
        else:
            parents = sqlapi.RecordSet2(
                fResourcePool.GetTableName(), cond2, ["parent_oid"]
            )
            if len(parents) > 0:
                return cls.noHeadOrgDemand(
                    cdb_project_id, task_id, parents[0].parent_oid, resource_type
                )
        return ""

    @classmethod
    def noSubOrgDemand(cls, cdb_project_id, task_id, pool_oid, resource_type):
        cond1 = (
            "resource_type LIKE '%s' AND cdb_project_id='%s' AND task_id='%s' AND "
            "(pool_oid IN (SELECT o1.pool_oid FROM %s o1 WHERE o1.parant_oid='%s') OR "
            "resource_oid IN (SELECT p1.resource_oid FROM %s p1 WHERE p1.pool_oid='%s'))"
            % (
                resource_type,
                cdb_project_id,
                task_id,
                fResourcePool.GetTableName(),
                pool_oid,
                fResourcePoolAssignment.GetTableName(),
                pool_oid,
            )
        )
        cond2 = "parent_oid='%s'" % (pool_oid)
        objs = cls.Query(cond1)
        if len(objs) > 0:
            if objs[0].pool_oid:
                myPool = fResourcePool.ByKeys(objs[0].pool_oid)
                if myPool:
                    return myPool.GetDescription()
            elif objs[0].resource_oid:
                myRes = fResource.ByKeys(objs[0].resource_oid)
                if myRes:
                    return myRes.GetDescription()
        else:
            children = sqlapi.RecordSet2(
                fResourcePool.GetTableName(), cond2, ["pool_oid"]
            )
            if len(children) > 0:
                for cld in children:
                    msg = cls.noSubOrgDemand(
                        cdb_project_id, task_id, cld.pool_oid, resource_type
                    )
                    if msg:
                        return msg
        return ""

    def ask_user(self, ctx):
        # Create a message box
        msgbox = ctx.MessageBox(
            "cdb_capa_adjust_02", [], "adjust", ctx.MessageBox.kMsgBoxIconQuestion
        )
        msgbox.addButton(ctx.MessageBoxButton("pcs_adjust_yes", "pcs_adjust_yes"))
        msgbox.addButton(ctx.MessageBoxButton("pcs_adjust_no", "pcs_adjust_no"))
        msgbox.addCancelButton(1)
        ctx.show_message(msgbox)

    def assignTeamMember(self, ctx):
        if (
            self.Project
            and not self.Project.template
            and self.ResourcePoolAssignment
            and self.ResourcePoolAssignment.Person
        ):
            self.Project.assignDefaultRoles(self.ResourcePoolAssignment.Person)

    def setDefaults(self, ctx):
        self.coverage = 0
        self.hours_assigned = 0.0

    def _create_from_pre_check(self, ctx=None):
        # Check follows before cdbpcs_create_from operation
        # 1. set_id
        # 2. setDefaults
        self.set_id(ctx)
        self.setDefaults(ctx)

    def _create_from_post_check(self, ctx=None):
        # Check check_demand_coverage after cdbpcs_create_from operation
        self.assignTeamMember(ctx)
        self.check_demand_coverage(ctx)
        self.createSchedules()

    def final_check(self, ctx):
        from cs.pcs import projects

        if hasattr(projects, "tasks_efforts"):
            projects.tasks_efforts.aggregate_changes(self.Project)

    def createSchedules(self, _ctx=None):
        fSCHEDULE_CALCULATOR.createSchedules_many([self.Task.cdb_object_id])

    @classmethod
    def updateScheduleViews(cls, obj):
        # load all entries within DemandSchedule
        data = {
            "cdb_project_id": obj.cdb_project_id,
            "task_id": obj.task_id,
            "cdb_demand_id": obj.cdb_demand_id,
        }
        sterms = ["%s='%s'" % (k, v) for (k, v) in data.items()]
        sqld = " and ".join(sterms)
        data["resource_oid"] = obj.resource_oid
        data["resource_type"] = obj.resource_type

        if obj.pool_oid:
            data["pool_oid"] = obj.pool_oid
        else:
            pool_oids = sqlapi.RecordSet2(
                fResourcePoolAssignment.GetTableName(),
                "resource_oid='%s'" % obj.resource_oid,
                ["pool_oid"],
            )
            if len(pool_oids):
                data["pool_oid"] = pool_oids[0].pool_oid

        data["cdb_alloc_id"] = ""
        sterms = ["%s='%s'" % (k, v) for (k, v) in data.items()]
        sql0 = " AND ".join(sterms)
        schedcond = "cdb_project_id='%s' AND task_id='%s' AND cdb_demand_id='%s'" % (
            obj.cdb_project_id,
            obj.task_id,
            obj.cdb_demand_id,
        )
        scheds = sqlapi.RecordSet2(fDemandSchedule.GetTableName(), schedcond)

        # iterate entries
        for viewkey in list(SCHEDULE_VIEWS):
            viewtable = SCHEDULE_VIEWS[viewkey][0]
            viewfunc = SCHEDULE_VIEWS[viewkey][1]

            dsql = " FROM %s WHERE %s" % (viewtable, sqld)
            sqlapi.SQLdelete(dsql)

            for sched in scheds:
                sstart = sched.start_date.date()
                send = sched.end_date.date()
                ivals = viewfunc(sstart, send)
                for ival in list(ivals):
                    start_date = to_legacy_str(ival)
                    days = ivals[ival]
                    sql = sql0 + " AND start_date=%s" % sqlapi.SQLdbms_date(start_date)
                    rsets = sqlapi.RecordSet2(viewtable, sql)
                    nval = 0
                    if sched.value:
                        nval = sched.value * days
                    if len(rsets):
                        rset = rsets[0]
                        if rset.d_value:
                            nval += rset.d_value
                        if nval != rset.d_value:
                            rset.update(d_value=nval)
                    else:
                        inserter = util.DBInserter(viewtable)
                        for (k, v) in data.items():
                            inserter.add(k, v)
                        inserter.add("d_value", nval)
                        inserter.add("start_date", start_date)
                        inserter.insert()

    @classmethod
    def clsUpdateSchedules(cls, obj, start_date, end_date):
        if obj:
            fDemandSchedule.KeywordQuery(
                cdb_project_id=obj.cdb_project_id,
                task_id=obj.task_id,
                cdb_demand_id=obj.cdb_demand_id,
            ).Delete()
            # schedule objects for demands presents only the uncovered value
            newval = obj.hours - obj.hours_assigned
            intervals, wdays = fDemandSchedule.genScheduleIntervals(
                start_date, end_date, obj.cdb_project_id, obj.subject_id
            )
            if len(intervals):
                newdata = {
                    "value": newval / wdays,
                    "cdb_project_id": obj.cdb_project_id,
                    "task_id": obj.task_id,
                    "cdb_demand_id": obj.cdb_demand_id,
                }
                for i in range(len(intervals) / 2):
                    st = intervals[i * 2]
                    et = intervals[i * 2 + 1]
                    fDemandSchedule.Create(
                        start_date=to_legacy_str(st),
                        end_date=to_legacy_str(et),
                        **newdata
                    )
            cls.updateScheduleViews(obj)

    @classmethod
    def getAssignableDemands(cls, cdb_project_id, task_id, show_covered=True):
        result = []
        cond = "cdb_project_id='%s' AND task_id='%s'" % (cdb_project_id, task_id)
        parents = sqlapi.RecordSet2(
            fTask.GetTableName(),
            "{} AND ce_baseline_id = ''".format(cond),
            ["parent_task"],
        )
        if not show_covered:
            cond += " AND coverage <> 1"
        result += RessourceDemand.Query(cond)
        if len(parents):
            result += cls.getAssignableDemands(
                cdb_project_id, parents[0].parent_task, show_covered
            )
        return result

    def deleteScheduleViews(self, ctx=None):
        data = {
            "cdb_project_id": self.cdb_project_id,
            "task_id": self.task_id,
            "cdb_demand_id": self.cdb_demand_id,
        }
        deleteScheduleViews(data=data, all=True)

    def check_resource(self, ctx):
        if self.assignment_oid:
            if not fResourcePoolAssignment.ByKeys(cdb_object_id=self.assignment_oid):
                p = fPerson.ByKeys(cdb_object_id=self.assignment_oid)
                resource_assignment = p.ResourceMember[0] if p.ResourceMember else None
                if resource_assignment:
                    self.assignment_oid = resource_assignment.cdb_object_id
                    self.resource_oid = resource_assignment.resource_oid
                    self.pool_oid = resource_assignment.pool_oid
                    ctx.set(
                        "original_resource_oid",
                        resource_assignment.original_resource_oid,
                    )

    def adjust_pool_assignments(self, ctx=None):
        adjust_pool_assignments(assignment_oids=[self.assignment_oid])

    event_map = {
        (("create", "copy"), "pre_mask"): (
            "check_resource",
            "check_task",
            "set_task_name",
            "propose_demand",
        ),
        (("modify"), "pre_mask"): ("set_task_name", "propose_demand"),
        (("info"), "pre_mask"): ("set_task_name"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialog_item_change"),
        (("create", "copy", "modify"), "post_mask"): (
            "check_task",
            "check_subject",
            "set_demand_type",
        ),
        (("create", "copy"), "pre"): (
            "check_resource",
            "set_id",
            "setDefaults",
            "setWorkdays",
        ),
        (("modify"), "pre"): ("setWorkdays"),
        (("create"), "post"): (
            "assignTeamMember",
            "createSchedules",
            "adjust_pool_assignments",
            "final_check",
        ),
        (("copy", "modify"), "post"): (
            "assignTeamMember",
            "check_demand_coverage",
            "createSchedules",
            "adjust_pool_assignments",
            "final_check",
        ),
        (("delete"), "post"): (
            "deleteScheduleViews",
            "adjust_pool_assignments",
            "final_check",
        ),
        (("relship_copy"), "post"): ("assignTeamMember", "check_demand_coverage"),
    }


class RessourceAssignment(Object):
    __classname__ = "cdbpcs_prj_alloc"
    __maps_to__ = "cdbpcs_prj_alloc"

    Project = Reference(1, fProject, fRessourceAssignment.cdb_project_id)
    Task = Reference(
        1, fTask, fRessourceAssignment.cdb_project_id, fRessourceAssignment.task_id
    )
    ResourcePool = Reference(1, fResourcePool, fRessourceAssignment.pool_oid)
    ResourcePoolAssignment = Reference(
        1,
        fResourcePoolAssignment,
        fResourcePoolAssignment.cdb_object_id == fRessourceAssignment.assignment_oid,
    )
    Resource = Reference(1, fResource, fRessourceAssignment.resource_oid)
    Resources = Reference(
        N, fResource, fResource.cdb_object_id == fRessourceAssignment.resource_oid
    )

    def _getDemand(self):
        demands = fRessourceDemand.KeywordQuery(
            cdb_project_id=self.cdb_project_id, cdb_demand_id=self.cdb_demand_id
        )
        if len(demands) == 1:
            return demands[0]
        demands = fRessourceDemand.KeywordQuery(
            cdb_project_id=self.cdb_project_id,
            task_id=self.task_id,
            cdb_demand_id=self.cdb_demand_id,
        )
        if len(demands) == 1:
            return demands[0]
        return None

    Demand = ReferenceMethods_1(fRessourceDemand, lambda self: self._getDemand())

    AssignmentSchedules = Reference(
        N,
        fAssignmentSchedule,
        fAssignmentSchedule.cdb_project_id == fRessourceAssignment.cdb_project_id,
        fAssignmentSchedule.task_id == fRessourceAssignment.task_id,
        fAssignmentSchedule.cdb_alloc_id == fRessourceAssignment.cdb_alloc_id,
    )

    # Flags to disallow the break down structure of assignments, which means:
    #     resource assignments can be created for a task if:
    #     - there is no assignments entry of the same type attached to the ancestors of current task and
    #     - there is no assignments entry of the same type attached to the descendants of current task.
    #     - there is no assignments entry of the same type from same task attached to the ancestors of org./person and
    #     - there is no assignments entry of the same type from same task attached to the descendants of this org.
    __NO_TASK_BREAK_DOWN__ = False
    __NO_ORG_BREAK_DOWN__ = False
    # Flag to allow the missing target deadlines to be automatically set using plan values while creating
    # demand/assignment
    __AUTO_SET_DEADLINE__ = True

    # tolerance for calculations
    Tolerance = 0.01

    @classmethod
    def getAssignments(
        cls,
        pool_list,
        res_list,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        all_status=False,
    ):
        if not pool_list and not res_list or not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = (
            "SELECT cdbpcs_prj_alloc.*"
            ", (cdbpcs_prj_alloc.hours / (cdbpcs_task.duration_fcast/8)) AS hpd"
            ", cdbpcs_task.%s AS start_time_fcast"
            ", cdbpcs_task.%s AS end_time_fcast" % (aStartTimeField, aEndTimeField)
        )
        sqlFrom = " FROM cdbpcs_prj_alloc, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_task.milestone != 1"
            " AND cdbpcs_task.duration_fcast > 0"
            " AND cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        # evaluate time frame
        if start_date and end_date:
            sd = sqlapi.SQLdbms_date(start_date)
            ed = sqlapi.SQLdbms_date(end_date)
            sqlWhere += (
                " AND (%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "%s <= cdbpcs_task.%s AND cdbpcs_task.%s <= %s OR "
                "cdbpcs_task.%s <= %s AND %s <= cdbpcs_task.%s)"
                % (
                    sd,
                    aStartTimeField,
                    aStartTimeField,
                    ed,
                    sd,
                    aEndTimeField,
                    aEndTimeField,
                    ed,
                    aStartTimeField,
                    sd,
                    ed,
                    aEndTimeField,
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            rule_cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(rule_cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_alloc.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, (prj_rule.expr(rule_cls)))
            )
        if with_prj_ids:
            sqlWithPrj = "cdbpcs_prj_alloc.cdb_project_id IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in with_prj_ids]
            )
        if without_prj_ids:
            sqlWithoutPrj = "cdbpcs_prj_alloc.cdb_project_id NOT IN (%s)" % ",".join(
                ["'%s'" % sqlapi.quote(x) for x in without_prj_ids]
            )
        sqlWhere += " AND (%s OR %s) AND %s" % (sqlPrjRule, sqlWithPrj, sqlWithoutPrj)

        # evaluate pool and resource parameters
        sqlOrg = sqlRes = "1=0"
        if pool_list:
            pool_list_str = ",".join(["'%s'" % sqlapi.quote(x) for x in pool_list])
            subSelect = (
                "SELECT resource_oid FROM cdbpcs_pool_assignment WHERE pool_oid IN (%s)"
                % pool_list_str
            )
            sqlOrg = (
                "(cdbpcs_prj_alloc.pool_oid IN (%s) OR cdbpcs_prj_alloc.resource_oid IN (%s))"
                % (pool_list_str, subSelect)
            )
        if res_list:
            res_list_str = ",".join(["'%s'" % sqlapi.quote(x) for x in res_list])
            sqlRes = "cdbpcs_prj_alloc.resource_oid IN (%s)" % res_list_str
        sqlWhere += " AND (%s OR %s)" % (sqlOrg, sqlRes)

        # send statement
        return sqlapi.RecordSet2(sql=sqlSelect + sqlFrom + sqlWhere)

    @classmethod
    def on_cdbpcs_alloc_open_now(cls, ctx):
        result = RessourceAssignment.Query(
            "cdb_project_id = '%(cdb_project_id)s'"
            " AND task_id = '%(task_id)s'"
            " AND pool_oid = '%(pool_oid)s'"
            " AND resource_oid = '%(resource_oid)s'" % ctx.dialog
        )
        if result:
            obj = result[0]
            args = {}
            for k, v in obj.items():
                args[k] = v
            link = obj.MakeURL("CDB_Modify")
            ctx.url(link)
        else:
            arg_names = [x.name for x in RessourceAssignment.GetFields()]
            arg_names = [x for x in arg_names if x in ctx.dialog.get_attribute_names()]
            args = [(x, ctx.dialog[x]) for x in arg_names]
            ctx.set_followUpOperation(
                "CDB_Create", keep_rship_context=True, predefined=args
            )

    def _generate_id(self):
        return "A" + ("%s" % util.nextval("cdbpcs_prj_alloc")).zfill(9)

    def hours_changed(self, ctx=None):
        if self.hours and self.Task:
            self.hours = max(self.hours, 0.0)
            myDays = float(self.workdays)
            if myDays:
                self.hours_per_day = round(self.hours / myDays, 2)
                ctx and ctx.set("cdbpcs_prj_alloc.hours_per_day", self.hours_per_day)
            else:
                self.hours_per_day = 0
                ctx and ctx.set("cdbpcs_prj_alloc.hours_per_day", 0)
        else:
            self.hours_per_day = 0
            ctx and ctx.set("cdbpcs_prj_alloc.hours_per_day", 0)

    def hours_per_day_changed(self, ctx=None):
        if self.workdays and self.hours_per_day and self.Task:
            self.hours = self.hours_per_day * self.workdays
            ctx and ctx.set("cdbpcs_prj_alloc.hours", self.hours)
        self.hours_changed(ctx)

    def getWorkdays(self, task=None):
        if not task:
            task = fTask.ByKeys(self.cdb_project_id, self.task_id)
        if task:
            if self.ResourcePoolAssignment:
                return task.getWorkdays(self.ResourcePoolAssignment.cdb_object_id)
            return task.getWorkdays()
        return 0

    # === new class methods to optimize the calendar logic ===
    @classmethod
    def clsGetWorkdays(cls, task, obj):
        if task:
            if obj.ResourcePoolAssignment:
                return fTask.clsGetWorkdays(task, obj.ResourcePoolAssignment.person_id)
            return fTask.clsGetWorkdays(task)
        return 0

    @classmethod
    def clsHoursChanged(cls, task, assignment):
        # Caution: the parameters task and assignment can be DB Record
        # Do not treat them as CDB object
        result = {}
        try:
            if assignment["hours"] and task:
                if assignment["hours"] < 0.0:
                    result["hours"] = 0.0
                    result["hours_per_day"] = 0.0
                else:
                    myDays = float(cls.clsGetWorkdays(task, assignment))
                    if myDays:
                        result["hours_per_day"] = round(assignment["hours"] / myDays, 2)
                    else:
                        result["hours_per_day"] = ""
            else:
                result["hours_per_day"] = ""
        except Exception:  # nosec
            pass
        return result

    def demand_changed(self, ctx=None):
        if self.cdb_demand_id:
            demands = RessourceDemand.KeywordQuery(
                cdb_project_id=self.cdb_project_id, cdb_demand_id=self.cdb_demand_id
            )
            if len(demands) == 1:
                self.propose_assignment(ctx=ctx, demand=demands[0])

    def check_demand(self, ctx=None):
        project = fProject.ByKeys(self.cdb_project_id)
        if not project:
            raise ue.Exception("cdb_capa_err_007")
        if len(project.RessourceDemands):
            if self.cdb_demand_id:
                demands = RessourceDemand.KeywordQuery(
                    cdb_project_id=self.cdb_project_id, cdb_demand_id=self.cdb_demand_id
                )
                if len(demands) < 1:
                    raise ue.Exception("cdb_capa_err_007")

    def dialog_item_change(self, ctx):
        self.setWorkdays(ctx)
        if ctx.changed_item == "pool_oid":
            self.hours_changed(ctx)
        elif ctx.changed_item == "original_resource_oid":
            self.hours_changed(ctx)
        elif ctx.changed_item == "hours":
            self.hours_changed(ctx)
        elif ctx.changed_item == "hours_per_day":
            self.hours_per_day_changed(ctx)
        elif ctx.changed_item == "cdb_demand_id":
            self.demand_changed(ctx=ctx)
        elif self.persno == "" and self.org_id == "":
            self.alloc_type = ""

        # do some checks
        self.set_alloc_type()
        if self.Demand:
            self.Demand.check_demand_coverage()

    def set_id(self, ctx):
        if not self.cdb_alloc_id or self.cdb_alloc_id == "#":
            self.cdb_alloc_id = self._generate_id()

    def setWorkdays(self, ctx=None):
        days = self.getWorkdays()
        if self.workdays != days:
            self.workdays = days
            ctx and ctx.set("cdbpcs_prj_alloc.workdays", days)
        return days

    def getHoursPerDay(self, hours=0.0):
        days = float(self.workdays)
        if not days:
            return ""
        if not hours:
            hours = self.hours or 0
        return round(hours / days, 2)

    def propose_assignment(self, ctx=None, demand=None):
        days = self.setWorkdays()
        hours = 0.0
        t_hours = 0.0
        task = fTask.ByKeys(self.cdb_project_id, self.task_id)
        if task:
            t_hours = task.assignmentRemainderInHours()

        if not demand:
            demands = RessourceDemand.KeywordQuery(
                cdb_project_id=self.cdb_project_id, cdb_demand_id=self.cdb_demand_id
            )
            if len(demands) == 1:
                demand = demands[0]
                hours = demand.demandRemainderInHours()
                if t_hours > 0:
                    hours = min(hours, t_hours)

        if not days:
            self.hours_per_day = ""
        elif ctx or self.hours is None and hours:
            if hasattr(ctx, "action") and ctx.action == "create":
                self.hours = max(0.0, hours)
                self.hours_per_day = self.getHoursPerDay()
            if (
                hasattr(ctx, "get_operation_name")
                and ctx.get_operation_name() == kOperationNew
            ):
                ctx.set("cdbpcs_prj_alloc.hours", max(0.0, hours))
                ctx.set("cdbpcs_prj_alloc.hours_per_day", self.getHoursPerDay(hours))
        elif not self.hours:
            self.hours = 0.0
            self.hours_per_day = 0.0
        if ctx:
            if (
                (hasattr(ctx, "action") and ctx.action == "modify")
                or (
                    hasattr(ctx, "get_operation_name")
                    and ctx.get_operation_name() == kOperationModify
                )
                and self.cdb_demand_id == ctx.object.cdb_demand_id
                and self.hours
            ):
                hours += self.hours
            ctx.set("hours_max", max(0.0, hours))

    def set_task_id(self, ctx):
        if not self.Task and self.Demand:
            self.task_id = self.Demand.task_id

    def set_task_name(self, ctx):
        if self.Task:
            ctx.set("task_name", self.Task.task_name)
        elif self.task_id:
            task = fTask.ByKeys(self.cdb_project_id, self.task_id)
            if task:
                ctx.set("task_name", task.task_name)
        if self.task_id:
            if ctx and ctx.action not in ["copy", "create"]:
                ctx.set_readonly("task_name")

    def assignment_without_demand(self, ctx):
        if self.Project and len(self.Project.RessourceDemands):
            ctx.set_mandatory("cdb_demand_id")
        if self.Project and self.Task and not self.Demand:
            demands = fRessourceDemand.getAssignableDemands(
                self.cdb_project_id, self.task_id, False
            )
            demands = self.filterDemandsByPool(demands)
            demands = self.filterDemandsByResource(demands)
            if len(demands) == 1:
                self.cdb_demand_id = demands[0].cdb_demand_id

    def filterDemandsByResource(self, demands):
        return [
            d
            for d in demands
            if not d.resource_oid or d.resource_oid == self.resource_oid
        ]

    def filterDemandsByPool(self, demands):
        if self.ResourcePool:
            pool_oids = [self.pool_oid]
            for pool in self.ResourcePool.AllParentPools:
                pool_oids.append(pool.cdb_object_id)
            return [d for d in demands if d.pool_oid in pool_oids]
        return []

    @classmethod
    def adjust_values_many(cls, task_uuids):
        adjust_values_many(cls.__maps_to__, task_uuids)

    def adjust_values(self, createSchedules=True):
        obj = self.getPersistentObject()
        obj.setWorkdays()
        obj.hours_changed()
        if not obj.hours_per_day:
            obj.Task.work_uncovered = 1
        if createSchedules:
            obj.createSchedules()

    def adjust_hours(self):
        if self.Demand:
            self.Demand.check_demand_coverage()

    def set_alloc_type(self, ctx=None):
        if not self.persno == "":
            self.alloc_type = 7
        elif not self.org_id == "":
            self.alloc_type = 6
        else:
            self.alloc_type = ""

    def check_subject(self, ctx=None, hook=None):
        myPool = fResourcePool.ByKeys(self.pool_oid) if self.pool_oid else None
        if not myPool:
            if hook:
                hook.set_error("", Message.GetMessage("cdb_capa_err_005"))
            else:
                raise ue.Exception("cdb_capa_err_005")
        myResAssign = (
            fResourcePoolAssignment.ByKeys(cdb_object_id=self.assignment_oid)
            if self.assignment_oid
            else None
        )

        # Resource assignment can be attached to a org./person if:
        # (- there is no assignment entry of the same type attached to the ancestors of org./person and)
        # (- there is no assignment entry of the same type attached to the descendants of this org.)
        if self.__NO_ORG_BREAK_DOWN__:
            errmsg = ""
            if myResAssign:
                errmsg = RessourceAssignment.noHeadPoolAssignment(
                    self.cdb_project_id,
                    self.task_id,
                    myResAssign.pool_oid,
                    self.cdb_demand_id,
                )
            elif myPool.parent_oid:
                errmsg = RessourceAssignment.noHeadPoolAssignment(
                    self.cdb_project_id,
                    self.task_id,
                    myPool.parent_oid,
                    self.cdb_demand_id,
                )
            if not errmsg:
                errmsg = RessourceAssignment.noSubPoolAssignment(
                    self.cdb_project_id, self.task_id, self.pool_oid, self.cdb_demand_id
                )
            if errmsg:
                raise ue.Exception("pcs_capa_err_018", errmsg)
        asgns = RessourceAssignment.Query(
            "cdb_project_id = '%(cdb_project_id)s' AND "
            "task_id = '%(task_id)s' AND "
            "pool_oid = '%(pool_oid)s' AND "
            "resource_oid = '%(resource_oid)s' AND "
            "cdb_demand_id = '%(cdb_demand_id)s' AND "
            "cdb_alloc_id <> '%(cdb_alloc_id)s'" % self
        )
        if len(asgns) > 0:
            raise ue.Exception("pcs_capa_err_020", asgns[0].GetDescription())

    def check_task(self, ctx=None, hook=None):
        # Resource assignment can be created for a task if:
        # - target start/end dates are set
        # (- there is no assignment entry for the same demand attached to the ancestors of this task and)
        # (- there is no assignment entry for the same demand attached to the descendants of this task.)
        if self.Task:
            if self.Task.milestone:
                if hook:
                    hook.set_error("", Message.GetMessage("cdb_capa_err_009"))
                else:
                    raise ue.Exception("cdb_capa_err_009")
            if (
                not self.Task.getAssignmentStartTime()
                or not self.Task.getAssignmentEndTime()
            ):
                if self.__AUTO_SET_DEADLINE__ and self.Task.acceptAllocation():
                    if (ctx and ctx.mode == "post_mask") or hook:
                        # auto adjust task deadlines
                        self.Task.autoSetAssignmentTime(ctx)
                else:
                    if hook:
                        hook.set_error("", Message.GetMessage("pcs_capa_err_024"))
                    else:
                        raise ue.Exception("pcs_capa_err_024")
            if (
                (ctx and ctx.mode == "post_mask") or hook
            ) and self.__NO_TASK_BREAK_DOWN__:
                task_id = RessourceAssignment.noParentTaskAssignment(
                    self.cdb_project_id, self.Task.parent_task, self.cdb_demand_id
                )
                if not task_id:
                    task_id = RessourceAssignment.noSubTaskAssignment(
                        self.cdb_project_id, self.task_id, self.cdb_demand_id
                    )
                if task_id:
                    task = fTask.ByKeys(self.cdb_project_id, task_id)
                    if task:
                        if hook:
                            msg = Message.GetMessage(
                                "pcs_capa_err_016", task.GetDescription()
                            )
                            hook.set_error("", msg)
                        else:
                            raise ue.Exception(
                                "pcs_capa_err_016", task.GetDescription()
                            )

    @classmethod
    def noParentTaskAssignment(cls, cdb_project_id, parent_id, cdb_demand_id):
        cond1 = "cdb_project_id='%s' and task_id='%s' and cdb_demand_id='%s'" % (
            cdb_project_id,
            parent_id,
            cdb_demand_id,
        )
        cond2 = "cdb_project_id='%s' and task_id='%s' AND ce_baseline_id = ''" % (
            cdb_project_id,
            parent_id,
        )
        asgn = RessourceAssignment.Query(cond1)
        if len(asgn) > 0:
            return asgn[0].task_id
        else:
            parents = sqlapi.RecordSet2(fTask.GetTableName(), cond2, ["parent_task"])
            if len(parents) > 0:
                return cls.noParentTaskAssignment(
                    cdb_project_id, parents[0].parent_task, cdb_demand_id
                )
            else:
                return ""

    @classmethod
    def noSubTaskAssignment(cls, cdb_project_id, parent_id, cdb_demand_id):
        cond1 = (
            "cdb_project_id='%s' and task_id in "
            "(select tt1.task_id from %s tt1 "
            "where tt1.cdb_project_id='%s' and tt1.parent_task='%s' AND tt1.ce_baseline_id = '') "
            "and cdb_demand_id='%s'"
            % (
                cdb_project_id,
                fTask.GetTableName(),
                cdb_project_id,
                parent_id,
                cdb_demand_id,
            )
        )
        cond2 = "cdb_project_id='%s' and parent_task='%s' AND ce_baseline_id = ''" % (
            cdb_project_id,
            parent_id,
        )
        asgn = RessourceAssignment.Query(cond1)
        if len(asgn) > 0:
            return asgn[0].task_id
        else:
            children = sqlapi.RecordSet2(fTask.GetTableName(), cond2, ["task_id"])
            if len(children) > 0:
                for cld in children:
                    tid = cls.noSubTaskAssignment(
                        cdb_project_id, cld.task_id, cdb_demand_id
                    )
                    if tid:
                        return tid
            return ""

    @classmethod
    def noHeadPoolAssignment(cls, cdb_project_id, task_id, pool_oid, cdb_demand_id):
        cond1 = (
            "cdb_project_id='%s' AND task_id='%s' AND pool_oid='%s' AND cdb_demand_id='%s'"
            % (cdb_project_id, task_id, pool_oid, cdb_demand_id)
        )
        cond2 = "pool_oid='%s'" % (pool_oid)
        if len(cls.Query(cond1)) > 0:
            mypool = fResourcePool.ByKeys(pool_oid)
            if mypool:
                return mypool.GetDescription()
        else:
            parents = sqlapi.RecordSet2(
                fResourcePool.GetTableName(), cond2, ["parent_oid"]
            )
            if len(parents) > 0:
                return cls.noHeadPoolAssignment(
                    cdb_project_id, task_id, parents[0].parent_oid, cdb_demand_id
                )
        return ""

    @classmethod
    def noSubPoolAssignment(cls, cdb_project_id, task_id, pool_oid, cdb_demand_id):
        cond1 = (
            "cdb_demand_id='%s' AND cdb_project_id='%s' AND task_id='%s' AND "
            "(pool_oid IN (SELECT o1.pool_oid FROM %s o1 WHERE o1.parent_oid='%s') OR"
            "resource_oid IN (SELECT p1.resource_oid FROM %s p1 WHERE p1.pool_oid='%s'))"
            % (
                cdb_demand_id,
                cdb_project_id,
                task_id,
                fResourcePool.GetTableName(),
                pool_oid,
                fResourcePoolAssignment.GetTableName(),
                pool_oid,
            )
        )
        cond2 = "parent_oid='%s'" % (pool_oid)
        objs = cls.Query(cond1)
        if len(objs) > 0:
            if objs[0].pool_oid:
                myPool = fResourcePool.ByKeys(objs[0].pool_oid)
                if myPool:
                    return myPool.GetDescription()
            elif objs[0].resource_oid:
                myRes = fResource.ByKeys(objs[0].resource_oid)
                if myRes:
                    return myRes.GetDescription()
        else:
            children = sqlapi.RecordSet2(
                fResourcePool.GetTableName(), cond2, ["pool_oid"]
            )
            if len(children) > 0:
                for cld in children:
                    msg = cls.noSubPoolAssignment(
                        cdb_project_id, task_id, cld.pool_oid, cdb_demand_id
                    )
                    if msg:
                        return msg
        return ""

    def check_demand_coverage(self, ctx=None):
        assign = self.getPersistentObject()
        assigned = self.hours
        if not assign or ctx and ctx.action == "delete":
            assigned = 0.0
        if self.Demand:
            assigned = functools.reduce(
                lambda a, b: a + b,
                self.Demand.Assignments.Query(
                    "cdb_alloc_id<>'%s'" % self.cdb_alloc_id
                ).hours,
                assigned,
            )
            if self.Demand.hours_assigned != assigned:
                self.Demand.hours_assigned = assigned
                self.Demand.createSchedules()
            if self.Demand.hours > assigned + self.Tolerance:
                # not enough capacity scheduled...
                self.Demand.coverage = 0
            else:
                # demand is covered...
                self.Demand.coverage = 1
        if assign and ctx and ctx.action == "modify":
            sqlstr = (
                "select sum(value) sum_value from %s "
                "where cdb_project_id='%s' and task_id='%s' "
                " and cdb_alloc_id='%s'"
                % (
                    fAssignmentSchedule.GetTableName(),
                    self.cdb_project_id,
                    self.task_id,
                    self.cdb_alloc_id,
                )
            )
            ssum = sqlapi.RecordSet2(sql=sqlstr)
            value = 0
            try:
                value = float(ssum[0].sum_value)
            except Exception:  # nosec
                pass
            if abs(self.hours - value) > self.Tolerance:
                self.createSchedules()
        if self.Task:
            self.Task.validateSchedule_many([self.Task])

    def check_team(self, ctx):
        if not self.resource_oid:
            return
        if self.Demand:
            if self.Demand.pool_oid:
                pool = fResourcePool.ByKeys(self.Demand.pool_oid)
                if pool and not pool.containsResource(self.resource_oid):
                    demand_pool_name = self.Demand.mapped_pool_name
                    alloc_pool_name = self.mapped_pool_name
                    if isinstance(ctx, DialogHook):
                        self.ask_user_web(
                            ctx, "cdb_capa_info_01", alloc_pool_name, demand_pool_name
                        )
                    elif "assign" not in ctx.dialog.get_attribute_names():
                        self.ask_user(ctx, alloc_pool_name, demand_pool_name)
            if (
                self.Demand.resource_oid
                and self.Demand.resource_oid != self.resource_oid
            ):
                demand_name = "%s (%s)" % (
                    self.Demand.joined_resource_name,
                    self.Demand.mapped_pool_name,
                )
                resource = fResource.ByKeys(self.resource_oid)
                alloc_name = "%s (%s)" % (
                    resource.name,  # joined_resource_name not available from dialog hook
                    self.mapped_pool_name,
                )
                if isinstance(ctx, DialogHook):
                    self.ask_user_web(ctx, "cdb_capa_info_01", alloc_name, demand_name)
                elif "assign" not in ctx.dialog.get_attribute_names():
                    self.ask_user(ctx, alloc_name, demand_name)

    def assignTeamMember(self, ctx):
        if (
            self.Project
            and not self.Project.template
            and self.ResourcePoolAssignment
            and self.ResourcePoolAssignment.Person
        ):
            self.Project.assignDefaultRoles(self.ResourcePoolAssignment.Person)

    def ask_user(self, ctx, alloc_pool_name, demand_pool_name):
        # Create a message box
        msgbox = ctx.MessageBox(
            "cdb_capa_info_01",
            [alloc_pool_name, demand_pool_name],
            "assign",
            ctx.MessageBox.kMsgBoxIconQuestion,
        )
        msgbox.addYesButton(1)
        msgbox.addCancelButton(1)
        ctx.show_message(msgbox)

    def _create_from_pre_check(self, ctx=None):
        # Check set_id before cdbpcs_create_from operation
        self.set_id(ctx)

    def _create_from_post_check(self, ctx=None):
        # Check follows after cdbpcs_create_from operation
        self.assignTeamMember(ctx)
        self.check_demand_coverage(ctx)
        self.createSchedules()

    def final_check(self, ctx):
        from cs.pcs import projects

        if hasattr(projects, "tasks_efforts"):
            projects.tasks_efforts.aggregate_changes(self.Project)

    def set_readonly(self, ctx):
        ctx.set_readonly("task_name")

    def createSchedules(self, _ctx=None):
        fSCHEDULE_CALCULATOR.createSchedules_many([self.Task.cdb_object_id])

    @classmethod
    def updateScheduleViews(cls, obj):
        dmd = sqlapi.RecordSet2(
            fRessourceDemand.GetTableName(),
            "cdb_project_id='%s' and cdb_demand_id='%s'"
            % (obj.cdb_project_id, obj.cdb_demand_id),
            ["resource_type"],
        )
        if len(dmd):
            resource_type = dmd[0].resource_type
        else:
            return
        data = {
            "cdb_project_id": obj.cdb_project_id,
            "task_id": obj.task_id,
            "cdb_alloc_id": obj.cdb_alloc_id,
        }
        sterms = ["%s='%s'" % (k, v) for (k, v) in data.items()]
        sqld = " and ".join(sterms)
        data["resource_oid"] = obj.resource_oid
        data["resource_type"] = resource_type
        if obj.org_id:
            data["pool_oid"] = obj.pool_oid
        else:
            ids = sqlapi.RecordSet2(
                "cdbpcs_resource",
                "cdb_object_id='%s'" % obj.resource_oid,
                ["pool_oid"],
            )
            if len(ids):
                data["pool_oid"] = ids[0].pool_oid

        data["cdb_demand_id"] = ""
        sterms = ["%s='%s'" % (k, v) for (k, v) in data.items()]
        sql0 = " and ".join(sterms)
        schedcond = "cdb_project_id='%s' and task_id='%s' and cdb_alloc_id='%s'" % (
            obj.cdb_project_id,
            obj.task_id,
            obj.cdb_alloc_id,
        )
        scheds = sqlapi.RecordSet2(fAssignmentSchedule.GetTableName(), schedcond)
        for viewkey in list(SCHEDULE_VIEWS):
            viewtable = SCHEDULE_VIEWS[viewkey][0]
            viewfunc = SCHEDULE_VIEWS[viewkey][1]

            dsql = " from %s where %s" % (viewtable, sqld)
            sqlapi.SQLdelete(dsql)

            for sched in scheds:
                sstart = sched.start_date.date()
                send = sched.end_date.date()
                ivals = viewfunc(sstart, send)
                for ival in list(ivals):
                    start_date = to_legacy_str(ival)
                    days = ivals[ival]
                    sql = sql0 + " and start_date=%s" % sqlapi.SQLdbms_date(start_date)
                    rsets = sqlapi.RecordSet2(viewtable, sql)
                    nval = 0
                    if sched.value:
                        nval = sched.value * days
                    if len(rsets):
                        rset = rsets[0]
                        if rset.a_value:
                            nval += rset.a_value
                        if nval != rset.a_value:
                            rset.update(a_value=nval)
                    else:
                        inserter = util.DBInserter(viewtable)
                        for (k, v) in data.items():
                            inserter.add(k, v)
                        inserter.add("a_value", nval)
                        inserter.add("start_date", start_date)
                        inserter.insert()

    @classmethod
    def clsUpdateSchedules(cls, obj, start_date, end_date):
        if obj:
            fAssignmentSchedule.KeywordQuery(
                cdb_project_id=obj.cdb_project_id,
                task_id=obj.task_id,
                cdb_alloc_id=obj.cdb_alloc_id,
            ).Delete()
            intervals, wdays = fAssignmentSchedule.genScheduleIntervals(
                start_date, end_date, obj.cdb_project_id, obj.persno
            )
            if len(intervals):
                newdata = {
                    "value": obj.hours / wdays,
                    "cdb_project_id": obj.cdb_project_id,
                    "task_id": obj.task_id,
                    "cdb_alloc_id": obj.cdb_alloc_id,
                }
                for i in range(len(intervals) / 2):
                    st = intervals[i * 2]
                    et = intervals[i * 2 + 1]
                    fAssignmentSchedule.Create(
                        start_date=to_legacy_str(st),
                        end_date=to_legacy_str(et),
                        **newdata
                    )
            cls.updateScheduleViews(obj)

    def deleteScheduleViews(self, ctx=None):
        data = {
            "cdb_project_id": self.cdb_project_id,
            "task_id": self.task_id,
            "cdb_alloc_id": self.cdb_alloc_id,
        }
        deleteScheduleViews(data=data, all=True)

    def check_resource(self, ctx):
        if self.assignment_oid:
            if not fResourcePoolAssignment.ByKeys(cdb_object_id=self.assignment_oid):
                p = fPerson.ByKeys(cdb_object_id=self.assignment_oid)
                resource_assignment = p.ResourceMember[0] if p.ResourceMember else None
                if resource_assignment:
                    self.assignment_oid = resource_assignment.cdb_object_id
                    self.resource_oid = resource_assignment.resource_oid
                    self.pool_oid = resource_assignment.pool_oid
                    ctx.set(
                        "original_resource_oid",
                        resource_assignment.original_resource_oid,
                    )

    def set_assignment(self, ctx):
        demand = self.Demand
        if demand:
            if demand.pool_oid and not self.pool_oid:
                self.pool_oid = demand.pool_oid
            if demand.assignment_oid and not self.assignment_oid:
                self.assignment_oid = demand.assignment_oid
                self.resource_oid = demand.resource_oid
                ctx.set("original_resource_oid", demand.original_resource_oid)

    def adjust_pool_assignments(self, ctx=None):
        adjust_pool_assignments(assignment_oids=[self.assignment_oid])

    event_map = {
        (("create", "copy"), "pre_mask"): (
            "check_resource",
            "check_task",
            "assignment_without_demand",
            "set_id",
            "set_task_id",
            "set_task_name",
            "set_assignment",
            "propose_assignment",
        ),
        (("modify"), "pre_mask"): (
            "set_task_name",
            "propose_assignment",
            "set_readonly",
        ),
        (("info"), "pre_mask"): ("set_task_name"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialog_item_change"),
        (("create", "copy", "modify"), "post_mask"): (
            "check_task",
            "check_subject",
            "check_demand",
            "set_alloc_type",
            "check_team",
        ),
        (("create", "copy"), "pre"): ("check_resource", "set_id", "setWorkdays"),
        (("modify"), "pre"): ("setWorkdays"),
        (("create", "copy", "modify"), "post"): (
            "assignTeamMember",
            "check_demand_coverage",
            "adjust_pool_assignments",
            "createSchedules",
            "final_check",
        ),
        (("delete"), "post"): (
            "check_demand_coverage",
            "adjust_pool_assignments",
            "deleteScheduleViews",
            "final_check",
        ),
    }


class CatalogPCSResDemandData(CDBCatalogContent):
    def __init__(self, cdb_project_id, task_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.task_id = task_id
        self.demands = fRessourceDemand.getAssignableDemands(cdb_project_id, task_id)

    def getNumberOfRows(self):
        return len(self.demands)

    def getRowObject(self, row):
        return self.demands[row].ToObjectHandle()


class CatalogPCSResDemand(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        # if the project is known, we fill the catalog on our own
        cdb_project_id = ""
        task_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
            task_id = self.getInvokingDlgValue("task_id")
        except Exception:  # nosec
            pass

        if cdb_project_id and task_id:
            self.setResultData(CatalogPCSResDemandData(cdb_project_id, task_id, self))


class ResourceScheduleHalfYear(Object):
    __classname__ = "cdbpcs_res_sched_ph"
    __maps_to__ = "cdbpcs_res_sched_ph"


class ResourceScheduleQuarter(Object):
    __classname__ = "cdbpcs_res_sched_pq"
    __maps_to__ = "cdbpcs_res_sched_pq"


class ResourceScheduleMonth(Object):
    __classname__ = "cdbpcs_res_sched_pm"
    __maps_to__ = "cdbpcs_res_sched_pm"


class ResourceScheduleWeek(Object):
    __classname__ = "cdbpcs_res_sched_pw"
    __maps_to__ = "cdbpcs_res_sched_pw"


class ResourceSchedule(Object):
    __classname__ = "cdbpcs_res_schedule"
    __maps_to__ = "cdbpcs_res_schedule"

    @classmethod
    def genScheduleIntervals(
        cls, start_date, end_date, cdb_project_id, personalnummer=None
    ):
        intervals = []
        wdays = Calendar.combined_workdays(
            cdb_project_id, personalnummer, start_date, end_date
        )
        if len(wdays):
            dstart = wdays[0]
            dend = wdays[-1]
            day0 = dstart
            oneday = datetime.timedelta(days=1)
            intervals.append(dstart)
            for d in wdays[1:]:
                if (d - day0) > oneday:
                    intervals.append(day0)
                    intervals.append(d)
                day0 = d
            intervals.append(dend)
        return intervals, len(wdays)

    @classmethod
    def _reSchedule(cls, condmap, changes):  # pylint: disable=too-many-statements
        """
        Reschedule the resources.
         :Parameters:
            - `condmap` : dictionary of key-value-mapping for where-condition of sql statement to look up
                          relevant schedule objects.
            - `changes` : a dictionary contains the changes.
        """
        cond = " and ".join(
            ["%s='%s'" % (k, sqlapi.quote(v)) for (k, v) in condmap.items()]
        )
        for (csd, ced) in changes:
            # search all relevant schedule objects according to start and end date
            value = changes[(csd, ced)]
            oneday = datetime.timedelta(days=1)
            csdday = to_legacy_str(csd)
            csdsql = sqlapi.SQLdbms_date(csdday)
            cedday = to_legacy_str(ced)
            cedsql = sqlapi.SQLdbms_date(cedday)
            prevday = to_legacy_str(csd - oneday)
            prevsql = sqlapi.SQLdbms_date(prevday)
            nextday = to_legacy_str(ced + oneday)
            nextsql = sqlapi.SQLdbms_date(nextday)

            # get the previous and next contiguous schedule objects
            condprev = "%s and end_date=%s and value=%f" % (cond, prevsql, value)
            prevobj = None
            prevobjs = cls.Query(condprev, order_by="start_date desc")
            if len(prevobjs):
                prevobj = prevobjs[0]
            condnext = "%s and start_date=%s and value=%f" % (cond, nextsql, value)
            nextobj = None
            nextobjs = cls.Query(condnext, order_by="start_date")
            if len(nextobjs):
                nextobj = nextobjs[0]

            # case 1: start <= change_start, change_end <= end
            cond1 = "%s and start_date<=%s and end_date>=%s" % (cond, csdsql, cedsql)
            objs = cls.Query(cond1, order_by="start_date")
            if len(objs):
                obj = objs[0]
                sd = obj.start_date.date()
                ed = obj.end_date.date()
                if obj.value != value:
                    # start == change_start, change_end == end
                    # -> change its value
                    if sd == csd and ed == ced:
                        if value > 0:
                            obj.Update(value=value)
                        else:
                            obj.Delete()

                    # else -> split it into parts
                    else:
                        ori_changed = False
                        ori_value = obj.value
                        ori_sd = obj.start_date
                        ori_ed = obj.end_date
                        # the changing part
                        if value > 0:
                            obj.Update(start_date=csdday, end_date=cedday, value=value)
                            ori_changed = True

                        if sd < csd:
                            # the fore part
                            if ori_changed:
                                obj.Copy(
                                    start_date=ori_sd, end_date=prevday, value=ori_value
                                )
                            else:
                                obj.Update(start_date=ori_sd, end_date=prevday)
                                ori_changed = True
                        if ed > ced:
                            # the rear part:
                            if ori_changed:
                                obj.Copy(
                                    start_date=nextday, end_date=ori_ed, value=ori_value
                                )
                            else:
                                obj.Update(start_date=nextday, end_date=ori_ed)
            else:
                # case 2: change_start <= start, end <= change_end
                # -> delete them
                # (change_start==start, end == change_end excluded -> case 1)
                cond2 = "%s and start_date>=%s and end_date<=%s" % (
                    cond,
                    csdsql,
                    cedsql,
                )
                cls.Query(cond2, order_by="start_date").Delete()
                # case 3: start < change_start <= end <= change_end
                cond3 = "%s and start_date<%s and end_date>=%s and end_date<=%s" % (
                    cond,
                    csdsql,
                    csdsql,
                    cedsql,
                )
                objs = cls.Query(cond3, order_by="start_date desc")
                if len(objs):
                    obj = objs[0]
                    if obj.value == value:
                        # previous contiguous schedule object can be extended
                        prevobj = obj
                    else:
                        obj.Update(end_date=prevday)
                # case 4: change_start <= start <= change_end < end
                cond4 = "%s and start_date>=%s and start_date<=%s and end_date>%s" % (
                    cond,
                    csdsql,
                    cedsql,
                    cedsql,
                )
                objs = cls.Query(cond4, order_by="start_date")
                if len(objs):
                    obj = objs[0]
                    if obj.value == value:
                        # next contiguous schedule object can be extended
                        nextobj = obj
                    else:
                        obj.Update(start_date=nextday)
                # perform the changes for period (change_start, change_end)
                if prevobj:
                    if nextobj:
                        # merge all the parts
                        next_ed = nextobj.end_date
                        nextobj.Delete()
                        prevobj.Update(end_date=next_ed)
                    else:
                        prevobj.Update(end_date=cedday)
                elif nextobj:
                    nextobj.Update(start_date=csdday)
                else:
                    # create the new schedule object
                    newdata = {}
                    newdata.update(**condmap)
                    newdata.update(start_date=csdday, end_date=cedday, value=value)
                    cls.Create(**newdata)


class DemandSchedule(ResourceSchedule):
    __classname__ = "cdbpcs_demand_schedule"
    __match__ = ResourceSchedule.cdb_classname >= __classname__

    Demand = Reference(
        1,
        fRessourceDemand,
        fDemandSchedule.cdb_project_id,
        fDemandSchedule.task_id,
        fDemandSchedule.cdb_demand_id,
    )

    @classmethod
    def reSchedule(cls, cdb_project_id, task_id, context_id, changes):
        """
        Reschedule the resources.
         :Parameters:
            - `cdb_project_id` : project ID
            - `task_id` : task ID
            - `context_id` : cdb_alloc_id for assignments or cdb_demand_id for demands
            - `changes` : a dictionary contains the changes. The key is a pair of python
                          date objects: (start_date, end_date), e.g.,
                          (01.01.2011, 05.01.2011) : 4.0 means the value for the period
                          2011-01-01 to 2011-01-05 is changed to 4.0.
        """
        condmap = {
            "cdb_project_id": cdb_project_id,
            "task_id": task_id,
            "cdb_demand_id": context_id,
        }
        cls._reSchedule(condmap, changes)


class AssignmentSchedule(ResourceSchedule):
    __classname__ = "cdbpcs_alloc_schedule"
    __match__ = ResourceSchedule.cdb_classname >= __classname__

    Assignment = Reference(
        1,
        fRessourceAssignment,
        fAssignmentSchedule.cdb_project_id,
        fAssignmentSchedule.task_id,
        fAssignmentSchedule.cdb_alloc_id,
    )

    @classmethod
    def reSchedule(cls, cdb_project_id, task_id, context_id, changes):
        """
        Reschedule the resources.
         :Parameters:
            - `cdb_project_id` : project ID
            - `task_id` : task ID
            - `context_id` : cdb_alloc_id for assignments or cdb_demand_id for demands
            - `changes` : a dictionary contains the changes. The key is a pair of python
                          date objects: (start_date, end_date), e.g.,
                          (01.01.2011, 05.01.2011) : 4.0 means the value for the period
                          2011-01-01 to 2011-01-05 is changed to 4.0.
        """
        condmap = {
            "cdb_project_id": cdb_project_id,
            "task_id": task_id,
            "cdb_alloc_id": context_id,
        }
        cls._reSchedule(condmap, changes)


def adjustDurations(persno, day_from, day_until):
    from cs.pcs.projects.tasks import Task

    try:
        resoure_objs = fPerson.KeywordQuery(personalnummer=persno)
        resoure_objs = [x for x in [p.Resource for p in resoure_objs] if x]
        resource_oids = ", ".join(["'%s'" % x.cdb_object_id for x in resoure_objs])
        # betroffene Bedarfe nach Kalenderaenderung anpassen
        if not resource_oids:
            return
        dem_sql = (
            "SELECT cdbpcs_task.* FROM cdbpcs_prj_demand, cdbpcs_task"
            " WHERE cdbpcs_prj_demand.resource_oid IN (%s)"
            " AND %s <= cdbpcs_task.%s"
            " AND cdbpcs_task.%s <= %s"
            " AND cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            % (
                resource_oids,
                sqlapi.SQLdbms_date(day_from),
                dEndTimeField,
                dStartTimeField,
                sqlapi.SQLdbms_date(day_until),
            )
        )
        ass_sql = (
            "SELECT cdbpcs_task.* FROM cdbpcs_prj_alloc, cdbpcs_task"
            " WHERE cdbpcs_prj_alloc.resource_oid IN (%s)"
            " AND %s <= cdbpcs_task.%s"
            " AND cdbpcs_task.%s <= %s"
            " AND cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            % (
                resource_oids,
                sqlapi.SQLdbms_date(day_from),
                aEndTimeField,
                aStartTimeField,
                sqlapi.SQLdbms_date(day_until),
            )
        )
        tasks = unique(fTask.SQL(dem_sql) + fTask.SQL(ass_sql))
        project_ids = unique([x.cdb_project_id for x in tasks])
        projects = fProject.KeywordQuery(cdb_project_id=project_ids)

        for p in projects:
            p.recalculate(skip_followups=True)

        all_tasks = Task.KeywordQuery(cdb_project_id=project_ids)
        Task.adjustDependingObjects_many(all_tasks)
        Task.updateResourceStatusSignals(all_tasks)
    except Exception:
        misc.log_traceback("Allocations have not been adjusted to calendar changes")
