#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock

from cdb import testcase
from cs.pcs.projects import Project
from cs.pcs.resources.web.models import project_resource_schedules


def setUpModule():
    testcase.run_level_setup()


def create_project_data(cdb_project_id, with_resource_schedule=True):
    project = Project.Create(cdb_project_id=cdb_project_id, ce_baseline_id="")
    ts = project.createTimeSchedule(None)
    resource_schedule = None
    if with_resource_schedule:
        resource_schedule = ts.create_resource_schedule()
    return project, ts, resource_schedule


class CreateResourceSchedule(testcase.RollbackTestCase):
    def test_create_resource_schedule(self):
        _, ts, _ = create_project_data("dummy_project2", False)
        model = project_resource_schedules.CreateResourceSchedule()
        request = mock.MagicMock(json=ts.cdb_object_id)
        result = model.create_resource_schedule(request)
        result_keys = set(result.keys())
        if set(["cdb_object_id", "description"]) != result_keys:
            raise AssertionError("UUID or description missing: {}".format(result_keys))


class ProjectResourceSchedule(testcase.RollbackTestCase):
    """
    Tests the backend response for getting project resource schedules.
    """

    maxDiff = None

    def test_resolve_context(self):
        project, ts, resource_schedule = create_project_data("dummy_project")
        model = project_resource_schedules.ProjectResourceSchedules(
            project.cdb_object_id
        )
        self.assertEqual(
            model.get_project_resource_schedules(None),
            {
                "timeschedules": [
                    {
                        "cdb_object_id": ts.cdb_object_id,
                        "description": ts.GetDescription(),
                    }
                ],
                "resource_schedules": {
                    ts.cdb_object_id: [
                        {
                            "cdb_object_id": resource_schedule.cdb_object_id,
                            "description": resource_schedule.GetDescription(),
                        }
                    ]
                },
            },
        )
