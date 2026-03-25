#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import mock
import pytest
from cdb import testcase
from mock import MagicMock, call, patch

from cs.pcs.projects import Project
from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.tests import common
from cs.pcs.timeschedule.web import pcs_plugins

TEST_PROJECT_ID = "schedule_plugin_test"


def create_project():
    return Project.Create(
        cdb_project_id=TEST_PROJECT_ID,
        ce_baseline_id="",
        cdb_object_id=TEST_PROJECT_ID,
        project_name="Time Schedule Plugin Integration Test",
    )


def create_task(id, parent, position=None):
    return Task.Create(
        cdb_project_id=TEST_PROJECT_ID,
        ce_baseline_id="",
        cdb_object_id=id,
        task_id=id,
        parent_task=parent,
        task_name=id,
        position=position or 10,
    )


@pytest.mark.unit
class Utility(unittest.TestCase):
    @patch.object(pcs_plugins, "open", create=True)
    @patch.object(pcs_plugins.os.path, "abspath")
    @patch.object(pcs_plugins.os.path, "dirname")
    @patch.object(pcs_plugins.misc, "jail_filename")
    def test_load_query_pattern(self, jail_filename, dirname, abspath, mock_open):
        read = mock_open.return_value.__enter__.return_value.read
        self.assertEqual(
            pcs_plugins.load_query_pattern("foo"),
            read.return_value,
        )
        mock_open.assert_called_once_with(
            jail_filename.return_value, "r", encoding="utf8"
        )
        read.assert_called_once_with()
        jail_filename.assert_called_once_with(abspath.return_value, "foo")
        abspath.assert_called_once_with(dirname.return_value)
        dirname.assert_called_once_with(pcs_plugins.__file__)


@pytest.mark.unit
class ProjectPlugin(unittest.TestCase):
    @patch.object(pcs_plugins.ProjectPlugin, "description_pattern")
    def test_GetDescription_psp(self, description_pattern):
        "uses PSP if non-empty"
        record = MagicMock(psp_code="psp", project_name="name")
        description_pattern.format.return_value = "psp+name"
        self.assertEqual(pcs_plugins.ProjectPlugin.GetDescription(record), "psp+name")
        description_pattern.format.assert_called_once_with(
            record.psp_code,
            record.project_name,
        )

    @patch.object(pcs_plugins.ProjectPlugin, "description_pattern")
    def test_GetDescription_no_psp(self, description_pattern):
        "uses project ID if PSP is empty"
        record = MagicMock(
            psp_code=None,
            cdb_project_id="id",
            project_name="name",
        )
        description_pattern.format.return_value = "id+name"
        self.assertEqual(pcs_plugins.ProjectPlugin.GetDescription(record), "id+name")
        description_pattern.format.assert_called_once_with(
            record.cdb_project_id,
            record.project_name,
        )

    def test_GetRequiredFields(self):
        self.assertEqual(
            pcs_plugins.ProjectPlugin.GetRequiredFields(),
            set(
                [
                    pcs_plugins.ProjectPlugin.olc_attr,
                    pcs_plugins.ProjectPlugin.description_attrs[0],
                    pcs_plugins.ProjectPlugin.description_attrs[1],
                    pcs_plugins.ProjectPlugin.description_attrs[2],
                    pcs_plugins.ProjectPlugin.description_attrs[3],
                    pcs_plugins.ProjectPlugin.description_attrs[4],
                    pcs_plugins.ProjectPlugin.calculation_attrs[0],
                    pcs_plugins.ProjectPlugin.calculation_attrs[1],
                    pcs_plugins.ProjectPlugin.calculation_attrs[2],
                    pcs_plugins.ProjectPlugin.calculation_attrs[3],
                    pcs_plugins.ProjectPlugin.calculation_attrs[4],
                    pcs_plugins.ProjectPlugin.calculation_attrs[5],
                    pcs_plugins.ProjectPlugin.calculation_attrs[6],
                    pcs_plugins.ProjectPlugin.subject_id_attr,
                ]
            ),
        )

    @patch.object(pcs_plugins, "TimeScheduleProjectView")
    def test_ResolveStructure(self, TimeScheduleProjectView):
        "uses TimeScheduleProjectView to resolve structure"
        self.assertEqual(
            pcs_plugins.ProjectPlugin.ResolveStructure("foo", "request"),
            TimeScheduleProjectView.return_value.resolve.return_value,
        )
        TimeScheduleProjectView.assert_called_once_with("foo", "request")
        TimeScheduleProjectView.return_value.resolve.assert_called_once_with()

    @patch.object(pcs_plugins.ProjectPlugin, "subject_id_attr", "sid")
    @patch.object(pcs_plugins.ProjectPlugin, "subject_type_attr", "stype")
    def test_GetResponsible(self):
        self.assertEqual(
            pcs_plugins.ProjectPlugin.GetResponsible(
                {
                    "sid": "foo",
                    "stype": "bar",
                }
            ),
            {
                "subject_id": "foo",
                "subject_type": "Person",
            },
        )

    @patch.object(pcs_plugins.sqlapi, "RecordSet2")
    @patch.object(pcs_plugins, "getObjectByName")
    def test_GetClassReadOnlyFields(self, getObjectByName, recordset):
        "return class specific read only fields"
        mock_class_object = MagicMock()
        mock_class_object.class_specific_read_only_fields = ["foo"]
        getObjectByName.return_value = mock_class_object
        mock_record = MagicMock()
        mock_record.fqpyname = "bar"
        recordset.return_value = [mock_record]
        self.assertEqual(pcs_plugins.ProjectPlugin.GetClassReadOnlyFields(), ["foo"])
        recordset.assert_called_once_with(
            "switch_tabelle", "classname='cdbpcs_project'", ["fqpyname"]
        )
        getObjectByName.assert_called_once_with("bar")

    @patch.object(pcs_plugins, "get_oid_query_str", return_value="oid_query_str")
    @patch.object(pcs_plugins.sqlapi, "RecordSet2")
    def test_GetObjectReadOnlyFields(self, recordset, get_oid_query_str):
        mock_project_record = MagicMock(
            cdb_object_id="oid1",
            cdb_project_id="pid1",
            status=50,
            msp_active=True,
            is_group=True,
            auto_update_effort=True,
            auto_update_time=True,
        )
        mock_timesheet_record = MagicMock(cdb_project_id="pid1")
        # assign return values for consecutive calls
        recordset.side_effect = [
            # 1st for project records
            [mock_project_record],
            # 2nd for pids with timesheet
            [mock_timesheet_record],
        ]

        self.assertCountEqual(
            pcs_plugins.ProjectPlugin.GetObjectReadOnlyFields(["oid1"]),
            {
                "oid1": [
                    "template",
                    "percent_complet",
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "auto_update_time",
                    "start_time_act",
                    "end_time_act",
                    "effort_act",
                    "effort",
                ]
            },
        )
        recordset.assert_has_calls(
            [
                call(
                    pcs_plugins.ProjectPlugin.table_name,
                    "oid_query_str",
                    access="read",
                ),
                call(
                    "cdbpcs_time_sheet",
                    "oid_query_str",
                    ["cdb_project_id"],
                ),
            ]
        )
        get_oid_query_str.assert_has_calls(
            [call(["oid1"]), call(["pid1"], attr="cdb_project_id")]
        )

    def test_GetObjectReadOnlyFields_no_oids(self):
        "no oids given"

        self.assertEqual(pcs_plugins.ProjectPlugin.GetObjectReadOnlyFields([]), {})


@pytest.mark.integration
class ProjectPluginIntegration(testcase.RollbackTestCase):
    def test_ResolveStructure(self):
        """
        returns structure sorted by position and cdb_object_id
        Project
            10 Task A
                10 Task A.1
            10 Task B (created first)
                10 Task B.1
            20 Task C
                10 Task C.1
        """
        project = create_project()
        create_task("B", "")
        create_task("A", "")
        create_task("C", "", 20)
        create_task("B.1", "B")
        create_task("C.1", "C")
        create_task("A.1", "A")

        params = {"subprojects": "0"}
        req = mock.Mock()
        req.json = {}
        req.params = params

        self.assertEqual(
            pcs_plugins.ProjectPlugin.ResolveStructure(project.cdb_object_id, req),
            [
                PCS_LEVEL(TEST_PROJECT_ID, "cdbpcs_project", level=0),
                PCS_LEVEL("A", "cdbpcs_task", level=1),
                PCS_LEVEL("A.1", "cdbpcs_task", level=2),
                PCS_LEVEL("B", "cdbpcs_task", level=1),
                PCS_LEVEL("B.1", "cdbpcs_task", level=2),
                PCS_LEVEL("C", "cdbpcs_task", level=1),
                PCS_LEVEL("C.1", "cdbpcs_task", level=2),
            ],
        )

    def test_ResolveRecords_without_joined_attributes(self):
        "Test ResovleRecords without joined attributes"
        project = common.generate_project()
        project.project_name = "Time Schedule Plugin Integration Test"
        records = pcs_plugins.ProjectPlugin.ResolveRecords([project.cdb_object_id])[0]
        self.assertEqual(
            records.record.project_name, "Time Schedule Plugin Integration Test"
        )
        self.assertFalse(hasattr(records.record, "joined_status_name_en"))

    def test_ResolveRecords_with_joined_attribute(self):
        "Test ResovleRecords with joined attributes"
        project = common.generate_project()
        project.project_name = "Time Schedule Plugin Integration Test"
        pcs_plugins.ProjectPlugin.table_view = "cdbpcs_project_v"
        records = (
            pcs_plugins.ProjectPlugin.ResolveRecords([project.cdb_object_id])[0],
        )
        del pcs_plugins.ProjectPlugin.table_view
        self.assertEqual(
            records[0].record.project_name, "Time Schedule Plugin Integration Test"
        )
        self.assertTrue(hasattr(records[0][1], "joined_status_name_en"))
        self.assertEqual(records[0].record.joined_status_name_en, "New")

    def test__register_task_plugin(self):
        callback = MagicMock()
        self.assertEqual(pcs_plugins._register_task_plugin(callback), None)
        callback.assert_called_once_with(pcs_plugins.TaskPlugin)


@pytest.mark.unit
class TaskPlugin(unittest.TestCase):
    @patch.object(pcs_plugins.TaskPlugin, "description_pattern")
    def test_GetDescription(self, description_pattern):
        "uses name as-is"
        record = MagicMock(task_name="foo")
        self.assertEqual(pcs_plugins.TaskPlugin.GetDescription(record), "foo")
        description_pattern.format.assert_not_called()

    def test_GetRequiredFields(self):
        self.assertEqual(
            pcs_plugins.TaskPlugin.GetRequiredFields(),
            set(
                [
                    pcs_plugins.TaskPlugin.olc_attr,
                    pcs_plugins.TaskPlugin.description_attrs[0],
                    pcs_plugins.TaskPlugin.description_attrs[1],
                    pcs_plugins.TaskPlugin.description_attrs[2],
                    pcs_plugins.TaskPlugin.calculation_attrs[0],
                    pcs_plugins.TaskPlugin.calculation_attrs[1],
                    pcs_plugins.TaskPlugin.calculation_attrs[2],
                    pcs_plugins.TaskPlugin.calculation_attrs[3],
                    pcs_plugins.TaskPlugin.calculation_attrs[4],
                    pcs_plugins.TaskPlugin.calculation_attrs[5],
                    pcs_plugins.TaskPlugin.calculation_attrs[6],
                    pcs_plugins.TaskPlugin.calculation_attrs[7],
                    pcs_plugins.TaskPlugin.calculation_attrs[8],
                    pcs_plugins.TaskPlugin.calculation_attrs[9],
                    pcs_plugins.TaskPlugin.subject_id_attr,
                    pcs_plugins.TaskPlugin.subject_type_attr,
                    pcs_plugins.TaskPlugin.task_id_attr,
                ]
            ),
        )

    @patch.object(pcs_plugins, "resolve_query")
    @patch.object(pcs_plugins, "load_query_pattern")
    @patch.object(pcs_plugins, "get_query_pattern")
    def test_ResolveStructure(
        self, get_query_pattern, load_query_pattern, resolve_query
    ):
        "returns pcs_levels of task structure"
        self.assertEqual(
            pcs_plugins.TaskPlugin.ResolveStructure("foo", "request"),
            resolve_query.return_value,
        )
        get_query_pattern.assert_called_once_with(
            "task_structure",
            load_query_pattern,
        )
        get_query_pattern.return_value.format.assert_called_once_with(
            oid="foo",
        )
        resolve_query.assert_called_once_with(
            get_query_pattern.return_value.format.return_value,
        )
        load_query_pattern.assert_not_called()

    @patch.object(pcs_plugins.TaskPlugin, "subject_id_attr", "sid")
    @patch.object(pcs_plugins.TaskPlugin, "subject_type_attr", "stype")
    def test_GetResponsible(self):
        self.assertEqual(
            pcs_plugins.TaskPlugin.GetResponsible(
                {
                    "sid": "foo",
                    "stype": "bar",
                }
            ),
            {
                "subject_id": "foo",
                "subject_type": "bar",
            },
        )

    @patch.object(pcs_plugins.sqlapi, "RecordSet2")
    @patch.object(pcs_plugins, "getObjectByName")
    def test_GetClassReadOnlyFields(self, getObjectByName, recordset):
        "return class specific read only fields"
        mock_class_object = MagicMock()
        mock_class_object.class_specific_read_only_fields = ["foo"]
        getObjectByName.return_value = mock_class_object
        mock_record = MagicMock()
        mock_record.fqpyname = "bar"
        recordset.return_value = [mock_record]
        self.assertEqual(pcs_plugins.TaskPlugin.GetClassReadOnlyFields(), ["foo"])
        recordset.assert_called_once_with(
            "switch_tabelle", "classname='cdbpcs_task'", ["fqpyname"]
        )
        getObjectByName.assert_called_once_with("bar")

    @patch.object(pcs_plugins, "get_oid_query_str", return_value="oid_query_str")
    @patch.object(pcs_plugins.sqlapi, "RecordSet2")
    def test_GetObjectReadOnlyFields(self, recordset, get_oid_query_str):
        # assign return values for consecutive calls
        # 1st for task records
        task = MagicMock(
            cdb_object_id="oid1",
            cdb_project_id="pid1",
            status=50,
            effort_act=True,
            is_group=True,
            auto_update_effort=True,
            auto_update_time=True,
            milestone=False,
        )
        task2 = MagicMock(
            cdb_object_id="oid2",
            cdb_project_id="pid2",
            status=0,
            effort_act=False,
            is_group=False,
            auto_update_effort=False,
            auto_update_time=False,
            milestone=True,
            start_is_early=False,
        )
        # 2nd for msp_active and locked by other user of project
        project = MagicMock(
            cdb_project_id="pid1",
            ce_baseline_id="",
            msp_active=True,
            locked_by="bar",
        )
        project2 = MagicMock(
            cdb_project_id="pid2",
            ce_baseline_id="",
            msp_active=False,
            locked_by=None,
        )
        recordset.side_effect = [[task, task2], [project, project2]]

        result = pcs_plugins.TaskPlugin.GetObjectReadOnlyFields(["oid1", "oid2"])

        self.assertEqual(sorted(list(result)), sorted(["oid1", "oid2"]))

        self.assertEqual(
            sorted(result["oid1"]),
            sorted(
                [
                    "parent_task_name",
                    "parent_task",
                    "milestone",
                    "position",
                    "percent_complet",
                    "start_time_act",
                    "end_time_act",
                    "effort_act",
                    "effort",
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "auto_update_time",
                    "start_is_early",
                    "end_is_early",
                    "automatic",
                    "constraint_type",
                    "constraint_date",
                    "task_name",
                    "mapped_constraint_type_name",
                    "predecessors",
                    "successors",
                ]
            ),
        )

        self.assertEqual(
            sorted(result["oid2"]),
            sorted(
                [
                    "percent_complet",
                    "effort_fcast",
                    "effort_plan",
                    "effort_act",
                    "days_fcast",
                    "start_time_fcast",
                    "start_time_act",
                    "end_time_act",
                ]
            ),
        )

        recordset.assert_has_calls(
            [
                call("cdbpcs_task", "oid_query_str"),
                call("cdbpcs_project", "oid_query_str And ce_baseline_id=''"),
            ]
        )
        self.assertEqual(recordset.call_count, 2)
        get_oid_query_str.assert_has_calls(
            [call(["oid1", "oid2"]), call(["pid1", "pid2"], attr="cdb_project_id")]
        )
        self.assertEqual(get_oid_query_str.call_count, 2)

    def test_GetObjectReadOnlyFields_no_oids(self):
        "no oids given"

        self.assertEqual(pcs_plugins.TaskPlugin.GetObjectReadOnlyFields([]), {})


@pytest.mark.integration
class TaskPluginIntegration(testcase.RollbackTestCase):
    def test_ResolveStructure(self):
        """
        returns structure sorted by position and cdb_object_id
        Task root
            10 Task A
                10 Task A.1
            10 Task B (created first)
                10 Task B.1
            20 Task C
                10 Task C.1
        """
        create_project()
        create_task("root", "")
        create_task("B", "root")
        create_task("A", "root")
        create_task("C", "root", 20)
        create_task("B.1", "B")
        create_task("C.1", "C")
        create_task("A.1", "A")

        self.assertEqual(
            pcs_plugins.TaskPlugin.ResolveStructure("root", "request"),
            [
                PCS_LEVEL("root", "cdbpcs_task", level=0),
                PCS_LEVEL("A", "cdbpcs_task", level=1),
                PCS_LEVEL("A.1", "cdbpcs_task", level=2),
                PCS_LEVEL("B", "cdbpcs_task", level=1),
                PCS_LEVEL("B.1", "cdbpcs_task", level=2),
                PCS_LEVEL("C", "cdbpcs_task", level=1),
                PCS_LEVEL("C.1", "cdbpcs_task", level=2),
            ],
        )


@pytest.mark.unit
class RegisterPlugins(unittest.TestCase):
    def test__register_project_plugin(self):
        callback = MagicMock()
        self.assertEqual(pcs_plugins._register_project_plugin(callback), None)
        callback.assert_called_once_with(pcs_plugins.ProjectPlugin)

    def test__register_task_plugin(self):
        callback = MagicMock()
        self.assertEqual(pcs_plugins._register_task_plugin(callback), None)
        callback.assert_called_once_with(pcs_plugins.TaskPlugin)


if __name__ == "__main__":
    unittest.main()
