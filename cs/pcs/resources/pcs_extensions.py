#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=C1801,W0703

from collections import defaultdict
from urllib import parse

from cdb import auth, sig, sqlapi, transactions, ue
from cdb.classbody import classbody
from cdb.constants import kOperationModify
from cdb.objects import ByID, Forward, Reference_N, ReferenceMapping_N
from cdb.objects.operations import operation
from cdb.objects.org import Person
from cdb.platform import gui
from cs.pcs.projects import (  # pylint: disable=W0611
    Project,
    SubjectAssignment,
    TeamMember,
)
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import (
    RessourceAssignment,
    RessourceDemand,
    db_tools,
    deleteScheduleViews,
)
from cs.pcs.resources.pools.assignments import Resource
from cs.pcs.resources.resourceschedule import (
    CombinedResourceSchedule,
    ResourceSchedule,
    ResourceScheduleTime,
)
from cs.pcs.resources.schedule import SCHEDULE_CALCULATOR
from cs.pcs.timeschedule import TimeSchedule  # noqa # pylint: disable=W0611

fTimeSchedule = Forward("cs.pcs.timeschedule.TimeSchedule")
fResourceSchedule = Forward("cs.pcs.resources.resourceschedule.ResourceSchedule")
fCombinedResourceSchedule = Forward(
    "cs.pcs.resources.resourceschedule.CombinedResourceSchedule"
)
fResourcePool = Forward("cs.pcs.resources.pools.ResourcePool")


@sig.connect(Task, "extend_task_adjust_own_values")
@sig.connect(Task, "extend_task_adjust_parent_to_subtasks")
def _extend_task_adjust_parent_to_subtasks(
    changes, effort_fcast_d=True, effort_fcast_a=True, **kwargs
):
    if effort_fcast_d:
        changes.append(
            """  effort_fcast_d = (SELECT CASE
                                              WHEN SUM(t.effort_fcast_d) > 0
                                              THEN SUM(t.effort_fcast_d)
                                              ELSE 0 END
                                              FROM cdbpcs_task t
                                              WHERE t.parent_task = cdbpcs_task.task_id
                                              AND t.cdb_project_id = cdbpcs_task.cdb_project_id
                                              AND t.ce_baseline_id = '') +
                                             (SELECT CASE
                                              WHEN SUM(d.hours) > 0
                                              THEN SUM(d.hours)
                                              ELSE 0 END
                                              FROM cdbpcs_prj_demand d
                                              WHERE d.task_id = cdbpcs_task.task_id
                                              AND d.cdb_project_id = cdbpcs_task.cdb_project_id)"""
        )
    if effort_fcast_a:
        changes.append(
            """  effort_fcast_a = (SELECT CASE
                                              WHEN SUM(t.effort_fcast_a) > 0
                                              THEN SUM(t.effort_fcast_a)
                                              ELSE 0 END
                                              FROM cdbpcs_task t
                                              WHERE t.parent_task = cdbpcs_task.task_id
                                              AND t.cdb_project_id = cdbpcs_task.cdb_project_id
                                              AND t.ce_baseline_id = '') +
                                             (SELECT CASE
                                              WHEN SUM(a.hours) > 0
                                              THEN SUM(a.hours)
                                              ELSE 0 END
                                              FROM cdbpcs_prj_alloc a
                                              WHERE a.task_id = cdbpcs_task.task_id
                                              AND a.cdb_project_id = cdbpcs_task.cdb_project_id)"""
        )


@sig.connect(Project, "extend_project_adjust_own_values")
@sig.connect(Project, "extend_project_adjust_parent_to_subtasks")
def _extend_project_adjust_parent_to_subtasks(
    changes, effort_fcast_d=True, effort_fcast_a=True, **kwargs
):
    kwargs2 = {}
    kwargs2["chr1"] = "''"
    if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
        kwargs2["chr1"] = "chr(1)"
    if effort_fcast_d:
        changes.append(
            """  effort_fcast_d = (SELECT SUM(t.effort_fcast_d)
                                              FROM cdbpcs_task t
                                              WHERE t.parent_task = %(chr1)s
                                              AND t.cdb_project_id = cdbpcs_project.cdb_project_id
                                              AND t.ce_baseline_id = '')"""
            % kwargs2
        )
    if effort_fcast_a:
        changes.append(
            """  effort_fcast_a = (SELECT SUM(t.effort_fcast_a)
                                              FROM cdbpcs_task t
                                              WHERE t.parent_task = %(chr1)s
                                              AND t.cdb_project_id = cdbpcs_project.cdb_project_id
                                              AND t.ce_baseline_id = '')"""
            % kwargs2
        )


@sig.connect("project_get_demands")
def project_get_demands(cdb_project_id):
    result = defaultdict(float)
    for rs in sqlapi.RecordSet2(
        "cdbpcs_prj_demand", "cdb_project_id = '{}'".format(cdb_project_id)
    ):
        result[rs.task_id] += rs.hours
    return result


@sig.connect("project_get_assignments")
def project_get_assignments(cdb_project_id):
    result = defaultdict(float)
    for rs in sqlapi.RecordSet2(
        "cdbpcs_prj_alloc", "cdb_project_id = '{}'".format(cdb_project_id)
    ):
        result[rs.task_id] += rs.hours
    return result


@sig.connect(Project, "delete", "pre")
@sig.connect(Task, "delete", "pre")
def delete_resource_schedule_objects(obj, ctx=None):
    for demand in obj.RessourceDemands:
        demand.deleteResourceScheduleObjects()
    for assignment in obj.RessourceAssignments:
        assignment.deleteResourceScheduleObjects()


@classbody
class TimeSchedule(object):

    CombinedResourceSchedules = Reference_N(
        fCombinedResourceSchedule,
        fCombinedResourceSchedule.time_schedule_oid == fTimeSchedule.cdb_object_id,
    )

    def on_CDBPCS_CapaChart_now(self, ctx):
        self.showCombinedSchedule(ctx=ctx)

    def create_resource_schedule(self):
        kwargs = {
            "cdb_project_id": self.cdb_project_id,
            "name": self.name,
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_objektart": "cdbpcs_res_schedule",
        }
        resource_schedule = None
        with transactions.Transaction():
            resource_schedule = ResourceScheduleTime.createObject(**kwargs)
            CombinedResourceSchedule.Create(
                time_schedule_oid=self.cdb_object_id,
                resource_schedule_oid=resource_schedule.cdb_object_id,
            )
        return resource_schedule

    def getResourceSchedule(self, ctx=None):
        """
        Gets the Resource Schedule to be displayed:
        - If an assigned Resource Schedule does not exist: a new one is created and returned
        - If exactly one Resource Schedule is assigned: this one is returned
        - If more than one Resource Schedule is assigned: the user selects a Resource Schedule from a catalog,
                                                          the selected one is returned
        :param ctx:
        :return: cs.pcs.resources.resourceschedule.ResourceSchedule
        """
        if self.CombinedResourceSchedules:
            return self.getPrimaryResourcesSchedule(ctx=ctx)
        return self.create_resource_schedule()

    def getPrimaryResourcesSchedule(self, ctx=None):
        if len(self.CombinedResourceSchedules) == 1:
            return ByID(self.CombinedResourceSchedules[0]["resource_schedule_oid"])
        if ctx and not ctx.catalog_selection:
            targs = {"time_schedule_oid": self.cdb_object_id}
            ctx.start_selection(catalog_name="cdbpcs_combined_trs_catalog2", **targs)
        else:
            return ByID(ctx.catalog_selection[0]["resource_schedule_oid"])
        return None

    def showCombinedSchedule(self, ctx):
        if not self.CheckAccess("read", auth.persno):
            raise ue.Exception("cdbpcs_operation_access")
        rs = self.getResourceSchedule(ctx=ctx)

        def quote(key):
            return parse.quote(key)

        if not rs:
            raise ue.Exception("resource_schedule_not_found")

        ctx.url(
            "/info/resource_schedule/{resourceschedule_oid}".format(
                resourceschedule_oid=quote(rs.cdb_object_id),
            )
        )

    def mirror_attribute_changes_to_RS(self, ctx):
        """
        Mirrors any changes to name, subject and project from TS
        to corresponding RS if TS is part of one or more combined schedules

        :param ctx:
        """
        # Note: These keys are schared between TS and RS
        attribute_keys_to_mirror = [
            "name", "subject_id", "subject_type", "cdb_project_id"
        ]
        if self.CombinedResourceSchedules:
            kwargs = {}
            for key in attribute_keys_to_mirror:
                if ctx.dialog[key] != ctx.previous_values[key]:
                    kwargs[key] = ctx.dialog[key]
            if kwargs:
                for crs in self.CombinedResourceSchedules:
                    operation(kOperationModify, crs.ResourceSchedule, **kwargs)

    event_map = {
        (("modify"), "post"): ("mirror_attribute_changes_to_RS"),
    }


@classbody
class Project(object):

    PrimaryResourceSchedule = Reference_N(
        fResourceSchedule, fResourceSchedule.cdb_project_id == Project.cdb_project_id
    )
    RessourceDemands = Reference_N(
        RessourceDemand, RessourceDemand.cdb_project_id == Project.cdb_project_id
    )
    RessourceAssignments = Reference_N(
        RessourceAssignment,
        RessourceAssignment.cdb_project_id == Project.cdb_project_id,
    )
    DemandsByOrg = ReferenceMapping_N(
        RessourceDemand,
        RessourceDemand.cdb_project_id == Project.cdb_project_id,
        indexed_by=RessourceDemand.org_id,
    )
    DemandsBySubject = ReferenceMapping_N(
        RessourceDemand,
        RessourceDemand.cdb_project_id == Project.cdb_project_id,
        indexed_by=RessourceDemand.subject_id,
    )
    AssignmentsByOrg = ReferenceMapping_N(
        RessourceAssignment,
        RessourceAssignment.cdb_project_id == Project.cdb_project_id,
        indexed_by=RessourceAssignment.org_id,
    )
    AssignmentsBySubject = ReferenceMapping_N(
        RessourceAssignment,
        RessourceAssignment.cdb_project_id == Project.cdb_project_id,
        indexed_by=RessourceAssignment.persno,
    )

    def on_CDBPCS_CapaChart_now(self, ctx):
        if not ctx.uses_webui:
            ts = self.getPrimaryTimeSchedule(ctx=ctx)
            if ts:
                ts.showCombinedSchedule(ctx=ctx)

    def on_CDBPCS_ResourceChart_now(self, ctx):
        ts = self.getPrimaryTimeSchedule(ctx=ctx)
        if ts:
            ctx.set_followUpOperation(
                opname="CDBPCS_CapaChart", use_result=1, op_object=ts
            )

    def createSchedules(self, ctx=None):
        SCHEDULE_CALCULATOR.createSchedules_many(self.Tasks.cdb_object_id)

    def getPrimaryResourceSchedule(self, ctx=None):
        if len(self.PrimaryResourceSchedule) == 1:
            return self.PrimaryResourceSchedule[0]
        if ctx and not ctx.catalog_selection:
            targs = {"cdb_project_id": self.cdb_project_id}
            ctx.start_selection(catalog_name="cdbpcs_rs_catalog2", **targs)
        else:
            return ByID(ctx.catalog_selection[0]["cdb_object_id"])
        return None

    def demandRemainderInHours(self, assigned=None):
        # unplanned efforts in hours
        result = 0.0
        try:
            total = float(self.effort_fcast_d)
            if assigned:
                total = total - assigned
        except Exception:
            total = 0.0
        try:
            planned = float(self.effort_plan) if len(self.Tasks) > 0 else 0.0
        except Exception:
            planned = 0.0
        if self.effort_fcast:
            result = self.effort_fcast - max(total, planned)
        else:
            result = -total
        return result

    @sig.connect(Project, "adjust_effort_fcast_d")
    def _adjust_effort_fcast_d(self, effort):
        if len(self.RessourceDemands) == 1:
            demands = self.RessourceDemands[0]
            operation(kOperationModify, demands, hours=effort)

    @sig.connect(Project, "adjust_effort_fcast_a")
    def _adjust_effort_fcast_a(self, effort):
        if len(self.RessourceAssignments) == 1:
            assignment = self.RessourceAssignments[0]
            operation(kOperationModify, assignment, hours=effort)

    @sig.connect(Project, "adjustDependingObjects")
    def removeOrphanedAllocations(self):
        # currently required due to the msp interface not removing tasks via operations
        for obj in RessourceDemand.Query(
            "cdb_object_id in (select cdb_object_id from cdbpcs_prj_demand_v where task_object_id is null)"
        ):
            data = {
                "cdb_project_id": obj.cdb_project_id,
                "task_id": obj.task_id,
                "cdb_demand_id": obj.cdb_demand_id,
            }
            deleteScheduleViews(data=data, all=True)
            obj.Delete()
        for obj in RessourceAssignment.Query(
            "cdb_object_id in (select cdb_object_id from cdbpcs_prj_alloc_v where task_object_id is null)"
        ):
            data = {
                "cdb_project_id": obj.cdb_project_id,
                "task_id": obj.task_id,
                "cdb_alloc_id": obj.cdb_alloc_id,
            }
            deleteScheduleViews(data=data, all=True)
            obj.Delete()

    @sig.connect(Project, "adjustAllocationsOnly")
    def adjustPoolAssignments(self, task_ids=None):
        if not task_ids:
            return
        from cs.pcs.resources import adjust_pool_assignments, format_in_condition

        condition = format_in_condition("task_id", list(task_ids))
        sql = """SELECT assignment_oid FROM cdbpcs_prj_demand
                  WHERE cdb_project_id = '%s' AND (%s)
                  UNION
                  SELECT assignment_oid FROM cdbpcs_prj_alloc
                  WHERE cdb_project_id = '%s' AND (%s)
              """ % (
            self.cdb_project_id,
            condition,
            self.cdb_project_id,
            condition,
        )
        assign_oids = [x["assignment_oid"] for x in sqlapi.RecordSet2(sql=sql)]
        adjust_pool_assignments(assignment_oids=assign_oids)

    @sig.connect(Project, "adjustAllocationsOnly")
    def adjustAllocationsOnly(self, task_ids=None):
        if task_ids:
            tasks = Task.KeywordQuery(
                cdb_project_id=self.cdb_project_id,
                task_id=task_ids,
                ce_baseline_id="",
            )
        else:
            tasks = self.Tasks

        Task.adjustAllocationsOnly_many(tasks)

    @sig.connect(Project, "do_consistency_checks")
    def adjustResourceSchedules(self, task_ids=None):

        SCHEDULE_CALCULATOR.createSchedules_many(self.Tasks.cdb_object_id)

    def deleteScheduleViews(self, _ctx=None):
        data = {"cdb_project_id": self.cdb_project_id}
        deleteScheduleViews(data=data, all=True)

    def createResourceSchedule(self, ctx):
        kwargs = {"cdb_project_id": self.cdb_project_id, "name": self.project_name}
        ResourceSchedule.createObject(**kwargs)

    def getAssignedOIDs(self):
        # return the id of resources that are used for this project
        assign_oids = []
        # for pool in fResourcePool.KeywordQuery(browser_root=1):
        #     assign_oids.append(pool.cdb_object_id)
        for tm in self.TeamMembers:
            if tm.Person:
                for rm in tm.Person.ResourceMember:
                    assign_oids.append(rm.cdb_object_id)
        return assign_oids

    def getRealizationBy(self):
        oids = self.getAssignedOIDs()
        if oids:
            oid_str = ", ".join(["'%s'" % x for x in oids])
            sql = """SELECT 1 AS position, name FROM cdbpcs_resource_v
                      WHERE referenced_oid IN ({oid_str})
                      UNION
                      SELECT 0 AS position, name FROM cdbpcs_resource_pool
                      WHERE cdb_object_id IN ({oid_str})
                      ORDER BY position, name
                  """.format(
                oid_str=oid_str
            )
            result = sqlapi.RecordSet2(sql=sql)
            if result:
                return ", ".join([x["name"] for x in result])
        return ""

    event_map = {
        (("delete"), "post"): ("deleteScheduleViews"),
    }


@classbody
class TeamMember(object):
    def checkTasksAssignments(self, _ctx):
        """
        the methode checkt the assignment between task and person.

        :Parameters:
            ``ctx``: *Context*

        :raise cdbpcs_check_task_r: Team member can not be deleted, because the
            team members was allocated to a task!
        """
        # Suche Ressourcenzuweisung einer Person
        mylist = self.Project.RessourceAssignments.KeywordQuery(
            persno=self.Person.personalnummer
        )
        if mylist:
            raise ue.Exception(
                "cdbpcs_check_tasks_r", self.Person.name, mylist[0].Task.task_name
            )

    event_map = {
        (("delete"), "pre"): "checkTasksAssignments",
    }


@classbody
class Task(object):

    # Flag to indicate how to calculate the available demand hours:
    # True: (effort_fcast - effort_fcast_d) => no matter whether the efforts are distributed to the subtasks
    # False: the minimum of (effort_fcast - effort_fcast_d) and (effort_fcast - effort_plan)
    #       => the distributed efforts would be taken off
    _NO_RESOURCE_BREAK_DOWN_ = True

    RessourceDemands = Reference_N(
        RessourceDemand,
        RessourceDemand.cdb_project_id == Task.cdb_project_id,
        RessourceDemand.task_id == Task.task_id,
    )
    RessourceAssignments = Reference_N(
        RessourceAssignment,
        RessourceAssignment.cdb_project_id == Task.cdb_project_id,
        RessourceAssignment.task_id == Task.task_id,
    )

    def on_CDBPCS_ProjectPlan_now(self, ctx):
        self.Project.on_CDBPCS_ProjectPlan_now(ctx=ctx)

    def on_CDBPCS_CapaChart_now(self, ctx):
        self.Project.on_CDBPCS_CapaChart_now(ctx=ctx)

    def createSchedules(self, ctx=None):
        SCHEDULE_CALCULATOR.createSchedules_many([self.cdb_object_id])

    # ----- Attention
    # The following methods overwrite the existing methods of Task. The warning
    # from the classbody implementation is accepted, to avoid an overly complex
    # alternative implementation.

    def getAssignedOIDs(self):
        # return the id of resources that are used for this task
        sql = (
            """SELECT pool_oid, assignment_oid FROM cdbpcs_prj_demand
                  WHERE cdb_project_id = '%(cdb_project_id)s'
                  AND   task_id = '%(task_id)s'
                  UNION
                  SELECT pool_oid, assignment_oid FROM cdbpcs_prj_alloc
                  WHERE cdb_project_id = '%(cdb_project_id)s'
                  AND   task_id = '%(task_id)s'
               """
            % self
        )
        rset = sqlapi.RecordSet2(sql=sql)
        result = set()
        # responsibles
        if self.subject_type == "Person":
            resp = self.Subject.getPersons()
            if len(resp):
                for rm in resp[0].ResourceMember:
                    result.add(rm.cdb_object_id)
        # assignments
        for r in rset:
            if r["assignment_oid"]:
                result.add(r["assignment_oid"])
            elif r["pool_oid"]:
                result.add(r["pool_oid"])
        return list(result)

    def hasResourceDemands(self):
        return len(self.RessourceDemands) > 0

    def hasResourceAssignments(self):
        return len(self.RessourceAssignments) > 0

    def assignedDemands(self, attr):
        """
        returns sum of given attribute over all assigned demands
        """
        return sum(a[attr] for a in self.RessourceDemands if a[attr])

    def assignedResources(self, attr):
        """
        returns sum of given attribute over all resource assignments
        """
        return sum(a[attr] for a in self.RessourceAssignments if a[attr])

    # ----- End Attention

    def demandRemainderInHours(self, assigned=None):
        # unplanned efforts in hours
        result = 0.0
        total = 0.0
        planned = 0.0
        if self.effort_fcast_d:
            total = self.effort_fcast_d
        if assigned:
            total -= assigned
        if self.is_group and self.effort_plan:
            planned = self.effort_plan
        if self.effort_fcast:
            if self._NO_RESOURCE_BREAK_DOWN_:
                result = self.effort_fcast - total
            else:
                result = self.effort_fcast - max(total, planned)
        elif self.effort_fcast == 0.0:
            result = -total
        else:
            if assigned is None:
                assigned = self.assignedDemands("hours")
            if self.ParentTask:
                result = self.ParentTask.demandRemainderInHours(assigned)
            else:
                result = self.Project.demandRemainderInHours(assigned)
            result = result - assigned
        return result

    @sig.connect(Task, "validateSchedule")
    def _validateSchedule(self):
        work_uncovered = max(
            min(
                1,
                len(
                    [
                        x
                        for x in self.RessourceDemands
                        if not x.hours_per_day and x.hours
                    ]
                ),
            ),
            min(
                1,
                len(
                    [
                        x
                        for x in self.RessourceAssignments
                        if not x.hours_per_day and x.hours
                    ]
                ),
            ),
        )
        if work_uncovered != self.work_uncovered:
            self.work_uncovered = work_uncovered

    @sig.connect(Task, "adjust_effort_fcast_d")
    def _adjust_effort_fcast_d(self, effort):
        if len(self.RessourceDemands) == 1:
            demand = self.RessourceDemands[0]
            operation(kOperationModify, demand, hours=effort)

    @sig.connect(Task, "adjust_effort_fcast_a")
    def _adjust_effort_fcast_a(self, effort):
        if len(self.RessourceAssignments) == 1:
            assignment = self.RessourceAssignments[0]
            operation(kOperationModify, assignment, hours=effort)

    @classmethod
    @sig.connect(Task, "adjustDependingObjects_many")
    def adjustDependingObjects_many(cls, tasks):
        """Die Methode passt alle Aufwände sowie Ressourcenbedarfe und
        Ressourcenzuweisungen an.
        Insbesondere werden die Std/Tag-Werte an das veränderte Zeitfenster
        der Aufgabe angepasst.
        """
        cls.adjustAllocationsOnly_many(tasks)

        task_uuids = [x.cdb_object_id for x in tasks]
        SCHEDULE_CALCULATOR.createSchedules_many(task_uuids)

    @sig.connect(Task, "adjustAllocationsOnly")
    def adjustPoolAssignments(self):
        self.Project.adjustPoolAssignments(task_ids=[self.task_id])

    @sig.connect(Task, "adjustAllocationsOnly")
    def adjustAllocationsOnly(self):
        task_uuids_d = db_tools.get_task_uuids(self.RessourceDemands)
        RessourceDemand.adjust_values_many(task_uuids_d)
        task_uuids_a = db_tools.get_task_uuids(self.RessourceAssignments)
        RessourceAssignment.adjust_values_many(task_uuids_a)

    @classmethod
    def adjustAllocationsOnly_many(cls, tasks):
        # does not call createSchedules
        task_uuids = [x.cdb_object_id for x in tasks]
        for clss in [RessourceDemand, RessourceAssignment]:
            clss.adjust_values_many(task_uuids)

    @sig.connect(Task, "copy_task_hook")
    def _copy_demands_for_new_task(self, new_project, new_task):
        """After copying a task, copy the corresponding demands too."""
        for resource_demand in self.RessourceDemands:
            resource_demand.MakeCopy(new_project, new_task)

    @sig.connect(Task, "checkEffortFields")
    def _check_resource_preconditions(self):
        # target start/end must be filled for demands/assignments
        if (len(self.RessourceDemands) or len(self.RessourceAssignments)) and not (
            self.start_time_fcast and self.end_time_fcast
        ):
            raise ue.Exception("pcs_capa_err_024")

    @sig.connect(Task, "getNotificationReceiver")
    def _getAssignmentsNotificationReceiver(self):
        rcvr = {}
        tolist = []
        for ra in self.RessourceAssignments:
            if ra.Person:
                pers = ra.Person
                if pers.email_notification_task():
                    if (pers.e_mail, pers.name) not in tolist:
                        tolist.append((pers.e_mail, pers.name))
        if tolist:
            rcvr["to"] = tolist
        return rcvr

    @classmethod
    def getStatusForResourceEvaluation(cls):
        """
        status numbers of tasks that are not completed or have been discarded
        :rtype: tupel
        """
        return Task.NEW.status, Task.READY.status, Task.EXECUTION.status

    @classmethod
    def get_condition_of_StatusForResourceEvaluation(cls, table_name="cdbpcs_task"):
        """
        SQL condition for
        status numbers of tasks that are not completed or have been discarded
        :return: unicode
        """
        return " {}.status IN ({}) ".format(
            table_name,
            ", ".join(["%s" % str(x) for x in Task.getStatusForResourceEvaluation()]),
        )

    @classmethod
    def isWorkUncovered(cls, current_task, changed_task):
        changed_st = current_task.start_time_fcast
        if not changed_st or changed_st == sqlapi.NULL:
            changed_st = changed_task.get(
                "start_time_fcast", current_task.start_time_fcast
            )
        changed_st = changed_st.date()
        changed_et = current_task.end_time_fcast
        if not changed_et or changed_et == sqlapi.NULL:
            changed_et = changed_task.get("end_time_fcast", current_task.end_time_fcast)
        changed_et = changed_et.date()
        work_uncovered = (
            0  # work_uncovered do the same thing as adjustDependingObjects_many
        )
        cond = "cdb_project_id = '%s'" " AND task_id = '%s'" % (
            sqlapi.quote(current_task.cdb_project_id),
            sqlapi.quote(current_task.task_id),
        )
        demands = sqlapi.RecordSet2(RessourceDemand.GetTableName(), cond)
        for demand in demands:
            changes = RessourceDemand.clsHoursChanged(current_task, demand)
            if changes:
                demand.update(**changes)
            RessourceDemand.clsUpdateSchedules(demand, changed_st, changed_et)
            if not changes.get("hours_per_day", None):
                work_uncovered = 1

        assignments = sqlapi.RecordSet2(RessourceAssignment.GetTableName(), cond)
        for assignment in assignments:
            changes = RessourceAssignment.clsHoursChanged(current_task, assignment)
            if changes:
                assignment.update(**changes)
            RessourceAssignment.clsUpdateSchedules(assignment, changed_st, changed_et)
            if not changes.get("hours_per_day", None):
                work_uncovered = 1

        # Testen ob die Aufgabe nicht durchführbar ist
        # self.validateSchedule()
        if not work_uncovered:
            # if work_uncovered !=1: try self.validateSchedule,
            # otherwise the work_uncovered=1 will be set
            # by calling adjustDependingObjects_many (see self.duration_changed)
            work_uncovered = cls.clsValidateSchedule(
                changed_task, demands, assignments
            ).get("work_uncovered", work_uncovered)
        return work_uncovered

    @classmethod
    def clsValidateSchedule(cls, task, demands, assignments):
        # Falls die Aufgabe nicht durchführbar ist,
        # wird sie als ungültig markiert
        result = {}
        if task["milestone"]:
            result["work_uncovered"] = 0
        else:
            result["work_uncovered"] = max(
                min(
                    1,
                    len([x for x in demands if not x["hours_per_day"] and x["hours"]]),
                ),
                min(
                    1,
                    len(
                        [
                            x
                            for x in assignments
                            if not x["hours_per_day"] and x["hours"]
                        ]
                    ),
                ),
            )
        return result

    @classmethod
    def clsCurrentAssignmentRemainderInHours(cls, task):  # deprecated
        pass

    def deleteScheduleViews(self, _ctx=None):
        data = {"cdb_project_id": self.cdb_project_id, "task_id": self.task_id}
        deleteScheduleViews(data=data, all=True)

    def resetAssignments(self, ctx=None):
        for a in self.RessourceAssignments:
            a.hours = 0.0
            a.adjust_values()
            a.adjust_hours()

    def cdbpcs_taskbreakdown_check_access(self):
        if hasattr(self, "acceptNewTask"):
            # TODO: ensures backward compatibility, remove in future versions
            self.acceptNewTask()
        else:
            self.accept_new_task()
        operation_label = gui.Label.ByKeys(ausgabe_label="cdbpcs_taskbreakdown")
        if not self.CheckAccess("create"):
            raise ue.Exception(
                "authorization_fail", operation_label.Text[""], "cdbpcs_task", "create"
            )

        if not self.CheckAccess("save"):
            raise ue.Exception(
                "authorization_fail", operation_label.Text[""], "cdbpcs_task", "save"
            )

        if not self.CheckAccess("accept"):
            raise ue.Exception(
                "authorization_fail", operation_label.Text[""], "cdbpcs_task", "accept"
            )

    def on_cdbpcs_taskbreakdown_elink_now(self, ctx):
        self.Project.checkStructureLock()
        if self.milestone:
            raise ue.Exception("cdbpcs_err_task_milestone")

        if self.Project.locked_by and not self.Project.locked_by == auth.persno:
            raise ue.Exception("pcs_tbd_locked", self.Project.locked_by)

        self.cdbpcs_taskbreakdown_check_access()

        if "%s" % self.is_group == "1":
            raise ue.Exception("pcs_tbd")

        if not self.start_time_fcast or not self.start_time_fcast:
            raise ue.Exception("cdbpcs_resource_no_data")

        effort_default = "true"
        demand_default = "true"
        alloc_default = "true"
        ea_default = "false"
        sub_elems_default = "3"

        check_d = "1" if self.hasResourceDemands() else "0"
        check_a = "1" if self.hasResourceAssignments() else "0"
        check_e = "1" if self.effort_fcast else "0"

        ctx.url(
            "/powerscript/cs.pcs.resources.taskbreakdown/start?task_id=%s&"
            "cdb_project_id=%s&check_d=%s&check_a=%s&check_e=%s&effort_default=%s&"
            "demand_default=%s&alloc_default=%s&ea_default=%s&sub_elems_default=%s"
            % (
                parse.quote(self.task_id),
                parse.quote(self.cdb_project_id),
                parse.quote(check_d),
                parse.quote(check_a),
                parse.quote(check_e),
                parse.quote(effort_default),
                parse.quote(demand_default),
                parse.quote(alloc_default),
                parse.quote(ea_default),
                parse.quote(sub_elems_default),
            )
        )

    def getRealizationBy(self):
        oids = self.getAssignedOIDs()
        if oids:
            oid_str = ", ".join(["'%s'" % x for x in oids])
            sql = """SELECT 1 AS position, name FROM cdbpcs_resource_v
                      WHERE referenced_oid IN ({oid_str})
                      UNION
                      SELECT 0 AS position, name FROM cdbpcs_resource_pool
                      WHERE cdb_object_id IN ({oid_str})
                      ORDER BY position, name
                  """.format(
                oid_str=oid_str
            )
            result = sqlapi.RecordSet2(sql=sql)
            if result:
                return ", ".join([x["name"] for x in result])
        return ""

    event_map = {
        (("delete"), "pre"): ("resetAssignments"),
        (("delete"), "post"): ("deleteScheduleViews"),
    }




@classbody
class SubjectAssignment(object):

    def keep_subj_with_assignment(self, _):
        # Check if person is also assigned to another role
        assignments = SubjectAssignment.KeywordQuery(cdb_project_id=self.cdb_project_id, subject_id=self.subject_id)
        if len(assignments) > 1:
            return
        # check if demand assignment exists
        person = Person.KeywordQuery(personalnummer=self.subject_id)[0]
        resources = Resource.KeywordQuery(referenced_oid=person.cdb_object_id)
        if len(resources) > 0:
            resource = resources[0]
            assignments = RessourceAssignment.KeywordQuery(
                resource_oid=resource.cdb_object_id,
                cdb_project_id=self.cdb_project_id
            )
            if len(assignments) > 0:
                raise ue.Exception("cdbpcs_person_has_assignments")

    event_map = {
        ("delete", "pre"): "keep_subj_with_assignment",
    }
