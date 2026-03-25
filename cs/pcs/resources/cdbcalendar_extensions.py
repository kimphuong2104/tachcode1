#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sig, sqlapi
from cdb.classbody import classbody
from cdb.objects import Forward
from cs.calendar import CalendarEntry, CalendarException  # pylint: disable=W0611
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import adjustDurations
from cs.pcs.resources.helpers import date_from_legacy_str
from cs.pcs.resources.pools.assignments import ResourcePoolAssignment

fResource = Forward("cs.pcs.resources.pools.assignments.Resource")
fPerson = Forward("cdb.objects.org.Person")


@classbody
class CalendarEntry(object):
    def _adjustResourceDurations(self, ctx):
        if self.personalnummer:
            if "old_day" in ctx.ue_args.get_attribute_names():
                old_day = date_from_legacy_str(ctx.ue_args["old_day"])
            else:
                old_day = None
            adjustDurations(self.personalnummer, self.day, self.day)
            if old_day:
                adjustDurations(self.personalnummer, old_day, old_day)

    def _signal_checkResourcesBySelf(self, ctx):
        p = fPerson.ByKeys(self.personalnummer)
        assignments = p.ResourceMember
        old_day = None
        if "old_day" in ctx.ue_args.get_attribute_names():
            old_day = date_from_legacy_str(ctx.ue_args["old_day"])
        if p:
            assigns = [
                x
                for x in assignments
                if (
                    (not x.start_date or x.start_date <= self.day)
                    and (not x.end_date or self.day <= x.end_date)
                )
            ]
            if old_day:
                assigns += [
                    x
                    for x in assignments
                    if (
                        (not x.start_date or x.start_date <= old_day)
                        and (not x.end_date or old_day <= x.end_date)
                    )
                ]
            # just update schedules in a very specific timeframe
            day = self.day

            if old_day is None:
                start, end = day, day
            else:
                start = min(old_day, day)
                end = max(old_day, day)

            ResourcePoolAssignment.createSchedules_many(assigns, start, end)

    @classmethod
    def _checkResourcesBySelf(cls, ctx):
        persno = ctx.dialog.personalnummer
        sd = date_from_legacy_str(ctx.dialog.day_from)
        ed = date_from_legacy_str(ctx.dialog.day_until)
        p = fPerson.ByKeys(persno)
        assignments = p.ResourceMember
        old_day = None
        if "old_day" in ctx.ue_args.get_attribute_names():
            old_day = date_from_legacy_str(ctx.ue_args["old_day"])
        if p:
            assigns = [
                x
                for x in assignments
                if (
                    (not x.start_date or x.start_date <= sd)
                    and (not x.end_date or ed <= x.end_date)
                )
            ]
            if old_day:
                assigns += [
                    x
                    for x in assignments
                    if (
                        (not x.start_date or x.start_date <= old_day)
                        and (not x.end_date or old_day <= x.end_date)
                    )
                ]
            ResourcePoolAssignment.createSchedules_many(assigns)

    @classmethod
    def _adjustResourceDurationAfterMultiNew(cls, ctx):
        if ctx.dialog.personalnummer:
            adjustDurations(
                ctx.dialog.personalnummer, ctx.dialog.day_from, ctx.dialog.day_until
            )

    event_map = {
        (("copy", "modify", "delete"), ("post")): (
            "_signal_checkResourcesBySelf",
            "_adjustResourceDurations",
        ),
        (("cdb_cal_entry_multi_new"), "post"): (
            "_checkResourcesBySelf",
            "_adjustResourceDurationAfterMultiNew",
        ),
    }


@classbody
class CalendarException(object):
    @sig.connect(CalendarException, "create", "post")
    @sig.connect(CalendarException, "copy", "post")
    @sig.connect(CalendarException, "modify", "post")
    @sig.connect(CalendarException, "delete", "post")
    @sig.connect(CalendarException, "cpe_adjust_tasks")
    def adjustCalendarChangesForTasks(self, ctx=None, **args):
        # calendar changes only for demands and assignments to persons
        # with fitting calendar profile:
        # (changes for projects with fitting profile will be done in other module)
        day = args.get("day", getattr(self, "day", None))
        cpe_master_data = {
            "cal_exc_start": day,
            "cal_exc_end": args.get("end_day", day),
            "cal_profile_id": args.get("calendar_profile_id", getattr(self, "calendar_profile_id", None)),
        }

        sig.emit(CalendarException, "prepareTaskAdjustments")(self, **cpe_master_data)

        sql_base_condition = self.get_sql_where_condition(**cpe_master_data)

        records = sqlapi.RecordSet2("cdbpcs_task", sql_base_condition)
        for task in records:
            Task.adjustCalenderChanges(task, cpe_master_data["cal_exc_start"], cpe_master_data["cal_exc_end"])

    @staticmethod
    def get_sql_where_condition(**args):
        cal_oid = sqlapi.quote(args.get("cal_profile_id", None))
        cal_exc_start = sqlapi.SQLdbms_date(args.get("cal_exc_start", None))
        cal_exc_end = sqlapi.SQLdbms_date(args.get("cal_exc_end", None))

        perssql = (
            f"SELECT r.referenced_oid"
            f" FROM {f'{fResource.GetTableName()}_v'} r"
            f" WHERE r.calendar_profile_id='{cal_oid}'"  # getTableName -> cdbpcs_resource
        )

        # task ids of all demands where resource with that calendar profile is demanded
        demands = (
            f"SELECT d.task_id"
            f" FROM cdbpcs_prj_demand d"
            f" WHERE d.resource_oid in ({perssql})"
            f" AND d.cdb_project_id=cdbpcs_task.cdb_project_id")

        # task ids of all allocations where resource with that calendar profile has been allocated
        allocations = (
            f"SELECT a.task_id"
            f" FROM cdbpcs_prj_alloc a"
            f" WHERE a.resource_oid in ({perssql})"
            f" AND a.cdb_project_id=cdbpcs_task.cdb_project_id")

        # all projects with the calendar profile
        projects = (
            f"SELECT p.cdb_project_id "
            f" FROM cdbpcs_project p "
            f" WHERE p.calendar_profile_id = '{cal_oid}'")

        return (
            f" cdbpcs_task.ce_baseline_id = ''"
            f" AND cdbpcs_task.cdb_project_id NOT IN ({projects})"
            f" AND (cdbpcs_task.task_id IN ({demands})"
            f"     OR cdbpcs_task.task_id IN ({allocations}))"
            f" AND ((cdbpcs_task.end_time_fcast is not null and "
            f"      {cal_exc_end}<=cdbpcs_task.end_time_fcast))"
            f" AND ((cdbpcs_task.start_time_fcast is not null and "
            f"      cdbpcs_task.start_time_fcast<={cal_exc_start}))"
        )
