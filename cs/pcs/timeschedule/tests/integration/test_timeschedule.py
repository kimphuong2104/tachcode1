#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import unittest

import mock
import pytest
from cdb import ElementsError, testcase

from cs.pcs.projects.tests import common
from cs.pcs.timeschedule import TimeSchedule


def _to_date(date_str):
    values = [int(x) for x in date_str.split("-")]
    return datetime.date(*values)


@pytest.mark.integration
class TimeScheduleIntegrationTestCase(testcase.RollbackTestCase):
    def check_dates(self, obj, start, end, days):
        start = _to_date(start)
        end = _to_date(end)
        self.assertEqual(
            obj.start_time_fcast,
            start,
            f"Start date does not match: {obj.start_time_fcast} != {start}",
        )
        self.assertEqual(
            obj.end_time_fcast,
            end,
            f"End date does not match: {obj.end_time_fcast} != {end}",
        )
        self.assertEqual(
            obj.days_fcast,
            days,
            f"Duration does not match: {obj.days_fcast} != {days}",
        )

    def test_create_operation_without_prj_context(self):
        "Create operation without project context: no content"
        ts = common.generate_taskschedule()
        content = ts.TimeScheduleContents
        self.assertEqual(len(content), 0)

    def test_create_operation_with_prj_context(self):
        "Create operation with project context: project found as content"
        project = common.generate_project()
        ts = common.generate_taskschedule(
            project_name=project.project_name, cdb_project_id=project.cdb_project_id
        )
        content = ts.TimeScheduleContents
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0].content_oid, project.cdb_object_id)

    @mock.patch("cs.pcs.projects.common.assert_valid_project_resp")
    def test_create_with_project(self, assert_valid_project_resp):
        prj = common.generate_project()
        result = TimeSchedule.KeywordQuery(cdb_project_id=prj.cdb_project_id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, prj.project_name)
        assert_valid_project_resp.assert_not_called()
        # Checking for sys_args not possible

    def test_attach_time_schedule_to_project(self):
        """Make time schedule of first project available to second
        project by attaching it to the second one."""
        project = common.generate_project()
        ts = common.generate_taskschedule(
            project_name=project.project_name, cdb_project_id=project.cdb_project_id
        )
        content = ts.TimeScheduleContents
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0].content_oid, project.cdb_object_id)
        link = common.link_project_to_taskschedule(project, ts)
        self.assertIsNotNone(link)

        user = common.generate_user("foo")
        common.assign_user_project_role(user, project, role_id="Projektmitglied")
        common.assign_user_project_role(user, project, role_id="Projektleiter")

        # check access right for creating link
        c, r, s, d = common.check_access_rights(link, user)
        self.assertTrue(c)
        self.assertTrue(r)
        self.assertTrue(s)
        self.assertTrue(d)

    def test_add_valid_object_to_time_schedule(self):
        """Make time schedule of first project available to second project
        by attaching it to the second one."""
        # A valid times schedule object is any project element, which offers the
        # possibility to set start and end date or in case of milestones just to
        # set an end date.
        # In order to add more content to a time schedule I attach a valid
        # time schedule object(s) to a time schedule.
        project = common.generate_project()
        task = common.generate_task(project, "task_1")
        ts = common.generate_taskschedule(
            project_name=project.project_name, cdb_project_id=project.cdb_project_id
        )
        # Time Schedule contains only the primary project
        self.assertEqual(len(ts.TimeScheduleContents), 1)
        self.assertTrue(project.cdb_object_id in ts.TimeScheduleContents.content_oid)

        # Attach project to Time Schedule
        project.insertIntoTimeSchedule(ts.cdb_object_id)

        # Time Schedule contains only the primary project
        self.assertEqual(len(ts.TimeScheduleContents), 1)
        self.assertTrue(project.cdb_object_id in ts.TimeScheduleContents.content_oid)

        # Attach task to Time Schedule
        task.insertIntoTimeSchedule(ts.cdb_object_id)

        # Time Schedule contains the task an still the primary project
        self.assertEqual(len(ts.TimeScheduleContents), 2)
        self.assertTrue(project.cdb_object_id in ts.TimeScheduleContents.content_oid)
        self.assertTrue(task.cdb_object_id in ts.TimeScheduleContents.content_oid)

    def test_move_object_by_adjusting_start_date(self):
        "Move a time schedule object by setting a new start date."
        # create test data
        project = common.generate_project(auto_update_time=0)
        task = common.generate_task(project, "task_1", auto_update_time=0, automatic=0)

        # Over a weekend
        kwargs = {
            "start_time_fcast": "02.01.2014",
            "end_time_fcast": "10.01.2014",
            "days_fcast": 7,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setStartTimeFcast(start=datetime.date(2014, 1, 15))
        self.check_dates(project, "2014-01-15", "2014-01-23", 7)
        task.setStartTimeFcast(start=datetime.date(2014, 1, 15))
        self.check_dates(task, "2014-01-15", "2014-01-23", 7)

        # Over new Year
        kwargs = {
            "start_time_fcast": "05.12.2013",
            "end_time_fcast": "08.01.2014",
            "days_fcast": 25,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setStartTimeFcast(start=datetime.date(2013, 12, 10))
        self.check_dates(project, "2013-12-10", "2014-01-13", 25)
        task.setStartTimeFcast(start=datetime.date(2013, 12, 10))
        self.check_dates(task, "2013-12-10", "2014-01-13", 25)

        # Start Date at a weekend
        kwargs = {
            "start_time_fcast": "04.01.2014",
            "end_time_fcast": "11.01.2014",
            "days_fcast": 5,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setStartTimeFcast(start=datetime.date(2014, 1, 13))
        self.check_dates(project, "2014-01-13", "2014-01-17", 5)
        task.setStartTimeFcast(start=datetime.date(2014, 1, 13))
        self.check_dates(task, "2014-01-13", "2014-01-17", 5)

        # Over a leap year
        kwargs = {
            "start_time_fcast": "22.02.2012",
            "end_time_fcast": "03.03.2012",
            "days_fcast": 8,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setStartTimeFcast(start=datetime.date(2012, 2, 28))
        self.check_dates(project, "2012-02-28", "2012-03-08", 8)
        task.setStartTimeFcast(start=datetime.date(2012, 2, 28))
        self.check_dates(task, "2012-02-28", "2012-03-08", 8)

    def test_change_duration_by_adjusting_days(self):
        "Changing duration of time schedule object by adjusting days."
        # create test data
        project = common.generate_project(auto_update_time=0)
        task = common.generate_task(project, "task_1", auto_update_time=0, automatic=0)

        # Over a weekend
        kwargs = {
            "start_time_fcast": "05.12.2013",
            "end_time_fcast": "08.01.2014",
            "days_fcast": 25,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setDaysFcast(days=30)
        self.check_dates(project, "2013-12-05", "2014-01-15", 30)
        task.setDaysFcast(days=30)
        self.check_dates(task, "2013-12-05", "2014-01-15", 30)

        # Over new Year
        kwargs = {
            "start_time_fcast": "05.12.2013",
            "end_time_fcast": "08.01.2014",
            "days_fcast": 25,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setDaysFcast(days=27)
        self.check_dates(project, "2013-12-05", "2014-01-10", 27)
        task.setDaysFcast(days=27)
        self.check_dates(task, "2013-12-05", "2014-01-10", 27)

        # Start Date at a weekend
        kwargs = {
            "start_time_fcast": "04.01.2014",
            "end_time_fcast": "11.01.2014",
            "days_fcast": 5,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setDaysFcast(days=12)
        self.check_dates(project, "2014-01-04", "2014-01-21", 12)
        task.setDaysFcast(days=12)
        self.check_dates(task, "2014-01-04", "2014-01-21", 12)

        # Over a leap year
        kwargs = {
            "start_time_fcast": "22.02.2012",
            "end_time_fcast": "03.03.2012",
            "days_fcast": 8,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setDaysFcast(days=15)
        self.check_dates(project, "2012-02-22", "2012-03-13", 15)
        task.setDaysFcast(days=15)
        self.check_dates(task, "2012-02-22", "2012-03-13", 15)

    def test_change_duration_by_adjusting_end_date(self):
        "Changing duration of time schedule object by adjusting end date."
        # create test data
        project = common.generate_project(auto_update_time=0)
        task = common.generate_task(project, "task_1", auto_update_time=0, automatic=0)

        # Over a weekend
        kwargs = {
            "start_time_fcast": "05.12.2013",
            "end_time_fcast": "08.01.2014",
            "days_fcast": 25,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setEndTimeFcast(end=datetime.date(2014, 1, 15))
        self.check_dates(project, "2013-12-05", "2014-01-15", 30)
        task.setEndTimeFcast(end=datetime.date(2014, 1, 15))
        self.check_dates(task, "2013-12-05", "2014-01-15", 30)

        # Over new Year
        kwargs = {
            "start_time_fcast": "05.12.2013",
            "end_time_fcast": "08.01.2014",
            "days_fcast": 25,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setEndTimeFcast(end=datetime.date(2014, 1, 10))
        self.check_dates(project, "2013-12-05", "2014-01-10", 27)
        task.setEndTimeFcast(end=datetime.date(2014, 1, 10))
        self.check_dates(task, "2013-12-05", "2014-01-10", 27)

        # Start Date at a weekend
        kwargs = {
            "start_time_fcast": "04.01.2014",
            "end_time_fcast": "11.01.2014",
            "days_fcast": 5,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setEndTimeFcast(end=datetime.date(2014, 1, 21))
        self.check_dates(project, "2014-01-04", "2014-01-21", 12)
        task.setEndTimeFcast(end=datetime.date(2014, 1, 21))
        self.check_dates(task, "2014-01-04", "2014-01-21", 12)

        # Over a leap year
        kwargs = {
            "start_time_fcast": "22.02.2012",
            "end_time_fcast": "03.03.2012",
            "days_fcast": 8,
        }
        project.Update(**kwargs)
        task.Update(**kwargs)
        project.setEndTimeFcast(end=datetime.date(2012, 3, 13))
        self.check_dates(project, "2012-02-22", "2012-03-13", 15)
        task.setEndTimeFcast(end=datetime.date(2012, 3, 13))
        self.check_dates(task, "2012-02-22", "2012-03-13", 15)

    @staticmethod
    def generate_three_tasks_with_connections():
        # create test data
        project = common.generate_project(auto_update_time=0)
        first = common.generate_task(
            project,
            "task_1",
            auto_update_time=0,
            automatic=0,
            start_time_fcast="17.08.2020",
            end_time_fcast="20.08.2020",
            days_fcast=4,
        )
        second = common.generate_task(
            project,
            "task_2",
            auto_update_time=0,
            automatic=0,
            start_time_fcast="24.08.2020",
            end_time_fcast="27.08.2020",
            days_fcast=4,
        )
        third = common.generate_task(
            project,
            "task_3",
            auto_update_time=0,
            automatic=0,
            start_time_fcast="31.08.2020",
            end_time_fcast="03.09.2020",
            days_fcast=4,
        )
        p_connect = common.generate_task_relation(first, second)
        s_connect = common.generate_task_relation(second, third)
        return first, second, third, p_connect, s_connect

    def test_move_connected_task_1(self):
        """Check dependency violations (based on 3 tasks with dependencies):
        Move middle element 1 workday to left --> dependency to predecessor is not violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_tasks_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 21))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual((p_connect.violation, s_connect.violation), (0, 0))

    def test_move_connected_task_2(self):
        """Check dependency violations (based on 3 tasks with dependencies):
        Move middle element 4 workday to left --> dependency to predecessor is violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_tasks_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 18))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual((p_connect.violation, s_connect.violation), (1, 0))

    def test_move_connected_task_3(self):
        """Check dependency violations (based on 3 tasks with dependencies):
        Move middle element 1 workday to right --> dependency to predecessor is not violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_tasks_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 25))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual((p_connect.violation, s_connect.violation), (0, 0))

    def test_move_connected_task_4(self):
        """Check dependency violations (based on 3 tasks with dependencies):
        Move middle element 4 workday to right --> dependency to predecessor is violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_tasks_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 28))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual((p_connect.violation, s_connect.violation), (0, 1))

    @staticmethod
    def generate_three_milestones_with_connections():
        # create test data
        project = common.generate_project(auto_update_time=0)
        manual_late_milestone = {
            "milestone": 1,
            "start_is_early": 1,
            "end_is_early": 1,
            "auto_update_time": 0,
            "automatic": 0,
            "days_fcast": 0,
            "daytime": 0,
        }
        first = common.generate_task(
            project,
            "task_1",
            start_time_fcast="17.08.2020",
            end_time_fcast="17.08.2020",
            **manual_late_milestone,
        )
        second = common.generate_task(
            project,
            "task_2",
            start_time_fcast="24.08.2020",
            end_time_fcast="24.08.2020",
            **manual_late_milestone,
        )
        third = common.generate_task(
            project,
            "task_3",
            start_time_fcast="31.08.2020",
            end_time_fcast="31.08.2020",
            **manual_late_milestone,
        )
        p_connect = common.generate_task_relation(first, second)
        s_connect = common.generate_task_relation(second, third)
        return first, second, third, p_connect, s_connect

    def test_move_connected_milestone_1(self):
        """Check dependency violations (based on 3 milestones with dependencies):
        Move middle element 5 workday to left --> dependency to predecessor is not violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_milestones_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 17))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual(
            (p_connect.violation, s_connect.violation),
            (0, 0),
        )

    def test_move_connected_milestone_2(self):
        """Check dependency violations (based on 3 milestones with dependencies):
        Move middle element 6 workday to left --> dependency to predecessor is violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_milestones_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 14))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual(
            (p_connect.violation, s_connect.violation),
            (1, 0),
        )

    def test_move_connected_milestone_3(self):
        """Check dependency violations (based on 3 milestones with dependencies):
        Move middle element 5 workday to right --> dependency to predecessor is not violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_milestones_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 8, 31))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual(
            (p_connect.violation, s_connect.violation),
            (0, 0),
        )

    def test_move_connected_milestone_4(self):
        """Check dependency violations (based on 3 milestones with dependencies):
        Move middle element 6 workday to right --> dependency to predecessor is violated."""
        (
            _,
            second,
            _,
            p_connect,
            s_connect,
        ) = self.generate_three_milestones_with_connections()
        second.setStartTimeFcast(start=datetime.date(2020, 9, 1))
        p_connect.Reload()
        s_connect.Reload()
        self.assertEqual(
            (p_connect.violation, s_connect.violation),
            (0, 1),
        )

    @staticmethod
    def generate_two_tasks():
        # create test data
        project = common.generate_project(auto_update_time=0)
        first = common.generate_task(
            project,
            "task_1",
            auto_update_time=0,
            automatic=0,
            start_time_fcast="17.08.2020",
            end_time_fcast="20.08.2020",
            days_fcast=4,
        )
        second = common.generate_task(
            project,
            "task_2",
            auto_update_time=0,
            automatic=0,
            start_time_fcast="24.08.2020",
            end_time_fcast="27.08.2020",
            days_fcast=4,
        )
        return first, second

    def test_create_dependencies_between_tasks(self):
        "Creating dependencies between tasks: there can only be one"
        first, second = self.generate_two_tasks()
        common.generate_task_relation(first, second, rel_type="EA")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(first, second, rel_type="AA")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(first, second, rel_type="AE")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(first, second, rel_type="EA")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(first, second, rel_type="EE")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(second, first, rel_type="AA")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(second, first, rel_type="AE")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(second, first, rel_type="EA")
        with self.assertRaises(ElementsError):
            common.generate_task_relation(second, first, rel_type="EE")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
