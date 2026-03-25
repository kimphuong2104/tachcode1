#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=arguments-differ,unnecessary-lambda,no-value-for-parameter

from datetime import date

import mock
import pytest
from cdb import testcase, transactions

from cs.pcs.projects import tasks
from cs.pcs.scheduling.tests.integration import ScheduleTestCase


def setup_module():
    testcase.run_level_setup()


def _assert_object_date(obj, date):
    obj.Reload()
    assert obj["start_time_fcast"] == date
    assert obj["end_time_fcast"] == date


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class AutomaticProjectStart(ScheduleTestCase):
    "Test Cases for automatically setting project start date (start_time_fcast)"
    pid = "INTEGRATION_TEST_X"
    bid = ""
    tid = "TEST_TASK_A"

    friday = date(2023, 7, 7)
    saturday = date(2023, 7, 8)
    sunday = date(2023, 7, 9)  # mocked "today"
    monday = date(2023, 7, 10)
    tuesday = date(2023, 7, 11)

    def create_data(self):
        with transactions.Transaction():
            self.project = tasks.Project.Create(
                cdb_project_id=self.pid,
                ce_baseline_id=self.bid,
                project_name="X",
                category="Forschung",
                project_manager="caddok",
                template=0,
                start_time_fcast=None,
                end_time_fcast=None,
                days_fcast=22,
                auto_update_time=1,
                is_group=1,
                calendar_profile_id="1cb4cf41-0f40-11df-a6f9-9435b380e702",
            )
            # add manual task without dates
            self.task = ScheduleTestCase.create_task(
                self.pid, self.bid, self.tid, None, None, 1
            )

    @mock.patch("cs.pcs.scheduling.calendar.date")
    def schedule_project(self, _date):
        _date.today.return_value = self.sunday
        _date.side_effect = lambda *args, **kw: date(*args, **kw)

        super().schedule_project()

        self.assertEqual(
            [
                self.calendar.network2day(-1),
                self.calendar.network2day(0),
                self.calendar.network2day(2),
            ],
            [self.friday, self.monday, self.tuesday],
        )

    def test_init_project(self):
        "Create new project without setting start/end date manually"
        self.schedule_project()
        # project starts and ends on next workday following today
        _assert_object_date(self.project, self.monday)
        # manual task is unchanged
        _assert_object_date(self.task, None)

    def _move_task(self, new_task_date, expected_project_date):
        self.schedule_project()
        # moving the (only) manual task's date also moves project
        self.set_dates(self.task, new_task_date, new_task_date)
        self.schedule_project()
        _assert_object_date(self.project, expected_project_date)
        _assert_object_date(self.task, new_task_date)

    def test_move_project_start_into_past(self):
        "Move only task's dates before project start"
        self._move_task(self.friday, self.friday)

    def test_move_task_to_weekend(self):
        "Move only task's dates to a weekend day"
        # projet start will move to next workday following the task's start date
        self._move_task(self.saturday, self.monday)

    def test_move_project_start_into_future(self):
        "Move only task's dates after project start"
        self._move_task(self.tuesday, self.tuesday)
