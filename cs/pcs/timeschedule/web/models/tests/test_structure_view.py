#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import mock
import pytest
from cdb import testcase
from cdb.constants import kOperationNew
from cdb.validationkit import operation
from cs.platform.web.root.main import _get_dummy_request

from cs.pcs.projects import Project
from cs.pcs.projects.project_structure import util
from cs.pcs.projects.tasks import Task
from cs.pcs.timeschedule.web.models import structure_view


@pytest.mark.integration
class TSProjectViewIntegration(testcase.RollbackTestCase):
    def test_resolve_structure(self):
        def create_task(project):
            preset = {
                "cdb_project_id": project.cdb_project_id,
                "subject_id": "Projektmitglied",
                "subject_type": "PCS Role",
            }
            user_input = {
                "task_name": "Task",
                "start_time_fcast": "01.01.2014",
                "end_time_fcast": "01.01.2014",
                "automatic": 0,
            }
            return operation(kOperationNew, Task, user_input=user_input, preset=preset)

        user_input = {"project_name": "project name", "template": 0}
        project = operation(kOperationNew, Project, user_input=user_input)

        t1 = create_task(project)
        t2 = create_task(project)

        bl_p = operation("ce_baseline_create", project)

        # delete a task and create a new one
        t1.Delete()
        t3 = create_task(project)

        # get the baselined task
        t1_bl = bl_p.Tasks[0]
        t2_bl = bl_p.Tasks[1]

        request = _get_dummy_request()
        request.json = {
            "selectedBaselines": {project.cdb_object_id: bl_p.ce_baseline_id}
        }

        view = structure_view.TimeScheduleProjectView(project.cdb_object_id, request)
        # expected 5 sql statements are:
        # 1. resolve project structure
        # 2. resolve baseline project
        # 3. resolve baseline project structure
        # 4. get task data of project
        # 5. get task data of baseline project
        with testcase.max_sql(5):
            received = view.resolve()
        self.assertEqual(
            received,
            [
                # Project as root level
                util.PCS_LEVEL(
                    project.cdb_object_id, "cdbpcs_project", 0, bl_p.cdb_object_id
                ),
                # level of the deleted task represented by baseline task
                util.PCS_LEVEL(t1_bl.cdb_object_id, "cdbpcs_task", 1, None),
                # task existing in baseline and current project head
                util.PCS_LEVEL(t2.cdb_object_id, "cdbpcs_task", 1, t2_bl.cdb_object_id),
                # task existing only in current project head
                util.PCS_LEVEL(t3.cdb_object_id, "cdbpcs_task", 1, None),
            ],
        )


@pytest.mark.unit
class TimeScheduleProjectView(unittest.TestCase):
    def test_view_name(self):
        self.assertEqual(
            structure_view.TimeScheduleProjectView.view_name,
            "timeschedule_project",
        )

    @mock.patch.object(structure_view, "get_requested_baseline")
    @mock.patch.object(structure_view.util, "resolve_structure")
    def test_resolve_structure(self, resolve_structure, get_requested_baseline):
        x = mock.MagicMock(spec=structure_view.TimeScheduleProjectView)
        x.root_oid = "root_id"
        x.subprojects = True
        get_requested_baseline.return_value = None
        self.assertIsNone(structure_view.TimeScheduleProjectView.resolve_structure(x))
        self.assertEqual(x.pcs_levels, resolve_structure.return_value)
        resolve_structure.assert_called_once_with(
            x.root_oid,
            "cdbpcs_project",
            x.subprojects,
        )

    @mock.patch.object(structure_view, "merge_with_baseline_proj")
    @mock.patch.object(structure_view, "get_requested_baseline")
    @mock.patch.object(structure_view.Project, "Query")
    @mock.patch.object(structure_view.util, "resolve_structure")
    def test_resolve_structure(
        self, resolve_structure, Query, get_requested_baseline, merge_with_baseline_proj
    ):
        x = mock.MagicMock(spec=structure_view.TimeScheduleProjectView)
        x.root_oid = "root_id"
        x.subprojects = False
        x.request = {}
        Query.return_value.__getitem__.return_value = mock.MagicMock(
            cdb_object_id="obj1"
        )
        get_requested_baseline.return_value = "bl_oid1"
        self.assertIsNone(structure_view.TimeScheduleProjectView.resolve_structure(x))
        self.assertEqual(x.pcs_levels, merge_with_baseline_proj.return_value)
        resolve_structure.assert_has_calls(
            [
                mock.call(x.root_oid, "cdbpcs_project", x.subprojects),
                mock.call("obj1", "cdbpcs_project", False),
            ]
        )
        get_requested_baseline.assert_called_once_with(x.root_oid, x.request)
        Query.assert_called_once_with("ce_baseline_id='bl_oid1'")

    def test_get_full_data(self):
        x = mock.MagicMock(
            spec=structure_view.TimeScheduleProjectView,
            full_nodes="?",
        )
        self.assertIsNone(structure_view.TimeScheduleProjectView.get_full_data(x, 1))
        self.assertEqual(x.full_nodes, "?")

    def test_format_response(self):
        x = mock.MagicMock(
            spec=structure_view.TimeScheduleProjectView,
            pcs_levels=mock.MagicMock(),
        )
        self.assertEqual(
            structure_view.TimeScheduleProjectView.format_response(x),
            x.pcs_levels,
        )


if __name__ == "__main__":
    unittest.main()
