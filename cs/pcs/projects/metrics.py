#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import functools

from cdb import sqlapi
from cdb.objects import ByID
from cdb.typeconversion import to_legacy_date_format_auto

from cs.pcs.projects import Project


def pcs_compute_planned_cost(qc):
    project = ByID(qc.cdbf_object_id)
    return project.getPlanCost()


def pcs_compute_actual_cost(qc):
    project = ByID(qc.cdbf_object_id)
    return project.getActCost()


def pcs_compute_earned_value(qc):
    project = ByID(qc.cdbf_object_id)
    return project.getEarnedValue()


def _get_closed_projects(end_date=None, time_range=0):
    """
    returns all closed projects whose end lies within
    the given time range before the given end date
    """
    if not end_date:
        end_date = datetime.date.today()
    sqlWhere = f"status = {Project.COMPLETED.status}"
    start_date = end_date - datetime.timedelta(days=time_range)
    ed = sqlapi.SQLdbms_date(to_legacy_date_format_auto(end_date))
    sd = sqlapi.SQLdbms_date(to_legacy_date_format_auto(start_date))
    sqlWhere += (
        f" AND ({sd} <= end_time_act AND end_time_act <= {ed}) AND ce_baseline_id =''"
    )
    return Project.Query(sqlWhere)


def pcs_compute_aver_overspending(qc):
    """
    Average exceeding of efforts
    of projects that have been closed within the actual year
    return value in hours
    """
    ps = _get_closed_projects(time_range=365)
    if not ps:
        return 0.0
    list_effort_fcast = [x.effort_fcast for x in ps]
    list_effort_act = [x.effort_act for x in ps]
    sum_effort_fcast = functools.reduce(lambda a, b: a + b, list_effort_fcast, 0.0)
    sum_effort_act = functools.reduce(lambda a, b: a + b, list_effort_act, 0.0)
    return float(sum_effort_act - sum_effort_fcast) / len(ps)


def pcs_compute_aver_process_time(qc):
    """
    Average duration
    of projects that have been closed within the actual year
    return value in days
    """
    ps = _get_closed_projects(time_range=365)
    if not ps:
        return 0.0
    list_duration = [x.days if x.days else 0 for x in ps]
    sum_duration = functools.reduce(lambda a, b: a + b, list_duration, 0.0)
    return float(sum_duration) / len(ps)


def pcs_compute_aver_timeout(qc):
    """
    Average exceeding of time
    of projects that have been closed within the actual year
    return value in days
    """
    ps = _get_closed_projects(time_range=365)
    if not ps:
        return 0.0
    list_delay = [x.get_delay() for x in ps]
    sum_delay = functools.reduce(lambda a, b: a + b, list_delay, 0.0)
    return float(sum_delay) / len(ps)
