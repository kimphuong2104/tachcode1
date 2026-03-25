#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi, transactions


class ResetForecastDates:
    """The update script resets the all tasks and projects forecast dates
    except for tasks with 'Adopt Bottom-Up-Dates as Forecast'
    After the update the forecast dates shall have the same state
    as they would have if they were newly created
    """

    __updates__ = [
        (
            "cdbpcs_task "
            "SET start_time_plan=NULL, end_time_plan=NULL, days=NULL "
            "Where cdb_object_id IN "
            " (SELECT a.cdb_object_id "
            "  FROM cdbpcs_task a, cdbpcs_project b "
            "  WHERE a.cdb_project_id=b.cdb_project_id AND b.status IN (0, 50, 60) "
            "  AND (a.is_group=0 OR (a.is_group=1 and a.auto_update_time=1))"
            "  AND a.ce_baseline_id=b.ce_baseline_id)"
        ),
        (
            "cdbpcs_project "
            "SET start_time_plan=NULL, end_time_plan=NULL, days=NULL "
            "WHERE status IN (0, 50, 60) AND "
            "(is_group=0 OR (is_group=1 AND auto_update_time=1)) "
        ),
    ]

    def run(self):
        with transactions.Transaction():
            for update in self.__updates__:
                sqlapi.SQLupdate(update)


class ResetProjectIsGroupFlag:
    """
    Reset invalid group flags back to value 1.
    """

    def run(self):
        sqlapi.SQLupdate("cdbpcs_project SET is_group = 1 WHERE is_group > 1")


pre = []
post = [ResetForecastDates, ResetProjectIsGroupFlag]
