#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from datetime import date

import pytest

from cdb import testcase
from cdb.objects.operations import operation
from cdb.validationkit.SwitchRoles import run_with_project_roles
from cs.pcs import resources
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


def generate_baseline_of_project(prj, **user_input):
    kwargs = {"ce_baseline_name": "", "ce_baseline_comment": ""}
    kwargs.update(**user_input)

    @run_with_project_roles(prj, ["Projektleiter"])
    def _create_baseline(prj, **kwargs):
        return operation("ce_baseline_create", prj, **kwargs)

    return _create_baseline(prj, **kwargs)


class WithAdjustValuesMany(testcase.RollbackTestCase):
    def _create_data(self, resource_cls, with_baseline):
        """
        creates two test projects with two tasks each,
        one assigned to the entries in ``resource_cls`,
        the other one not

        Ptest.resources0
            Ttest.assigned0
            Ttest.unassigned0

        Ptest.resources1
            Ttest.assigned1
            Ttest.unassigned1

        for each assignment, three entries are created in ``resource_cls``:
            1. empty assignment_oid, matching cdb_workdays_v entry
            2. assignment_oid, matching cdbpcs_capa_sched_pd entry
            3. assignment_oid, no matching cdbpcs_capa_sched_pd entry

        we always assign the demand/allocation for 5 hours,
        tasks span 2 workdays and 1 capa entries each, so we expect
        2.5 and 5 hours per day, respectively

        returns a 2-tuple with these elements:
            1. a list containing the uuids of all four generated tasks
            2. a list containing the uuids of generated assignments
        """
        # late import so DB is connected
        from cs.pcs.resources import capacity

        task_uuids, assignment_uuids = [], []

        capa = capacity.CapacityScheduleDay.Create(
            assignment_oid="Ctest.integration",
            day=date(2022, 5, 16),
            resource_oid="irrelevant",
            pool_oid="irrelevant",
        )
        capa.Copy(day=date(2022, 5, 17))  # test date limits

        for project_no in range(2):
            project_id = "Ptest.resources{}".format(project_no)
            prj = Project.Create(
                cdb_project_id=project_id,
                # standard calendar profile
                calendar_profile_id="1cb4cf41-0f40-11df-a6f9-9435b380e702",
            )

            for task_id, assign in [
                ("Ttest.assigned{}".format(project_no), True),
                ("Ttest.unassigned{}".format(project_no), False),
            ]:
                task = Task.Create(
                    cdb_project_id=project_id,
                    task_id=task_id,
                    ce_baseline_id="",
                    start_time_fcast=date(2022, 5, 13),
                    end_time_fcast=date(2022, 5, 16),
                )
                task_uuids.append(task.cdb_object_id)

                if assign:
                    workday = resource_cls.Create(
                        cdb_project_id=project_id,
                        task_id=task_id,
                        hours=5,
                        cdb_demand_id="0-{}".format(task_id),
                        cdb_alloc_id="0-{}".format(task_id),
                    )
                    with_capa = workday.Copy(
                        assignment_oid=capa.assignment_oid,
                        cdb_demand_id="1-{}".format(task_id),
                        cdb_alloc_id="1-{}".format(task_id),
                    )
                    no_capa = workday.Copy(
                        assignment_oid="no capa entry",
                        cdb_demand_id="2-{}".format(task_id),
                        cdb_alloc_id="2-{}".format(task_id),
                    )
                    assignment_uuids += [
                        with_capa.cdb_object_id,
                        no_capa.cdb_object_id,
                        workday.cdb_object_id,
                    ]
            if with_baseline:
                generate_baseline_of_project(prj)
        return [task_uuids, assignment_uuids]

    def _adjust_values_many(self, resource_cls, with_baseline):
        task_uuids, assignment_uuids = self._create_data(resource_cls, with_baseline)

        # SQL statements:
        # 1. select res table to collect UUIDs and group by assignment y/n
        # 2. set workdays of assigned resources from capa schedule
        # 3. set workdays of unassigned resources from workdays_v
        # 4. set daily hours
        with testcase.max_sql(4):
            self.assertIsNone(resource_cls.adjust_values_many(task_uuids))

        result = {
            (x.assignment_oid, x.hours, x.workdays, x.hours_per_day)
            for x in resource_cls.KeywordQuery(cdb_object_id=assignment_uuids)
        }
        self.assertEqual(
            result,
            set([
                # assignment_oid, hours, workdays, hours_per_day
                (None, 5, 2, 2.5),
                ("no capa entry", 5, 0, 0),
                ("Ctest.integration", 5, 1, 5),
            ]),
        )


@pytest.mark.integration
class RessourceDemand(WithAdjustValuesMany):
    resource_cls = resources.RessourceDemand

    def test_adjust_values_many(self):
        self._adjust_values_many(self.resource_cls, False)

    def test_adjust_values_many_baselined(self):
        self._adjust_values_many(self.resource_cls, True)


@pytest.mark.integration
class RessourceAssignment(WithAdjustValuesMany):
    resource_cls = resources.RessourceAssignment

    def test_adjust_values_many(self):
        self._adjust_values_many(self.resource_cls, False)

    def test_adjust_values_many_baselined(self):
        self._adjust_values_many(self.resource_cls, True)


if __name__ == "__main__":
    unittest.main()
