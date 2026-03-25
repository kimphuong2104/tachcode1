#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=consider-using-f-string, duplicate-code, too-many-lines

"""
(re-)create these allocation and demand schedules for given project or task:
    * daily
    * weekly
    * monthly
    * quarter-yearly
    * half-yearly

for performance reasons, this is based exclusively on SQL


DBMS-specific functions used in this script:

convert a date to string/varchar:
    sqlite: STRFTIME('%Y-%m-%d', date)
    oracle: TO_CHAR(date, 'dd.mm.YYYY')
    mssql:  FORMAT(date, 'dd.MM.yyyy') (>= 2012 only!)
    postgresql: TO_CHAR(date, 'dd-mm-YYYY')

convert a date into string/varchar:
    mssql >= 2012:  FORMAT
          <  2012:  CONVERT, LEFT, RIGHT, SUBSTRING

convert a string/varchar to date:
    sqlite: STRFTIME('%Y-%m-%d', date)
    oracle: TO_DATE(string, 'dd.mm.YYYY')
    mssql >= 2012:  PARSE(date AS DATE), CONVERT(DATE, date)
          <  2012:  CAST(date AS DATE), CONVERT(DATE, date)
    postgresql: TO_DATE(string, 'dd-mm-YYYY')
"""
import itertools

from cdb import sqlapi, transaction
from cdb.objects import Forward
from cs.pcs.resources import db_tools

fResourceSchedule = Forward("cs.pcs.resources.ResourceSchedule")
fResourceScheduleWeek = Forward("cs.pcs.resources.ResourceScheduleWeek")
fResourceScheduleMonth = Forward("cs.pcs.resources.ResourceScheduleMonth")
fResourceScheduleQuarter = Forward("cs.pcs.resources.ResourceScheduleQuarter")
fResourceScheduleHalfYear = Forward("cs.pcs.resources.ResourceScheduleHalfYear")

SCHEDULE_CALCULATOR = None
__CAST_AS_INTEGER__ = "CAST({} AS INTEGER)"


class ScheduleCalculator(object):
    __empty_string__ = "''"
    __first_weekday__ = None

    @classmethod
    def initForDB(cls, dbms):  # pylint: disable=R1710
        if dbms == sqlapi.DBMS_ORACLE:
            return ScheduleCalculatorOracle()
        if dbms == sqlapi.DBMS_SQLITE:
            return ScheduleCalculatorSqlite()
        if dbms == sqlapi.DBMS_MSSQL:
            return ScheduleCalculatorMsSQL()
        if dbms == sqlapi.DBMS_POSTGRES:
            return ScheduleCalculatorPostgres()

    def __init__(self):
        self.__class__.__all_schedule_tables__ = [
            fResourceSchedule.GetTableName(),
            fResourceScheduleWeek.GetTableName(),
            fResourceScheduleMonth.GetTableName(),
            fResourceScheduleQuarter.GetTableName(),
            fResourceScheduleHalfYear.GetTableName(),
        ]

    @classmethod
    def _date_format_literal(cls, day=True, month=True, year=True, is_sqlite=False):
        result = cls.__sql_date_format_separator__.join(
            itertools.compress(
                cls.__sql_date_format__,
                cls.__sql_date_format_mask__(day, month, year),
            )
        )
        if is_sqlite and day and month and year:
            result += "T%H:%M:%S"
        return result

    @classmethod
    def __sql_first_of_quarter__(cls, date_or_attr):
        return cls.__sql_str_to_date__(
            cls.__sql_first_of_quarter_template__.format(
                month=__CAST_AS_INTEGER__.format(
                    cls.__sql_date_to_str__(date_or_attr, day=False, year=False)
                ),
                year=cls.__sql_date_to_str__(date_or_attr, day=False, month=False),
                concatenation=cls.__sql_concatenation__,
            )
        )

    @classmethod
    def __sql_first_of_halfyear__(cls, date_or_attr):
        return cls.__sql_str_to_date__(
            cls.__sql_first_of_halfyear_template__.format(
                month=__CAST_AS_INTEGER__.format(
                    cls.__sql_date_to_str__(date_or_attr, day=False, year=False)
                ),
                year=cls.__sql_date_to_str__(date_or_attr, day=False, month=False),
                concatenation=cls.__sql_concatenation__,
            )
        )

    # sub select needed because ms sql can't group by aliased columns
    # also, GROUP BY attributes 3-n are needed for ms sql servers with
    # sql_mode='ONLY_FULL_GROUP_BY' (default)
    __sql_alloc_base__ = """
        INTO {{aggregation_table}} (
            assignment_oid,
            resource_oid,
            start_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type,
            a_value
        )
        SELECT
            assignment_oid,
            resource_oid,
            aggregated_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type,
            SUM(a_value) AS a_value
        FROM (
            SELECT
                a.assignment_oid,
                a.resource_oid,
                {date_aggregation} AS aggregated_date,
                a.cdb_project_id,
                a.task_id,
                a.cdb_alloc_id,
                {empty_string} AS cdb_demand_id,
                CASE
                    WHEN a.resource_oid > {empty_string} THEN (
                        SELECT pool_oid
                        FROM cdbpcs_pool_assignment
                        WHERE resource_oid=a.resource_oid
                        AND cdb_object_id=a.assignment_oid
                    ) ELSE a.pool_oid
                END AS pool_oid,
                'manpower' AS resource_type,
                s.a_value AS a_value
            FROM cdbpcs_prj_alloc a,
                {{schedule_table}} s

            WHERE {{base_condition}}
                AND a.cdb_project_id = s.cdb_project_id
                AND a.task_id = s.task_id
                AND a.cdb_alloc_id = s.cdb_alloc_id
                AND s.cdb_classname = 'cdbpcs_alloc_schedule'
        ) sub
        GROUP BY
            assignment_oid,
            resource_oid,
            aggregated_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type
        """

    __sql_demand_base__ = """
        INTO {{aggregation_table}} (
            assignment_oid,
            resource_oid,
            start_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type,
            d_value
        )
        SELECT
            assignment_oid,
            resource_oid,
            aggregated_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type,
            SUM(d_value) AS d_value
        FROM (
            SELECT
                d.assignment_oid,
                d.resource_oid,
                {date_aggregation} AS aggregated_date,
                d.cdb_project_id,
                d.task_id,
                {empty_string} AS cdb_alloc_id,
                d.cdb_demand_id,
                CASE
                    WHEN d.resource_oid > {empty_string} THEN (
                        SELECT pool_oid
                        FROM cdbpcs_pool_assignment
                        WHERE resource_oid=d.resource_oid
                        AND cdb_object_id=d.assignment_oid
                    ) ELSE d.pool_oid
                END AS pool_oid,
                d.resource_type,
                s.d_value AS d_value

            FROM cdbpcs_prj_demand d,
                {{schedule_table}} s

            WHERE {{base_condition}}
                AND d.cdb_project_id = s.cdb_project_id
                AND d.task_id = s.task_id
                AND d.cdb_demand_id = s.cdb_demand_id
                AND s.cdb_classname = 'cdbpcs_demand_schedule'
        ) sub
        GROUP BY
            assignment_oid,
            resource_oid,
            aggregated_date,
            cdb_project_id,
            task_id,
            cdb_alloc_id,
            cdb_demand_id,
            pool_oid,
            resource_type
        """

    @classmethod
    def __daily_alloc1__(cls, aggregation_table, base_condition):
        return """
            INTO {aggregation_table} (
                cdb_project_id,
                task_id,
                cdb_alloc_id,
                cdb_demand_id,
                start_date,
                end_date,
                cdb_classname,
                assignment_oid,
                resource_oid,
                pool_oid,
                resource_type,
                a_value,
                value)
            SELECT DISTINCT
                a.cdb_project_id,
                a.task_id,
                a.cdb_alloc_id,
                {empty_string} AS cdb_demand_id,
                c.day,
                c.day,
                'cdbpcs_alloc_schedule',
                a.assignment_oid,
                a.resource_oid,
                a.pool_oid,
                a.demand_resource_type,
                CASE WHEN a.workdays > 0
                THEN a.hours / a.workdays
                ELSE 0 END,
                a.hours
            FROM cdbpcs_prj_alloc_v a

            LEFT JOIN cdbpcs_project p
                ON a.cdb_project_id = p.cdb_project_id
                AND p.ce_baseline_id = ''

            LEFT JOIN cdb_calendar_entry c
            ON c.personalnummer IS NULL
                AND c.calendar_profile_id = p.calendar_profile_id
                AND CAST(c.day_type_id AS INTEGER) = 1
                AND a.start_time_fcast <= c.day
                AND c.day <= a.end_time_fcast

            WHERE {base_condition}
                AND a.resource_oid = {empty_string}
                AND c.day IS NOT NULL
        """.format(
            aggregation_table=aggregation_table,
            base_condition=base_condition,
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __daily_alloc2__(cls, aggregation_table, base_condition):
        return """
            INTO {aggregation_table} (
                cdb_project_id,
                task_id,
                cdb_alloc_id,
                cdb_demand_id,
                start_date,
                end_date,
                cdb_classname,
                assignment_oid,
                resource_oid,
                pool_oid,
                resource_type,
                a_value,
                value)
            SELECT DISTINCT
                a.cdb_project_id,
                a.task_id,
                a.cdb_alloc_id,
                {empty_string} AS cdb_demand_id,
                c.day,
                c.day,
                'cdbpcs_alloc_schedule',
                a.assignment_oid,
                a.resource_oid,
                a.pool_oid,
                a.demand_resource_type,
                CASE WHEN a.workdays > 0
                THEN a.hours / a.workdays
                ELSE 0 END,
                a.hours
            FROM cdbpcs_prj_alloc_v a

            LEFT JOIN cdbpcs_capa_sched_pd c
            ON a.assignment_oid = c.assignment_oid
                AND a.start_time_fcast <= c.day
                AND c.day <= a.end_time_fcast

            WHERE {base_condition}
                AND a.assignment_oid > {empty_string}
                AND a.workdays > 0
                AND c.day IS NOT NULL
        """.format(
            aggregation_table=aggregation_table,
            base_condition=base_condition,
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __daily_demand1__(cls, aggregation_table, base_condition):
        return """
            INTO {aggregation_table} (
                cdb_project_id,
                task_id,
                cdb_alloc_id,
                cdb_demand_id,
                start_date,
                end_date,
                cdb_classname,
                assignment_oid,
                resource_oid,
                pool_oid,
                resource_type,
                d_value,
                value)
            SELECT DISTINCT
                d.cdb_project_id,
                d.task_id,
                {empty_string} AS cdb_alloc_id,
                d.cdb_demand_id,
                c.day,
                c.day,
                'cdbpcs_demand_schedule',
                d.assignment_oid,
                d.resource_oid,
                d.pool_oid,
                d.resource_type,
                CASE WHEN d.workdays > 0 AND (d.hours - d.hours_assigned) / d.workdays > 0
                THEN (d.hours - d.hours_assigned) / d.workdays
                ELSE 0 END,
                CASE WHEN d.hours - d.hours_assigned > 0
                THEN d.hours - d.hours_assigned
                ELSE 0 END
            FROM cdbpcs_prj_demand_v d

            LEFT JOIN cdbpcs_project p
                ON d.cdb_project_id = p.cdb_project_id
                AND p.ce_baseline_id = ''

            LEFT JOIN cdb_calendar_entry c
            ON c.personalnummer IS NULL
                AND c.calendar_profile_id = p.calendar_profile_id
                AND CAST(c.day_type_id AS INTEGER) = 1
                AND d.start_time_fcast <= c.day
                AND c.day <= d.end_time_fcast

            WHERE {base_condition}
                AND d.resource_oid = {empty_string}
                AND c.day IS NOT NULL
        """.format(
            aggregation_table=aggregation_table,
            base_condition=base_condition,
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __daily_demand2__(cls, aggregation_table, base_condition):
        return """
            INTO {aggregation_table} (
                cdb_project_id,
                task_id,
                cdb_alloc_id,
                cdb_demand_id,
                start_date,
                end_date,
                cdb_classname,
                assignment_oid,
                resource_oid,
                pool_oid,
                resource_type,
                d_value,
                value)
            SELECT DISTINCT
                d.cdb_project_id,
                d.task_id,
                {empty_string} AS cdb_alloc_id,
                d.cdb_demand_id,
                c.day,
                c.day,
                'cdbpcs_demand_schedule',
                d.assignment_oid,
                d.resource_oid,
                d.pool_oid,
                d.resource_type,
                CASE WHEN d.workdays > 0 AND (d.hours - d.hours_assigned) / d.workdays > 0
                THEN (d.hours - d.hours_assigned) / d.workdays
                ELSE 0 END,
                CASE WHEN d.hours - d.hours_assigned > 0
                THEN d.hours - d.hours_assigned
                ELSE 0 END
            FROM cdbpcs_prj_demand_v d

            LEFT JOIN cdbpcs_capa_sched_pd c
            ON d.assignment_oid = c.assignment_oid
                AND d.start_time_fcast <= c.day
                AND c.day <= d.end_time_fcast

            WHERE {base_condition}
                AND d.assignment_oid > {empty_string}
                AND d.workdays > 0
                AND c.day IS NOT NULL
        """.format(
            aggregation_table=aggregation_table,
            base_condition=base_condition,
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __weekly_alloc__(cls):
        return cls.__sql_alloc_base__.format(
            date_aggregation=cls.__sql_first_of_week__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __weekly_demand__(cls):
        return cls.__sql_demand_base__.format(
            date_aggregation=cls.__sql_first_of_week__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __monthly_alloc__(cls):
        return cls.__sql_alloc_base__.format(
            date_aggregation=cls.__sql_first_of_month__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __monthly_demand__(cls):
        return cls.__sql_demand_base__.format(
            date_aggregation=cls.__sql_first_of_month__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __quarterly_alloc__(cls):
        return cls.__sql_alloc_base__.format(
            date_aggregation=cls.__sql_first_of_quarter__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __quarterly_demand__(cls):
        return cls.__sql_demand_base__.format(
            date_aggregation=cls.__sql_first_of_quarter__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __halfyearly_alloc__(cls):
        return cls.__sql_alloc_base__.format(
            date_aggregation=cls.__sql_first_of_halfyear__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    @classmethod
    def __halfyearly_demand__(cls):
        return cls.__sql_demand_base__.format(
            date_aggregation=cls.__sql_first_of_halfyear__("s.start_date"),
            empty_string=cls.__empty_string__,
        )

    def get_query_stmt(self, project_id, task_ids=None, prefix=None):
        """
        Get an expression for use in SQL statements
        :param project_id: cdb_project_id to be searched for
        :param task_ids: task_ids to be searched for
        :param prefix: A table alias that is set before the column name when the condition is used
                       in SQL join statements. The table alias does not have to refer to the table name.
        :return: SQL expression for use in WHERE conditions
        """
        p_attr = "cdb_project_id"
        p_attr = "{}.{}".format(prefix, p_attr) if prefix else p_attr
        sql_cond = "{}='{}'".format(p_attr, sqlapi.quote(project_id))

        if task_ids:
            oor = db_tools.OneOfReduced(table_name="cdbpcs_task")
            sql_cond = "({} AND {})".format(
                sql_cond,
                oor.get_expression(
                    column_name="task_id", values=task_ids, table_alias=prefix
                ),
            )
        return sql_cond

    # SQL operations
    @classmethod
    def _removeSchedules(cls, query_pattern):
        for tbl in cls.__all_schedule_tables__:
            sqlapi.SQLdelete(
                "FROM {table} WHERE {condition}".format(
                    table=tbl,
                    condition=query_pattern.format(tbl),
                )
            )

    @classmethod
    def _createDailyAllocationSchedule(cls, query_a):
        sqlapi.SQLinsert(
            cls.__daily_alloc1__(
                aggregation_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )
        sqlapi.SQLinsert(
            cls.__daily_alloc2__(
                aggregation_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )

    @classmethod
    def _createDailyDemandSchedule(cls, query_d):
        sqlapi.SQLinsert(
            cls.__daily_demand1__(
                aggregation_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )
        sqlapi.SQLinsert(
            cls.__daily_demand2__(
                aggregation_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )

    @classmethod
    def _evenlySpreadDailyValue(cls, query_pattern):
        table = fResourceSchedule.GetTableName()
        sqlapi.SQLupdate(
            """
            {aggregation_table}
            SET value = value / (
                SELECT t.days_fcast
                FROM cdbpcs_task t
                WHERE {aggregation_table}.cdb_project_id = t.cdb_project_id
                    AND {aggregation_table}.task_id = t.task_id
                    AND t.ce_baseline_id = ''
            )
            WHERE {base_condition}""".format(
                aggregation_table=table,
                base_condition=query_pattern.format(table),
            )
        )

    @classmethod
    def _createWeeklyAllocationSchedule(cls, query_a):
        sqlapi.SQLinsert(
            cls.__weekly_alloc__().format(
                aggregation_table=fResourceScheduleWeek.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )

    @classmethod
    def _createWeeklyDemandSchedule(cls, query_d):
        sqlapi.SQLinsert(
            cls.__weekly_demand__().format(
                aggregation_table=fResourceScheduleWeek.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )

    @classmethod
    def _createMonthlyAllocationSchedule(cls, query_a):
        sqlapi.SQLinsert(
            cls.__monthly_alloc__().format(
                aggregation_table=fResourceScheduleMonth.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )

    @classmethod
    def _createMonthlyDemandSchedule(cls, query_d):
        sqlapi.SQLinsert(
            cls.__monthly_demand__().format(
                aggregation_table=fResourceScheduleMonth.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )

    @classmethod
    def _createQuarterlyAllocationSchedule(cls, query_a):
        sqlapi.SQLinsert(
            cls.__quarterly_alloc__().format(
                aggregation_table=fResourceScheduleQuarter.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )

    @classmethod
    def _createQuarterlyDemandSchedule(cls, query_d):
        sqlapi.SQLinsert(
            cls.__quarterly_demand__().format(
                aggregation_table=fResourceScheduleQuarter.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )

    @classmethod
    def _createHalfYearlyAllocationSchedule(cls, query_a):
        sqlapi.SQLinsert(
            cls.__halfyearly_alloc__().format(
                aggregation_table=fResourceScheduleHalfYear.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_a,
            )
        )

    @classmethod
    def _createHalfYearlyDemandSchedule(cls, query_d):
        sqlapi.SQLinsert(
            cls.__halfyearly_demand__().format(
                aggregation_table=fResourceScheduleHalfYear.GetTableName(),
                schedule_table=fResourceSchedule.GetTableName(),
                base_condition=query_d,
            )
        )

    @classmethod
    # pylint: disable=inconsistent-return-statements
    def createSchedules_many(cls, task_uuids=None):
        if not task_uuids:
            return None

        delete_pattern = db_tools.get_res_sched_condition("{0}", task_uuids)
        create_pattern = db_tools.get_res_sched_condition(
            "{0}", task_uuids, "status != 180"
        )

        with transaction.Transaction():
            cls._removeSchedules(delete_pattern)

            if create_pattern:  # entries are to be (re-)created
                query_a = "({})".format(create_pattern.format("a"))
                query_d = "({})".format(create_pattern.format("d"))

                cls._createDailyAllocationSchedule(query_a)
                cls._createDailyDemandSchedule(query_d)
                cls._evenlySpreadDailyValue(create_pattern)
                cls._createWeeklyAllocationSchedule(query_a)
                cls._createWeeklyDemandSchedule(query_d)
                cls._createMonthlyAllocationSchedule(query_a)
                cls._createMonthlyDemandSchedule(query_d)
                cls._createQuarterlyAllocationSchedule(query_a)
                cls._createQuarterlyDemandSchedule(query_d)
                cls._createHalfYearlyAllocationSchedule(query_a)
                cls._createHalfYearlyDemandSchedule(query_d)


class ScheduleCalculatorOracle(ScheduleCalculator):
    dbms = sqlapi.DBMS_ORACLE
    __sql_date_format__ = ["dd", "mm", "YYYY"]
    __sql_date_format_separator__ = "."
    __sql_concatenation__ = "||"

    __empty_string__ = "chr(1)"

    @classmethod
    def __sql_date_format_mask__(cls, day=True, month=True, year=True):
        return [day, month, year]

    @classmethod
    def __sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        return "TO_CHAR({}, '{}')".format(
            date_or_attr, cls._date_format_literal(day, month, year)
        )

    @classmethod
    def __sql_str_to_date__(cls, date_or_attr, day=True, month=True, year=True):
        # oracle seems to be the sole sane dbms out of the three...
        return "TO_DATE({}, '{}')".format(
            date_or_attr, cls._date_format_literal(day, month, year)
        )

    @classmethod
    def __sql_first_of_week__(cls, date_or_attr):
        return "TRUNC({}, 'DAY')".format(date_or_attr)

    @classmethod
    def __sql_first_of_month__(cls, date_or_attr):
        return "TRUNC({}, 'MONTH')".format(date_or_attr)

    @classmethod
    def __sql_first_of_quarter__(cls, date_or_attr):
        return "TRUNC({}, 'Q')".format(date_or_attr)

    __sql_first_of_halfyear_template__ = """
        CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '01.01.'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '01.07.'
        END {concatenation} {year}
        """


class ScheduleCalculatorSqlite(ScheduleCalculator):
    dbms = sqlapi.DBMS_SQLITE
    __sql_date_format__ = ["%Y", "%m", "%d"]
    __sql_date_format_separator__ = "-"
    __sql_concatenation__ = "||"

    @classmethod
    def __sql_date_format_mask__(cls, day=True, month=True, year=True):
        return [year, month, day]

    @classmethod
    def __sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        return "STRFTIME('{}', {})".format(
            cls._date_format_literal(day, month, year, is_sqlite=True), date_or_attr
        )

    @classmethod
    def __sql_str_to_date__(cls, date_or_attr, day=True, month=True, year=True):
        # sqlite stores dates as strings, but reversed from output
        return "STRFTIME('{}', {})".format(
            cls._date_format_literal(day, month, year, is_sqlite=True), date_or_attr
        )

    __first_weekday__ = 1  # monday (use 0 for sunday)

    @classmethod
    def __sql_first_of_week__(cls, date_or_attr):
        result = """
            CASE
                WHEN DATE({date}, 'weekday {first}') = STRFTIME('%Y-%m-%d', {date})
                    THEN STRFTIME('%Y-%m-%d', {date})
                ELSE DATE({date}, 'weekday {first}', '-7 days')
            END {concatenation} 'T00:00:00'
        """.format(
            date=date_or_attr,
            first=cls.__first_weekday__,
            concatenation=cls.__sql_concatenation__,
        )
        return result

    @classmethod
    def __sql_first_of_month__(cls, date_or_attr):
        return "DATE({date}, 'start of month') {concatenation} 'T00:00:00'".format(
            date=date_or_attr, concatenation=cls.__sql_concatenation__
        )

    __sql_first_of_quarter_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 3 THEN '-01-01'
            WHEN {month}
                BETWEEN 4 AND 6 THEN '-04-01'
            WHEN {month}
                BETWEEN 7 AND 9 THEN '-07-01'
            ELSE '-10-01'
        END {concatenation} 'T00:00:00'
        """

    __sql_first_of_halfyear_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '-01-01'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '-07-01'
        END {concatenation} 'T00:00:00'
        """


class ScheduleCalculatorMsSQL(ScheduleCalculator):
    dbms = sqlapi.DBMS_MSSQL
    __sql_date_format__ = ["yyyy", "MM", "dd"]
    __sql_date_format_separator__ = ""
    __sql_concatenation__ = "+"

    __date_first_offset__ = {
        "1": "1",
        "2": "0",
        "3": "-1",
        "4": "-2",
        "5": "4",
        "6": "3",
        "7": "2",
    }

    @classmethod
    def sql_server_major_version(cls):
        # detect SQL Server Version
        # see: Microsoft KB 321185 (http://support.microsoft.com/kb/321185)
        # not listing the cumulative update versions
        stmt = """SELECT TOP 1 CAST(SERVERPROPERTY('productversion') AS NVARCHAR(12)) pversion,
                         CAST(SERVERPROPERTY('edition') AS NVARCHAR(100)) pedition FROM cdb_sys_keys"""

        rs = sqlapi.RecordSet2(sql=stmt)
        row = rs[0]
        major = int(row.pversion.split(".", 1)[0])
        return major

    @classmethod
    def __sql_date_format_mask__(cls, day=True, month=True, year=True):
        return [year, month, day]

    @classmethod
    def __2012_sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        return "FORMAT({}, '{}')".format(
            date_or_attr, cls._date_format_literal(day, month, year)
        )

    @classmethod
    def __2008_sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        """
           Day Month Year    Result
        #1   T     T    T  YYYYMMDD
        #2   T     T    F      MMDD
        #3   T     F    T    YYYYDD
        #4   T     F    F        DD
        #5   F     F    F
        #6   F     F    T      YYYY
        #7   F     T    F        MM
        #8   F     T    T    YYYYMM
        """
        result = "CONVERT(VARCHAR(8), {date_or_attr}, 112)".format(
            date_or_attr=date_or_attr
        )  # 1
        if day and month and not year:  # 2
            result = "RIGHT({}, 4)".format(result)
        if day and not month and year:  # 3
            _year = "LEFT({}, 4)".format(result)
            _day = "RIGHT({}, 2)".format(result)
            result = "({} + {})".format(_year, _day)
        if day and not month and not year:  # 4
            result = "RIGHT({}, 2)".format(result)
        if not day and not month and not year:  # 5
            result = "''"
        if not day and not month and year:  # 6
            result = "LEFT({}, 4)".format(result)
        if not day and month and not year:  # 7
            result = "SUBSTRING({}, 5, 2)".format(result)
        if not day and month and year:  # 6
            result = "LEFT({}, 6)".format(result)
        return result

    @classmethod
    def __sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        """
        Forwards to the version specific method
        Refer to E041586: A project task cannot be created: DBError raised
        """
        if cls.sql_server_major_version() < 11:
            # MS SQL Server up to major release 2008
            return cls.__2008_sql_date_to_str__(date_or_attr, day, month, year)
        else:
            # MS SQL Server from major release 2008
            return cls.__2012_sql_date_to_str__(date_or_attr, day, month, year)

    @classmethod
    def __sql_str_to_date__(cls, date_or_attr, day=True, month=True, year=True):
        # ms sql does some guessing regarding the date's format
        # Refer to E041586: A project task cannot be created: DBError raised
        func_name = "PARSE" if cls.sql_server_major_version() >= 11 else "CAST"
        return "{}({} AS DATE)".format(func_name, date_or_attr)

    __first_weekday__ = 2  # monday (use 1 for sunday)
    _first_weekday = None

    @classmethod
    def __sql_first_of_week__(cls, date_or_attr):
        """
        cs.resource always uses Monday as the first day of the week
        """
        if cls._first_weekday is None:
            # NOTE: Meaningless FROM part of following statement is necessary to avoid DBError
            rset = sqlapi.RecordSet2(sql="select @@DATEFIRST AS df from cdb_sys_keys")
            df = rset[0]["df"] if rset else "0"
            cls._first_weekday = cls.__date_first_offset__.get(
                str(df), cls.__first_weekday__
            )

        return "DATEADD(DAY, {0}-DATEPART(WEEKDAY, {1}), {1})".format(
            cls._first_weekday,
            date_or_attr,
        )

    @classmethod
    def __sql_first_of_month__(cls, date_or_attr):
        return "DATEADD(MONTH, DATEDIFF(MONTH, 0, {}), 0)".format(date_or_attr)

    @classmethod
    def __sql_first_of_quarter__(cls, date_or_attr):
        return "DATEADD(QQ, DATEDIFF(QQ, 0, {}), 0)".format(date_or_attr)

    __sql_first_of_halfyear_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '-01-01'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '-07-01'
        END
        """


class ScheduleCalculatorPostgres(ScheduleCalculator):
    dbms = sqlapi.DBMS_POSTGRES
    __sql_date_format__ = ["YYYY", "MM", "DD"]
    __sql_date_format_separator__ = "-"
    __sql_concatenation__ = "||"

    @classmethod
    def __sql_date_format_mask__(cls, day=True, month=True, year=True):
        return [year, month, day]

    @classmethod
    def __sql_date_to_str__(cls, date_or_attr, day=True, month=True, year=True):
        return "TO_CHAR({}, '{}')".format(
            date_or_attr, cls._date_format_literal(day, month, year)
        )

    @classmethod
    def __sql_str_to_date__(cls, date_or_attr, day=True, month=True, year=True):
        return "TO_DATE({}, '{}')".format(
            date_or_attr, cls._date_format_literal(day, month, year)
        )

    @classmethod
    def __sql_first_of_week__(cls, date_or_attr):
        return "DATE_TRUNC('WEEK', {})".format(date_or_attr)

    @classmethod
    def __sql_first_of_month__(cls, date_or_attr):
        return "DATE_TRUNC('MONTH', {})".format(date_or_attr)

    @classmethod
    def __sql_first_of_quarter__(cls, date_or_attr):
        return "DATE_TRUNC('QUARTER', {})".format(date_or_attr)

    __sql_first_of_quarter_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 3 THEN '-01-01'
            WHEN {month}
                BETWEEN 4 AND 6 THEN '-04-01'
            WHEN {month}
                BETWEEN 7 AND 9 THEN '-07-01'
            ELSE '-10-01'
        END
        """

    __sql_first_of_halfyear_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '-01-01'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '-07-01'
        END
        """


def instantiate_schedule_creator():
    global SCHEDULE_CALCULATOR  # pylint: disable=W0603
    if not SCHEDULE_CALCULATOR:
        SCHEDULE_CALCULATOR = ScheduleCalculator.initForDB(sqlapi.SQLdbms())


instantiate_schedule_creator()
