#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import sys
import traceback

from cdb import ddl, sqlapi
from cdb.comparch import protocol


class CheckDatabase(object):
    def run(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
            raise RuntimeError(
                "SQLite databases can not be updated due to changes on primary keys. Please recreate database."
            )


class PrepareResourceTable(object):
    """Prepare table cdbpcs_res_schedule for updates."""

    def run(self):
        if (
            sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE
            or sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL
        ):
            sqlapi.SQLupdate(
                "cdbpcs_res_schedule SET cdb_demand_id = '' WHERE cdb_demand_id IS NULL"
            )
            sqlapi.SQLupdate(
                "cdbpcs_res_schedule SET cdb_alloc_id = '' WHERE cdb_alloc_id IS NULL"
            )
        elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            sqlapi.SQLupdate(
                "cdbpcs_res_schedule SET cdb_demand_id = chr(1) WHERE cdb_demand_id IS NULL"
            )
            sqlapi.SQLupdate(
                "cdbpcs_res_schedule SET cdb_alloc_id = chr(1) WHERE cdb_alloc_id IS NULL"
            )


class MoveReports(object):
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
                "cdbxml_dataprovider SET source = '%s' WHERE source = '%s'"
                % (new_value, old_value)
            )


class MoveMTAUpdateClockCatalog(object):
    """Changing the fully qualified python name for MTAUpdateClockCatalog went wrong during update"""

    def run(self):
        upd = """browsers SET fqpyname = 'cs.pcs.projects.reports.MTAUpdateClockCatalog'
                           WHERE katalog = 'cdbpcs_mta_update_clock_browser'
                           AND fqpyname = 'cs.pcs.resources.reports.MTAUpdateClockCatalog'"""
        sqlapi.SQLupdate(upd)


class CreateWorkdaysView(object):
    """Creating view cdb_workdays_v and add column workdays to tables
    cdbpcs_prj_demand and cdbpcs_prj_alloc, because we need them for updates."""

    def run(self):

        if ddl.View("cdb_workdays_v").exists():
            protocol.logMessage("View cdb_workdays_v exists. Nothing to do.")
            return

        try:
            if (
                sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE
                or sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL
            ):
                sql = """CREATE VIEW cdb_workdays_v AS
                                SELECT calendar_profile_id, day, personalnummer
                                FROM cdb_calendar_entry
                                WHERE day_type_id=1 AND personalnummer IS NULL
                                UNION
                                SELECT '', day, personalnummer
                                FROM cdb_person_calendar_v
                                WHERE day_off=0
                      """
                sqlapi.SQL(sql)
            elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                sql = """CREATE VIEW cdb_workdays_v AS
                                SELECT calendar_profile_id, day, personalnummer
                                FROM cdb_calendar_entry
                                WHERE day_type_id=1 AND personalnummer IS NULL
                                UNION
                                SELECT chr(1), day, personalnummer
                                FROM cdb_person_calendar_v
                                WHERE day_off=0
                      """
                sqlapi.SQL(sql)
        except Exception as ex:  # pylint: disable=W0703
            protocol.logError(
                "New view cdb_workdays_v has not been created by update:\n%s" % ex
            )


class AdjustDemandTable(object):
    """Setting values for some new fields within the table cdbpcs_prj_demand."""

    def run(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
            protocol.logWarning(
                "New fields of table cdbpcs_prj_demand have not been updated."
            )
        elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            upd = """cdbpcs_prj_demand SET cdbpcs_prj_demand.org_id = angestellter.org_id
                      FROM cdbpcs_prj_demand INNER JOIN angestellter
                      ON cdbpcs_prj_demand.subject_id = angestellter.personalnummer
                  """
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_prj_demand SET cdbpcs_prj_demand.workdays = (SELECT COUNT(*) FROM cdb_workdays_v
                                                                          WHERE day >= cdbpcs_task.start_time_fcast
                                                                          AND day <= cdbpcs_task.end_time_fcast
                                                                          AND
                                                                          personalnummer = cdbpcs_prj_demand.subject_id)
                      FROM cdbpcs_prj_demand INNER JOIN cdbpcs_task
                      ON cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id
                      AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id
                      AND '' = cdbpcs_task.ce_baseline_id
                   """
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_prj_demand SET cdbpcs_prj_demand.workdays = cdbpcs_task.days_fcast
                      FROM cdbpcs_prj_demand INNER JOIN cdbpcs_task
                      ON cdbpcs_prj_demand.cdb_project_id = cdbpcs_task.cdb_project_id
                      AND cdbpcs_prj_demand.task_id = cdbpcs_task.task_id
                      AND '' = cdbpcs_task.ce_baseline_id
                      WHERE cdbpcs_prj_demand.workdays = 0
                   """
            sqlapi.SQLupdate(upd)
        elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            upd = """(SELECT d.subject_id, p.personalnummer, d.org_id AS org_id1, p.org_id AS org_id2
                       FROM cdbpcs_prj_demand d INNER JOIN angestellter p
                       ON d.subject_id = p.personalnummer) x
                       SET x.org_id1 = x.org_id2
                      """
            sqlapi.SQLupdate(upd)
            upd = """(SELECT d.cdb_project_id, d.task_id, d.subject_id, d.workdays, t.days_fcast, t.start_time_fcast,
            t.end_time_fcast
                       FROM cdbpcs_prj_demand d INNER JOIN cdbpcs_task t
                       ON d.cdb_project_id = t.cdb_project_id AND d.task_id = t.task_id
                       AND '' = t.ce_baseline_id
                   ) x
                       SET x.workdays = (SELECT COUNT(*) FROM cdb_workdays_v WHERE day >= x.start_time_fcast
                       AND day <= x.end_time_fcast AND personalnummer = x.subject_id)
                      """
            sqlapi.SQLupdate(upd)
            upd = """(SELECT d.cdb_project_id, d.task_id, d.workdays, t.days_fcast
                       FROM cdbpcs_prj_demand d INNER JOIN cdbpcs_task t
                       ON d.cdb_project_id = t.cdb_project_id AND d.task_id = t.task_id
                       AND '' = t.ce_baseline_id
                   ) x
                       SET x.workdays = x.days_fcast
                       WHERE x.workdays = 0
                      """
            sqlapi.SQLupdate(upd)


class AdjustAssignmentTable(object):
    """Setting values for some new fields within the table cdbpcs_prj_alloc."""

    def run(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
            protocol.logWarning(
                "New fields of table cdbpcs_prj_alloc have not been updated."
            )
        elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            upd = """cdbpcs_prj_alloc SET cdbpcs_prj_alloc.org_id = angestellter.org_id
                      FROM cdbpcs_prj_alloc INNER JOIN angestellter
                      ON cdbpcs_prj_alloc.persno = angestellter.personalnummer
                   """
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_prj_alloc SET cdbpcs_prj_alloc.workdays = (SELECT COUNT(*) FROM cdb_workdays_v
                                                                        WHERE day >= cdbpcs_task.start_time_fcast
                                                                        AND day <= cdbpcs_task.end_time_fcast
                                                                        AND personalnummer = cdbpcs_prj_alloc.persno)
                      FROM cdbpcs_prj_alloc INNER JOIN cdbpcs_task
                      ON cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id
                      AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id
                      AND '' = cdbpcs_task.ce_baseline_id
                   """
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_prj_alloc SET cdbpcs_prj_alloc.workdays = cdbpcs_task.days_fcast
                      FROM cdbpcs_prj_alloc INNER JOIN cdbpcs_task
                      ON cdbpcs_prj_alloc.cdb_project_id = cdbpcs_task.cdb_project_id
                      AND cdbpcs_prj_alloc.task_id = cdbpcs_task.task_id
                      AND '' = cdbpcs_task.ce_baseline_id
                      WHERE cdbpcs_prj_alloc.workdays = 0
                   """
            sqlapi.SQLupdate(upd)
        elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            upd = """(SELECT a.persno, p.personalnummer, a.org_id AS org_id1, p.org_id AS org_id2
                       FROM cdbpcs_prj_alloc a INNER JOIN angestellter p
                       ON a.persno = p.personalnummer) x
                       SET x.org_id1 = x.org_id2
                      """
            sqlapi.SQLupdate(upd)
            upd = """(SELECT a.cdb_project_id, a.task_id, a.persno, a.workdays, t.days_fcast, t.start_time_fcast,
            t.end_time_fcast
                       FROM cdbpcs_prj_alloc a INNER JOIN cdbpcs_task t
                       ON a.cdb_project_id = t.cdb_project_id AND a.task_id = t.task_id
                       AND '' = t.ce_baseline_id
                   ) x
                       SET x.workdays = (SELECT COUNT(*) FROM cdb_workdays_v WHERE day >= x.start_time_fcast
                       AND day <= x.end_time_fcast AND personalnummer = x.persno)
                      """
            sqlapi.SQLupdate(upd)
            upd = """(SELECT a.cdb_project_id, a.task_id, a.workdays, t.days_fcast
                       FROM cdbpcs_prj_alloc a INNER JOIN cdbpcs_task t
                       ON a.cdb_project_id = t.cdb_project_id AND a.task_id = t.task_id
                       AND '' = t.ce_baseline_id
                   ) x
                       SET x.workdays = x.days_fcast
                       WHERE x.workdays = 0
                      """
            sqlapi.SQLupdate(upd)


class ModifySchemaOfResourceTable(object):
    """
    Set cdbpcs_res_schedule.cdb_object_id to NOT NULL
    """

    # noinspection PyBroadException
    def run(self):
        try:
            if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
                sqlapi.SQL("ALTER TABLE cdbpcs_res_schedule DROP COLUMN cdb_object_id")
            elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_res_schedule ALTER COLUMN cdb_object_id NVARCHAR(40) NULL"
                )
            elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                sqlapi.SQL(
                    "ALTER TABLE cdbpcs_res_schedule MODIFY cdb_object_id VARCHAR2(40) DEFAULT '' NULL"
                )
        except:  # noqa # pylint: disable=W0702
            msg = "".join(traceback.format_exception(*sys.exc_info()))
            protocol.logWarning(
                "Attribute 'cdbpcs_res_schedule.cdb_object_id' could not be set to "
                "nullable. Make sure that the attribute  does not exist or is "
                "set to nullable.",
                details_longtext=msg,
            )


class AdjustResourceTable(object):
    """Setting values for some new fields within the table cdbpcs_res_schedule."""

    def run(self):
        if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
            protocol.logWarning(
                "Values for new fields within table cdbpcs_res_schedule have not been set."
            )
        elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            upd = (
                "cdbpcs_res_schedule SET cdb_demand_id = '' WHERE cdb_demand_id IS NULL"
            )
            sqlapi.SQLupdate(upd)
            upd = "cdbpcs_res_schedule SET cdb_alloc_id = '' WHERE cdb_alloc_id IS NULL"
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_res_schedule
                      SET cdbpcs_res_schedule.personalnummer = cdbpcs_prj_demand.subject_id,
                          cdbpcs_res_schedule.org_id = cdbpcs_prj_demand.org_id,
                          cdbpcs_res_schedule.resource_type = cdbpcs_prj_demand.resource_type,
                          cdbpcs_res_schedule.d_value = CASE WHEN cdbpcs_prj_demand.workdays > 0
                                      AND  (cdbpcs_prj_demand.hours - cdbpcs_prj_demand.hours_assigned) /
                                      cdbpcs_prj_demand.workdays > 0
                                      THEN (cdbpcs_prj_demand.hours - cdbpcs_prj_demand.hours_assigned) /
                                      cdbpcs_prj_demand.workdays
                                      ELSE 0 END
                      FROM cdbpcs_res_schedule INNER JOIN cdbpcs_prj_demand
                      ON cdbpcs_res_schedule.cdb_project_id = cdbpcs_prj_demand.cdb_project_id
                      AND cdbpcs_res_schedule.task_id = cdbpcs_prj_demand.task_id
                      AND cdbpcs_res_schedule.cdb_demand_id = cdbpcs_prj_demand.cdb_demand_id
                   """
            sqlapi.SQLupdate(upd)
            upd = """cdbpcs_res_schedule
                      SET cdbpcs_res_schedule.personalnummer = cdbpcs_prj_alloc.persno,
                          cdbpcs_res_schedule.org_id = cdbpcs_prj_alloc.org_id,
                          cdbpcs_res_schedule.resource_type = 'manpower',
                          cdbpcs_res_schedule.a_value = CASE WHEN cdbpcs_prj_alloc.workdays > 0
                                      AND  cdbpcs_prj_alloc.hours / cdbpcs_prj_alloc.workdays > 0
                                      THEN cdbpcs_prj_alloc.hours / cdbpcs_prj_alloc.workdays
                                      ELSE 0 END
                      FROM cdbpcs_res_schedule INNER JOIN cdbpcs_prj_alloc
                      ON cdbpcs_res_schedule.cdb_project_id = cdbpcs_prj_alloc.cdb_project_id
                      AND cdbpcs_res_schedule.task_id = cdbpcs_prj_alloc.task_id
                      AND cdbpcs_res_schedule.cdb_alloc_id = cdbpcs_prj_alloc.cdb_alloc_id
                   """
            sqlapi.SQLupdate(upd)
        elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            upd = "cdbpcs_res_schedule SET cdb_demand_id = chr(1) WHERE cdb_demand_id IS NULL"
            sqlapi.SQLupdate(upd)
            upd = "cdbpcs_res_schedule SET cdb_alloc_id = chr(1) WHERE cdb_alloc_id IS NULL"
            sqlapi.SQLupdate(upd)
            upd = """(SELECT s.cdb_project_id, s.task_id, s.cdb_demand_id,
                        s.org_id AS org_id1,
                        d.org_id AS org_id2,
                        s.resource_type AS resource_type1,
                        d.resource_type AS resource_type2,
                        s.personalnummer,
                        d.subject_id,
                        s.d_value,
                        d.hours,
                        d.hours_assigned,
                        d.workdays
                        FROM cdbpcs_res_schedule s INNER JOIN cdbpcs_prj_demand d
                      ON s.cdb_project_id = d.cdb_project_id
                      AND s.task_id = d.task_id
                      AND s.cdb_demand_id = d.cdb_demand_id) x
                      SET x.personalnummer = x.subject_id,
                          x.org_id1 = x.org_id2,
                          x.resource_type1 = x.resource_type2,
                          x.d_value = CASE WHEN x.workdays > 0
                                      AND  (x.hours - x.hours_assigned) / x.workdays > 0
                                      THEN (x.hours - x.hours_assigned) / x.workdays
                                      ELSE 0 END
                      """
            sqlapi.SQLupdate(upd)
            upd = """(SELECT s.cdb_project_id, s.task_id, s.cdb_alloc_id,
                        s.org_id AS org_id1,
                        a.org_id AS org_id2,
                        s.resource_type,
                        s.personalnummer,
                        a.persno,
                        s.a_value,
                        a.hours,
                        a.workdays
                        FROM cdbpcs_res_schedule s INNER JOIN cdbpcs_prj_alloc a
                      ON s.cdb_project_id = a.cdb_project_id
                      AND s.task_id = a.task_id
                      AND s.cdb_alloc_id = a.cdb_alloc_id) x
                      SET x.personalnummer = x.persno,
                          x.org_id1 = x.org_id2,
                          x.resource_type = 'manpower',
                          x.a_value = CASE WHEN x.workdays > 0
                                      AND  x.hours / x.workdays > 0
                                      THEN x.hours / x.workdays
                                      ELSE 0 END
                      """
            sqlapi.SQLupdate(upd)


pre = [CheckDatabase, PrepareResourceTable, CreateWorkdaysView]
post = [
    MoveReports,
    MoveMTAUpdateClockCatalog,
    ModifySchemaOfResourceTable,
    AdjustDemandTable,
    AdjustAssignmentTable,
    AdjustResourceTable,
]
