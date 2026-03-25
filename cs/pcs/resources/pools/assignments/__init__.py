#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=C0302,W0212,W0703,R0913

import datetime
import logging

from cdb import i18n, sig, sqlapi, transactions, ue
from cdb.classbody import classbody
from cdb.objects import (
    Forward,
    Object,
    Reference,
    Reference_1,
    Reference_Methods,
    Reference_N,
)
from cdb.platform import gui
from cdb.typeconversion import to_user_repr_date_format
from cs.calendar import CalendarException, workday
from cs.pcs.projects import calendar
from cs.pcs.resources.db_tools import get_task_uuids
from cs.pcs.resources.helpers import date_from_legacy_str, to_legacy_str
from cs.platform.web.uisupport import get_webui_link

# Forward declarations
fTask = Forward("cs.pcs.projects.tasks.Task")
fPerson = Forward("cdb.objects.org.Person")
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")
fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fResourcePoolAssignment = Forward(
    "cs.pcs.resources.pools.assignments.ResourcePoolAssignment"
)
fResourcePoolAssignmentPerson = Forward(
    "cs.pcs.resources.pools.assignments.person.ResourcePoolAssignmentPerson"
)
fResourceDemand = Forward("cs.pcs.resources.RessourceDemand")
fResourceAssignment = Forward("cs.pcs.resources.RessourceAssignment")
fCAPACITY_CALCULATOR = Forward("cs.pcs.resources.capacity.CAPACITY_CALCULATOR")
fSCHEDULE_CALCULATOR = Forward("cs.pcs.resources.schedule.SCHEDULE_CALCULATOR")
fCalendarProfile = Forward("cs.calendar.CalendarProfile")


def get_real_date(value, default=None):
    """
    :param value: date representation of type basestring as used by ctx.Object or
                                      of type datetime.date as used by ctx.objects.Object
    :param default: default values of type datetime.date, if None, current date will be used
    :returns: Returns the default value, if the value is not set.
        If default is not set, the current date will be used
    :rtype: type datetime.date
    """

    if default:
        if isinstance(default, datetime.datetime):
            default = default.date()
    else:
        default = datetime.date.today()

    if not isinstance(default, datetime.date):
        raise ValueError(
            "datetime.date object expected as default value. Got {} as {}".format(
                default, type(default)
            )
        )

    if isinstance(value, str):
        if not value:
            return default
        else:
            return date_from_legacy_str(value)

    return value.date() if value else default


class Resource(Object):
    __classname__ = "cdbpcs_resource"
    __maps_to__ = "cdbpcs_resource"

    CalendarProfile = Reference_1(fCalendarProfile, fResource.calendar_profile_id)
    PoolAssignments = Reference_N(
        fResourcePoolAssignment,
        fResourcePoolAssignment.resource_oid == fResource.cdb_object_id,
    )

    AllDemands = Reference_N(
        fResourceDemand, fResourceDemand.resource_oid == fResource.cdb_object_id
    )

    AllAssignments = Reference_N(
        fResourceAssignment, fResourceAssignment.resource_oid == fResource.cdb_object_id
    )

    AssignedPerson = Reference_1(
        fPerson, fPerson.cdb_object_id == fResource.referenced_oid
    )

    def getDemands(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_covered=False,
        all_status=False,
        **kargs
    ):
        if not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_demand.*, cdbpcs_task.position"
        sqlFrom = " FROM cdbpcs_prj_demand, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_prj_demand.resource_oid = '%s'"
            " AND cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            " AND cdbpcs_task.milestone != 1" % self.cdb_object_id
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        if not include_covered:
            sqlWhere += " AND cdbpcs_prj_demand.coverage = 0"

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
                    fTask.getDemandStartTimeFieldName(),
                    fTask.getDemandStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getDemandEndTimeFieldName(),
                    fTask.getDemandEndTimeFieldName(),
                    ed,
                    fTask.getDemandStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getDemandEndTimeFieldName(),
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_demand.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
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
        sqlOrder = " ORDER BY cdbpcs_prj_demand.coverage, cdbpcs_prj_demand.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceDemand.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    def getAssignments(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        all_status=False,
        **kargs
    ):
        if not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_alloc.*, cdbpcs_task.position "
        sqlFrom = " FROM cdbpcs_prj_alloc, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_prj_alloc.resource_oid='%s'"
            " AND cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            " AND cdbpcs_task.milestone != 1" % self.cdb_object_id
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
                    fTask.getAssignmentStartTimeFieldName(),
                    fTask.getAssignmentStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getAssignmentEndTimeFieldName(),
                    fTask.getAssignmentEndTimeFieldName(),
                    ed,
                    fTask.getAssignmentStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getAssignmentEndTimeFieldName(),
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_alloc.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
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
        sqlOrder = " ORDER BY cdbpcs_prj_alloc.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceAssignment.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    def getTotalDemandInPeriod(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_covered=False,
        **kargs
    ):
        load = 0.0
        for demand in self.getDemands(
            start_date=start_date,
            end_date=end_date,
            prj_rule=prj_rule,
            with_prj_ids=with_prj_ids,
            without_prj_ids=without_prj_ids,
            include_covered=include_covered,
        ):
            hours = demand.hours
            if not include_covered and hours:
                hours = demand.demandRemainderInHours()
            task = demand.Task
            duration_total = task.getWorkdays()
            duration_period = task.getWorkdaysInPeriod(start_date, end_date)
            if duration_total and duration_period and hours:
                load += float(duration_period) / duration_total * hours
        return load

    def getTotalAssignmentInPeriod(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        **kargs
    ):
        load = 0.0
        for assign in self.getAssignments(
            start_date=start_date,
            end_date=end_date,
            prj_rule=prj_rule,
            with_prj_ids=with_prj_ids,
            without_prj_ids=without_prj_ids,
        ):
            task = assign.Task
            duration_total = task.getWorkdays()
            duration_period = task.getWorkdaysInPeriod(start_date, end_date)
            if duration_total and duration_period and assign.hours:
                load += float(duration_period) / duration_total * assign.hours
        return load

    def getTotalCapacityInPeriod(self, start_date, end_date, **kargs):
        return self.capacity * len(workday.workdays(start_date, end_date))

    def getCapacityPerDay(self):
        if self.Person and self.Person.capacity:
            return self.Person.capacity
        return 0.0

    def getFreeCapacityInPeriod(
        self,
        start_date,
        end_date,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        **kargs
    ):
        return (
            self.getTotalCapacityInPeriod(start_date=start_date, end_date=end_date)
            - self.getTotalDemandInPeriod(
                start_date=start_date,
                end_date=end_date,
                prj_rule=prj_rule,
                with_prj_ids=with_prj_ids,
                without_prj_ids=without_prj_ids,
            )
            - self.getTotalAssignmentInPeriod(
                start_date=start_date,
                end_date=end_date,
                prj_rule=prj_rule,
                with_prj_ids=with_prj_ids,
                without_prj_ids=without_prj_ids,
            )
        )

    def createSchedules(self, ctx=None):
        fCAPACITY_CALCULATOR.createSchedules([self.cdb_object_id])

    def disable_all_fields(self, ctx):
        ctx.set_readonly("name")
        ctx.set_readonly("capacity")
        ctx.set_readonly("calendar_profile_id")
        ctx.set_readonly("referenced_oid")

    event_map = {
        (("create", "copy", "delete"), "post"): ("createSchedules"),
        (("modify"), "pre_mask"): "disable_all_fields",
    }


class ResourcePoolAssignment(Object):
    __classname__ = "cdbpcs_pool_assignment"
    __maps_to__ = "cdbpcs_pool_assignment"

    ResourcePool = Reference(1, fResourcePool, fResourcePoolAssignment.pool_oid)
    Resource = Reference(1, fResource, fResourcePoolAssignment.resource_oid)
    ResourceDemands = Reference_N(
        fResourceDemand,
        fResourceDemand.assignment_oid == fResourcePoolAssignment.cdb_object_id,
    )
    ResourceAllocations = Reference_N(
        fResourceAssignment,
        fResourceAssignment.assignment_oid == fResourcePoolAssignment.cdb_object_id,
    )
    PlusConcurrent = Reference_N(
        fResourcePoolAssignment,
        fResourcePoolAssignment.resource_oid == fResourcePoolAssignment.resource_oid,
    )

    def _getConcurrents(self):
        return [
            rs for rs in self.PlusConcurrent if rs.cdb_object_id != self.cdb_object_id
        ]

    Concurrent = Reference_Methods(
        fResourcePoolAssignmentPerson, lambda self: self._getConcurrents()
    )

    def getDemands(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        include_covered=False,
        all_status=False,
        **kargs
    ):
        if not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_demand.*, cdbpcs_task.position"
        sqlFrom = " FROM cdbpcs_prj_demand, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_prj_demand.assignment_oid = '%s'"
            " AND cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            " AND cdbpcs_task.milestone != 1" % self.cdb_object_id
        )
        if not all_status:
            sqlWhere += " AND {}".format(
                fTask.get_condition_of_StatusForResourceEvaluation()
            )

        if not include_covered:
            sqlWhere += " AND cdbpcs_prj_demand.coverage = 0"

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
                    fTask.getDemandStartTimeFieldName(),
                    fTask.getDemandStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getDemandEndTimeFieldName(),
                    fTask.getDemandEndTimeFieldName(),
                    ed,
                    fTask.getDemandStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getDemandEndTimeFieldName(),
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_demand.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
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
        sqlOrder = " ORDER BY cdbpcs_prj_demand.coverage, cdbpcs_prj_demand.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceDemand.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    def getAssignments(
        self,
        start_date=None,
        end_date=None,
        prj_rule=None,
        with_prj_ids=None,
        without_prj_ids=None,
        all_status=False,
        **kargs
    ):
        if not prj_rule and not with_prj_ids:
            return []

        # basic statement
        sqlSelect = "SELECT cdbpcs_prj_alloc.*, cdbpcs_task.position "
        sqlFrom = " FROM cdbpcs_prj_alloc, cdbpcs_task"
        sqlWhere = (
            " WHERE cdbpcs_prj_alloc.assignment_oid='%s'"
            " AND cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id"
            " AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id"
            " AND cdbpcs_task.ce_baseline_id = ''"
            " AND cdbpcs_task.milestone != 1" % self.cdb_object_id
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
                    fTask.getAssignmentStartTimeFieldName(),
                    fTask.getAssignmentStartTimeFieldName(),
                    ed,
                    sd,
                    fTask.getAssignmentEndTimeFieldName(),
                    fTask.getAssignmentEndTimeFieldName(),
                    ed,
                    fTask.getAssignmentStartTimeFieldName(),
                    sd,
                    ed,
                    fTask.getAssignmentEndTimeFieldName(),
                )
            )

        # evaluate project parameters
        sqlPrjRule = sqlWithPrj = "1=0"
        sqlWithoutPrj = "1=1"
        if prj_rule:
            cls = prj_rule.getClasses()[0]
            root = prj_rule._GetNode(cls)
            sqlFrom += ", %s" % root.build_join()
            sqlPrjRule = (
                "(cdbpcs_prj_alloc.cdb_project_id = %s.cdb_project_id"
                " AND %s)" % (root.alias, prj_rule.expr(cls))
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
        sqlOrder = " ORDER BY cdbpcs_prj_alloc.cdb_project_id, cdbpcs_task.position"

        # send statement
        return fResourceAssignment.SQL(sqlSelect + sqlFrom + sqlWhere + sqlOrder)

    @property
    def real_start_date(self):
        """
        Returns the start date of the membership to be calculated
        If start date does not exist, valid from date of the resource's calendar will be used
        :return: type datetime.date
        """
        return self.start_date or self.Resource.CalendarProfile.valid_from

    @property
    def real_end_date(self):
        """
        Returns the end date of the membership to be calculated
        If end date does not exist, valid until date of the resource's calendar will be used
        :return: type datetime.date
        """
        return self.end_date or self.Resource.CalendarProfile.valid_until

    def on_cdbpcs_pool_assignment_end_pre_mask(self, ctx):
        """
        Prevents execution if an end of membership is already set
        Determines the earliest possible end of membership and prepares the user's confirmation
        """
        if self.end_date:
            raise ue.Exception(
                "resources_end_of_membership_exists",
                to_user_repr_date_format(self.end_date, i18n.get_date_format()),
            )

        end_date = self._get_minimum_end()
        ctx.set(
            "end_date_plan_user",
            to_user_repr_date_format(end_date, i18n.get_date_format()),
        )
        ctx.set("end_date_plan", end_date)

    # noinspection PyAttributeOutsideInit
    def on_cdbpcs_pool_assignment_end_now(self, ctx):
        """
        Accepts the date confirmed by the user from the input dialog or
        determines the earliest possible end date of membership.
        Updates the end date of the membership in the database
        Updates the values of the auxiliary tables for capacity, resource demands and resource assignments.
        """
        end_date = getattr(ctx.dialog, "end_date_plan", None)
        if not end_date:
            end_date = self._get_minimum_end()
        # sets the end of membership
        self.end_date = end_date
        # updates plan values
        self.adjustSchedules()

    def on_CDBPCS_ResourceChart_now(self, ctx):
        if self.ResourcePool:
            self.ResourcePool.show_resource_chart(ctx=ctx)

    def on_cdbpcs_goto_resource_now(self, ctx):
        if self.Person:
            url = get_webui_link(None, self.Person)
        else:
            url = get_webui_link(None, self)
        ctx.url(url)

    def on_cdbpcs_goto_resource_pool_now(self, ctx):
        if self.ResourcePool:
            url = get_webui_link(None, self.ResourcePool)
        else:
            raise ue.Exception("cdbpcs_no_resource_pool_assigned")
        ctx.url(url)

    def check_prerequisites(self, ctx):
        """
        Modifying is not permitted if resource demands or resource assignments exist
        """
        if self.ResourceDemands or self.ResourceAllocations:
            logging.info(
                "NOTE: Pool membership can not be changed. "
                "Resource demands and/or resource allocations exist.",
            )
            ctx.set_fields_readonly(["pool_oid", "mapped_person", "resource_oid"])

    def _get_start(self, max_start=None):
        if self.start_date:
            return self.start_date
        if not max_start:
            max_start = datetime.date.today()
        if self.end_date:
            return min(max_start, self.end_date)
        return max_start

    def _get_end(self, min_end=None):
        if self.end_date:
            _start_date = (
                self.start_date
                if self.start_date
                else self.Resource.CalendarProfile.valid_from
            )
            return max(_start_date, self.end_date)
        if not min_end:
            min_end = datetime.date.today()
        if self.start_date:
            return max(min_end, self.start_date)
        return min_end

    def getNextDate(self, day, dist=0):
        return day + datetime.timedelta(days=dist)

    def getStart(self):
        if self.resource_oid and not self.start_date:
            start_date = self._get_maximum_start()
            if start_date:
                self.start_date = start_date
                return start_date
        return None

    def setStart(self, ctx):
        start_date = self.getStart()
        if start_date:
            ctx.set("start_date", start_date)

    def _get_maximum_start(self):
        # today is the default
        start_date = self._get_start()

        # it has to fit existing demands and assignments
        for obj in self.ResourceDemands + self.ResourceAllocations:
            task = obj.Task
            if task and task.start_time_fcast and task.start_time_fcast > start_date:
                start_date = task.start_time_fcast

        # it has to be a date after all predecessors
        entries = self.Concurrent
        if entries:
            end_dates = []
            for entry in entries:
                end_date = entry._get_end()
                for obj in entry.ResourceDemands + entry.ResourceAllocations:
                    task = obj.Task
                    if task and task.end_time_fcast and task.end_time_fcast > end_date:
                        end_date = task.end_time_fcast
                end_dates.append(end_date)
            max_end_date = self.getNextDate(max(end_dates), 1)
            start_date = max(start_date, max_end_date)
        return start_date

    def getEnd(self):
        end_date = None
        if self.resource_oid and not self.end_date:
            entries = self.Concurrent
            if entries:
                min_start_date = min(x._get_start() for x in entries)
                if min_start_date > self.start_date:
                    end_date = self.getNextDate(min_start_date, -1)
        return end_date

    def setEnd(self, ctx):
        end_date = self.getEnd()
        if end_date:
            self.end_date = end_date

    def setPredecessorsEnd(self, ctx):
        start = self.start_date

        with transactions.Transaction():
            if start:
                for rs in self.Concurrent:
                    if not rs.end_date:
                        if rs.real_start_date < start:
                            min_end = self.getNextDate(start, -1)
                            rs.Update(end_date=min_end)
            self.check_dates_overlap_(ctx)

    def _get_minimum_end(self, min_end=None):
        """
        Returns the earliest possible end of a pool membership, taking into account existing
        resource demands and resource assignments.
        :param min_end:
        :type min_end:
        :return: earliest possible end of a pool membership
        :rtype: datetime.date
        """
        # today is the default
        end_date = self._get_end(min_end=min_end)

        # it has to fit existing demands and assignments
        for obj in self.ResourceDemands + self.ResourceAllocations:
            task = obj.Task
            if task and task.end_time_fcast and task.end_time_fcast > end_date:
                end_date = task.end_time_fcast

        # it has to be a date before all successors
        # self.Concurrent holds all ResourcePoolAssignments
        # of the same Resource to the same Pool
        # we've to filter for all of those, that start after this one
        successors = [x for x in self.Concurrent if x.start_date > self.start_date]
        if successors:
            min_start_date = min(x.start_date for x in successors)
            min_start_date = self.getNextDate(min_start_date, -1)
            end_date = min(end_date, min_start_date)
        return end_date

    def check_dates_overlap_(self, ctx):
        # determine all entries that might result in a conflict
        start = self.start_date
        end = self.end_date

        for rs in self.Concurrent:
            rs_start = rs.start_date
            rs_end = rs.end_date

            if rs_end and start and rs_end < start:
                pass
            elif end and rs_start and end < rs_start:
                pass
            else:
                raise ue.Exception("cdbpcs_pool_ass_overlap", rs.ResourcePool.name)

    def check_dates_overlap(self, orig_start_date, orig_end_date, start_date, end_date):
        if start_date != orig_start_date or end_date != orig_end_date:
            # if start or end date is modified in the mask
            self.check_dates_overlap_(None)

    def _check_dates_overlap(self, ctx):
        self.check_dates_overlap(
            ctx.object.start_date,  # original start_date
            ctx.object.end_date,  # original end_date
            ctx.dialog.start_date,  # modified start_date
            ctx.dialog.end_date,  # modified end_date
        )

    def check_dates(self, ctx):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ue.Exception("cdbpcs_pool_assign_date_overlap")

    @classmethod
    def createSchedules_many(cls, rpas, start=None, end=None):
        fCAPACITY_CALCULATOR.createSchedules([x.resource_oid for x in rpas], start, end)

    def createSchedules(self, ctx=None):
        fCAPACITY_CALCULATOR.createSchedules([self.resource_oid])

    def remember_values(self, ctx=None):
        """
        Save current start and end date into user exit arguments *as string* in order to access these values later
        :param ctx:
        :return: None
        """
        cp = self.Resource.CalendarProfile
        sd = ctx.object.start_date or to_legacy_str(cp.valid_from)
        ed = ctx.object.end_date or to_legacy_str(cp.valid_until)
        ctx.keep("old_start_date", sd)
        ctx.keep("old_end_date", ed)

    def adjustSchedules(self, ctx=None):
        # all changed pool assignments have to be adjusted
        sd = self.real_start_date
        ed = self.real_end_date

        if ctx and getattr(ctx.ue_args, "old_start_date", None):
            sd = min(sd, date_from_legacy_str(ctx.ue_args["old_start_date"]))
        if ctx and getattr(ctx.ue_args, "old_end_date", None):
            ed = max(ed, date_from_legacy_str(ctx.ue_args["old_end_date"]))

        ResourcePoolAssignment.adjustCapacitys(
            resource_oids=[self.resource_oid], day_from=sd, day_until=ed
        )
        ResourcePoolAssignment.adjustAllocations(
            resource_oids=[self.resource_oid], day_from=sd, day_until=ed
        )

    @classmethod
    def _getPoolAssignments(cls, resource_oids, day_from, day_until):
        oids = ", ".join(["'%s'" % sqlapi.quote(x) for x in resource_oids])
        sqlfrom = sqlapi.SQLdbms_date(day_from)
        sqluntil = sqlapi.SQLdbms_date(day_until)
        cond = (
            "resource_oid IN (%s)"
            " AND (end_date IS NULL OR %s <= end_date)"
            " AND (start_date IS NULL OR start_date <= %s)" % (oids, sqlfrom, sqluntil)
        )
        return ResourcePoolAssignment.Query(cond)

    @classmethod
    def adjustCapacitys(cls, resource_oids, day_from, day_until):
        rpas = cls._getPoolAssignments(resource_oids, day_from, day_until)
        try:
            # adjust resource pool assignments after calendar changes
            fCAPACITY_CALCULATOR.createSchedules(rpas.resource_oid)
        except Exception:
            logging.exception(
                "Resource pool assignments have not been"
                " adjusted to calendar changes"
            )

    @classmethod
    def _getAllocations(cls, resource_oids, day_from, day_until):
        oids = ",".join(["'%s'" % sqlapi.quote(x) for x in resource_oids])
        sd = sqlapi.SQLdbms_date(day_from)
        ed = sqlapi.SQLdbms_date(day_until)
        cond = (
            "resource_oid IN (%s) AND "
            "end_time_fcast >= %s AND "
            "start_time_fcast <= %s" % (oids, sd, ed)
        )
        return (
            fResourceDemand.SQL("SELECT * FROM cdbpcs_prj_demand_v WHERE %s" % cond),
            fResourceAssignment.SQL("SELECT * FROM cdbpcs_prj_alloc_v WHERE %s" % cond),
        )

    @classmethod
    def adjustAllocations(cls, resource_oids, day_from, day_until):
        # determine all demands and assignments affected by changes
        demands, assignments = cls._getAllocations(resource_oids, day_from, day_until)
        task_uuids_d = get_task_uuids(demands)
        task_uuids_a = get_task_uuids(assignments)

        try:
            fResourceDemand.adjust_values_many(task_uuids_d)
            fResourceAssignment.adjust_values_many(task_uuids_a)
        except Exception:
            logging.exception(
                "could not adjust resource demands or assignments "
                "to pool assignments"
            )

        fSCHEDULE_CALCULATOR.createSchedules_many(task_uuids_d + task_uuids_a)

    def check_for_conflicts(self, ctx=None):
        """
        If the memberships is to be ended earlier or is to be started later and in the period of reduction
        demands or allocation do exist, a confirmation of the user is required to change the durationof the membership.
        :param ctx:
        :return:
        """
        if ctx and "adjust" in ctx.dialog.get_attribute_names():
            # User request has been done in the run before
            return

        # Determine the real dates, considering empty values
        cp = self.Resource.CalendarProfile

        previous_start_date = cp.valid_from
        previous_end_date = cp.valid_until

        # If action == create or copy, previous object does not exist
        if ctx and hasattr(ctx, "object") and hasattr(ctx.object, "start_date"):
            previous_start_date = get_real_date(ctx.object["start_date"], cp.valid_from)
        if ctx and hasattr(ctx, "object") and hasattr(ctx.object, "end_date"):
            previous_end_date = get_real_date(ctx.object["end_date"], cp.valid_until)

        if (
            self.real_start_date <= previous_start_date
            and previous_end_date <= self.real_end_date
        ):
            # Duration of membership has been extended
            return

        if ctx and ctx.action not in ["create", "copy"]:
            if previous_end_date > self.real_end_date:
                # The memberships is to be ended earlier
                # Are there any demands or allocations in this time
                end_demands, end_allocations = ResourcePoolAssignment._getAllocations(
                    [self.resource_oid],
                    day_from=self.getNextDate(self.real_end_date, dist=1),
                    day_until=previous_end_date,
                )

                if end_demands or end_allocations:
                    self.ask_user(ctx)
                    return

            if self.real_start_date > previous_start_date:
                # The membership is to be started later
                # Are there any demands or allocations in this time
                (
                    start_demands,
                    start_allocations,
                ) = ResourcePoolAssignment._getAllocations(
                    [self.resource_oid],
                    day_from=previous_start_date,
                    day_until=self.getNextDate(self.real_start_date, dist=-1),
                )

                if start_demands or start_allocations:
                    self.ask_user(ctx)
                    return
        else:
            demands, allocations = ResourcePoolAssignment._getAllocations(
                [self.resource_oid],
                day_from=self.real_start_date,
                day_until=self.real_end_date,
            )

            if demands or allocations:
                self.ask_user(ctx)
                return

    @staticmethod
    def ask_user(ctx):
        # Create a message box
        msgbox = ctx.MessageBox(
            "cdb_capa_adjust_01", [], "adjust", ctx.MessageBox.kMsgBoxIconQuestion
        )
        msgbox.addYesButton(is_dflt=True)
        msgbox.addButton(
            ctx.MessageBoxButton(
                "button.mnemonic_no",
                ctx.MessageBox.kMsgBoxResultCancel,
                action=ctx.MessageBoxButton.kButtonActionCancel,
                is_dflt=False,
            )
        )
        ctx.show_message(msgbox)

    def dialogitem_change(self, ctx):
        if ctx and ctx.changed_item in ["resource_oid", "mapped_person"]:
            self.start_date = ""
            self.end_date = ""
            self.setStart(ctx=ctx)
            self.setEnd(ctx=ctx)

    event_map = {
        (("create", "copy"), "pre_mask"): ("setStart", "setEnd"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialogitem_change"),
        (("modify"), "pre_mask"): ("check_prerequisites", "setStart", "setEnd"),
        (("modify"), "post_mask"): ("_check_dates_overlap"),
        (("create", "copy"), "pre"): (
            "check_dates",
            "check_for_conflicts",
            "setStart",
            "setEnd",
            "setPredecessorsEnd",
        ),
        (("modify"), "pre"): (
            "check_dates",
            "remember_values",
            "check_for_conflicts",
            "setStart",
            "setEnd",
        ),
        (("create", "copy", "modify", "delete"), ("post")): ("adjustSchedules"),
    }


@classbody
class CalendarException(object):
    @sig.connect(CalendarException, "prepareTaskAdjustments")
    def aggregate_demands_and_allocations(self, ctx=None, **args):
        # Find the cdb_project_ids of all the Projects which have Tasks
        # affected by this CalendarException
        # i.e. start_time <= Exception Day <= end_time
        start = args.get("cal_exc_start", getattr(self, "day", None))
        end = args.get("cal_exc_end", start)
        id = args.get('cal_profile_id', self.calendar_profile_id)

        start_str = sqlapi.SQLdbms_date(start)
        end_str = sqlapi.SQLdbms_date(end)
        SQLQuery = (
            "SELECT DISTINCT cdb_object_id"
            " FROM cdbpcs_pool_assignment_v"
            f" WHERE calendar_profile_id = '{sqlapi.quote(id)}'"
            " AND (cdbpcs_pool_assignment_v.end_date IS NULL"
            " OR (cdbpcs_pool_assignment_v.start_date IS NOT NULL"
            f" AND cdbpcs_pool_assignment_v.end_date BETWEEN {start_str} AND {end_str}))"
            " AND (cdbpcs_pool_assignment_v.start_date IS NULL"
            " OR (cdbpcs_pool_assignment_v.end_date IS NOT NULL"
            f" AND cdbpcs_pool_assignment_v.start_date BETWEEN {start_str} AND {end_str}))"
        )

        oids = [x.cdb_object_id for x in sqlapi.RecordSet2(sql=SQLQuery)]
        assignments = fResourcePoolAssignment.KeywordQuery(cdb_object_id=oids)
        profiles = set()
        resources_demands = set()
        resources_allocations = set()
        for a in assignments:
            profiles.add(a.calendar_profile_id)
            resources_demands = resources_demands.union(a.ResourceDemands)
            resources_allocations = resources_allocations.union(a.ResourceAllocations)
        for pid in profiles:
            calendar.clearCalendarIndex(pid)
        task_uuids_d = get_task_uuids(resources_demands)
        task_uuids_a = get_task_uuids(resources_allocations)
        fSCHEDULE_CALCULATOR.createSchedules_many(set(task_uuids_d + task_uuids_a))


class CatalogPCSResAssignData(gui.CDBCatalogContent):
    def __init__(self, cdb_project_id, task_id, pool_oid, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        gui.CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.task_id = task_id
        self.pool_oid = pool_oid
        sql = """SELECT cdbpcs_pool_assignment.* FROM cdbpcs_pool_assignment"""
        if self.task_id and self.cdb_project_id:
            sql = """
                SELECT cdbpcs_pool_assignment.*
                FROM cdbpcs_pool_assignment, (
                    SELECT start_time_fcast AS task_start, end_time_fcast AS task_end
                    FROM cdbpcs_task
                    WHERE task_id='{0}' AND cdb_project_id='{1}' AND ce_baseline_id = ''
                ) task_dates
                WHERE
                    NOT (
                        (cdbpcs_pool_assignment.end_date IS NOT NULL
                        AND cdbpcs_pool_assignment.end_date < task_dates.task_start) OR
                        (cdbpcs_pool_assignment.start_date IS NOT NULL
                        AND cdbpcs_pool_assignment.start_date > task_dates.task_end)
                    )
            """.format(
                self.task_id, self.cdb_project_id
            )
            if self.pool_oid:
                sql += """ AND pool_oid='{0}' """.format(self.pool_oid)
        else:
            if self.pool_oid:
                sql += """ WHERE pool_oid='{0}' """.format(self.pool_oid)
        # TODO? RecordSet can take a max_records parameter even with sql
        self.assignments = ResourcePoolAssignment.FromRecords(
            sqlapi.RecordSet2(sql=sql)
        )

    def getNumberOfRows(self):
        return len(self.assignments)

    def getRowObject(self, row):
        return self.assignments[row].ToObjectHandle()


class CatalogPCSResAssign(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        cdb_project_id = ""
        task_id = ""
        pool_oid = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
            task_id = self.getInvokingDlgValue("task_id")
            pool_oid = self.getInvokingDlgValue("pool_oid")
        except Exception:  # nosec
            pass
        self.setResultData(
            CatalogPCSResAssignData(cdb_project_id, task_id, pool_oid, self)
        )
