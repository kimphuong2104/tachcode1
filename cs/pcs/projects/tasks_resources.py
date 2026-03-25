#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable-msg=E0213,E1103,E0102,E0203,W0212,W0621,W0201

"""
Utilities only used in `cs.resources`;
Will be moved there in the next synchronized release.
"""

import logging

from cdb import sqlapi
from cdb.classbody import classbody

from cs.pcs.projects import Project, calendar
from cs.pcs.projects.common import format_in_condition
from cs.pcs.projects.tasks import Task


@classbody
class Task:
    def acceptAllocation(self):
        # Check the deadlines
        # Work together with autoSetDemandTime/autoSetAssignementTime
        # Other checks would be found in Demand/Assignment classes
        return self.start_time_fcast and self.end_time_fcast

    def autoSetDemandTime(self, ctx=None):  # TODO: DEPRECATED
        # Set missing DemandTimeStart/DemandTimeEnd automatically
        # Fieldnames must be changed if getDemand...TimeFieldName() changed
        pass

    def autoSetAssignmentTime(self, ctx=None):  # TODO: DEPRECATED
        # Set missing AssignmentTimeStart/AssignmentTimeEnd automatically
        # Fieldnames must be changed if getAssignment...TimeFieldName() changed
        pass

    @classmethod
    def clsCheckResourceStatusSignals(cls, obj, ctx=None):
        # Check effort status after calendar changes
        # work_uncovered => red
        if obj and Task.isFinalStatus(obj["status"]) and obj["work_uncovered"] == 1:
            return 3
        else:
            return 0

    @classmethod
    def updateResourceStatusSignals(cls, tasks):
        """
        batch version of clsCheckResourceStatusSignals
        that immediately updates tasks where effort status is 3
        """
        uuid_condition = format_in_condition(
            "cdb_object_id", [x.cdb_object_id for x in tasks]
        )
        final_statuses = ", ".join(
            [f"{status}" for status in cls.endStatus(full_cls=False)]
        )

        sqlapi.SQLupdate(
            f"""cdbpcs_task
            SET status_effort_fcast = 3
            WHERE ({uuid_condition})
                AND work_uncovered = 1
                AND status IN ({final_statuses})
        """
        )

    # === new class methods to optimize the calendar logic ===
    @classmethod
    def adjustCalenderChanges(cls, current_task, day_from, day_until):
        # pylint: disable=too-many-locals
        cdb_project_id = current_task["cdb_project_id"]
        task_id = current_task["task_id"]
        ce_baseline_id = current_task["ce_baseline_id"]
        changes = {}

        # adjust all sub tasks
        sql_from = sqlapi.SQLdbms_date(day_from)
        sql_until = sqlapi.SQLdbms_date(day_until)
        cond = (
            f"cdb_project_id = '{sqlapi.quote(cdb_project_id)}'"
            f" AND ce_baseline_id = '{sqlapi.quote(ce_baseline_id)}'"
            " AND ("
            f"(end_time_fcast IS NOT NULL AND {sql_from} <= end_time_fcast) OR "
            f"(end_time_fcast IS NULL AND {sql_from} <= end_time_plan)"
            ") AND ("
            f"(start_time_fcast IS NOT NULL AND start_time_fcast <= {sql_until}) OR "
            f"(start_time_fcast IS NULL AND start_time_plan <= {sql_until})"
            f") AND parent_task = '{sqlapi.quote(task_id)}'"
        )
        chg_sub_tasks = sqlapi.RecordSet2(Task.GetTableName(), cond)
        for task in chg_sub_tasks:
            Task.adjustCalenderChanges(task, day_from, day_until)

        # TODO: also need to be called: TimeStatusSignals()?
        #       or save all the calls bcz. no date changes would be done
        status_list = [
            Task.NEW.status,
            Task.READY.status,
            Task.EXECUTION.status,
            Task.FINISHED.status,
        ]
        cond = (
            f"cdb_project_id = '{sqlapi.quote(cdb_project_id)}'"
            f" AND parent_task = '{sqlapi.quote(task_id)}'"
            f" AND ce_baseline_id = '{sqlapi.quote(ce_baseline_id)}'"
        )
        subs = sqlapi.RecordSet2(Task.GetTableName(), cond)
        if subs and current_task.status in status_list:
            stp = None
            etp = None
            try:
                # only existing dates of sub tasks will be aggregated
                start_dates = []
                end_dates = []
                for t in subs:
                    if t.start_time_fcast:
                        start_dates.append(t.start_time_fcast)
                    elif t.start_time_plan:
                        start_dates.append(t.start_time_plan)
                    if t.end_time_fcast:
                        end_dates.append(t.end_time_fcast)
                    elif t.end_time_plan:
                        end_dates.append(t.end_time_plan)
                stp = min(start_dates)
                etp = max(end_dates)
            except Exception as exc:
                print(exc)

            # only recalculate dates if changes occur
            if current_task.start_time_plan != stp or current_task.end_time_plan != etp:
                changes["start_time_plan"] = stp if stp else ""
                changes["end_time_plan"] = etp if etp else ""

        # always recalculate dates, because calendar changes
        # could effect duration and workdays
        changed_task = dict(current_task)
        changed_task.update(changes)
        workdays = cls.clsGetWorkdays(changed_task)
        changes["days"] = workdays
        changed_task.update(changes)

        # test if task is not covered
        changes["work_uncovered"] = cls.isWorkUncovered(current_task, changed_task)

        # check effort status:
        changes["status"] = current_task.status
        effort_status = Task.clsCheckResourceStatusSignals(changes)
        if effort_status:
            changes["status_effort_fcast"] = effort_status
        if changes:
            current_task.update(**changes)

    @classmethod
    def isWorkUncovered(cls, current_task, changed_task):
        return 0

    @classmethod
    def clsGetWorkdays(cls, task, persno=None):
        try:
            if task["milestone"]:
                return 0
            start_date = task["start_time_fcast"]
            end_date = task["end_time_fcast"]
            if start_date and end_date:
                p = Project.ByKeys(cdb_project_id=task["cdb_project_id"])
                return calendar.combined_workday_count(
                    start_date=start_date, end_date=end_date, prj=p, persno=persno
                )
            else:
                return 0
        except Exception:
            logging.exception("Workdays invalid")
            return 0
