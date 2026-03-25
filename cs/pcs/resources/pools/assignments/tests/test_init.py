#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

import mock

from cdb import auth, testcase
from cdb.objects.org import User
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import RessourceDemand
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools import assignments as cal
from cs.pcs.resources.pools.assignments import Resource
from cs.pcs.resources.pools.assignments.person import ResourcePoolAssignmentPerson


def setup_module():
    testcase.run_level_setup()


class TestCalendarException(testcase.RollbackTestCase):

    def test_aggregate_demands_and_allocations(self):
        prof = User.ByKeys(auth.persno).calendar_profile_id
        task = Task.Create(
            ce_baseline_id='',
            cdb_project_id="proj_id",
            task_id="task_id",
            end_time_fcast=datetime.date(2023, 1, 3),
            start_time_fcast=datetime.date(2023, 1, 1),
        )
        Project.Create(
            ce_baseline_id='',
            cdb_project_id="proj_id",
            name="project",
            calendar_profile_id=prof,
        )
        user = User.Create(
            personalnummer="test",
            name="name",
            calendar_profile_id=prof,
        )
        res = Resource.Create(referenced_oid=user.cdb_object_id)
        res_pool = ResourcePool.Create(name="res_pool1")
        pool_assignment = ResourcePoolAssignmentPerson.Create(
            pool_oid=res_pool.cdb_object_id,
            resource_oid=res.cdb_object_id,
        )
        RessourceDemand.Create(
            cdb_demand_id="demand_id1",
            cdb_project_id="proj_id",
            task_id="task_id",
            resource_oid="",
            assignment_oid=pool_assignment.cdb_object_id,
        )
        exc = cal.CalendarException.Create(
            calendar_profile_id=prof,
            day=datetime.date(2023, 1, 1),
        )
        args = {
            "cal_exc_start": '01.01.2023 00:00:00',
            "cal_exc_end": '01.01.2023 00:00:00',
            "cal_profile_id": prof,
        }
        with mock.patch("cs.pcs.resources.schedule.SCHEDULE_CALCULATOR") as mocked_sch:
            exc.aggregate_demands_and_allocations(**args)
        mocked_sch.createSchedules_many.assert_called_once_with({task.cdb_object_id})
