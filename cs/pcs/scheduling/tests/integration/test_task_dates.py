#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=pointless-string-statement

from datetime import date

import pytest
from cdb import testcase
from cdb.objects.operations import operation

from cs.pcs.projects.tests import common_data
from cs.pcs.scheduling.tests.integration import ScheduleTestCase

PROJECT_START = (2021, 8, 2)
PROJECT_END = (2021, 8, 17)


def setup_module():
    testcase.run_level_setup()


@pytest.mark.integration
class DateAggregationTest(ScheduleTestCase):
    maxDiff = None

    def create_data(self):
        """
        Sets up a project "aggr"
        with two FS-connected task groups "aggr_00000" and "aggr_00003".
        Each group contains two FS-connected children.
        Each child's duration is 3 days.

        The project is not scheduled, but if it was, it'd look like this:

        .            00  02  04  06  08  10  12  14  16  18  20  22
        "aggr_00000" ████████████████████████
        "aggr_00001" ████████████
        "aggr_00002"             ████████████
        "aggr_00003"                         ████████████████████████
        "aggr_00004"                         ████████████
        "aggr_00005"                                     ████████████
        August 2021  02  03  04  05  06  09  10  11  12  13  16  17

        """
        self.p, _ = common_data.create_structured_project(
            "aggr",
            start_date=date(*PROJECT_START),
            days=3,
            tasks_per_level=2,
            depth=1,
        )
        parents = self.p.Tasks.KeywordQuery(is_group=1, order_by="position")
        common_data.create_task_relation(self.p, parents[0], parents[1])

        subs = self.p.Tasks.KeywordQuery(is_group=0, order_by="position")
        for i in range(len(subs) - 1):
            common_data.create_task_relation(self.p, subs[i], subs[i + 1])

        self.t0, self.t3 = parents
        self.t1, self.t2, self.t4, self.t5 = subs

    def reload_all(self):
        for obj in [self.p, self.t0, self.t3, self.t1, self.t2, self.t4, self.t5]:
            obj.Reload()

    def set_auto_update_time(self, auto_update_time=0):
        self.p.Update(auto_update_time=auto_update_time)
        self.p.Tasks.Update(auto_update_time=auto_update_time)
        self.p.recalculate()
        self.reload_all()

    def modify_object(self, obj, **kwargs):
        operation("CDB_Modify", obj, **kwargs)
        self.reload_all()

    FIELDS = [
        "start_time_fcast",
        "end_time_fcast",
        "start_time_plan",
        "end_time_plan",
    ]

    def check_dates(self, objs_and_dates):
        found_values, expected_values = {}, {}

        for obj, s_target, e_target, s_aggregate, e_aggregate in objs_and_dates:
            desc = obj.GetDescription()
            found_values[desc] = [
                obj[field].timetuple()[:3] if obj[field] else None
                for field in self.FIELDS
            ]
            expected_values[desc] = [
                s_target,
                e_target,
                s_aggregate,
                e_aggregate,
            ]

        self.assertEqual(found_values, expected_values)

    def test_aggregation_of_task_values_01(self):
        "Test aggregation for task values: auto_update_time=0"
        """
        Setup:
            - Project Ptest.aggr 02. - 17.08.2021 (12 workdays, starting on a monday)
            - 0
                - 1
                - 2
            - 3
                - 4
                - 5
            - 0 -FS-> 3
            - 1 -FS-> 2
            - 4 -FS-> 5
            - No date aggregation

        Task 5 is then moved to start on 01.09.
        """
        self.set_auto_update_time(0)
        self.check_dates(
            [
                [self.p, PROJECT_START, PROJECT_START, PROJECT_START, PROJECT_END],
                [self.t0, PROJECT_START, (2021, 8, 4), PROJECT_START, (2021, 8, 9)],
                [self.t1, PROJECT_START, (2021, 8, 4), None, None],
                [self.t2, (2021, 8, 5), (2021, 8, 9), None, None],
                [self.t3, (2021, 8, 5), (2021, 8, 9), (2021, 8, 10), PROJECT_END],
                [self.t4, (2021, 8, 10), (2021, 8, 12), None, None],
                [self.t5, (2021, 8, 13), PROJECT_END, None, None],
            ]
        )

        self.modify_object(
            self.t5,
            automatic=0,
            start_time_fcast=date(2021, 9, 1),
        )
        self.check_dates(
            [
                [self.p, PROJECT_START, PROJECT_START, PROJECT_START, PROJECT_END],
                [self.t0, PROJECT_START, (2021, 8, 4), PROJECT_START, (2021, 8, 9)],
                [self.t1, PROJECT_START, (2021, 8, 4), None, None],
                [self.t2, (2021, 8, 5), (2021, 8, 9), None, None],
                [self.t3, (2021, 8, 5), (2021, 8, 9), (2021, 8, 10), PROJECT_END],
                [self.t4, (2021, 8, 10), (2021, 8, 12), None, None],
                [self.t5, (2021, 9, 1), PROJECT_END, None, None],
            ]
        )

    def test_aggregation_of_task_values_02(self):
        "Test aggregation for task values: auto_update_time=1"
        self.set_auto_update_time(1)
        self.check_dates(
            [
                [self.p, PROJECT_START, PROJECT_END, PROJECT_START, PROJECT_START],
                [self.t0, PROJECT_START, (2021, 8, 9), None, None],
                [self.t1, PROJECT_START, (2021, 8, 4), None, None],
                [self.t2, (2021, 8, 5), (2021, 8, 9), None, None],
                [self.t3, (2021, 8, 10), PROJECT_END, None, None],
                [self.t4, (2021, 8, 10), (2021, 8, 12), None, None],
                [self.t5, (2021, 8, 13), PROJECT_END, None, None],
            ]
        )

        self.modify_object(
            self.t5,
            automatic=0,
            start_time_fcast=date(2021, 9, 1),
            end_time_fcast=date(2021, 9, 3),
        )

        self.check_dates(
            [
                [self.p, PROJECT_START, (2021, 9, 3), PROJECT_START, PROJECT_START],
                [self.t0, PROJECT_START, (2021, 8, 9), None, None],
                [self.t1, PROJECT_START, (2021, 8, 4), None, None],
                [self.t2, (2021, 8, 5), (2021, 8, 9), None, None],
                [self.t3, (2021, 8, 10), (2021, 9, 3), None, None],
                [self.t4, (2021, 8, 10), (2021, 8, 12), None, None],
                [self.t5, (2021, 9, 1), (2021, 9, 3), None, None],
            ]
        )

    def test_aggregation_of_task_values_03(self):
        "edge test for aggregation: FNLT constraint on parent task"
        """
        This test starts with an unscheduled project, e.g. it has not start date yet.

        First, task 1 gets a constraint "must start on August 1st, 2022":

        .            00  02  04  06  08  10  12  14  16  18  20  22
        "aggr_00000" ████████████████████████
        "aggr_00001" ████████████
        "aggr_00002"             ████████████
        "aggr_00003"                         ████████████████████████
        "aggr_00004"                         ████████████
        "aggr_00005"                                     ████████████
        August 2022  01  02  03  04  05  08  09  10  11  12  15  16

        Then, group 0 gets a constraint "finish no later than August 24th, 2022".
        This does not change the schedule any further.
        """
        self.p.Update(
            auto_update_time=1,
            end_time_fcast=None,
            end_time_plan=None,
            start_time_fcast=None,
            start_time_plan=None,
        )
        self.p.Tasks.Update(
            automatic=1,
            auto_update_time=1,
            constraint_type="0",  # ASAP
            constraint_date=None,
        )
        # aggregate to prepare test
        self.modify_object(
            self.t1,
            constraint_type="2",  # MSO
            constraint_date=date(2022, 8, 1),
        )

        self.check_dates(
            [
                [self.p, (2022, 8, 1), (2022, 8, 16), None, None],
                [self.t0, (2022, 8, 1), (2022, 8, 8), None, None],
                [self.t1, (2022, 8, 1), (2022, 8, 3), None, None],
                [self.t2, (2022, 8, 4), (2022, 8, 8), None, None],
                [self.t3, (2022, 8, 9), (2022, 8, 16), None, None],
                [self.t4, (2022, 8, 9), (2022, 8, 11), None, None],
                [self.t5, (2022, 8, 12), (2022, 8, 16), None, None],
            ]
        )

        # execute test
        self.modify_object(
            self.t0,
            auto_update_time=0,
            constraint_type="7",  # FNLT
            constraint_date=date(2022, 8, 24),
        )

        self.check_dates(
            [
                [self.p, (2022, 8, 1), (2022, 8, 16), None, None],
                [self.t0, (2022, 8, 1), (2022, 8, 8), (2022, 8, 1), (2022, 8, 8)],
                [self.t1, (2022, 8, 1), (2022, 8, 3), None, None],
                [self.t2, (2022, 8, 4), (2022, 8, 8), None, None],
                [self.t3, (2022, 8, 9), (2022, 8, 16), None, None],
                [self.t4, (2022, 8, 9), (2022, 8, 11), None, None],
                [self.t5, (2022, 8, 12), (2022, 8, 16), None, None],
            ]
        )

    def test_aggregation_of_task_values_04(self):
        "edge test for aggregation requiring more than two scheduling runs"
        """
        This test starts with an unscheduled project, e.g. it has not start date yet.

        Then, task 2 gets a constraint "must start on August 1st, 2022":

        (note calendar index "00" is actually a large negative number
        due to the calendar being initialized starting "today")
        .            00  02  04  06  08  10  12  14  16
        "aggr_00000" ████████████
        "aggr_00001" ████████████
        "aggr_00002" ████████████
        "aggr_00003"             ████████████████████████
        "aggr_00004"             ████████████
        "aggr_00005"                         ████████████
        August 2022  01  02  03  04  05  08  09  10  11

        The relationship between tasks 1 and 2 is violated.
        """
        self.p.Update(
            auto_update_time=1,
            end_time_fcast=None,
            end_time_plan=None,
            start_time_fcast=None,
            start_time_plan=None,
        )
        self.p.Tasks.Update(
            automatic=1,
            auto_update_time=1,
            constraint_type="0",  # ASAP
            constraint_date=None,
        )

        self.modify_object(
            self.t2,
            constraint_type="2",  # MSO
            constraint_date=date(2022, 8, 1),
        )

        self.check_dates(
            [
                [self.p, (2022, 8, 1), (2022, 8, 11), None, None],
                [self.t0, (2022, 8, 1), (2022, 8, 3), None, None],
                [self.t1, (2022, 8, 1), (2022, 8, 3), None, None],
                [self.t2, (2022, 8, 1), (2022, 8, 3), None, None],
                [self.t3, (2022, 8, 4), (2022, 8, 11), None, None],
                [self.t4, (2022, 8, 4), (2022, 8, 8), None, None],
                [self.t5, (2022, 8, 9), (2022, 8, 11), None, None],
            ]
        )

    def test_aggregation_of_task_values_05(self):
        "edge test for ALAP"
        """
        This test starts with an unscheduled project, e.g. it has not start date yet.

        task 1 gets a constraint "must start on August 1st, 2022"
        task 2 gets a constraint "must start on August 11st, 2022"
        task 4 gets a constraint "as late as possible"
        tasks 4 is predecessor of task 5
        tasks 5 is predecessor of task 2

        .            00  02  04  06  08  10  12  14  16
        "aggr_00000" ████████████████████████████████████
        "aggr_00001" ████
        "aggr_00002"                                 ████
        "aggr_00003"                 ████████████████
        "aggr_00004"                 ████
        "aggr_00005"                     ████████████
        August 2022  01  02  03  04  05  08  09  10  11

        The relationship between tasks 1 and 2 is violated.
        """
        self.p.Update(
            auto_update_time=1,
            end_time_fcast=None,
            end_time_plan=None,
            start_time_fcast=None,
            start_time_plan=None,
        )
        self.p.Tasks.Update(
            automatic=1,
            auto_update_time=1,
            constraint_type="0",  # ASAP
            constraint_date=None,
            end_time_fcast=None,
            end_time_plan=None,
            start_time_fcast=None,
            start_time_plan=None,
        )
        self.t1.Update(
            days_fcast=1,
        )
        self.t2.Update(
            days_fcast=1,
        )
        self.t4.Update(
            days_fcast=1,
        )

        taskrelations = self.p.TaskRelations
        taskrelations.Delete()
        common_data.create_task_relation(self.p, self.t4, self.t5)
        common_data.create_task_relation(self.p, self.t5, self.t2)

        self.modify_object(
            self.t1,
            constraint_type="2",  # MSO
            constraint_date=date(2022, 8, 1),
        )
        self.modify_object(
            self.t2,
            constraint_type="2",  # MSO
            constraint_date=date(2022, 8, 11),
        )
        self.modify_object(
            self.t4,
            constraint_type="1",  # ALAP
            constraint_date=None,
        )

        self.check_dates(
            [
                [self.p, (2022, 8, 1), (2022, 8, 11), None, None],
                [self.t0, (2022, 8, 1), (2022, 8, 11), None, None],
                [self.t1, (2022, 8, 1), (2022, 8, 1), None, None],
                [self.t2, (2022, 8, 11), (2022, 8, 11), None, None],
                [self.t3, (2022, 8, 5), (2022, 8, 10), None, None],
                [self.t4, (2022, 8, 5), (2022, 8, 5), None, None],
                [self.t5, (2022, 8, 8), (2022, 8, 10), None, None],
            ]
        )
