#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import dberrors, ddl, sqlapi, util
from cdb.comparch import protocol


class DataMigrations:
    def run(self):
        self.update_taskrelations()
        self.update_tasks()
        self.update_projects()
        self.change_primary_key()

    def change_primary_key(self):
        table = ddl.Table("cdbpcs_taskrel")
        primary_key = ddl.PrimaryKey(
            "cdb_project_id", "task_id", "cdb_project_id2", "task_id2", "rel_type"
        )

        # First of all Check, whether primary_key is already correct
        if table and table.exists():
            ti = util.tables[table.name]
            if not primary_key.diffToDatabase(ti):
                return
        table.setPrimaryKey(primary_key)

    def update_taskrelations(self):
        sqlapi.SQLupdate("cdbpcs_taskrel SET cdb_project_id2 = cdb_project_id")
        sqlapi.SQLupdate(
            """cdbpcs_taskrel SET succ_project_oid = (SELECT cdb_object_id FROM cdbpcs_project
            WHERE cdbpcs_taskrel.cdb_project_id = cdbpcs_project.cdb_project_id)"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_taskrel SET pred_project_oid = (SELECT cdb_object_id FROM cdbpcs_project
                WHERE cdbpcs_taskrel.cdb_project_id2 = cdbpcs_project.cdb_project_id)"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_taskrel SET succ_task_oid = (SELECT cdb_object_id FROM cdbpcs_task
                WHERE cdbpcs_taskrel.cdb_project_id = cdbpcs_task.cdb_project_id
                AND cdbpcs_taskrel.task_id = cdbpcs_task.task_id)"""
        )
        sqlapi.SQLupdate(
            """cdbpcs_taskrel SET pred_task_oid = (SELECT cdb_object_id FROM cdbpcs_task WHERE
                cdbpcs_taskrel.cdb_project_id2 = cdbpcs_task.cdb_project_id
                AND cdbpcs_taskrel.task_id2 = cdbpcs_task.task_id)"""
        )
        sqlapi.SQLupdate(
            "cdbpcs_taskrel SET cross_project = 0 WHERE succ_project_oid = pred_project_oid"
        )
        sqlapi.SQLupdate(
            "cdbpcs_taskrel SET cross_project = 1 WHERE succ_project_oid != pred_project_oid"
        )
        # has to be done via powerscript now (cdbpcs_taskrel.gap has been removed in 15.8.0)
        # sqlapi.SQLupdate("cdbpcs_taskrel SET violation = 0")
        # sqlapi.SQLupdate("cdbpcs_taskrel SET violation = 1 WHERE gap < 0")

    def update_projects(self):
        cal_prof_id = sqlapi.RecordSet2(
            sql="SELECT cdb_object_id FROM cdb_calendar_profile WHERE name = 'Standard'"
        )[0]["cdb_object_id"]
        # pylint: disable-next=consider-using-f-string
        upd = """cdbpcs_project SET
                     days_fcast = 1+
                          (SELECT early_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_project.end_time_fcast = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL) -
                          (SELECT late_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_project.start_time_fcast = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL),
                     days = 1+
                          (SELECT early_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_project.end_time_plan = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL) -
                          (SELECT late_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_project.start_time_plan = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL)
                 """ % {
            "cal_prof_id": cal_prof_id
        }
        sqlapi.SQLupdate(upd)

    def update_tasks(self):
        cal_prof_id = sqlapi.RecordSet2(
            sql="SELECT cdb_object_id FROM cdb_calendar_profile WHERE name = 'Standard'"
        )[0]["cdb_object_id"]
        # pylint: disable-next=consider-using-f-string
        upd = """cdbpcs_task SET
                      days_fcast = 1+
                          (SELECT early_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_task.end_time_fcast = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL) -
                          (SELECT late_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_task.start_time_fcast = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL),
                      days = 1+
                          (SELECT early_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_task.end_time_plan = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL) -
                          (SELECT late_work_idx
                           FROM cdb_calendar_entry c
                           WHERE cdbpcs_task.start_time_plan = c.day
                           AND c.calendar_profile_id = '%(cal_prof_id)s'
                           AND c.personalnummer IS NULL AND c.cdb_project_id IS NULL)
                   WHERE milestone != 1
                """ % {
            "cal_prof_id": cal_prof_id
        }
        sqlapi.SQLupdate(upd)
        upd = "cdbpcs_task SET days = 0, days_fcast = 0 WHERE milestone = 1"
        sqlapi.SQLupdate(upd)
        upd = """cdbpcs_task SET early_start = start_time_fcast, late_start = start_time_fcast,
                 early_finish = end_time_fcast, late_finish = end_time_fcast,
                 total_float = 0, start_is_early = 1, end_is_early = 0"""
        sqlapi.SQLupdate(upd)


class DataMigrationsAdditional1:
    """Sets the is_group flag for all existing projects and early_position for all tasks"""

    def run(self):
        self.setProjectGroupFlag()
        self.setEarlyPosition()

    def setProjectGroupFlag(self):
        upd = """cdbpcs_project SET is_group = (SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END FROM cdbpcs_task
                                                WHERE cdbpcs_task.cdb_project_id = cdbpcs_project.cdb_project_id
                                                AND cdbpcs_task.ce_baseline_id = cdbpcs_project.ce_baseline_id)"""  # noqa
        sqlapi.SQLupdate(upd)

    def setEarlyPosition(self):
        for field in ["start_is_early", "end_is_early"]:
            upd = f"cdbpcs_task SET {field} = 0 WHERE {field} != 1"
            sqlapi.SQLupdate(upd)


class MoveReports:
    def run(self):
        data = (
            (
                "cs.pcs.resources.reports.ProjectMTA",
                "cs.pcs.projects.reports.ProjectMTA",
            ),
            (
                "cs.pcs.resources.reports.ProjectEvaluationProvider",
                "cs.pcs.projects.reports.ProjectEvaluationProvider",
            ),
            (
                "cs.pcs.resources.reports.QualityGates",
                "cs.pcs.checklists.reports.QualityGates",
            ),
            (
                "cs.pcs.resources.reports.QualityGatesItems",
                "cs.pcs.checklists.reports.QualityGatesItems",
            ),
            ("cs.pcs.resources.reports.TaskIssues", "cs.pcs.issues.reports.TaskIssues"),
            (
                "cs.pcs.resources.reports.ProjectIssues",
                "cs.pcs.issues.reports.ProjectIssues",
            ),
            (
                "cs.pcs.resources.reports.ProjectEfforts",
                "cs.pcs.efforts.reports.ProjectEfforts",
            ),
            (
                "cs.pcs.resources.reports.TaskEfforts",
                "cs.pcs.efforts.reports.TaskEfforts",
            ),
        )
        for old_value, new_value in data:
            sqlapi.SQLupdate(
                f"cdbxml_dataprovider SET source = '{new_value}' WHERE source = '{old_value}'"
            )


class CreateTimeSchedules:
    """Create Time Schedules for projects that are planned or still in progress"""

    def run(self):
        for r in sqlapi.RecordSet2(
            sql="SELECT cdb_project_id, project_name, cdb_cpersno FROM cdbpcs_project"
            " WHERE ce_baseline_id=''"
        ):
            i = util.DBInserter("cdbpcs_time_schedule")
            i.add("cdb_project_id", r["cdb_project_id"])
            i.add("name", r["project_name"])
            persno = r["cdb_cpersno"]
            if persno:
                i.add("subject_id", persno)
                i.add("subject_type", "Person")
                i.add("cdb_objektart", "cdbpcs_time_schedule")
            i.insert()

        for r in sqlapi.RecordSet2(
            sql="SELECT cdb_project_id, cdb_object_id FROM cdbpcs_time_schedule"
        ):
            i = util.DBInserter("cdbpcs_project2time_schedule")
            i.add("cdb_project_id", r["cdb_project_id"])
            i.add("time_schedule_oid", r["cdb_object_id"])
            try:
                i.insert()
            except Exception:
                logging.exception("insert failed")

        for r in sqlapi.RecordSet2(
            sql="""SELECT  p.cdb_project_id AS cdb_project_id,
                                                  p.cdb_object_id AS content_oid,
                                                  t.cdb_object_id AS view_oid
                                          FROM cdbpcs_time_schedule t, cdbpcs_project p
                                          WHERE p.cdb_project_id = t.cdb_project_id AND p.ce_baseline_id=''"""
        ):
            i = util.DBInserter("cdbpcs_ts_content")
            i.add("view_oid", r["view_oid"])
            i.add("position", 1)
            i.add("content_oid", r["content_oid"])
            i.add("cdb_project_id", r["cdb_project_id"])
            i.add("cdb_content_classname", "cdbpcs_project")
            try:
                i.insert()
            except Exception:
                logging.exception("insert failed")


class SetGroupFlag:
    """Setting the is_group flag for projects"""

    def run(self):
        upd1 = """cdbpcs_project SET is_group = 1 WHERE cdb_project_id
            IN (SELECT DISTINCT cdb_project_id FROM cdbpcs_task)"""
        upd2 = """cdbpcs_project SET is_group = 0 WHERE cdb_project_id NOT
            IN (SELECT DISTINCT cdb_project_id FROM cdbpcs_task)"""
        sqlapi.SQLupdate(upd1)
        sqlapi.SQLupdate(upd2)


class MoveMTAUpdateClockCatalog:
    """Changing the fully qualified python name for MTAUpdateClockCatalog went wrong during update"""

    def run(self):
        upd = """browsers SET fqpyname = 'cs.pcs.projects.reports.MTAUpdateClockCatalog'
                           WHERE katalog = 'cdbpcs_mta_update_clock_browser'
                           AND fqpyname = 'cs.pcs.resources.reports.MTAUpdateClockCatalog'"""
        sqlapi.SQLupdate(upd)


class DropViews:

    tbd_views = ["cdbpcs_sync_constraint_v"]

    def run(self):

        for tbd_view in self.tbd_views:

            stmt = f"table_name from cdb_tables where table_name = '{tbd_view}'"
            try:
                if sqlapi.SQLrows(sqlapi.SQLselect(stmt)) == 1:
                    sqlapi.SQL(f"drop view {tbd_view}")
            except dberrors.DBError:
                protocol.logWarning(
                    f"The view {tbd_view} could not be removed. "
                    "This is fine if the view does not exist."
                )


pre = [DataMigrations, DataMigrationsAdditional1]
post = [
    MoveReports,
    CreateTimeSchedules,
    SetGroupFlag,
    MoveMTAUpdateClockCatalog,
    DropViews,
]
