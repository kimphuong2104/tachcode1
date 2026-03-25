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
from cdb import testcase

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.updates.v15_4_5 import update_projects_and_tasks

DAY1_STR = "01.01.2020"
DAY1 = datetime.date(2020, 1, 1)
DAY2_STR = "02.01.2020"
DAY2 = datetime.date(2020, 1, 2)
DAY3_STR = "03.01.2020"
DAY3 = datetime.date(2020, 1, 3)
STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


@pytest.mark.integration
class UpdateTaskAndProjectsIntegration(testcase.RollbackTestCase):
    def _create_project(self, pid, bid, **kwargs):
        return Project.Create(
            cdb_project_id=pid,
            cdb_object_id=pid,
            ce_baseline_id=bid,
            calendar_profile_id=STANDARD_PROFILE,
            **kwargs,
        )

    def _create_task(self, oid, pid, bid, tid, **kwargs):
        return Task.Create(
            cdb_object_id=oid,
            cdb_project_id=pid,
            ce_baseline_id=bid,
            task_id=tid,
            **kwargs,
        )

    @mock.patch.object(
        update_projects_and_tasks,
        "QUERY",
        {
            "ce_baseline_id": "",
            "cdb_project_id": ["P1", "P2"],
        },
    )
    def test_recalculate(self):
        # project with start-end-diff 1 and 2 days
        p1 = self._create_project(
            "P1",
            "",
            start_time_fcast=DAY1_STR,
            end_time_fcast=DAY1_STR,
            days_fcast=0,
            auto_update_time=1,
            status=0,
            project_name="Project1",
        )
        # project without dates, but tasks with dates
        p2 = self._create_project(
            "P2",
            "",
            start_time_fcast=DAY1_STR,
            end_time_fcast=DAY1_STR,
            project_name="Project2",
            auto_update_time=1,
            status=0,
            is_group=1,
        )

        # task with start-end-diff 2 and 1 day
        p2_t1 = self._create_task(
            "P2_T1",
            p2.cdb_project_id,
            "",
            "T1",
            start_time_fcast=DAY1_STR,
            end_time_fcast=DAY2_STR,
            days_fcast=1,
            constraint_type="4",
            constraint_date=DAY1_STR,
            auto_update_time=1,
            automatic=1,
            status=0,
            task_name="Task1",
        )
        # task with start-end-diff 3 and 0 days
        p2_t2 = self._create_task(
            "P2_T2",
            p2.cdb_project_id,
            "",
            "T2",
            start_time_fcast=DAY1_STR,
            end_time_fcast=DAY3_STR,
            days_fcast=0,
            constraint_type=0,
            constraint_date=None,
            auto_update_time=1,
            automatic=1,
            status=0,
            task_name="Task2",
        )

        # recalculate tasks and projects (keeps start and end, adjusts days)
        update_projects_and_tasks.recalculate("days_fcast")

        expected = {
            "P1": {
                "days_fcast": 1,
                "end_time_fcast": DAY1,
                "start_time_fcast": DAY1,
            },
            "P2": {
                "days_fcast": 3,
                "end_time_fcast": DAY3,
                "start_time_fcast": DAY1,
            },
            "P2_T1": {
                "days_fcast": 2,
                "end_time_fcast": DAY2,
                "start_time_fcast": DAY1,
            },
            "P2_T2": {
                "days_fcast": 3,
                "end_time_fcast": DAY3,
                "start_time_fcast": DAY1,
            },
        }

        unexpected = {}
        compare = ["days_fcast", "end_time_fcast", "start_time_fcast"]

        for obj in [p1, p2, p2_t1, p2_t2]:
            obj.Reload()
            uuid = obj.cdb_object_id
            for attr in compare:
                actual = obj[attr]
                should = expected[uuid][attr]
                if actual != should:
                    unexpected[f"{uuid}.{attr}"] = {
                        "is": actual,
                        "should_be": should,
                    }

        self.maxDiff = None
        self.assertEqual(unexpected, {})

    @mock.patch.object(
        update_projects_and_tasks,
        "QUERY",
        {
            "ce_baseline_id": "",
            "cdb_project_id": ["P1", "P2"],
        },
    )
    def test_recalculate_with_more_than_1000_projects_and_tasks(self):
        self.skipTest("Skip until CR E061034 of cs.resources is fixed")
        for i in range(2000):
            pid = f"P{i}"
            self._create_project(
                pid,
                "",
                start_time_fcast=DAY1_STR,
                end_time_fcast=DAY1_STR,
                days_fcast=0,
                project_name=f"Project{i}",
            )
            toid = f"P0_T{i}"
            self._create_task(
                toid,
                pid,
                "",
                f"T_{i}",
                start_time_fcast=DAY1_STR,
                end_time_fcast=DAY3_STR,
                days_fcast=0,
                constraint_type=0,
                constraint_date=None,
                task_name=f"Task{i}",
            )

        # expect no error due to big sql-statements
        update_projects_and_tasks.recalculate("days_fcast")


if __name__ == "__main__":
    unittest.main()
