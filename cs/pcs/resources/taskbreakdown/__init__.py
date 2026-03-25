#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=W0102,W0603,C0200,W0212,R0912,R0914

import functools
import time

from cdb import cdbuuid, elink, transactions, util
from cdb.platform import olc
from cs.pcs.projects import Project
from cs.pcs.projects import calendar as Calendar
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.resources import RessourceAssignment, RessourceDemand
from cs.pcs.resources.helpers import date_from_legacy_str, to_legacy_str
from cs.shared.elink_plugins import check_license

ELINK_LABELS = {}


def decode_js_text(txt):
    if isinstance(txt, str):
        return "%s" % txt
    return txt


def encode_js_text(txt):
    if isinstance(txt, str):
        return "%s" % txt
    return txt


def get_label(name):
    return ELINK_LABELS.setdefault(name, encode_js_text(util.get_label(name)))


@elink.using_template_engine("chameleon")
@check_license.check_license("RESOURCES_004")
class TaskBreakDownElinkAPP(elink.Application):
    def __init__(self):
        super(TaskBreakDownElinkAPP, self).__init__("CDB Task Break Down")
        self.add("start", TaskBreakDownElinkPage())
        self.add("table", TaskBreakDownScheme())
        self.addJSON(self.savedata)

    def getWorkdays(self, sd, ed, prj_id):
        result = Calendar.getProjectWorkdays(
            with_prj_ids=[prj_id], start_date=sd, end_date=ed
        )
        return [x[0] for x in result[prj_id]]

    def getNextWorkdayIndex(self, my_workdays, date):
        for i in range(len(my_workdays)):
            myday = my_workdays[i]
            if date <= myday:
                return i
        return -1

    def getLastWorkdayIndex(self, my_workdays, date):
        for i in range(len(my_workdays)):
            myday = my_workdays[i]
            if date == myday:
                return i
        return -1

    def _new_task(self, parent_task):
        new_task = Task(**parent_task._record)
        new_task.parent_task = parent_task.task_id
        new_task.cdb_object_id = cdbuuid.create_uuid()
        new_task.setTaskID(None)
        new_task.effort_fcast_d = ""
        new_task.effort_fcast_a = ""
        new_task.effort_fcast = ""
        new_task.effort_plan = ""
        new_task.position = ""
        new_task.material_cost = ""
        return new_task

    def _update_parent_task(self, parent_task, sd, sa):
        parent_task.is_group = "1"
        # """ delete demand - and alloc-objects, if nessessary """
        if sd == "true":
            for rd in parent_task.RessourceDemands:
                # rd.Delete()
                rd.deleteScheduleViews()
            parent_task.RessourceDemands.Delete()

        if sa == "true":
            for ass in parent_task.RessourceAssignments:
                # ass.Delete()
                ass.deleteScheduleViews()
            parent_task.RessourceAssignments.Delete()

        if hasattr(Task, "_mark_changed_tasks"):
            # TODO: ensures backward compatibility, remove in future versions
            Task._mark_changed_tasks(task_oids=[parent_task.cdb_object_id])
        else:
            Task.mark_as_changed(cdb_object_id=[parent_task.cdb_object_id])
        parent_task.Reload()
        parent_task.auto_update_time = 0
        parent_task.auto_update_effort = 0
        return parent_task

    def update_tasks(self, mylist):
        if not mylist:
            return
        mylist[0].recalculate()

        from cs.pcs import projects

        if hasattr(projects, "tasks_efforts"):
            projects.tasks_efforts.aggregate_changes(mylist[0].Project)
            return

        # TODO: remove old code, used by cs.pcs <= 15.6.1
        for t in mylist:
            t.Reload()
            t.adjust_values(
                adjust_parents=True,
                effort_plan=True,
                effort_act=True,
                time_act=True,
                effort_fcast_d=True,
                effort_fcast_a=True,
                effort_fcast=t.auto_update_effort,
            )
            t.adjust_values(adjust_parents=True, percentage=True)
            t.updateStatusSignals(effort=True)
            t.validateSchedule_many([t])
        object_ids = [x.cdb_object_id for x in mylist]
        if hasattr(Task, "_mark_changed_tasks"):
            Task._mark_changed_tasks(task_oids=object_ids)
        else:
            Task.mark_as_changed(cdb_object_id=object_ids)

    def savedata(self, **kwargs):  # pylint: disable=too-many-statements
        if self.request:
            self.request.charset = "utf-8"
        with transactions.Transaction():
            cdb_project_id = kwargs["cdb_project_id"]
            task_id = kwargs["task_id"]
            project = Project.ByKeys(cdb_project_id)

            task_list = []
            effort = 0.0
            split_effort = "false"
            split_demand = "false"
            split_alloc = "false"

            if "split_effort" in kwargs:
                split_effort = kwargs["split_effort"]
                if split_effort == "checked":
                    split_effort = "true"
            if "split_demand" in kwargs:
                split_demand = kwargs["split_demand"]
                if split_demand == "checked":
                    split_demand = "true"
            if "split_alloc" in kwargs:
                split_alloc = kwargs["split_alloc"]
                if split_alloc == "checked":
                    split_alloc = "true"

            new_parent_task = Task.ByKeys(
                task_id=task_id, cdb_project_id=cdb_project_id
            )
            if not new_parent_task.CheckAccess("write"):
                return
            new_task = self._new_task(new_parent_task)
            min_start_date = new_parent_task.start_time_fcast
            max_end_date = new_parent_task.end_time_fcast

            if kwargs["check_e"] == "1":
                if new_parent_task.effort_fcast:
                    effort = float(new_parent_task.effort_fcast)

            i = int(kwargs["task_count"])
            if not i:
                raise util.ErrorMessage("cdbpcs_tbd_no_of_subtasks")
            if "create_ea_rel" in kwargs:
                ea_bool = "true"
            else:
                ea_bool = "false"

            workday_list = []
            for num in range(i):
                start_date = date_from_legacy_str(kwargs["start_date%s" % (num + 1)])
                end_date = date_from_legacy_str(kwargs["end_date%s" % (num + 1)])
                if start_date > end_date:
                    raise util.ErrorMessage(
                        "cdbpcs_tbd_wrong_timeperiod", new_task.task_name
                    )
                if min_start_date > start_date or max_end_date < end_date:
                    raise util.ErrorMessage("cdbpcs_tbd_timeframe")

                sd_index = Calendar.getIndexByDate(
                    project.calendar_profile_id, start_date
                )[0]
                ed_index = Calendar.getIndexByDate(
                    project.calendar_profile_id, end_date
                )[0]
                workday_list.append(ed_index - sd_index + 1)

            workdays_sum = functools.reduce(lambda a, b: a + b, workday_list, 0.0)
            effort_per_day = float(effort / workdays_sum)

            for num in range(i):
                new_task = self._new_task(new_parent_task)
                new_task.Update(**Task.MakeChangeControlAttributes())
                new_task.task_name = decode_js_text(kwargs["task_name%s" % (num + 1)])
                new_task.start_time_fcast = kwargs["start_date%s" % (num + 1)]
                new_task.end_time_fcast = kwargs["end_date%s" % (num + 1)]
                new_task.days_fcast = workday_list[num]
                new_task.duration_fcast = workday_list[num] * 8
                workday_count = workday_list[num]
                if split_effort == "true" or split_demand == "true":
                    new_task.effort_fcast = round(effort_per_day * workday_count, 2)
                    new_task.effort_plan = round(effort_per_day * workday_count, 2)
                else:
                    new_task.effort_fcast = 0.0
                    new_task.effort_plan = 0.0
                new_task.is_group = 0
                new_task.automatic = 0

                task = Task.Create(**new_task)
                task.setPosition(None)
                task_list.append(task)

                if split_demand == "true":
                    split_alloc = "true"

                if split_demand == "true" or split_alloc == "true":
                    for d in new_parent_task.RessourceDemands:
                        demand_id = d.cdb_demand_id
                        if split_demand == "true":
                            demand_per_day = float(d.hours / workdays_sum)
                            demand_args = {
                                "cdb_object_id": cdbuuid.create_uuid(),
                                "cdb_demand_id": d._generate_id(),
                                "demand_type": d.demand_type,
                                "cdb_project_id": task.cdb_project_id,
                                "task_id": task.task_id,
                                "subject_id": d.subject_id,
                                "org_id": d.org_id,
                                "pool_oid": d.pool_oid,
                                "resource_oid": d.resource_oid,
                                "assignment_oid": d.assignment_oid,
                                "resource_type": d.resource_type,
                                "hours_assigned": 0.0,
                                "coverage": 0,
                                "hours_per_day": 0.0,
                                "hours": round(demand_per_day * workday_count, 2),
                            }
                            new_demand = RessourceDemand.Create(**demand_args)
                            new_demand.setWorkdays()
                            new_demand.hours_changed()
                            demand_id = new_demand.cdb_demand_id
                        if split_alloc == "true":
                            for a in d.Assignments:
                                assign_per_day = float(a.hours / workdays_sum)
                                alloc_args = {
                                    "cdb_object_id": cdbuuid.create_uuid(),
                                    "cdb_alloc_id": a._generate_id(),
                                    "cdb_project_id": task.cdb_project_id,
                                    "task_id": task.task_id,
                                    "cdb_demand_id": demand_id,
                                    "persno": a.persno,
                                    "org_id": a.org_id,
                                    "pool_oid": a.pool_oid,
                                    "resource_oid": a.resource_oid,
                                    "assignment_oid": a.assignment_oid,
                                    "hours_per_day": 0.0,
                                    "hours": round(assign_per_day * workday_count, 2),
                                }
                                new_alloc = RessourceAssignment.Create(**alloc_args)
                                new_alloc.setWorkdays()
                                new_alloc.hours_changed()
                                new_alloc.check_demand_coverage()

            if split_effort == "true" or split_demand == "true":
                if new_parent_task.Subtasks:
                    myEffortList = [x.effort_fcast for x in new_parent_task.Subtasks]
                    myEffortList = [x for x in myEffortList if x]
                    effort_sum = functools.reduce(lambda a, b: a + b, myEffortList, 0.0)
                    if effort_sum != effort:
                        myEffort = (
                            new_parent_task.Subtasks[
                                len(new_parent_task.Subtasks) - 1
                            ].effort_fcast
                            - effort_sum
                            + effort
                        )
                        new_parent_task.Subtasks[
                            len(new_parent_task.Subtasks) - 1
                        ].effort_fcast = myEffort
                        new_parent_task.Subtasks[
                            len(new_parent_task.Subtasks) - 1
                        ].effort_plan = myEffort

            self._update_parent_task(new_parent_task, split_demand, split_alloc)
            self.update_tasks(task_list)

            if task_list and ea_bool == "true":
                parent_task_state = new_parent_task.status
                first_task = task_list[0]

                if parent_task_state == 20:
                    first_task.status = parent_task_state
                    first_task.cdb_status_txt = olc.StateDefinition.ByKeys(
                        Task.READY.status, "cdbpcs_task"
                    ).StateText[""]

                    for t in task_list[1:]:
                        t.status = 0
                        t.cdb_status_txt = olc.StateDefinition.ByKeys(
                            Task.NEW.status, "cdbpcs_task"
                        ).StateText[""]

                elif parent_task_state == 50:
                    first_task.status = parent_task_state
                    first_task.cdb_status_txt = olc.StateDefinition.ByKeys(
                        Task.EXECUTION.status, "cdbpcs_task"
                    ).StateText[""]

                    for t in task_list[1:]:
                        t.status = 0
                        t.cdb_status_txt = olc.StateDefinition.ByKeys(
                            Task.NEW.status, "cdbpcs_task"
                        ).StateText[""]

            if ea_bool == "true":
                if task_list:
                    b = len(task_list)
                    for num in range(b - 1):
                        task1 = task_list[num]
                        task2 = task_list[num + 1]
                        if task1 and task2:
                            trel_args = {
                                "cdb_project_id": kwargs["cdb_project_id"],
                                "task_id": task2.task_id,
                                "cdb_project_id2": kwargs["cdb_project_id"],
                                "task_id2": task1.task_id,
                                "rel_type": "EA",
                                "name": "",
                                "minimal_gap": 0,
                                "gap": 0,
                            }
                            TaskRelation.createRelation(**trel_args)


class TaskBreakDownElinkPage(elink.Template):
    __template__ = "cdbpcs_taskbreakdown.htm"

    def get_label(self, name):
        return get_label(name)

    def check_umlauts(self, string):
        string = string.replace("Ä", "%C4")
        string = string.replace("Ö", "%D6")
        string = string.replace("Ü", "%DC")
        string = string.replace("ä", "%E4")
        string = string.replace("ö", "%F6")
        string = string.replace("ü", "%FC")
        string = string.replace("ß", "%DF")
        return string

    def render(self, context, *args, **varkw):
        context.cdb_project_id = varkw["cdb_project_id"]
        context.task_id = varkw["task_id"]
        cdb_project_id = None
        task_id = None
        context.call_time = time.time()
        context.invalid_value = self.check_umlauts(
            util.get_label("cdbpcs_tbd_invalid_value")
        )

        if "check_d" in varkw:
            check_d = varkw.get("check_d", "")
            context.check_d = check_d

        if "check_a" in varkw:
            check_a = varkw.get("check_a", "")
            context.check_a = check_a

        if "check_e" in varkw:
            check_e = varkw.get("check_e", "")
            context.check_e = check_e

        if "effort_default" in varkw:
            context.effort_default = varkw.get("effort_default", "")

        if "demand_default" in varkw:
            demand_default = varkw.get("demand_default", "")
            context.demand_default = demand_default
            if demand_default == "true":
                context.disabled = "true"
            else:
                context.disabled = "false"

        if "alloc_default" in varkw:
            alloc_default = varkw.get("alloc_default", "")
            context.alloc_default = alloc_default

        if "sub_elems_default" in varkw:
            context.sub_elems_default = varkw.get("sub_elems_default", "")

        if "ea_default" in varkw:
            context.ea_default = varkw.get("ea_default", "")

        if "cdb_project_id" in varkw:
            cdb_project_id = varkw.get("cdb_project_id", "")
            context.cdb_project_id = cdb_project_id
        else:
            context.cdb_project_id = None

        if "task_id" in varkw:
            task_id = varkw.get("task_id", "")
            context.task_id = task_id
            tobj = Task.ByKeys(task_id=task_id, cdb_project_id=cdb_project_id)

            if tobj and tobj.CheckAccess("read"):
                context.is_group = "%s" % tobj.is_group
                if tobj.task_name:
                    context.name = tobj.task_name
                else:
                    context.name = ""

                if tobj.start_time_fcast:
                    context.start = tobj.start_time_fcast
                else:
                    context.start = ""

                if tobj.end_time_fcast:
                    context.end = tobj.end_time_fcast
                else:
                    context.end = ""

                if tobj.effort_fcast:
                    context.eff = tobj.effort_fcast
                else:
                    context.eff = ""

                if tobj.effort_fcast_d:
                    context.demand = tobj.effort_fcast_d
                else:
                    context.demand = ""

                if tobj.effort_fcast_a:
                    context.alloc = tobj.effort_fcast_a
                else:
                    context.alloc = ""

                if (
                    tobj.start_time_fcast
                    and tobj.end_time_fcast
                    and tobj.cdb_project_id
                ):
                    startdate = tobj.start_time_fcast
                    enddate = tobj.end_time_fcast
                    result = Calendar.getProjectWorkdays(
                        with_prj_ids=[tobj.cdb_project_id],
                        start_date=startdate,
                        end_date=enddate,
                    )
                    context.workdays = len([x[0] for x in result[tobj.cdb_project_id]])
                    context.sub_elems_incorrect = (
                        self.check_umlauts(
                            util.get_label("cdbpcs_tbd_no_subelems_incorrect")
                        )
                        + " "
                        + str(context.workdays)
                    )


class TaskBreakDownScheme(elink.Template):
    __template__ = "cdbpcs_taskbreakdown_scheme.htm"

    def get_label(self, name):
        return get_label(name)

    def getWorkdays(self, sd, ed, prj_id):
        result = Calendar.getProjectWorkdays(
            with_prj_ids=[prj_id], start_date=sd, end_date=ed
        )
        return [x[0] for x in result[prj_id]]

    def getLastWorkdayIndex(self, my_workdays, date):
        for i in range(len(my_workdays)):
            myday = my_workdays[i]
            if date == myday:
                return i
        return -1

    def render(self, context, **kwargs):
        self.request.charset = "utf-8"
        context.cdb_project_id = kwargs["cdb_project_id"]
        context.task_id = kwargs["task_id"]
        context.liste = []
        liste = []
        if "task_id" not in kwargs or "cdb_project_id" not in kwargs:
            return
        if kwargs["new_elems"] == "":
            return
        i = int(kwargs["new_elems"])
        if i <= 0:
            return

        new_parent_task = Task.ByKeys(
            task_id=kwargs["task_id"], cdb_project_id=kwargs["cdb_project_id"]
        )
        if not new_parent_task.CheckAccess("write"):
            return
        project_id = new_parent_task.cdb_project_id
        startdate = new_parent_task.start_time_fcast
        enddate = new_parent_task.end_time_fcast
        project = Project.ByKeys(project_id)
        cal_id = project.calendar_profile_id

        min_sd_index = Calendar.getIndexByDate(cal_id, startdate)[0]
        max_ed_index = Calendar.getIndexByDate(cal_id, enddate)[0]
        total_days = max_ed_index - min_sd_index + 1
        average_days_per_task = total_days / i
        rest_days = total_days % i
        sd_index = min_sd_index
        count = 1
        task_values = []
        while total_days > 0:
            days = average_days_per_task + rest_days
            total_days -= days
            rest_days -= rest_days
            ed_index = sd_index + days - 1
            task_sd = to_legacy_str(Calendar.getDateByIndex(cal_id, sd_index))
            task_ed = to_legacy_str(Calendar.getDateByIndex(cal_id, ed_index))
            task_name = "%s_%s" % (new_parent_task.task_name, count)
            task_values.append((task_sd, task_ed, days, task_name))
            sd_index = ed_index + 1
            count += 1

        for my_task in task_values:
            new_task = {}
            new_task["start_time_fcast"] = my_task[0]
            new_task["end_time_fcast"] = my_task[1]
            new_task["task_name"] = my_task[3]

            context.liste.append(new_task)
            liste.append(new_task)


# lazy instantiation
app = None


def _getapp():
    global app
    if app is None:
        app = TaskBreakDownElinkAPP()
    return app


def handle_request(req):
    """Shortcut to the app"""
    return _getapp().handle_request(req)
