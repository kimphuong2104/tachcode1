#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sig, sqlapi
from cdb.classbody import classbody
from cdb.objects import Reference_N
from cdb.objects.org import Person
from cs.calendar import CalendarException, CalendarProfile

from cs.pcs.projects import Project, calendar
from cs.pcs.projects.tasks import Task
from cs.pcs.scheduling import calendar as calendar_scheduling


@classbody
class CalendarProfile:

    Projects = Reference_N(
        Project, Project.calendar_profile_id == CalendarProfile.cdb_object_id
    )

    Resources = Reference_N(
        Person,
        Person.calendar_profile_id == CalendarProfile.cdb_object_id,
        Person.is_resource == 1,
    )

    @classmethod
    def get_by_name(cls, name):
        """
        Returns the calendar profile by name, if name exists and name is unique
        :return: cs.calendar.CalendarProfile
        """
        calendar_profiles = cls.KeywordQuery(name=name)
        if len(calendar_profiles) == 1:
            return calendar_profiles[0]
        return None


@classbody
class CalendarException:
    @sig.connect(CalendarException, "create", "post")
    @sig.connect(CalendarException, "copy", "post")
    @sig.connect(CalendarException, "modify", "post")
    @sig.connect(CalendarException, "delete", "post")
    @sig.connect(CalendarException, "cpe_adjust_tasks")
    def adjust_affected_tasks(self, ctx=None, **args):
        """
        Adjusts start and end dates and duration of tasks affected by the calendar profile exception.
        Reschedules affected projects.
        Submits the `prepareTaskAdjustments` signal with the calendar profile exception to
        enable enhancements (e.g. cs.resources) or customizing

        Calendar profile exception can be a single day or a time period.
        In the case of a single day, the start and end of the calendar profile exception
        do have the same value.
        The following condition finds all affected tasks:
        `task.start_date <= exception end date AND task.end_date >= exception start date`

        calendar_profile_id=None, start_day=None, end_day=None
        :param ctx: operation context
        :param args: master data of a calendar exception's time period
            - calendar_profile_id
            - start_day
            - end_day
        :return: None
        """

        # In case of a single day, start and end date are taken from the instance itself
        # In case of a time period, start and end date are passed by the signal `cpe_adjust_tasks`
        # In case of a single day, `end_day` gets the same value as the exceptions start date
        cpe_master_data = {}
        cpe_master_data["cal_exc_start"] = args.get("day", getattr(self, "day", None))
        cpe_master_data["cal_exc_end"] = args.get(
            "end_day", cpe_master_data.get("cal_exc_start", None)
        )
        cpe_master_data["cal_profile_id"] = args.get(
            "calendar_profile_id", getattr(self, "calendar_profile_id", None)
        )

        # calendar caches have to be cleared for reload within scheduling
        calendar.clearCalendarIndex(cpe_master_data["cal_profile_id"])

        sig.emit(CalendarException, "prepareTaskAdjustments")(self, **cpe_master_data)

        sql_base_condition = self.get_sql_where_condition_for_tasks(**cpe_master_data)

        # manual tasks will not be changed by planning, let's adjust them first
        self.adjust_manual_tasks(sql_base_condition)
        self.adjust_forecast_tasks(sql_base_condition)

        # rescheduling of affected projects
        sql = f"SELECT DISTINCT cdb_project_id FROM cdbpcs_task WHERE {sql_base_condition}"
        records = sqlapi.RecordSet2(sql=sql)
        calendar_scheduling.get_calendar_exceptions.cache_clear()
        for project in records:
            Project.adjustCalenderChanges(
                project.cdb_project_id,
                cpe_master_data["cal_exc_start"],
                cpe_master_data["cal_exc_end"],
            )

    @staticmethod
    def adjust_manual_tasks(sql_base_condition):
        """
        Adjust all manual tasks, given based on the passed sql base condition

        :param sql_base_condition: sql condition to get all tasks
               that are affected by the calendar profile exception
        :return: None
        """
        sql_condition = f"{sql_base_condition} AND automatic = 0"
        for task in Task.Query(sql_condition):
            task.setTimeframe(start=task.start_time_fcast, days=task.days_fcast)

    @staticmethod
    def adjust_forecast_tasks(sql_base_condition):
        """
        Adjust all forecast tasks,
        given based on the passed sql base condition

        :param sql_base_condition: sql condition to get all tasks
               that are affected by the calendar profile exception
        :return: None
        """
        sql_condition = f"{sql_base_condition} AND auto_update_time IN (0, 2)"
        for task in Task.Query(sql_condition):
            task.change_start_time_plan()

    @staticmethod
    def get_sql_where_condition_for_tasks(**args):
        """
        Constructs the where condition to find all tasks that are affected by the passed time period
        """
        cal_oid = sqlapi.quote(args.get("cal_profile_id", None))
        cal_exc_start = sqlapi.SQLdbms_date(args.get("cal_exc_start", None))
        cal_exc_end = sqlapi.SQLdbms_date(args.get("cal_exc_end", None))
        return (
            "cdb_project_id IN ("
            "SELECT cdb_project_id"
            " FROM cdbpcs_project"
            " WHERE calendar_profile_id = '{cal}'"
            ") AND ("
            "(cdbpcs_task.end_time_fcast IS NOT NULL AND"
            " cdbpcs_task.end_time_fcast >= {cal_exc_start})"
            " OR "
            "(cdbpcs_task.end_time_plan IS NOT NULL AND"
            " cdbpcs_task.end_time_plan >= {cal_exc_start})"
            " OR "
            "(cdbpcs_task.end_time_act IS NOT NULL AND"
            " cdbpcs_task.end_time_act >= {cal_exc_start})"
            ") AND ("
            "(cdbpcs_task.start_time_fcast IS NOT NULL AND"
            " cdbpcs_task.start_time_fcast <= {cal_exc_end})"
            " OR "
            "(cdbpcs_task.start_time_plan IS NOT NULL AND"
            " cdbpcs_task.start_time_plan <= {cal_exc_end})"
            " OR "
            "(cdbpcs_task.start_time_act IS NOT NULL AND"
            " cdbpcs_task.start_time_act <= {cal_exc_end})"
            ")"
            " AND ce_baseline_id = ''"
        ).format(cal=cal_oid, cal_exc_start=cal_exc_start, cal_exc_end=cal_exc_end)
