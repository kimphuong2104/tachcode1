#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module cdblic.lstatistics

Parser for lstatistics datasets
"""
# Some imports
from collections import OrderedDict, defaultdict

from cdb import sqlapi
from cdb.dberrors import DBError

from . import config
from .utils import first_row, get_rows

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = [
    "get_dataset_shape",
    "get_module_usage_by_org_id",
    "get_module_usage_by_site_id",
    "get_module_usage_by_region",
    "get_module_usage_by_user_daily",
    "get_session_frequencies_per_user_daily",
    "get_session_start_frequencies_hourly",
    "get_session_start_frequencies_hourly_by_org_id",
    "get_session_start_frequencies_hourly_by_site_id",
    "get_session_start_frequencies_weekday_hourly",
    "get_session_start_frequencies_weekday_hourly_by_site_id",
    "get_used_modules",
    "get_user_count",
    "get_user_count_by_org_id",
    "get_user_count_by_site_id",
    "get_host_count",
    "get_host_user_count",
    "get_host_site_count",
]


def get_dataset_shape(tables):
    """Find the shape of the available data

    e.g.
    max intervals
    total users
    total hosts

    to be used for breakdown.
    """
    sql = (
        """SELECT MAX(lbtime) max_time,
                    MIN(lbtime) min_time,
                    COUNT(DISTINCT uname) unames,
                    COUNT(DISTINCT hostname) hosts,
                    COUNT(DISTINCT hostid) hostids,
                    COUNT(DISTINCT pid) sessions,
                    COUNT(DISTINCT mno) lictypes,
                    COUNT(*) events
             FROM %(lstatistics)s
          """
        % tables
    )
    return first_row(sql)


def get_used_modules(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               DISTINCT mno
             FROM %(lstatistics)s
             WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
          """
        % d
    )
    return [row["mno"] for row in get_rows(sql) if row["mno"]]


def get_user_count(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               COUNT(DISTINCT uname) user_count
             FROM %(lstatistics)s
             WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
          """
        % d
    )
    return first_row(sql)


def get_user_count_by_org_id(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               COUNT(ang.personalnummer) user_count,
               ang.org_id
             FROM (SELECT DISTINCT uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN angestellter ang ON ls.uname = ang.personalnummer
             GROUP BY ang.org_id
          """
        % d
    )
    result = {}
    for row in get_rows(sql):
        result[row["org_id"]] = row["user_count"]
    return result


def get_user_count_by_site_id(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
        "angestellter": tables["angestellter"],
    }
    sql = (
        """SELECT
               COUNT(ls.uname) user_count,
               lsm.license_site_id site_id
             FROM (SELECT DISTINCT uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             GROUP BY lsm.license_site_id
          """
        % d
    )
    result = {}
    for row in get_rows(sql):
        result[row["site_id"]] = row["user_count"]
    return result


def get_user_count_by_region(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "licsites": tables["cdbfls_license_site"],
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               COUNT(ls.uname) user_count,
               lr.license_region_id      region
             FROM (SELECT DISTINCT uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             LEFT JOIN %(licsites)s lr ON lsm.license_site_id = lr.cdb_object_id
             GROUP BY lr.license_region_id
          """
        % d
    )
    result = {}
    for row in get_rows(sql):
        result[row["region"]] = row["user_count"]
    return result


def get_host_count(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               COUNT(DISTINCT hostname) host_count
             FROM %(lstatistics)s
             WHERE lbtime BETWEEN  '%(start_time)s' AND '%(end_time)s'
          """
        % d
    )
    return first_row(sql)


def get_host_user_count(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT COUNT(*) host_user_count
             FROM (SELECT DISTINCT hostname, uname FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') hu
          """
        % d
    )
    return first_row(sql)


def get_host_site_count(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    oracle_sql = (
        """SELECT count(*) host_site
             FROM (SELECT DISTINCT hostname, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             ORDER BY hostname, lsm.license_site_id
          """
        % d
    )
    ms_sql = (
        """SELECT count(*) host_site
             FROM (SELECT DISTINCT hostname, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             GROUP BY hostname, lsm.license_site_id
             ORDER BY hostname, lsm.license_site_id
          """
        % d
    )
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        return first_row(ms_sql)
    else:
        return first_row(oracle_sql)


def get_host_count_by_site_id(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               COUNT(ls.hostname) host_count,
               lsm.license_site_id site_id
             FROM (SELECT DISTINCT hostname, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s') ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             GROUP BY lsm.license_site_id
             ORDER BY 1 DESC
          """
        % d
    )
    result = {}
    for row in get_rows(sql):
        result[row["site_id"]] = row["host_count"]
    return result


def get_multi_host_users(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT ls.uname uname,
                    COUNT(DISTINCT ls.hostname) host_count
             FROM %(lstatistics)s ls
             WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
             GROUP BY ls.uname
             HAVING COUNT(DISTINCT ls.hostname) > 1
             ORDER BY host_count DESC
         """
        % d
    )

    mapper = kwargs.get("pseudonymizer")

    result = {}
    for row in get_rows(sql):
        k = row["uname"] if not mapper else mapper.get_id("user", row["uname"])
        result[k] = row["host_count"]
    return result


def get_module_usage_by_site_id(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               ls.mno  licname,
               lsm.license_site_id site_id,
               COUNT(*) user_count
             FROM (SELECT mno, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
                   AND event IN ('A', 'R', 'F')
                   GROUP BY mno, uname) ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             GROUP BY ls.mno, lsm.license_site_id
          """
        % d
    )

    result = defaultdict(dict)
    for row in get_rows(sql):
        if row["licname"]:
            result[row["licname"]][row["site_id"]] = row["user_count"]
    return result


def get_module_usage_by_region(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "licsites": tables["cdbfls_license_site"],
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               ls.mno  licname,
               lr.license_region_id region,
               COUNT(*) user_count
             FROM (SELECT mno, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
                   AND event IN ('A', 'R', 'F')
                   GROUP BY mno, uname) ls
             LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
             LEFT JOIN %(licsites)s lr ON lsm.license_site_id = lr.cdb_object_id
             GROUP BY ls.mno, lr.license_region_id
          """
        % d
    )

    result = defaultdict(dict)
    for row in get_rows(sql):
        if row["licname"]:
            result[row["licname"]][row["region"]] = row["user_count"]
    return result


def get_module_usage_by_org_id(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """SELECT
               ls.mno  licname,
               ang.org_id org_id,
               COUNT(*) user_count
             FROM (SELECT mno, uname
                   FROM %(lstatistics)s
                   WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
                   AND event IN ('A', 'R', 'F')
                   GROUP BY mno, uname) ls
             LEFT JOIN angestellter ang ON ls.uname = ang.personalnummer
             GROUP BY ls.mno, ang.org_id
          """
        % d
    )

    result = defaultdict(dict)

    for row in get_rows(sql):
        if row["licname"]:
            result[row["licname"]][row["org_id"]] = row["user_count"]
    return result


def get_module_usage_by_user_daily(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    oracle_sql = (
        """
        SELECT
          SUBSTR(lbtime,1,10) time_prefix,
          mno,
          COUNT(DISTINCT uname) user_count
        FROM %(lstatistics)s
        WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        AND event IN ('A', 'R', 'F')
        GROUP BY SUBSTR(lbtime,1,10), mno
    """
        % d
    )
    ms_sql = (
        """
        SELECT
          SUBSTRING(lbtime,1,10) time_prefix,
          mno,
          COUNT(DISTINCT uname) user_count
        FROM %(lstatistics)s
        WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        AND event IN ('A', 'R', 'F')
        GROUP BY SUBSTRING(lbtime,1,10), mno
    """
        % d
    )
    result = defaultdict(dict)

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            if row["mno"]:
                result[row["time_prefix"]][row["mno"]] = row["user_count"]
    else:
        for row in get_rows(oracle_sql):
            if row["mno"]:
                result[row["time_prefix"]][row["mno"]] = row["user_count"]

    return result


def session_start_marker(table, prefix=""):
    """
    Since E044855 we have S/Q markers in the database.
    Check if there are any markers and use them if yes.
    """
    oracle_sql = "SELECT 1 FROM DUAL WHERE EXISTS (SELECT 1 FROM %s WHERE event='S')"
    mssql_sql = (
        "SELECT 1 FROM cdb_sys_keys WHERE EXISTS (SELECT 1 FROM %s WHERE event='S')"
    )

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        stmt = mssql_sql % table
    else:
        stmt = oracle_sql % table
    rows = get_rows(stmt)
    # We have start markers if we get any result
    if rows:
        return "AND %sevent = 'S'" % prefix
    else:
        return "AND %sevent = 'A' AND %sfeature_id = 'PLATFORM_001'" % (prefix, prefix)


def get_session_start_frequencies_hourly(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"])
    d["marker"] = marker

    # We need the distinct PID here: COUNT(DISTINCT pid) starts_per_hour
    # because there could be more than one 'A' per session
    # but this still counts events multiple times, if
    # they are more than an hour apart.
    oracle_sql = (
        """
        SELECT
          SUBSTR(lbtime,1,13) time_prefix,
          COUNT(DISTINCT pid) starts_per_hour
        FROM %(lstatistics)s
        WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTR(lbtime,1,13)
    """
        % d
    )
    ms_sql = (
        """
        SELECT
          SUBSTRING(lbtime,1,13) time_prefix,
          COUNT(DISTINCT pid) starts_per_hour
        FROM %(lstatistics)s
        WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTRING(lbtime,1,13)
    """
        % d
    )

    result = {}

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            result[row["time_prefix"]] = row["starts_per_hour"]
    else:
        for row in get_rows(oracle_sql):
            result[row["time_prefix"]] = row["starts_per_hour"]

    return result


def get_session_start_frequencies_weekday_hourly(
    start_time, end_time, tables, **kwargs
):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"])
    d["marker"] = marker

    oracle_sql = (
        """
        SELECT
        -- get weekday (if mon-fr)
        CASE
         WHEN TO_CHAR(TO_DATE(SUBSTR(hourstat.time_prefix,1,10), 'yyyy.mm.dd'), 'D') IN ('1', '2', '3', '4', '5') THEN 1
        ELSE 0
        END day_of_week,
        -- get hour
        SUBSTR(hourstat.time_prefix,12,2) hour_bucket,
        -- average over same weekday
        AVG(hourstat.starts_per_hour) avg_starts
        FROM
        -- stats per day
        (SELECT
           SUBSTR(lbtime,1,13) time_prefix,
           COUNT(DISTINCT pid) starts_per_hour
         FROM %(lstatistics)s
         WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
         -- a session starts with allocation event 'A' of the base license
         %(marker)s
         -- date prefix, date and hour (lbtime is CHAR...)
         GROUP BY SUBSTR(lbtime,1,13)
        ) hourstat
        GROUP BY
          -- by weekday
          CASE WHEN TO_CHAR(TO_DATE(SUBSTR(hourstat.time_prefix,1,10), 'yyyy.mm.dd'), 'D') IN ('1','2','3','4','5')
          THEN 1 ELSE 0 END,
          -- by daily hour
          SUBSTR(hourstat.time_prefix,12,2)
    """
        % d
    )
    ms_sql = (
        """
        SELECT
        -- get weekday (if mon-fr)
        CASE
         WHEN datepart(dw,convert(datetime, SUBSTRING(hourstat.time_prefix,1,10), 102)) IN ('1', '2', '3', '4', '5') THEN 1
        ELSE 0
        END day_of_week,
        -- get hour
        SUBSTRING(hourstat.time_prefix,12,2) hour_bucket,
        -- average over same weekday
        AVG(hourstat.starts_per_hour) avg_starts
        FROM
        -- stats per day
        (SELECT
           SUBSTRING(lbtime,1,13) time_prefix,
           COUNT(DISTINCT pid) starts_per_hour
         FROM %(lstatistics)s
         WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
         -- a session starts with allocation event 'A' of the base license
         %(marker)s
         -- date prefix, date and hour (lbtime is CHAR...)
         GROUP BY SUBSTRING(lbtime,1,13)
        ) hourstat
        GROUP BY
          -- by weekday
          CASE WHEN datepart(dw,convert(datetime, SUBSTRING(hourstat.time_prefix,1,10), 102)) IN ('1','2','3','4','5')
          THEN 1 ELSE 0 END,
          -- by daily hour
          SUBSTRING(hourstat.time_prefix,12,2)
    """
        % d
    )
    result = defaultdict(float)

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            if int(row["day_of_week"]) == 1:
                result[row["hour_bucket"]] = row["avg_starts"]
    else:
        for row in get_rows(oracle_sql):
            if int(row["day_of_week"]) == 1:
                result[row["hour_bucket"]] = row["avg_starts"]

    return result


def get_session_start_frequencies_weekday_hourly_by_site_id(
    start_time, end_time, tables, **kwargs
):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"], "ls.")
    d["marker"] = marker

    oracle_sql = (
        """
        SELECT
        -- get weekday
        CASE
         WHEN TO_CHAR(TO_DATE(SUBSTR(hourstat.time_prefix,1,10), 'yyyy.mm.dd'), 'D') IN ('1', '2', '3', '4', '5') THEN 1
        ELSE 0
        END day_of_week,
        -- get hour
        SUBSTR(hourstat.time_prefix,12,2) hour_bucket,
        -- site
        site_id,
        -- average over same weekday
        AVG(hourstat.starts_per_hour) avg_starts
        FROM
        -- stats per day
        (SELECT
           SUBSTR(ls.lbtime,1,13) time_prefix,
           lsm.license_site_id site_id,
           COUNT(DISTINCT ls.pid) starts_per_hour
         FROM %(lstatistics)s ls
         LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
         WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
         %(marker)s
         GROUP BY SUBSTR(ls.lbtime,1,13), lsm.license_site_id
        ) hourstat
        GROUP BY
          -- by weekday
          CASE WHEN TO_CHAR(TO_DATE(SUBSTR(hourstat.time_prefix,1,10), 'yyyy.mm.dd'), 'D') IN ('1','2','3','4','5')
          THEN 1 ELSE 0 END,
          -- by daily hour
          SUBSTR(hourstat.time_prefix,12,2),
          -- by site_id
          site_id
    """
        % d
    )
    ms_sql = (
        """
        SELECT
        -- get weekday
        CASE
         WHEN datepart(dw,convert(datetime, SUBSTRING(hourstat.time_prefix,1,10), 102)) IN ('1', '2', '3', '4', '5') THEN 1
        ELSE 0
        END day_of_week,
        -- get hour
        SUBSTRING(hourstat.time_prefix,12,2) hour_bucket,
        -- site
        site_id,
        -- average over same weekday
        AVG(hourstat.starts_per_hour) avg_starts
        FROM
        -- stats per day
        (SELECT
           SUBSTRING(ls.lbtime,1,13) time_prefix,
           lsm.license_site_id site_id,
           COUNT(DISTINCT ls.pid) starts_per_hour
         FROM %(lstatistics)s ls
         LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
         WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
         %(marker)s
         GROUP BY SUBSTRING(ls.lbtime,1,13), lsm.license_site_id
        ) hourstat
        GROUP BY
          -- by weekday
          CASE WHEN datepart(dw,convert(datetime, SUBSTRING(hourstat.time_prefix,1,10), 102)) IN ('1','2','3','4','5')
          THEN 1 ELSE 0 END,
          -- by daily hour
          SUBSTRING(hourstat.time_prefix,12,2),
          -- by site_id
          site_id
    """
        % d
    )

    rec_dd = lambda: defaultdict(rec_dd)
    result = rec_dd()

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            result[row["hour_bucket"]][row["site_id"]] = row["avg_starts"]
    else:
        for row in get_rows(oracle_sql):
            result[row["hour_bucket"]][row["site_id"]] = row["avg_starts"]

    return result


def get_session_start_frequencies_hourly_by_org_id(
    start_time, end_time, tables, **kwargs
):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"], "ls.")
    d["marker"] = marker

    oracle_sql = (
        """
        SELECT
          -- lbtime is string, so just strip minutes and seconds
          SUBSTR(ls.lbtime,1,13) time_prefix,
          ang.org_id org_id,
          COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        LEFT JOIN angestellter ang ON ls.uname = ang.personalnummer
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTR(ls.lbtime,1,13), ang.org_id
    """
        % d
    )
    ms_sql = (
        """
        SELECT
          -- lbtime is string, so just strip minutes and seconds
          SUBSTRING(ls.lbtime,1,13) time_prefix,
          ang.org_id org_id,
          COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        LEFT JOIN angestellter ang ON ls.uname = ang.personalnummer
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTRING(ls.lbtime,1,13), ang.org_id
    """
        % d
    )

    result = defaultdict(dict)
    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            result[row["time_prefix"]][row["org_id"]] = row["starts_per_hour"]
    else:
        for row in get_rows(oracle_sql):
            result[row["time_prefix"]][row["org_id"]] = row["starts_per_hour"]
    return result


def get_session_start_frequencies_hourly_by_site_id(
    start_time, end_time, tables, **kwargs
):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "angestellter": tables["angestellter"],
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"], "ls.")
    d["marker"] = marker

    oracle_sql = (
        """
        SELECT
          SUBSTR(ls.lbtime,1,13) time_prefix,
          lsm.license_site_id site_id,
          COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTR(ls.lbtime,1,13), lsm.license_site_id
    """
        % d
    )
    ms_sql = (
        """
        SELECT
          SUBSTRING(ls.lbtime,1,13) time_prefix,
          lsm.license_site_id site_id,
          COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        LEFT JOIN %(angestellter)s lsm ON ls.uname = lsm.personalnummer
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTRING(ls.lbtime,1,13), lsm.license_site_id
    """
        % d
    )

    result = defaultdict(dict)

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            result[row["time_prefix"]][row["site_id"]] = row["starts_per_hour"]
    else:
        for row in get_rows(oracle_sql):
            result[row["time_prefix"]][row["site_id"]] = row["starts_per_hour"]

    return result


def get_session_frequencies_per_user_daily(start_time, end_time, tables, **kwargs):
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    marker = session_start_marker(d["lstatistics"], "ls.")
    d["marker"] = marker
    oracle_sql = (
        """
        SELECT
          time_prefix,
          COUNT(DISTINCT uname) total_users,
          SUM(starts_per_hour) total_starts,
          MAX(starts_per_hour) max_starts_per_user,
          AVG(starts_per_hour) avg_starts_per_user,
          MEDIAN(starts_per_hour) med_starts_per_user,
          MIN(starts_per_hour) min_starts_per_user,
          STDDEV(starts_per_hour) stddev_starts_per_user
        FROM
        (SELECT SUBSTR(ls.lbtime,1,10) time_prefix,
               ls.uname uname,
               COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTR(ls.lbtime,1,10), ls.uname, ls.pid) pu
        GROUP BY time_prefix
    """
        % d
    )
    ms_sql = (
        """
        SELECT
          time_prefix,
          COUNT(DISTINCT uname) total_users,
          SUM(starts_per_hour) total_starts,
          MAX(starts_per_hour) max_starts_per_user,
          AVG(starts_per_hour) avg_starts_per_user,
          PERCENTILE_CONT(0.5) WITHIN GROUP (order by starts_per_hour) over() med_starts_per_user,
          MIN(starts_per_hour) min_starts_per_user,
          STDEV(starts_per_hour) stddev_starts_per_user
        FROM
        (SELECT SUBSTRING(ls.lbtime,1,10) time_prefix,
               ls.uname uname,
               COUNT(DISTINCT ls.pid) starts_per_hour
        FROM %(lstatistics)s ls
        WHERE ls.lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        %(marker)s
        GROUP BY SUBSTRING(ls.lbtime,1,10), ls.uname, ls.pid) pu
        GROUP BY time_prefix, starts_per_hour
    """
        % d
    )

    result = {}

    if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        for row in get_rows(ms_sql):
            result[row["time_prefix"]] = dict(row)
    else:
        for row in get_rows(oracle_sql):
            result[row["time_prefix"]] = dict(row)

    return result


def get_license_mappings(start_time, end_time, tables, **kwargs):
    """
    Returns all used license names and the corresponding sub-licenses if license is a package.
    Dictionary keys contain the mno, values the mapped sub-licenses (if any).
    :param start_time:
    :param end_time:
    :param tables:
    :return:
    """
    d = {
        "start_time": start_time,
        "end_time": end_time,
        "lstatistics": tables["lstatistics"],
    }
    sql = (
        """
        SELECT DISTINCT mno FROM %(lstatistics)s
        WHERE lbtime BETWEEN '%(start_time)s' AND '%(end_time)s'
        ORDER BY mno
    """
        % d
    )
    # Get full list of license packages
    packages = get_license_packages(d["start_time"], d["end_time"], d["lstatistics"])
    # Ordered dict to keep order from sql select
    result = OrderedDict()
    for row in get_rows(sql):
        if not row["mno"]:
            continue
        if row["mno"] in packages:
            result[row["mno"]] = packages[row["mno"]]
        else:
            result[row["mno"]] = []
    return result


def get_license_packages(start_time, end_time, table, **kwargs):
    """
    Returns dict of sub-licenses of license packages if available.
    :param start_time: start of the interval
    :param end_time: boundary of the interval
    :param table: lstatistics table to use
    :return:
    """
    # Skip execution if mapping table doesn't exist (i.e. inside customer environment)
    try:
        sqlapi.RecordSet2(sql="""SELECT 1 FROM bestellnr_zuordnung""")
    except DBError as e:
        # Error code -942 is to be expected if relation not found (Oracle)
        #             208 for MS SQL
        if e.code == -942 or e.code == 208:
            return {}
        else:
            raise

    # Fetch all licenses from database which are mapped by 'bestellnr_zuordnung' and used by the customer
    qry = """
        SELECT bnz.bestellnr AS package, bnz.bestellnr2 AS lic
            FROM bestellnr_zuordnung bnz
            WHERE bnz.bestellnr IN (
                SELECT mno FROM %s
                WHERE lbtime BETWEEN '%s' AND '%s'
            )
            ORDER BY bnz.bestellnr, bnz.bestellnr2
        """ % (
        table,
        start_time,
        end_time,
    )
    licenses_resolved = {}
    for row in sqlapi.RecordSet2(sql=qry):
        if row["package"] in licenses_resolved:
            licenses_resolved[row["package"]].append(row["lic"])
        else:
            licenses_resolved[row["package"]] = [row["lic"]]
    return licenses_resolved


def summary():
    return get_dataset_shape({"lstatistics": config.LSTAT_TABLE})


# Guard importing as main module
if __name__ == "__main__":
    print("SUMMARY:")
    print(summary())
    print("SESSION START CONDITION:")
    print(session_start_marker("lstatistics"))
