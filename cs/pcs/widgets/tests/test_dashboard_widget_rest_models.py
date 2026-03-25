#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from datetime import date, timedelta

import cdb
import mock
import webob
from cdb import testcase

from cs.pcs.widgets import widget_rest_models


class WithProjectAccess:
    @property
    def model(self):
        raise RuntimeError("implemented by subclasses")

    def test_init_None(self):
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model(None)

    def test_init_unknown(self):
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model("not a rest key")

    def test_init_baseline(self):
        "reise exception, when baseline_id not empty string"
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model("cdb_project_id@ce_baseline_id")

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_init_denied(self, Project):
        mock_project = mock.MagicMock()
        mock_project.CheckAccess.return_value = False
        Project.return_value = mock_project

        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model("unreadable project")


class RatingModelTest(testcase.RollbackTestCase, WithProjectAccess):
    model = widget_rest_models.RatingModel

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_rating(self, Project):
        mock_project = mock.PropertyMock()
        type(mock_project).rating = "A"
        type(mock_project).rating_descr = "B"
        Project.return_value = mock_project

        self.assertEqual(
            self.model("x@").get_rating(),
            {
                "rating": "A",
                "rating_descr": "B",
            },
        )


class InTimeModelTest(testcase.RollbackTestCase, WithProjectAccess):
    model = widget_rest_models.InTimeModel

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_in_time_tasks(self, Project):
        self.maxDiff = None
        mock_project = mock.PropertyMock()
        mock_timeschedule = mock.PropertyMock(
            cdb_object_id="OID", status=0, cdb_status_txt="New"
        )
        mock_ts_name = mock.PropertyMock(return_value="test")
        type(mock_timeschedule).name = mock_ts_name
        type(mock_project).PrimaryTimeSchedule = [mock_timeschedule]
        type(mock_project).Tasks = [1]
        mock_project.get_ev_pv_for_project.return_value = (0.0, 0.0)
        mock_project.get_schedule_state.return_value = "ABCDEFG"
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_in_time(),
            {
                "efficiency": "D",
                "variance": "C",
                "projectHasNoTask": False,
                "timeSchedules": {
                    mock_timeschedule.getProjectPlanURL.return_value: {
                        "name": "test",
                        "status": "New",
                    }
                },
            },
        )

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_in_time_no_tasks(self, Project):
        mock_project = mock.PropertyMock(PrimaryTimeSchedule=[], Tasks=[])
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_in_time(),
            {
                "projectHasNoTask": True,
                "timeSchedules": {},
            },
        )


class InBudgetModelTest(testcase.RollbackTestCase, WithProjectAccess):
    model = widget_rest_models.InBudgetModel

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_in_budget_tasks(self, Project):
        mock_project = mock.PropertyMock()
        mock_project.get_ev_pv_for_project.return_value = (0.0, 0.0)
        mock_project.get_cost_state.return_value = "ABCDEFG"
        type(mock_project).Tasks = [1]
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_in_budget(),
            {
                "efficiency": "D",
                "variance": "C",
                "projectHasNoTask": False,
            },
        )

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_in_budget_no_tasks(self, Project):
        mock_project = mock.PropertyMock()
        Project.return_value = mock_project
        self.assertEqual(self.model("x@").get_in_budget(), {"projectHasNoTask": True})


class RemainingTimeModelTest(testcase.RollbackTestCase, WithProjectAccess):
    model = widget_rest_models.RemainingTimeModel

    @mock.patch.object(widget_rest_models, "getWorkdays", return_value="foo")
    def test_get_remaining_time(self, getWorkdays):
        model = mock.Mock(
            spec=self.model,
            cdb_project_id="mock_pid",
            project=mock.Mock(
                start_time_fcast=date(2019, 8, 5),
                end_time_fcast=date(2019, 9, 2),
                status=42,
                EXECUTION=mock.MagicMock(status=42),
            ),
        )
        valid_until = date.today() + timedelta(days=1)
        model.project.CalendarProfile.valid_until = valid_until
        self.assertEqual(
            self.model.get_remaining_time(model),
            {
                "status": "Execution",
                "plannedStart": "2019-08-05",
                "plannedEnd": "2019-09-02",
                "projectHasNoDatesSet": False,
                "remainingWorkDays": "foo",
                "endDateCalendarProfile": valid_until.strftime("%Y-%m-%d"),
            },
        )
        getWorkdays.assert_called_with(
            model.project.cdb_project_id,
            date.today(),
            model.project.end_time_fcast,
        )

    @mock.patch.object(widget_rest_models, "getWorkdays", return_value="foo")
    def test_get_remaining_time_calendar_overdue(self, getWorkdays):
        model = mock.Mock(
            spec=self.model,
            cdb_project_id="mock_pid",
            project=mock.Mock(
                start_time_fcast=date(2019, 8, 5),
                end_time_fcast=date(2019, 9, 2),
                status=42,
                EXECUTION=mock.MagicMock(status=42),
            ),
        )
        valid_until = date.today() - timedelta(days=1)
        model.project.CalendarProfile.valid_until = valid_until
        self.assertEqual(
            self.model.get_remaining_time(model),
            {
                "status": "Execution",
                "plannedStart": "2019-08-05",
                "plannedEnd": "2019-09-02",
                "projectHasNoDatesSet": False,
                "remainingWorkDays": "foo",
                "endDateCalendarProfile": valid_until.strftime("%Y-%m-%d"),
            },
        )
        getWorkdays.assert_called_with(
            model.project.cdb_project_id,
            valid_until,
            model.project.end_time_fcast,
        )

    def test_get_remaining_time_missing_date(self):
        model = mock.Mock(
            spec=self.model,
            cdb_project_id="mock_pid",
            project=mock.Mock(
                start_time_fcast=None,
                end_time_fcast=None,
            ),
        )
        model.project.CalendarProfile.valid_until = None

        self.assertEqual(
            self.model.get_remaining_time(model),
            {
                "status": "NotExecNorFin",
                "plannedStart": None,
                "plannedEnd": None,
                "projectHasNoDatesSet": True,
                "remainingWorkDays": None,
                "endDateCalendarProfile": None,
            },
        )


class UnassignedRolesModelTest(testcase.RollbackTestCase, WithProjectAccess):
    model = widget_rest_models.UnassignedRolesModel

    def get_mocked_task(self, name, is_running):
        mock_task = mock.PropertyMock()
        type(mock_task).task_name = name
        if is_running:
            type(mock_task).status = 42
            type(mock_task.EXECUTION).status = 42
        else:
            type(mock_task).status = 42
            type(mock_task.READY).status = 42
        return mock_task

    def get_mocked_role(self, name, tasks, owners):
        mock_role = mock.PropertyMock()
        type(mock_role).role_id = name
        type(mock_role).Tasks = tasks
        type(mock_role).Owners = list(range(owners))
        return mock_role

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_unassigned_roles_and_tasks_danger(self, Project):
        self.maxDiff = None
        mock_project = mock.PropertyMock()
        type(mock_project).Roles = [
            self.get_mocked_role(
                "ROLE NOK",
                [
                    self.get_mocked_task("RUNNING TASK NOK", True),
                    self.get_mocked_task("PLANNED TASK NOK", False),
                ],
                0,
            ),
            self.get_mocked_role(
                "ROLE OK",
                [
                    self.get_mocked_task("RUNNING TASK OK", True),
                    self.get_mocked_task("PLANNED TASK OK", False),
                ],
                1,
            ),
            self.get_mocked_role("IRRELEVANT ROLE", [], 1),
        ]
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_unassigned_roles_and_tasks(),
            {
                "status": "danger",
                "totalNumberOfTasks": 2,
                "totalUnassignedRoles": 1,
                "otherRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 2,
                    "Total_tasks": 2,
                    "roles_id": ["ROLE NOK"],
                },
                "newRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 0,
                    "Total_tasks": 0,
                    "roles_id": [],
                },
            },
        )

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_unassigned_roles_and_tasks_danger_2(self, Project):
        self.maxDiff = None
        mock_project = mock.PropertyMock()
        type(mock_project).Roles = [
            self.get_mocked_role(
                "ROLE NOK",
                [
                    self.get_mocked_task("PLANNED TASK NOK", False),
                ],
                0,
            ),
            self.get_mocked_role(
                "ROLE OK",
                [
                    self.get_mocked_task("RUNNING TASK OK", True),
                    self.get_mocked_task("PLANNED TASK OK", False),
                ],
                1,
            ),
            self.get_mocked_role("IRRELEVANT ROLE", [], 1),
        ]
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_unassigned_roles_and_tasks(),
            {
                "status": "danger",
                "totalNumberOfTasks": 1,
                "totalUnassignedRoles": 1,
                "otherRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 1,
                    "Total_tasks": 1,
                    "roles_id": ["ROLE NOK"],
                },
                "newRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 0,
                    "Total_tasks": 0,
                    "roles_id": [],
                },
            },
        )

    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_unassigned_roles_and_tasks_success(self, Project):
        self.maxDiff = None
        mock_project = mock.PropertyMock()
        type(mock_project).Roles = [
            self.get_mocked_role("ROLE NOK", [], 0),
            self.get_mocked_role(
                "ROLE OK",
                [
                    self.get_mocked_task("RUNNING TASK OK", True),
                    self.get_mocked_task("PLANNED TASK OK", False),
                ],
                1,
            ),
            self.get_mocked_role("IRRELEVANT ROLE", [], 1),
        ]
        Project.return_value = mock_project
        self.assertEqual(
            self.model("x@").get_unassigned_roles_and_tasks(),
            {
                "status": "success",
                "totalNumberOfTasks": 0,
                "totalUnassignedRoles": 0,
                "otherRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 0,
                    "Total_tasks": 0,
                    "roles_id": [],
                },
                "newRolesAndTasks": {
                    "cdbpcs_cl_item": 0,
                    "cdbpcs_checklist": 0,
                    "cdbpcs_issue": 0,
                    "cdbpcs_task": 0,
                    "Total_tasks": 0,
                    "roles_id": [],
                },
            },
        )


class ProjectNotesModelTest(testcase.RollbackTestCase):
    model = widget_rest_models.ProjectNotesModel

    def test_init_None(self):
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model(None, None)

    def test_init_unknown(self):
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model("not a cdb_project_id", "not a cdb_object_id")

    @mock.patch.object(widget_rest_models.NotesContent, "ByKeys")
    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_init_denied(self, Project, NotesContent):
        mock_project = mock.MagicMock()
        mock_project.CheckAccess.return_value = False
        Project.return_value = mock_project

        mock_notes_content = mock.MagicMock()
        NotesContent.return_value = mock_notes_content

        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model("unreadable project", "unreadable notes")

    @mock.patch.object(cdb.util, "PersonalSettings")
    @mock.patch.object(widget_rest_models.NotesContent, "ByKeys")
    @mock.patch.object(widget_rest_models.Project, "ByKeys")
    def test_get_notes(self, Project, NotesContent, PersSet):
        self.maxDiff = None
        mock_project = mock.PropertyMock()
        mock_project.CheckAccess.return_value = True
        Project.return_value = mock_project
        NotesContent.return_value = None
        getDefault = mock.MagicMock(return_value="foo_text")
        PersSet.return_value = mock.PropertyMock(getValueOrDefaultForUser=getDefault)

        with mock.patch.object(cdb.i18n, "default", return_value="foo"):
            return_value = self.model("project_id@", "notes_id").get_notes()

        self.assertEqual(
            return_value,
            {
                "content": "foo_text",
                "isAllowedToModify": True,
            },
        )
        getDefault.assert_has_calls(
            [
                mock.call(
                    "cs.pcs.widgets.project_notes_default_txt_en", "", "caddok", ""
                ),
                mock.call(
                    "cs.pcs.widgets.project_notes_default_txt_foo",
                    "",
                    "caddok",
                    "foo_text",
                ),
            ]
        )


class ListModelTest(testcase.RollbackTestCase):
    model = widget_rest_models.ListModel

    @mock.patch.object(widget_rest_models, "auth", persno="foo_user")
    @mock.patch.object(widget_rest_models.logging, "error")
    @mock.patch.object(widget_rest_models.sqlapi, "quote", return_value="foo")
    @mock.patch.object(
        widget_rest_models, "get_and_check_object", return_value="foo_project"
    )
    @mock.patch.object(widget_rest_models.ListConfig, "Query", return_value=[])
    def test___init__no_config_no_access(
        self, LC_Query, get_and_check_object, sql_quote, logging_error, auth_persno
    ):
        """Testing for if no config exists or logged in user has no read access"""

        mock_model = mock.MagicMock(spec=self.model)

        self.model.__init__(
            mock_model,
            "foo_cdb_project_id@",
            "foo_list_config_name",
        )

        self.assertEqual(mock_model.list_config_name, "foo_list_config_name")
        self.assertEqual(mock_model.cdb_project_id, "foo_cdb_project_id")
        self.assertEqual(mock_model.rest_key, "foo_cdb_project_id@")
        self.assertIsNone(mock_model.list_config)

        get_and_check_object.assert_called_once_with(
            widget_rest_models.Project,
            "read",
            cdb_project_id="foo_cdb_project_id",
            ce_baseline_id="",
        )
        LC_Query.assert_called_once_with(
            "name = 'foo'",
            access="read",
        )
        sql_quote.assert_called_once_with("foo_list_config_name")
        logging_error.assert_called_once_with(
            "ListModel - user '%s' has no read access on list config '%s'"
            + " or the list config does not exists.",
            "foo_user",
            "foo_list_config_name",
        )

    @mock.patch.object(
        widget_rest_models.util,
        "get_label",
        side_effect=["foo_title", "foo_error_msg with: {}"],
    )
    def test_get_JSON_no_config(self, get_label):

        mock_model = mock.MagicMock(spec=self.model, list_config_name="foo_lcn")
        mock_model.list_config = None
        mock_request = mock.MagicMock()

        self.assertDictEqual(
            self.model.get_JSON(mock_model, mock_request),
            {
                "title": "foo_title",
                "items": [],
                "displayConfigs": {},
                "configError": "foo_error_msg with: foo_lcn",
            },
        )
        get_label.assert_has_calls(
            [
                mock.call("web.cs-pcs-widgets.list_widget_error_title"),
                mock.call("cs.pcs.projects.common.lists.list_access_error"),
            ]
        )

    def test_get_JSON(self):
        mock_model = mock.MagicMock(spec=self.model, rest_key="foo_pid@")
        mock_model.list_config = mock.MagicMock()
        mock_request = mock.MagicMock()

        self.assertEqual(
            mock_model.list_config.generateListJSON.return_value,
            self.model.get_JSON(mock_model, mock_request),
        )

        mock_model.list_config.generateListJSON.assert_called_once_with(
            mock_request,
            "foo_pid@",
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
