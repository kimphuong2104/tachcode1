#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access,too-many-lines

import unittest

import mock
import pytest
from cdb import testcase, ue

from cs.pcs import timeschedule


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TestTimeSchedule(unittest.TestCase):
    def test_getProjectPlanURL(self):
        "URL for time schedule is returned correctly"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "test_oid"
        self.assertEqual(
            ts.getProjectPlanURL(),
            "/info/timeschedule/test_oid",
            "URL is not created as expected.",
        )

    def test_on_CDBPCS_ProjectPlan_now(self):
        "Time schedule is called correctly"
        ctx = mock.Mock()
        ts = timeschedule.TimeSchedule()
        with mock.patch.object(
            timeschedule.TimeSchedule, "getProjectPlanURL", return_value="test_url"
        ):
            ts.on_CDBPCS_ProjectPlan_now(ctx)
        ctx.url.assert_called_once_with("test_url")

    @mock.patch.object(timeschedule, "auth", persno="my_test_user")
    @mock.patch.object(timeschedule.TimeSchedule, "delete_chart_setting")
    def test_on_cdbpcs_delete_settings_now(self, delete_chart_setting, auth):
        "Settings are deleted by operation"
        ctx = mock.Mock()
        ts = timeschedule.TimeSchedule()
        ts.on_cdbpcs_delete_settings_now(ctx)
        delete_chart_setting.assert_called_once_with(ctx, persno="my_test_user")

    def test__get_selection(self):
        "Get catalog selection"
        ctx = mock.Mock()
        with mock.patch.object(ctx, "start_selection"):
            ts = timeschedule.TimeSchedule()
            ctx.catalog_selection = None
            result = ts._get_selection(ctx, "test_catalog")
            self.assertEqual(result, [], "Result list is not empty.")

            ctx.catalog_selection = "selected object"
            result = ts._get_selection(ctx, "test_catalog")
            self.assertEqual(
                result,
                "selected object",
                "Result list does not contain value 'selected object'.",
            )

            ctx.start_selection.assert_called_once_with(catalog_name="test_catalog")

    @mock.patch.object(timeschedule.TimeSchedule, "_insertObject")
    def test_on_cdbpcs_add_project_now(self, _insertObject):
        "Project is added to a time schedule"
        ctx = mock.Mock()
        project = mock.Mock(spec=timeschedule.Project)
        project.cdb_project_id = "project id"
        ts = timeschedule.TimeSchedule()
        with mock.patch.object(timeschedule.Project, "ByKeys", return_value=project):
            with mock.patch.object(
                timeschedule.TimeSchedule, "_get_selection", return_value=[project]
            ):
                ts.on_cdbpcs_add_project_now(ctx)
                ts._get_selection.assert_called_once_with(
                    ctx, "pcs_projects_list_by_id"
                )
                ts._insertObject.assert_called_once_with(project)

    @mock.patch.object(timeschedule.TimeSchedule, "_insertObject")
    def test_on_cdbpcs_add_task_now(self, _insertObject):
        "Task is added to a time schedule"
        ctx = mock.Mock()
        task = mock.Mock(spec=timeschedule.Task)
        task.cdb_project_id = "project id"
        task.task_id = "task id"
        ts = timeschedule.TimeSchedule()
        with mock.patch.object(timeschedule.Task, "ByKeys", return_value=task):
            with mock.patch.object(
                timeschedule.TimeSchedule, "_get_selection", return_value=[task]
            ):
                ts.on_cdbpcs_add_task_now(ctx)
                ts._get_selection.assert_called_once_with(ctx, "pcs_tasks_list_by_uuid")
                ts._insertObject.assert_called_once_with(task)

    def test_getNextPosition_content_exists(self):
        "Get next position for time schedule content object; content exists"
        tsc1 = mock.Mock()
        tsc1.position = 10
        tsc2 = mock.Mock()
        tsc2.position = 5
        with mock.patch.object(
            timeschedule.TimeSchedule, "TimeScheduleContents", [tsc1, tsc2]
        ):
            ts = timeschedule.TimeSchedule()
            result = ts.getNextPosition()
            self.assertEqual(
                result,
                11,
                f"Result for next value ({result}) not as expected ({1}).",
            )

    def test_getNextPosition_no_content_exists(self):
        "Get next position for time schedule content object; no content exists"
        with mock.patch.object(timeschedule.TimeSchedule, "TimeScheduleContents", []):
            ts = timeschedule.TimeSchedule()
            result = ts.getNextPosition()
            self.assertEqual(
                result,
                1,
                f"Result for next value ({result}) not as expected ({1}).",
            )

    def test_setOrderBy(self):
        "Setting order of schedule content objects"
        tsc1 = mock.Mock(spec=timeschedule.TimeScheduleObject)
        tsc1.position = 0
        cobj1 = mock.Mock()
        cobj1.getAttributeValue.return_value = "successor"
        tsc1.getContentObject.return_value = cobj1

        tsc2 = mock.Mock(spec=timeschedule.TimeScheduleObject)
        tsc2.position = 0
        cobj2 = mock.Mock()
        cobj2.getAttributeValue.return_value = "predecessor"
        tsc2.getContentObject.return_value = cobj2

        ts = mock.Mock(spec=timeschedule.TimeSchedule)
        ts.TimeScheduleContents = [tsc1, tsc2]

        # actual call
        timeschedule.TimeSchedule.setOrderBy(ts, "test_attr")

        tsc1.getContentObject.assert_called_once()
        tsc2.getContentObject.assert_called_once()
        cobj1.getAttributeValue.assert_called_once_with("test_attr")
        cobj2.getAttributeValue.assert_called_once_with("test_attr")
        self.assertEqual(
            tsc1.position,
            2,
            "Objects not sorted as expected: "
            f"successor sorted to position {tsc1.position}",
        )
        self.assertEqual(
            tsc2.position,
            1,
            "Objects not sorted as expected: "
            f"predecessor sorted to position {tsc1.position}",
        )

    def test_insertObjects(self):
        "Insert list of objects into time schedule"
        with mock.patch.object(timeschedule.TimeSchedule, "_insertObject"):
            ts = timeschedule.TimeSchedule()
            obj1 = mock.Mock()
            obj2 = mock.Mock()
            ts.insertObjects([obj1, obj2])
            ts._insertObject.assert_has_calls(
                [mock.call(obj1), mock.call(obj2)], any_order=False
            )

    @mock.patch.object(timeschedule.TimeScheduleObject, "KeywordQuery")
    def test__insertObject_object_exists(self, KeywordQuery):
        "Insert object into time schedule that already contains it"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "schedule_oid"
        obj = mock.Mock()
        obj.cdb_object_id = "object_oid"

        # try to insert an object into time schedule
        ts._insertObject(obj)

        obj.createObject.assert_not_called()
        KeywordQuery.assert_called_once_with(
            view_oid="schedule_oid", content_oid="object_oid"
        )

    @mock.patch.object(timeschedule.TimeScheduleObject, "createObject")
    @mock.patch.object(
        timeschedule.TimeScheduleObject, "KeywordQuery", return_value=None
    )
    def test__insertObject_removable_project_does_not_contain(
        self, KeywordQuery, createObject
    ):
        "Insert removable project into time schedule that does not contain it"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "schedule_oid"

        obj = mock.Mock(autospec=timeschedule.Project)
        obj.cdb_object_id = "object_oid"
        obj.GetClassname.return_value = "name of class"
        obj.createObject.return_value = "new object"

        # try to insert an object into time schedule
        ts._insertObject(obj)
        createObject.assert_called_once_with(
            view_oid="schedule_oid",
            content_oid="object_oid",
            cdb_content_classname="name of class",
            unremovable=0,
        )
        obj.GetClassname.assert_called_once()
        KeywordQuery.assert_called_once_with(
            view_oid="schedule_oid", content_oid="object_oid"
        )

    @mock.patch.object(timeschedule.TimeScheduleObject, "createObject")
    @mock.patch.object(
        timeschedule.TimeScheduleObject, "KeywordQuery", return_value=None
    )
    def test__insertObject_unremovable_project_does_not_contain(
        self, KeywordQuery, createObject
    ):
        "Insert unremovable project into time schedule that does not contain it"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "schedule_oid"

        obj = mock.Mock(autospec=timeschedule.Project)
        obj.cdb_object_id = "object_oid"
        obj.GetClassname.return_value = "name of class"
        obj.createObject.return_value = "new object"

        # try to insert an object into time schedule
        ts._insertObject(obj, unremovable=True)
        createObject.assert_called_once_with(
            view_oid="schedule_oid",
            content_oid="object_oid",
            cdb_content_classname="name of class",
            unremovable=1,
        )
        obj.GetClassname.assert_called_once()
        KeywordQuery.assert_called_once_with(
            view_oid="schedule_oid", content_oid="object_oid"
        )

    @mock.patch.object(timeschedule.TimeScheduleObject, "createObject")
    @mock.patch.object(
        timeschedule.TimeScheduleObject, "KeywordQuery", return_value=None
    )
    def test__insertObject_removable_task_does_not_exist(
        self, KeywordQuery, createObject
    ):
        "Insert removable task into time schedule that does not contain it"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "schedule_oid"

        obj = mock.Mock(autospec=timeschedule.Task)
        obj.cdb_object_id = "object_oid"
        obj.GetClassname.return_value = "name of class"
        obj.createObject.return_value = "new object"

        # try to insert an object into time schedule
        ts._insertObject(obj)
        createObject.assert_called_once_with(
            view_oid="schedule_oid",
            content_oid="object_oid",
            cdb_content_classname="name of class",
            unremovable=0,
        )
        obj.GetClassname.assert_called_once()
        KeywordQuery.assert_called_once_with(
            view_oid="schedule_oid", content_oid="object_oid"
        )

    @mock.patch.object(timeschedule.TimeScheduleObject, "createObject")
    @mock.patch.object(
        timeschedule.TimeScheduleObject, "KeywordQuery", return_value=None
    )
    def test__insertObject_unremovable_task_does_not_contain(
        self, KeywordQuery, createObject
    ):
        "Insert unremovable task into time schedule that does not contain it"
        ts = timeschedule.TimeSchedule()
        ts.cdb_object_id = "schedule_oid"

        obj = mock.Mock(autospec=timeschedule.Task)
        obj.cdb_object_id = "object_oid"
        obj.GetClassname.return_value = "name of class"
        obj.createObject.return_value = "new object"

        # try to insert an object into time schedule
        ts._insertObject(obj, unremovable=True)
        createObject.assert_called_once_with(
            view_oid="schedule_oid",
            content_oid="object_oid",
            cdb_content_classname="name of class",
            unremovable=1,
        )
        obj.GetClassname.assert_called_once()
        KeywordQuery.assert_called_once_with(
            view_oid="schedule_oid", content_oid="object_oid"
        )

    @mock.patch.object(timeschedule.Project, "insertIntoTimeSchedule")
    @mock.patch.object(timeschedule.Project2TimeSchedule, "ByKeys")
    @mock.patch.object(timeschedule.Project2TimeSchedule, "Create")
    def test_insertProject_error_occurs(self, Create, ByKeys, insertIntoTimeSchedule):
        "Insert a project into time schedule: error occurs"
        ctx = mock.Mock("error")
        ctx.error = 1
        ts = timeschedule.TimeSchedule()

        # actual call
        ts.insertProject(ctx)
        insertIntoTimeSchedule.assert_not_called()
        ByKeys.assert_not_called()
        Create.assert_not_called()

    @mock.patch.object(timeschedule.Project, "insertIntoTimeSchedule")
    @mock.patch.object(timeschedule.Project2TimeSchedule, "ByKeys", return_value=None)
    @mock.patch.object(timeschedule.Project2TimeSchedule, "Create")
    def test_insertProject_no_project_assigned(
        self, Create, ByKeys, insertIntoTimeSchedule
    ):
        "Insert a project into time schedule: no project assigned"
        ctx = mock.Mock("error", "relationship_name")
        ctx.error = 0
        ctx.relationship_name = "cdbpcs_project2time_schedule"

        with mock.patch.object(
            timeschedule.TimeSchedule,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=None,
        ):
            ts = timeschedule.TimeSchedule()
            ts.cdb_object_id = "foo"
            ts.cdb_project_id = "bar"

            # actual call
            ts.insertProject(ctx)
            insertIntoTimeSchedule.assert_not_called()
            ByKeys.assert_not_called()
            Create.assert_not_called()

    @mock.patch.object(timeschedule.Project2TimeSchedule, "ByKeys", return_value=None)
    @mock.patch.object(timeschedule.Project2TimeSchedule, "Create")
    def test_insertProject_relationship_name_does_match(self, Create, ByKeys):
        "Intert a project into time schedule: relationship name does match"
        ctx = mock.Mock("error", "relationship_name")
        ctx.error = 0
        ctx.relationship_name = "cdbpcs_project2time_schedule"

        project = mock.MagicMock(spec=timeschedule.Project)
        with mock.patch.object(
            timeschedule.TimeSchedule,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=project,
        ):
            ts = timeschedule.TimeSchedule()
            ts.cdb_object_id = "foo"

            # actual call
            ts.insertProject(ctx)
            project.insertIntoTimeSchedule.assert_called_once_with(
                schedule_oid="foo", unremovable=True
            )
            ByKeys.assert_not_called()
            Create.assert_not_called()

    @mock.patch.object(timeschedule.Project, "insertIntoTimeSchedule")
    @mock.patch.object(
        timeschedule.Project2TimeSchedule, "ByKeys", return_value="rel found"
    )
    @mock.patch.object(timeschedule.Project2TimeSchedule, "Create")
    def test_insertProject_relationship_to_project_already_exists(
        self, Create, ByKeys, insertIntoTimeSchedule
    ):
        "Insert a project into time schedule: relationship to project already exists"
        ctx = mock.Mock("error", "relationship_name")
        ctx.error = 0
        ctx.relationship_name = "another relationship name"

        with mock.patch.object(
            timeschedule.TimeSchedule,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=None,
        ):
            ts = timeschedule.TimeSchedule()
            ts.cdb_object_id = "foo"
            ts.cdb_project_id = "bar"

            # actual call
            ts.insertProject(ctx)
            insertIntoTimeSchedule.assert_not_called()
            ByKeys.assert_called_once_with(
                time_schedule_oid="foo", cdb_project_id="bar"
            )
            Create.assert_not_called()

    @mock.patch.object(timeschedule.Project, "insertIntoTimeSchedule")
    @mock.patch.object(timeschedule.Project2TimeSchedule, "ByKeys", return_value=None)
    @mock.patch.object(timeschedule.Project2TimeSchedule, "Create")
    def test_insertProject_relationship_to_project_does_not_yet_exist(
        self, Create, ByKeys, insertIntoTimeSchedule
    ):
        "Insert a project into time schedule: relationship to project does not yet exist"
        ctx = mock.Mock("error", "relationship_name")
        ctx.error = 0
        ctx.relationship_name = "another relationship name"

        with mock.patch.object(
            timeschedule.TimeSchedule,
            "Project",
            new_callable=mock.PropertyMock,
            return_value=None,
        ):
            ts = timeschedule.TimeSchedule()
            ts.cdb_object_id = "foo"
            ts.cdb_project_id = "bar"

            # actual call
            ts.insertProject(ctx)
            insertIntoTimeSchedule.assert_not_called()
            ByKeys.assert_called_once_with(
                time_schedule_oid="foo", cdb_project_id="bar"
            )
            Create.assert_called_once_with(
                time_schedule_oid="foo", cdb_project_id="bar"
            )

    @mock.patch.object(timeschedule, "auth", persno="foo")
    def test_setSubject_id_already_set(self, auth):
        "Subject ID is not overwritten if already filled"
        ctx = mock.Mock()
        ts = timeschedule.TimeSchedule()
        ts.subject_id = "bar"
        ts.subject_type = "babel"

        # actual call
        ts.setSubject(ctx)
        self.assertEqual(ts.subject_id, "bar", "Subject ID has not been set properly.")
        self.assertEqual(
            ts.subject_type, "babel", "Subject type has not been set properly."
        )

    @mock.patch.object(timeschedule, "auth", persno="foo")
    def test_setSubject_id_is_not_set(self, auth):
        "Subject ID is filled if empty"
        ctx = mock.Mock()
        ts = timeschedule.TimeSchedule()
        ts.subject_id = None
        ts.subject_type = "babel"

        # actual call
        ts.setSubject(ctx)
        self.assertEqual(
            ts.subject_id, auth.persno, "Subject ID has not been set properly."
        )
        self.assertEqual(
            ts.subject_type, "Person", "Subject type has not been set properly."
        )

    @mock.patch.object(timeschedule.Project, "ByKeys", return_value=None)
    def test_setProjectID_no_ctx(self, ByKeys):
        "Project name is set within ctx object: no ctx given"
        ts = timeschedule.TimeSchedule()
        ts.cdb_project_id = None

        # actual call
        ts.setProjectID(None)
        self.assertEqual(
            ts.cdb_project_id, None, "Project ID should not have been set."
        )
        ByKeys.assert_not_called()

    @mock.patch.object(timeschedule.Project, "ByKeys", return_value=None)
    def test_setProjectID_ctx_without_parent(self, ByKeys):
        "Project name is set within ctx object: ctx has no parent"
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        ctx.parent = None
        ts = timeschedule.TimeSchedule()
        ts.cdb_project_id = None

        # actual call
        ts.setProjectID(ctx)
        self.assertEqual(
            ts.cdb_project_id, None, "Project ID should not have been set."
        )
        ByKeys.assert_not_called()
        ctx.set.assert_not_called()

    @mock.patch.object(timeschedule.Project, "ByKeys", return_value=None)
    def test_setProjectID_parent_has_no_project_id(self, ByKeys):
        "Project name is set within ctx object: parent has no project id"
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        parent = mock.MagicMock(spec=dict)
        del parent.cdb_project_id
        ctx.parent = parent
        ts = timeschedule.TimeSchedule()
        ts.cdb_project_id = None

        # actual call
        ts.setProjectID(ctx)
        self.assertEqual(
            ts.cdb_project_id, None, "Project ID should not have been set."
        )
        ByKeys.assert_not_called()
        ctx.set.assert_not_called()

    @mock.patch.object(timeschedule.Project, "ByKeys", return_value=None)
    def test_setProjectID_project_not_found(self, ByKeys):
        "Project name is set within ctx object: project is not found"
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        parent = mock.MagicMock()
        ctx.parent = parent
        r = {"cdb_project_id": "foo", "ce_baseline_id": "bar"}
        parent.__getitem__.side_effect = r.__getitem__
        ts = timeschedule.TimeSchedule()
        ts.cdb_project_id = None

        # actual call
        ts.setProjectID(ctx)
        self.assertEqual(
            ts.cdb_project_id, "foo", "Project ID has not been set properly."
        )
        ByKeys.assert_called_once_with(cdb_project_id="foo", ce_baseline_id="bar")
        ctx.set.assert_not_called()

    @mock.patch.object(timeschedule.Project, "ByKeys", return_value=None)
    def test_setProjectID_correctly(self, ByKeys):
        "Project name is correctly set within ctx object"
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        parent = mock.MagicMock()
        ctx.parent = parent
        r = {"cdb_project_id": "foo", "ce_baseline_id": "bar"}
        parent.__getitem__.side_effect = r.__getitem__

        project = mock.MagicMock(timeschedule.Project)
        project.project_name = "baz"
        ByKeys.return_value = project

        ts = timeschedule.TimeSchedule()
        ts.cdb_project_id = None

        # actual call
        ts.setProjectID(ctx)
        self.assertEqual(
            ts.cdb_project_id, "foo", "Project ID has not been set properly."
        )
        ByKeys.assert_called_once_with(cdb_project_id="foo", ce_baseline_id="bar")
        ctx.set.assert_called_once_with("project_name", "baz")

    @mock.patch.object(
        timeschedule,
        "MakeReportURL",
        return_value="this is my url cdb:texttodisplay not found",
    )
    def test_cdbpcs_timeschedule_ganttexport_ctx_given(self, MakeReportURL):
        "Gantt report is called: ctx is given"
        ctx = mock.MagicMock()
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)

        # actual call
        timeschedule.TimeSchedule.cdbpcs_timeschedule_ganttexport(ts, ctx)
        MakeReportURL.assert_called_once_with(ts, None, "", report_name="ExportGantt")
        ctx.url.assert_called_once_with("this is my url")

    @mock.patch.object(
        timeschedule,
        "MakeReportURL",
        return_value="this is my url cdb:texttodisplay not found",
    )
    def test_cdbpcs_timeschedule_ganttexport_ctx_not_given(self, MakeReportURL):
        "Gantt report is called: ctx is not given"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)

        # actual call
        with self.assertRaises(AttributeError):
            timeschedule.TimeSchedule.cdbpcs_timeschedule_ganttexport(ts, None)
        MakeReportURL.assert_called_once_with(ts, None, "", report_name="ExportGantt")

    @mock.patch.object(timeschedule, "system_args")
    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    def test_createObject_with_kwargs(self, operation, kOperationNew, system_args):
        "Create operation is called for class time schedule: kwargs given"
        kwargs = {"foo": "foo", "bar": "bar", "bass": "bass"}
        timeschedule.TimeSchedule.createObject(**kwargs)
        operation.assert_called_once_with(
            kOperationNew,
            timeschedule.TimeSchedule,
            system_args(skip_access_check=True),
            foo="foo",
            bar="bar",
            bass="bass",
        )

    @mock.patch.object(timeschedule, "system_args")
    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    def test_createObject_no_kwargs(self, operation, kOperationNew, system_args):
        "Create operation is called for class time schedule: no kwargs given"
        timeschedule.TimeSchedule.createObject()
        operation.assert_called_once_with(
            kOperationNew,
            timeschedule.TimeSchedule,
            system_args(skip_access_check=True),
        )

    @mock.patch.object(timeschedule, "assert_valid_project_resp")
    def test_checkResponsible_with_pid(self, validate):
        "[checkResponsible] schedule with project id"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_project_id = "foo"
        ctx = mock.MagicMock()
        ctx.sys_args = mock.MagicMock()
        ctx.sys_args.get_attribute_names.return_value = []
        self.assertIsNone(timeschedule.TimeSchedule.checkResponsible(ts, ctx))
        validate.assert_called_once_with(ctx)

    @mock.patch.object(timeschedule, "assert_valid_project_resp")
    def test_checkResponsible_no_pid_no_pcs_role(self, validate):
        "[checkResponsible] schedule without project id, subject anything but PCS Role"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_project_id = None
        self.assertIsNone(timeschedule.TimeSchedule.checkResponsible(ts, "ctx"))
        validate.assert_not_called()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkResponsible_no_pid_pcs_role(self, CDBMsg):
        "[checkResponsible] schedule without project id, subject PCS Role"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.subject_type = "PCS Role"
        ts.cdb_project_id = None
        with self.assertRaises(ue.Exception):
            timeschedule.TimeSchedule.checkResponsible(ts, None)
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_project_id_needed")

    @mock.patch.object(timeschedule, "kOperationDelete")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "KeywordQuery")
    def test_delete_chart_setting_persno_given(
        self, KeywordQuery, operation, kOperationDelete
    ):
        "Use operation to delete chart settings: persno is given"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_object_id = "foo"
        obj1 = mock.Mock()
        obj2 = mock.Mock()
        KeywordQuery.return_value = [obj1, obj2]

        # actual call
        timeschedule.TimeSchedule.delete_chart_setting(ts, None, "bar")
        KeywordQuery.assert_called_once_with(chart_oid="foo", persno="bar")
        operation.assert_has_calls(
            [mock.call(kOperationDelete, obj1), mock.call(kOperationDelete, obj2)],
            any_order=False,
        )

    @mock.patch.object(timeschedule, "kOperationDelete")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "KeywordQuery")
    def test_delete_chart_setting_no_persno(
        self, KeywordQuery, operation, kOperationDelete
    ):
        "Use operation to delete chart settings: no persno given"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_object_id = "foo"
        obj1 = mock.Mock()
        obj2 = mock.Mock()
        KeywordQuery.return_value = [obj1, obj2]

        # actual call
        timeschedule.TimeSchedule.delete_chart_setting(ts, None)
        KeywordQuery.assert_called_once_with(chart_oid="foo")
        operation.assert_has_calls(
            [mock.call(kOperationDelete, obj1), mock.call(kOperationDelete, obj2)],
            any_order=False,
        )

    def prepare_reveal_tso_in_schedule(self, tso_content_oid="not sub"):
        top = mock.Mock(cdb_object_id="top", cdb_project_id="project id")
        top.getParentObject.return_value = None
        top.GetClassname.return_value = "class name"
        middle = mock.Mock(cdb_object_id="middle", cdb_project_id="project id")
        middle.getParentObject.return_value = top
        middle.GetClassname.return_value = "class name"
        sub = mock.Mock(cdb_object_id="sub", cdb_project_id="project id")
        sub.getParentObject.return_value = middle
        sub.GetClassname.return_value = "class name"

        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_object_id = "foo"
        tso = mock.Mock(content_oid=tso_content_oid)
        ts.TimeScheduleContents = [tso]

        kwargs = {
            "view_oid": "foo",
            "content_oid": "top",
            "cdb_content_classname": "class name",
            "cdb_project_id": "project id",
        }
        return ts, sub, kwargs

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["bass"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_variant_1(
        self, auth, getSetting, setSetting, operation
    ):
        "Expand object structure and save settings: variant 1"
        # call of reveal_tso_in_schedule --> object NOT GIVEN, KEEP expanded ids
        # call of getSetting             --> parents NOT EXPANDED"
        # call of TimeScheduleContents   --> object NOT CONTAINED in ts objects

        ts, _, _ = self.prepare_reveal_tso_in_schedule()
        # actual call
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, None, True)
        self.assertEqual(
            str(error.exception), "'NoneType' object has no attribute 'getParentObject'"
        )
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_not_called()

    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["bass"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_variant_2(
        self, auth, getSetting, setSetting, operation, kOperationNew
    ):
        "Expand object structure and save settings: variant 2"
        # call of reveal_tso_in_schedule --> object GIVEN, KEEP expanded ids
        # call of getSetting             --> parents NOT EXPANDED
        # call of TimeScheduleContents   --> object NOT CONTAINED in ts objects

        ts, obj, kwargs = self.prepare_reveal_tso_in_schedule()
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, True)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_called_once_with(
            kOperationNew, timeschedule.TimeScheduleObject, **kwargs
        )
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle", "top", "bass"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["bass"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_variant_3(
        self, auth, getSetting, setSetting, operation, kOperationNew
    ):
        "Expand object structure and save settings: variant 3"
        # call of reveal_tso_in_schedule --> object GIVEN, DISCARD expanded ids
        # call of getSetting             --> parents NOT EXPANDED
        # call of TimeScheduleContents   --> object NOT CONTAINED in ts objects

        ts, obj, kwargs = self.prepare_reveal_tso_in_schedule()
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, False)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_called_once_with(
            kOperationNew, timeschedule.TimeScheduleObject, **kwargs
        )
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle", "top"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["top"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_variant_4(
        self, auth, getSetting, setSetting, operation, kOperationNew
    ):
        "Expand object structure and save settings: variant 4"
        # call of reveal_tso_in_schedule --> object GIVEN, KEEP expanded ids
        # call of getSetting             --> parents EXPANDED
        # call of TimeScheduleContents   --> object NOT CONTAINED in ts objects

        ts, obj, _ = self.prepare_reveal_tso_in_schedule()
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, True)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle", "top"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "kOperationNew")
    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["top"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_5(
        self, auth, getSetting, setSetting, operation, kOperationNew
    ):
        "Expand object structure and save settings: variant 5"
        # call of reveal_tso_in_schedule --> object GIVEN, DISCARD expanded ids
        # call of getSetting             --> parents EXPANDED
        # call of TimeScheduleContents   --> object NOT CONTAINED in ts objects

        ts, obj, kwargs = self.prepare_reveal_tso_in_schedule()
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, False)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_called_once_with(
            kOperationNew, timeschedule.TimeScheduleObject, **kwargs
        )
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=[])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_6(self, auth, getSetting, setSetting, operation):
        "Expand object structure and save settings: variant 6"
        # call of reveal_tso_in_schedule --> object NOT GIVEN, KEEP expanded ids
        # call of getSetting             --> parents NOT EXPANDED
        # call of TimeScheduleContents   --> object CONTAINED in ts objects

        ts, _, _ = self.prepare_reveal_tso_in_schedule("middle")
        # actual call
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, None, True)
        self.assertEqual(
            str(error.exception), "'NoneType' object has no attribute 'getParentObject'"
        )
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_not_called()

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=[])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_7(self, auth, getSetting, setSetting, operation):
        "Expand object structure and save settings: variant 7"
        # call of reveal_tso_in_schedule --> object GIVEN, KEEP expanded ids
        # call of getSetting             --> parents NOT EXPANDED
        # call of TimeScheduleContents   --> object CONTAINED in ts objects

        ts, obj, _ = self.prepare_reveal_tso_in_schedule("middle")
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, True)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=[])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_8(self, auth, getSetting, setSetting, operation):
        "Expand object structure and save settings: variant 8"
        # call of reveal_tso_in_schedule --> object GIVEN, DISCARD expanded ids
        # call of getSetting             --> parents NOT EXPANDED
        # call of TimeScheduleContents   --> object CONTAINED in ts objects

        ts, obj, _ = self.prepare_reveal_tso_in_schedule("middle")
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, False)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_called_once_with(
            "test_user", "foo", ["middle"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["middle"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_9(self, auth, getSetting, setSetting, operation):
        "Expand object structure and save settings: variant 9"
        # call of reveal_tso_in_schedule --> object GIVEN, KEEP expanded ids
        # call of getSetting             --> parents EXPANDED
        # call of TimeScheduleContents   --> object CONTAINED in ts objects

        ts, obj, _ = self.prepare_reveal_tso_in_schedule("top")
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, False)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_called_once_with(
            "test_user", "foo", ["top"], setting_name="#expandedId#"
        )

    @mock.patch.object(timeschedule, "operation")
    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["middle"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_reveal_tso_in_schedule_10(self, auth, getSetting, setSetting, operation):
        "Expand object structure and save settings: variant 10"
        # call of reveal_tso_in_schedule --> object GIVEN, DISCARD expanded ids
        # call of getSetting             --> parents EXPANDED
        # call of TimeScheduleContents   --> object CONTAINED in ts objects

        ts, obj, _ = self.prepare_reveal_tso_in_schedule("top")
        # actual call
        result = timeschedule.TimeSchedule.reveal_tso_in_schedule(ts, obj, False)
        self.assertEqual(result, None)
        getSetting.assert_called_once_with(
            "test_user", "foo", setting_name="#expandedId#"
        )
        operation.assert_not_called()
        setSetting.assert_called_once_with(
            "test_user", "foo", ["top"], setting_name="#expandedId#"
        )

    def get_object_structure(self):
        sub = mock.Mock(cdb_object_id="sub")
        sub.getChildrenObjects.return_value = []
        middle = mock.Mock(cdb_object_id="middle")
        middle.getChildrenObjects.return_value = [sub]
        top = mock.Mock(cdb_object_id="top")
        top.getChildrenObjects.return_value = [middle]
        return top

    def test__fully_expand_tso_in_schedule_given_object_and_empty_list(self):
        "Get object ids for expanded object structure: giving object and empty list"
        top = self.get_object_structure()
        ts = timeschedule.TimeSchedule()
        result = timeschedule.TimeSchedule._fully_expand_tso_in_schedule(ts, top, [])
        self.assertEqual(result, ["top", "middle"])

    def test__fully_expand_tso_in_schedule_given_object_and_list_with_object(self):
        "Get object ids for expanded object structure: giving object and list with object"
        top = self.get_object_structure()
        ts = timeschedule.TimeSchedule()
        result = timeschedule.TimeSchedule._fully_expand_tso_in_schedule(
            ts, top, ["another"]
        )
        self.assertEqual(result, ["another", "top", "middle"])

    def test__fully_expand_tso_in_schedule_given_object_and_no_list(self):
        "Get object ids for expanded object structure: giving object and no list"
        top = self.get_object_structure()
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(TypeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(ts, top, None)
        self.assertEqual(
            str(error.exception), "argument of type 'NoneType' is not iterable"
        )

    def test__fully_expand_tso_in_schedule_given_object_and_object(self):
        "Get object ids for expanded object structure: giving object and second object"
        top = self.get_object_structure()
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(TypeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(
                ts, top, mock.Mock()
            )
        self.assertEqual(
            str(error.exception), "argument of type 'Mock' is not iterable"
        )

    def test__fully_expand_tso_in_schedule_given_no_object_and_empty_list(self):
        "Get object ids for expanded object structure: giving no object and empty list"
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(ts, None, [])
        self.assertEqual(
            str(error.exception),
            "'NoneType' object has no attribute 'getChildrenObjects'",
        )

    def test__fully_expand_tso_in_schedule_given_no_object_and_list_with_object(self):
        "Get object ids for expanded object structure: giving no object and list with object"
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(
                ts, None, ["another"]
            )
        self.assertEqual(
            str(error.exception),
            "'NoneType' object has no attribute 'getChildrenObjects'",
        )

    def test__fully_expand_tso_in_schedule_given_no_object_and_no_list(self):
        "Get object ids for expanded object structure: giving no object and no list"
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(ts, None, None)
        self.assertEqual(
            str(error.exception),
            "'NoneType' object has no attribute 'getChildrenObjects'",
        )

    def test__fully_expand_tso_in_schedule_given_no_object_and_object(self):
        "Get object ids for expanded object structure: giving no object and second object"
        ts = timeschedule.TimeSchedule()
        with self.assertRaises(AttributeError) as error:
            timeschedule.TimeSchedule._fully_expand_tso_in_schedule(
                ts, None, mock.Mock()
            )
        self.assertEqual(
            str(error.exception),
            "'NoneType' object has no attribute 'getChildrenObjects'",
        )

    @mock.patch.object(timeschedule.ChartConfig, "setSetting")
    @mock.patch.object(timeschedule.ChartConfig, "getSetting", return_value=["ids"])
    @mock.patch.object(timeschedule, "auth", persno="test_user")
    def test_fully_expand_tso_in_schedule(self, auth, getSetting, setSetting):
        "Expand object structure and save settings"
        ts = mock.MagicMock(spec=timeschedule.TimeSchedule)
        ts.cdb_object_id = "foo"
        with mock.patch.object(
            ts, "_fully_expand_tso_in_schedule", return_value=["new ids"]
        ):
            # actual call
            timeschedule.TimeSchedule.fully_expand_tso_in_schedule(ts, "object")
            getSetting.assert_called_once_with(
                "test_user", "foo", setting_name="#expandedId#"
            )
            ts._fully_expand_tso_in_schedule.assert_called_once_with("object", ["ids"])
            setSetting.assert_called_once_with(
                "test_user", "foo", ["new ids"], setting_name="#expandedId#"
            )


if __name__ == "__main__":
    unittest.main()
