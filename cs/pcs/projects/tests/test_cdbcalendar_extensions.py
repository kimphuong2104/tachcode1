#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import cdbcalendar_extensions as cal


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["cs.pcs.projects"])
@pytest.mark.unit
class TestCalendarException(unittest.TestCase):
    @mock.patch.object(cal.calendar, "clearCalendarIndex")
    @mock.patch.object(cal.Project, "adjustCalenderChanges")
    @mock.patch.object(cal.sig, "emit", autospec=True)
    def test_adjust_affected_tasks_single_date(
        self, emit, adjustCalenderChanges, clearCalendarIndex
    ):
        "Find and adjust tasks that are affected by CalendarException"
        cal_exception = mock.MagicMock(spec=cal.CalendarException)
        cal_exception.get_sql_where_condition_for_tasks.return_value = "burr"
        args = {
            "calendar_profile_id": "bass",
            "day": "start_date",
        }

        task1 = mock.MagicMock(spec=cal.Task)
        task1.cdb_project_id = "foo1"

        task2 = mock.MagicMock(spec=cal.Task)
        task2.cdb_project_id = "foo2"

        with mock.patch.object(cal.sqlapi, "RecordSet2", return_value=[task1, task2]):
            cal.CalendarException.adjust_affected_tasks(cal_exception, **args)
            cal.sqlapi.RecordSet2.assert_called_once_with(
                sql="SELECT DISTINCT cdb_project_id " "FROM cdbpcs_task WHERE burr"
            )

        cal_exc_data = {
            "cal_exc_start": "start_date",
            "cal_exc_end": "start_date",
            "cal_profile_id": "bass",
        }

        emit.assert_called_once_with(cal.CalendarException, "prepareTaskAdjustments")
        clearCalendarIndex.assert_called_once_with("bass")
        cal_exception.get_sql_where_condition_for_tasks.assert_called_once_with(
            **cal_exc_data
        )
        cal_exception.adjust_manual_tasks.assert_called_once_with("burr")
        adjustCalenderChanges.assert_has_calls(
            [
                mock.call("foo1", "start_date", "start_date"),
                mock.call("foo2", "start_date", "start_date"),
            ],
            any_order=False,
        )

    @mock.patch.object(cal.calendar, "clearCalendarIndex")
    @mock.patch.object(cal.Project, "adjustCalenderChanges")
    @mock.patch.object(cal.sig, "emit", autospec=True)
    def test_adjust_affected_tasks_time_period(
        self, emit, adjustCalenderChanges, clearCalendarIndex
    ):
        "Find and adjust tasks that are affected by CalendarException"
        cal_exception = mock.MagicMock(spec=cal.CalendarException)
        cal_exception.get_sql_where_condition_for_tasks.return_value = "burr"
        args = {
            "calendar_profile_id": "bass",
            "day": "start_date",
            "end_day": "end_date",
        }

        task1 = mock.MagicMock(spec=cal.Task)
        task1.cdb_project_id = "foo1"

        task2 = mock.MagicMock(spec=cal.Task)
        task2.cdb_project_id = "foo2"

        with mock.patch.object(cal.sqlapi, "RecordSet2", return_value=[task1, task2]):
            cal.CalendarException.adjust_affected_tasks(cal_exception, **args)
            cal.sqlapi.RecordSet2.assert_called_once_with(
                sql="SELECT DISTINCT cdb_project_id " "FROM cdbpcs_task WHERE burr"
            )

        cal_exc_data = {
            "cal_exc_start": "start_date",
            "cal_exc_end": "end_date",
            "cal_profile_id": "bass",
        }

        emit.assert_called_once_with(cal.CalendarException, "prepareTaskAdjustments")
        clearCalendarIndex.assert_called_once_with("bass")
        cal_exception.get_sql_where_condition_for_tasks.assert_called_once_with(
            **cal_exc_data
        )
        cal_exception.adjust_manual_tasks.assert_called_once_with("burr")
        adjustCalenderChanges.assert_has_calls(
            [
                mock.call("foo1", "start_date", "end_date"),
                mock.call("foo2", "start_date", "end_date"),
            ],
            any_order=False,
        )

    def test_adjust_manual_tasks(self):
        "Find and adjust manual tasks that are affected by CalendarException"
        sql_condition = "burr"

        task1 = mock.MagicMock(spec=cal.Task)
        task1.start_time_fcast = "foo1"
        task1.days_fcast = "bass1"

        task2 = mock.MagicMock(spec=cal.Task)
        task2.start_time_fcast = "foo2"
        task2.days_fcast = "bass2"

        with mock.patch.object(cal.Task, "Query", return_value=[task1, task2]):
            cal.CalendarException.adjust_manual_tasks(sql_condition)
            cal.Task.Query.assert_called_once_with("burr AND automatic = 0")
            task1.setTimeframe.assert_called_once_with(start="foo1", days="bass1")
            task2.setTimeframe.assert_called_once_with(start="foo2", days="bass2")

    @mock.patch.object(cal.sqlapi, "SQLdbms_date")
    @mock.patch.object(cal.sqlapi, "quote")
    def test_get_sql_where_condition_for_tasks(self, quote, SQLdbms_date):
        "Construct the where condition to find all tasks" " affected by a CalendarException."
        cal_exception = mock.MagicMock(spec=cal.CalendarException)
        cal_exception.day = "foo"
        cal_exception.calendar_profile_id = "bass"
        cpe_master_data = {
            "cal_profile_id": "bass",
            "cal_exc_start": "foo",
            "cal_exc_end": "bar",
        }

        cal.CalendarException.get_sql_where_condition_for_tasks(**cpe_master_data)
        SQLdbms_date.assert_has_calls([mock.call("foo"), mock.call("bar")])
        quote.assert_called_once_with("bass")
