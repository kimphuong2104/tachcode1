# coding: utf-8
# pylint: disable=consider-using-f-string, too-many-lines, duplicate-code
"""
(re-)create these pool assignments for resources:
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
import datetime
import itertools
import logging

from cdb import sqlapi, transaction
from cdb.objects import Forward, Object

fCapacityScheduleDay = Forward("cs.pcs.resources.capacity.CapacityScheduleDay")
fCapacityScheduleWeek = Forward("cs.pcs.resources.capacity.CapacityScheduleWeek")
fCapacityScheduleMonth = Forward("cs.pcs.resources.capacity.CapacityScheduleMonth")
fCapacityScheduleQuarter = Forward("cs.pcs.resources.capacity.CapacityScheduleQuarter")
fCapacityScheduleHalfYear = Forward(
    "cs.pcs.resources.capacity.CapacityScheduleHalfYear"
)

CAPACITY_CALCULATOR = None
# sub select needed because ms sql can't group by aliased columns
# also, GROUP BY attributes 3-n are needed for ms sql servers with
# sql_mode='ONLY_FULL_GROUP_BY' (default)
SQL_CAPACITY_BASE = """INTO {table} (
    assignment_oid,
    pool_oid,
    resource_oid,
    day,
    capacity
)
SELECT
    assignment_oid,
    pool_oid,
    resource_oid,
    aggregated_date,
    SUM(capacity) AS capacity
FROM (
    SELECT
        a.assignment_oid,
        a.pool_oid,
        a.resource_oid,
        {date_aggregation} AS aggregated_date,
        a.capacity
    FROM cdbpcs_capa_sched_pd a
    WHERE
        {where}
) sub
GROUP BY
    assignment_oid,
    pool_oid,
    resource_oid,
    aggregated_date
"""

__CAST_AS_INTEGER__ = "CAST({} AS INTEGER)"


class CapacityScheduleHalfYear(Object):
    __classname__ = "cdbpcs_capa_sched_ph"
    __maps_to__ = "cdbpcs_capa_sched_ph"

    @classmethod
    def GetStartAndEnd(cls, start, end):
        if start:
            if start.month > 6:
                start_of_halfyear = datetime.date(start.year, 7, 1)
            else:
                start_of_halfyear = datetime.date(start.year, 1, 1)
        else:
            start_of_halfyear = None
        if end:
            if end.month > 6:
                end_of_halfyear = datetime.date(end.year, 12, 31)
            else:
                end_of_halfyear = datetime.date(end.year, 6, 30)
        else:
            end_of_halfyear = None
        return start_of_halfyear, end_of_halfyear

    @classmethod
    def RecreateCapacitySchedule(cls, calculator, resource_oids, start, end):
        start_of_halfyear, end_of_halfyear = cls.GetStartAndEnd(start, end)
        where_delete = calculator.get_query_stmt(resource_oids, start=start_of_halfyear, end=end_of_halfyear)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE {where_delete}")
        stmt = calculator.__sql_capacity_base__.format(
            table="cdbpcs_capa_sched_ph",
            date_aggregation=calculator.__sql_first_of_halfyear__("a.day"),
            where=calculator.get_query_stmt(resource_oids, prefix="a", start=start_of_halfyear, end=end_of_halfyear),
        )
        sqlapi.SQLinsert(stmt)


class CapacityScheduleQuarter(Object):
    __classname__ = "cdbpcs_capa_sched_pq"
    __maps_to__ = "cdbpcs_capa_sched_pq"

    @classmethod
    def GetStartAndEnd(cls, start, end):
        from cs.pcs.resources.web.models.helpers import get_quarter

        def get_quarter_no(month):
            if month < 4:
                return 1
            if month < 7:
                return 2
            if month < 10:
                return 3
            return 4

        if start:
            start_of_quarter = get_quarter(start.year, get_quarter_no(start.month))
        else:
            start_of_quarter = None
        if end:
            end_of_quarter = get_quarter(end.year, get_quarter_no(end.month), True)
        else:
            end_of_quarter = None
        return start_of_quarter, end_of_quarter

    @classmethod
    def RecreateCapacitySchedule(cls, calculator, resource_oids, start, end):
        start_of_quarter, end_of_quarter = cls.GetStartAndEnd(start, end)
        where_delete = calculator.get_query_stmt(resource_oids, start=start_of_quarter, end=end_of_quarter)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE {where_delete}")
        stmt = calculator.__sql_capacity_base__.format(
            table="cdbpcs_capa_sched_pq",
            date_aggregation=calculator.__sql_first_of_quarter__("a.day"),
            where=calculator.get_query_stmt(resource_oids, prefix="a", start=start_of_quarter, end=end_of_quarter),
        )
        sqlapi.SQLinsert(stmt)


class CapacityScheduleMonth(Object):
    __classname__ = "cdbpcs_capa_sched_pm"
    __maps_to__ = "cdbpcs_capa_sched_pm"

    @classmethod
    def GetStartAndEnd(cls, start, end):
        if start:
            start_of_month = datetime.date(start.year, start.month, 1)
        else:
            start_of_month = None
        if end:
            if end.month == 12:
                end_of_month = datetime.date(end.year, 12, 31)
            else:
                end_of_month = datetime.date(end.year, end.month + 1, 1) - datetime.timedelta(days=1)
        else:
            end_of_month = None
        return start_of_month, end_of_month

    @classmethod
    def RecreateCapacitySchedule(cls, calculator, resource_oids, start, end):
        start_of_month, end_of_month = cls.GetStartAndEnd(start, end)
        where_delete = calculator.get_query_stmt(resource_oids, start=start_of_month, end=end_of_month)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE {where_delete}")
        stmt = calculator.__sql_capacity_base__.format(
            table="cdbpcs_capa_sched_pm",
            date_aggregation=calculator.__sql_first_of_month__("a.day"),
            where=calculator.get_query_stmt(resource_oids, prefix="a", start=start_of_month, end=end_of_month),
        )
        sqlapi.SQLinsert(stmt)


class CapacityScheduleWeek(Object):
    __classname__ = "cdbpcs_capa_sched_pw"
    __maps_to__ = "cdbpcs_capa_sched_pw"

    @classmethod
    def GetStartAndEnd(cls, start, end):
        if start:
            start_of_week = start - datetime.timedelta(days=start.weekday())
        else:
            start_of_week = None
        if end:
            end_of_week = end + datetime.timedelta(days=6 - end.weekday())
        else:
            end_of_week = None
        return start_of_week, end_of_week

    @classmethod
    def RecreateCapacitySchedule(cls, calculator, resource_oids, start, end):
        start_of_week, end_of_week = cls.GetStartAndEnd(start, end)
        where_delete = calculator.get_query_stmt(resource_oids, start=start_of_week, end=end_of_week)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE {where_delete}")
        stmt = calculator.__sql_capacity_base__.format(
            table="cdbpcs_capa_sched_pw",
            date_aggregation=calculator.__sql_first_of_week__("a.day"),
            where=calculator.get_query_stmt(resource_oids, prefix="a", start=start_of_week, end=end_of_week),
        )
        sqlapi.SQLinsert(stmt)


class CapacityScheduleDay(Object):
    __classname__ = "cdbpcs_capa_sched_pd"
    __maps_to__ = "cdbpcs_capa_sched_pd"

    __daily_capacity__ = """
        INTO cdbpcs_capa_sched_pd (
            assignment_oid,
            pool_oid,
            resource_oid,
            day,
            capacity
        )
        SELECT DISTINCT
            a.cdb_object_id,
            a.pool_oid,
            a.resource_oid,
            c.day,
            c.capacity
        FROM
            cdbpcs_pool_assignment a
        LEFT JOIN
            cdb_resource_calendar_v c
        ON
            c.day_off = 0
            AND a.cdb_object_id = c.assignment_oid
            AND (a.start_date IS NULL OR a.start_date <= c.day)
            AND (a.end_date IS NULL OR c.day <= a.end_date)
        WHERE
            {}
            AND c.day IS NOT NULL
        """

    @classmethod
    def RecreateCapacitySchedule(cls, calculator, resource_oids, start, end):
        where_delete = calculator.get_query_stmt(resource_oids, start=start, end=end)
        sqlapi.SQLdelete(f"FROM {cls.__maps_to__} WHERE {where_delete}")
        stmt = cls.__daily_capacity__.format(calculator.get_query_stmt(resource_oids, prefix="c", start=start, end=end))
        sqlapi.SQLinsert(stmt)


class CapacityCalculator(object):
    __sql_capacity_base__ = SQL_CAPACITY_BASE
    __empty_string__ = "''"

    @property
    def first_weekday(self):
        return self._first_weekday

    @classmethod
    def initForDB(cls, dbms):  # pylint: disable=R1710
        if dbms == sqlapi.DBMS_ORACLE:
            return CapacityCalculatorOracle()
        if dbms == sqlapi.DBMS_SQLITE:
            return CapacityCalculatorSqlite()
        if dbms == sqlapi.DBMS_MSSQL:
            return CapacityCalculatorMsSQL()
        if dbms == sqlapi.DBMS_POSTGRES:
            return CapacityCalculatorPostgres()

    def __init__(self):
        self._first_weekday = None

    def _date_format_literal(self, day=True, month=True, year=True, is_sqlite=False):
        result = self.__sql_date_format_separator__.join(
            itertools.compress(
                self.__sql_date_format__,
                self.__sql_date_format_mask__(day, month, year),
            )
        )
        if is_sqlite and day and month and year:
            result += "T%H:%M:%S"
        return result

    def __sql_first_of_quarter__(self, date_or_attr):
        return self.__sql_str_to_date__(
            self.__sql_first_of_quarter_template__.format(
                month=__CAST_AS_INTEGER__.format(
                    self.__sql_date_to_str__(date_or_attr, day=False, year=False)
                ),
                year=self.__sql_date_to_str__(date_or_attr, day=False, month=False),
                concatenation=self.__sql_concatenation__,
            )
        )

    def __sql_first_of_halfyear__(self, date_or_attr):
        return self.__sql_str_to_date__(
            self.__sql_first_of_halfyear_template__.format(
                month=__CAST_AS_INTEGER__.format(
                    self.__sql_date_to_str__(date_or_attr, day=False, year=False)
                ),
                year=self.__sql_date_to_str__(date_or_attr, day=False, month=False),
                concatenation=self.__sql_concatenation__,
            )
        )

    # helpers for SQL statement generation
    def _getAttribute(self, attr, prefix=None):
        if prefix:
            return ".".join([prefix, attr])
        return attr

    def get_query_stmt(self, resource_oids=None, prefix=None, start=None, end=None):
        # constructs WHERE conditions: (<oid> in (<resource_oids>))
        # returns '1=0' if no resource_oids are given
        result = "1=0"
        if resource_oids:
            val = "(%s)" % ",".join(["'%s'" % sqlapi.quote(x) for x in resource_oids])
            result = "{attr} IN {val}".format(
                attr=self._getAttribute("resource_oid", prefix), val=val
            )

        attr_day = self._getAttribute("day", prefix)
        if start:
            result = "{} AND {} >= {}".format(
                result, attr_day, sqlapi.SQLdate_literal(start)
            )
        if end:
            result = "{} AND {} <= {}".format(
                result, attr_day, sqlapi.SQLdate_literal(end)
            )

        return result

    # "main" method
    def createSchedules(self, resource_oids=None, start=None, end=None):
        if resource_oids:
            with transaction.Transaction():
                for capa_class in [
                    CapacityScheduleDay,
                    CapacityScheduleWeek,
                    CapacityScheduleMonth,
                    CapacityScheduleQuarter,
                    CapacityScheduleHalfYear,
                ]:
                    try:
                        capa_class.RecreateCapacitySchedule(self, resource_oids, start, end)
                    except Exception:
                        logging.exception("%s.RecreateCapacitySchedule failed (%s - %s)", capa_class, start, end)
                        raise


class CapacityCalculatorOracle(CapacityCalculator):
    dbms = sqlapi.DBMS_ORACLE
    __sql_date_format__ = ["dd", "mm", "YYYY"]
    __sql_date_format_separator__ = "."
    __sql_concatenation__ = "||"

    __empty_string__ = "chr(1)"

    def __sql_date_format_mask__(self, day=True, month=True, year=True):
        return [day, month, year]

    def __sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
        return "TO_CHAR({}, '{}')".format(
            date_or_attr, self._date_format_literal(day, month, year)
        )

    def __sql_str_to_date__(self, date_or_attr, day=True, month=True, year=True):
        # oracle seems to be the sole sane dbms out of the three...
        return "TO_DATE({}, '{}')".format(
            date_or_attr, self._date_format_literal(day, month, year)
        )

    def __sql_first_of_week__(self, date_or_attr):
        return "TRUNC({}, 'DAY')".format(date_or_attr)

    def __sql_first_of_month__(self, date_or_attr):
        return "TRUNC({}, 'MONTH')".format(date_or_attr)

    def __sql_first_of_quarter__(self, date_or_attr):
        return "TRUNC({}, 'Q')".format(date_or_attr)

    __sql_first_of_halfyear_template__ = """
        CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '01.01.'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '01.07.'
        END {concatenation} {year}
        """


class CapacityCalculatorSqlite(CapacityCalculator):
    dbms = sqlapi.DBMS_SQLITE
    __sql_date_format__ = ["%Y", "%m", "%d"]
    __sql_date_format_separator__ = "-"
    __sql_concatenation__ = "||"

    def __sql_date_format_mask__(self, day=True, month=True, year=True):
        return [year, month, day]

    def __sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
        return "STRFTIME('{}', {})".format(
            self._date_format_literal(day, month, year, is_sqlite=True), date_or_attr
        )

    def __sql_str_to_date__(self, date_or_attr, day=True, month=True, year=True):
        # sqlite stores dates as strings, but reversed from output
        return "STRFTIME('{}', {})".format(
            self._date_format_literal(day, month, year, is_sqlite=True), date_or_attr
        )

    __first_weekday__ = 1  # monday (use 0 for sunday)

    def __sql_first_of_week__(self, date_or_attr):
        result = """
            CASE
                WHEN DATE({date}, 'weekday {first}') = STRFTIME('%Y-%m-%d', {date})
                    THEN STRFTIME('%Y-%m-%d', {date})
                ELSE DATE({date}, 'weekday {first}', '-7 days')
            END {concatenation} 'T00:00:00'
            """.format(
            date=date_or_attr,
            first=self.__first_weekday__,
            concatenation=self.__sql_concatenation__,
        )
        return result

    def __sql_first_of_month__(self, date_or_attr):
        return "DATE({date}, 'start of month') {concatenation} 'T00:00:00'".format(
            date=date_or_attr, concatenation=self.__sql_concatenation__
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


class CapacityCalculatorMsSQL(CapacityCalculator):
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

    @property
    def first_weekday(self):
        if self._first_weekday is None:
            # NOTE: Meaningless FROM part of following statement is necessary to avoid DBError
            rset = sqlapi.RecordSet2(sql="select @@DATEFIRST AS df from cdb_sys_keys")
            df = rset[0]["df"] if rset else "0"
            self._first_weekday = self.__date_first_offset__.get(
                str(df), self.__first_weekday__
            )
        return self._first_weekday

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

    def __sql_date_format_mask__(self, day=True, month=True, year=True):
        return [year, month, day]

    def __2012_sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
        return "FORMAT({}, '{}')".format(
            date_or_attr, self._date_format_literal(day, month, year)
        )

    def __2008_sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
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

    def __sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
        """
        Forwards to the version specific method
        Refer to E041586: A project task cannot be created: DBError raised
        """
        if self.sql_server_major_version() < 11:
            # MS SQL Server up to major release 2008
            return self.__2008_sql_date_to_str__(date_or_attr, day, month, year)
        else:
            # MS SQL Server from major release 2008
            return self.__2012_sql_date_to_str__(date_or_attr, day, month, year)

    def __sql_str_to_date__(self, date_or_attr, day=True, month=True, year=True):
        # ms sql does some guessing regarding the date's format
        # Refer to E041586: A project task cannot be created: DBError raised
        func_name = "PARSE" if self.sql_server_major_version() >= 11 else "CAST"
        return "{}({} AS DATE)".format(func_name, date_or_attr)

    __first_weekday__ = 2  # monday (use 1 for sunday)

    def __sql_first_of_week__(self, date_or_attr):
        """
        cs.resource always uses Monday as the first day of the week
        """
        return "DATEADD(DAY, {1}-DATEPART(WEEKDAY, {0}), {0})".format(
            date_or_attr, self.first_weekday
        )

    def __sql_first_of_month__(self, date_or_attr):
        return "DATEADD(MONTH, DATEDIFF(MONTH, 0, {}), 0)".format(date_or_attr)

    def __sql_first_of_quarter__(self, date_or_attr):
        return "DATEADD(QQ, DATEDIFF(QQ, 0, {}), 0)".format(date_or_attr)

    __sql_first_of_halfyear_template__ = """
        {year} {concatenation} CASE
            WHEN {month}
                BETWEEN 1 AND 6 THEN '-01-01'
            WHEN {month}
                BETWEEN 7 AND 12 THEN '-07-01'
        END
        """


class CapacityCalculatorPostgres(CapacityCalculator):
    dbms = sqlapi.DBMS_POSTGRES
    __sql_date_format__ = ["YYYY", "MM", "DD"]
    __sql_date_format_separator__ = "-"
    __sql_concatenation__ = "||"

    def __sql_date_format_mask__(self, day=True, month=True, year=True):
        return [year, month, day]

    def __sql_date_to_str__(self, date_or_attr, day=True, month=True, year=True):
        return "TO_CHAR({}, '{}')".format(
            date_or_attr, self._date_format_literal(day, month, year)
        )

    def __sql_str_to_date__(self, date_or_attr, day=True, month=True, year=True):
        return "TO_DATE({}, '{}')".format(
            date_or_attr, self._date_format_literal(day, month, year)
        )

    def __sql_first_of_week__(self, date_or_attr):
        return "DATE_TRUNC('WEEK', {})".format(date_or_attr)

    def __sql_first_of_month__(self, date_or_attr):
        return "DATE_TRUNC('MONTH', {})".format(date_or_attr)

    def __sql_first_of_quarter__(self, date_or_attr):
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
    global CAPACITY_CALCULATOR  # pylint: disable=W0603
    if not CAPACITY_CALCULATOR:
        CAPACITY_CALCULATOR = CapacityCalculator.initForDB(sqlapi.SQLdbms())


instantiate_schedule_creator()
