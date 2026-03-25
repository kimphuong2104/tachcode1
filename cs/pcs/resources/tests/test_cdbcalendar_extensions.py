#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import datetime

import mock

from cdb import auth, constants, sqlapi, testcase
from cdb.objects.operations import operation
from cdb.objects.org import User
from cs.calendar import CalendarException, CalendarProfile
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import RessourceDemand
from cs.pcs.resources import cdbcalendar_extensions as cal
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments import Resource, ResourcePoolAssignment

STANDARD_CAL_PROF = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


def setup_module():
    testcase.run_level_setup()


class TestCalendarException(testcase.RollbackTestCase):
    def create_instances(self):
        prof = CalendarProfile.Create(
            name="newCalProfile",
            valid_from=datetime.date(2023, 1, 1),
            valid_until=datetime.date(2023, 12, 31),
            mo_type_id='1',
            tu_type_id='1',
            we_type_id='1',
            th_type_id='2',
            fr_type_id='2',
            sa_type_id='2',
            su_type_id='2',
        )

        Task.Create(
            ce_baseline_id='',
            cdb_project_id="proj_id",
            task_id="task_id",
            end_time_fcast=datetime.date(2023, 12, 31),
            start_time_fcast=datetime.date(2023, 1, 1),
        )
        Project.Create(
            cdb_project_id="proj_id",
            name="project",
            calendar_profile_id=User.ByKeys(auth.persno).calendar_profile_id,
        )
        user = User.Create(
            personalnummer="test",
            name="name",
            active_account="1",
            calendar_profile_id=prof.cdb_object_id,
        )
        Resource.Create(referenced_oid=user.cdb_object_id)
        RessourceDemand.Create(
            cdb_demand_id="demand_id1",
            cdb_project_id="proj_id",
            task_id="task_id",
            resource_oid=user.cdb_object_id,
        )

        return prof.cdb_object_id

    def _assert_capa(self, resource_oid, expected):
        from cs.pcs.resources import capacity
        where = f"resource_oid = '{resource_oid}'"
        entries = [
            len(sqlapi.RecordSet2(table, where))
            for table in [
                capacity.CapacityScheduleDay.__maps_to__,
                capacity.CapacityScheduleWeek.__maps_to__,
                capacity.CapacityScheduleMonth.__maps_to__,
                capacity.CapacityScheduleQuarter.__maps_to__,
                capacity.CapacityScheduleHalfYear.__maps_to__,
            ]
        ]
        self.assertEqual(entries, expected)

    def test__signal_checkResourcesBySelf(self):
        user = User.Create(
            cdb_object_id="user",
            personalnummer="test",
            name="user name",
            active_account="1",
            is_resource=1,
            calendar_profile_id=STANDARD_CAL_PROF,
        )
        resource = Resource.Create(
            cdb_object_id="resource",
            referenced_oid=user.cdb_object_id,
        )
        pool = ResourcePool.Create(
            cdb_object_id="pool",
            name="pool name",
        )
        asgn = ResourcePoolAssignment.Create(
            cdb_object_id="pool_asgn",
            pool_oid=pool.cdb_object_id,
            resource_oid=resource.cdb_object_id,
            start_date=datetime.date(2023, 10, 1),
            end_date=datetime.date(2023, 10, 15),
            cdb_classname="cdbpcs_pool_person_assign",
            person_id=user.personalnummer,
        )

        # create calendar entry that is not the start of any non-day interval
        # e.g. not the 1st day of the month and not a monday
        cal_entry = cal.CalendarEntry.Create(
            cdb_object_id="cal_entry",
            day=datetime.date(2023, 10, 5),
            personalnummer=user.personalnummer,
            day_type_id="5",  # sick leave
        )

        ResourcePoolAssignment.createSchedules_many([asgn])

        self._assert_capa(resource.cdb_object_id, [9, 2, 1, 1, 1])
        operation(constants.kOperationDelete, cal_entry)
        self._assert_capa(resource.cdb_object_id, [10, 2, 1, 1, 1])

    def test_get_sql_where_condition_test(self):
        id = "cal_prof_id"
        args = {
            "cal_exc_end": '01.01.2023 00:00:00',
            "cal_exc_start": '01.01.2023 00:00:00',
            "cal_profile_id": id,
        }
        # date = sqlapi.SQLdbms_date(args["cal_exc_end"]
        projects = (
            f"SELECT p.cdb_project_id "
            f" FROM cdbpcs_project p "
            f" WHERE p.calendar_profile_id = '{id}'")

        perssql = (
            f"SELECT r.referenced_oid"
            f" FROM cdbpcs_resource_v r"
            f" WHERE r.calendar_profile_id='{id}'"  # getTableName -> cdbpcs_resource
        )

        demands = (
            f"SELECT d.task_id"
            f" FROM cdbpcs_prj_demand d"
            f" WHERE d.resource_oid in ({perssql})"
            f" AND d.cdb_project_id=cdbpcs_task.cdb_project_id")

        allocations = (
            f"SELECT a.task_id"
            f" FROM cdbpcs_prj_alloc a"
            f" WHERE a.resource_oid in ({perssql})"
            f" AND a.cdb_project_id=cdbpcs_task.cdb_project_id")

        actual = (
            f" cdbpcs_task.ce_baseline_id = ''"
            f" AND cdbpcs_task.cdb_project_id NOT IN ({projects})"  # why not in?
            f" AND (cdbpcs_task.task_id IN ({demands})"
            f"     OR cdbpcs_task.task_id IN ({allocations}))"
            f" AND ((cdbpcs_task.end_time_fcast is not null and "
            f"      '2023-01-01T00:00:00'<=cdbpcs_task.end_time_fcast))"
            f" AND ((cdbpcs_task.start_time_fcast is not null and "
            f"      cdbpcs_task.start_time_fcast<='2023-01-01T00:00:00'))"
        )
        with mock.patch.object(sqlapi, "SQLdbms_date", return_value="'2023-01-01T00:00:00'"):
            self.assertEqual(CalendarException.get_sql_where_condition(**args), actual)

    def test_adjustCalendarChangesForTasks(self):
        id = self.create_instances()
        exc = cal.CalendarException.Create(
            calendar_profile_id=id,
            day=datetime.date(2023, 1, 1),
        )
        args = {
            "day": '01.01.2023 00:00:00',
            "calendar_profile_id": id,
        }
        task = Task.ByKeys(task_id="task_id", cdb_project_id="proj_id")
        with mock.patch.object(Task, "adjustCalenderChanges", autospec=True):
            exc.adjustCalendarChangesForTasks(**args)
            Task.adjustCalenderChanges.assert_called_once_with(
                task._record, '01.01.2023 00:00:00', '01.01.2023 00:00:00')
