#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import datetime
import unittest

import pytest
from cdb import testcase
from mock import MagicMock, call, patch

from cs import calendar
from cs.pcs import projects
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


@pytest.mark.unit
class ProjectTestCase(testcase.RollbackTestCase):
    def test_getEffortAvailable_effort_fcast_None(self):
        prj = Project()
        prj.effort_fcast = None
        prj.effort_plan = 1
        mock_tasks = ["foo"]

        with patch.object(Project, "Tasks", mock_tasks):
            self.assertEqual(-1.0, prj.getEffortAvailable())

    def test_getEffortAvailable_effort_plan_None(self):
        prj = Project()
        prj.effort_fcast = 1
        prj.effort_plan = None
        mock_tasks = None

        with patch.object(Project, "Tasks", mock_tasks):
            self.assertEqual(1.0, prj.getEffortAvailable())

    def test_getEffortAvailable(self):
        prj = Project()
        prj.effort_fcast = 10
        prj.effort_plan = 9
        mock_tasks = ["foo"]

        with patch.object(Project, "Tasks", mock_tasks):
            self.assertEqual(1.0, prj.getEffortAvailable())

    # unit test for all UserExits of Project Create
    def test_verifyProjectManager_for_template(self):
        "If project is a template skip verification"
        prj = Project(template=True)
        mock_ctx = MagicMock()
        prj.verifyProjectManager(mock_ctx)
        # ensure project manager is not set
        self.assertIsNone(prj.project_manager)

    @patch.object(projects, "auth")
    def test_verifyProjectManager_set_project_manager(self, auth):
        "Set project manager if project has none"
        prj = Project(template=False, project_manager=None)
        mock_ctx = MagicMock()
        auth.persno = "foo"
        prj.verifyProjectManager(mock_ctx)
        # ensure project manager is set
        self.assertEqual(prj.project_manager, "foo")

    @patch.object(projects.util, "nextval", return_value=1)
    def test_setProjectId_pid_placeholder(self, nextval):
        "project.cdb_project_id is not set, if there aleady is a value"
        prj = Project()
        prj.cdb_project_id = "#"
        mock_ctx = MagicMock()
        prj.setProjectId(mock_ctx)

        self.assertEqual(prj.cdb_project_id, "P000001")
        nextval.assert_called_once_with("PROJECT_ID_SEQ")

    @patch.object(projects.util, "nextval", return_value=1)
    def test_setProjectId_pid_no_placeholder(self, nextval):
        "set project.cdb_project_id"
        prj = Project()
        prj.cdb_project_id = "foo"
        mock_ctx = MagicMock()
        prj.setProjectId(mock_ctx)

        self.assertEqual(prj.cdb_project_id, "foo")
        nextval.assert_not_called()

    def test_setPosition_already_set_position(self):
        "project.position is not set, if there already is a value"
        prj = Project()
        prj.position = 10
        mock_ctx = MagicMock()
        parent = MagicMock(autospec=Project)
        with patch.object(Project, "ParentProject", parent):
            prj.setPosition(mock_ctx)
        self.assertEqual(prj.position, 10)

    def test_setPosition(self):
        "set project position"
        prj = Project()
        prj.position = None
        mock_ctx = MagicMock()
        parent = MagicMock(autospec=Project)
        parent.Subprojects = ["some", "faked", "subProjects"]
        with patch.object(Project, "ParentProject", parent):
            prj.setPosition(mock_ctx)
        self.assertEqual(prj.position, 40)

    def test_setTemplateOID_copy(self):
        "set template_oid to template's cdb_project_id, if ctx action is copy"
        prj = Project()
        prj.template_oid = None
        mock_ctx = MagicMock(action="copy", cdbtemplate={"cdb_object_id": "foo"})
        prj.setTemplateOID(mock_ctx)
        self.assertEqual(prj.template_oid, "foo")

    @patch.object(projects.sqlapi, "SQLupdate")
    def test_setTemplateOID_delete(self, SQLupdate):
        "set template_oid to '' and set template_oid for each task, if ctx action is delete"
        prj = Project()
        prj.template_oid = "foo"
        prj.cdb_object_id = "bar"
        mock_ctx = MagicMock(action="delete")

        task1 = MagicMock(autospec=Task)
        task2 = MagicMock(autospec=Task)
        with patch.object(Project, "Tasks", [task1, task2]):
            prj.setTemplateOID(mock_ctx)
        # since the template_oid is set on database-level, we can just assert,
        # the sql update statement is correct
        SQLupdate.assert_called_once_with(
            "cdbpcs_project SET template_oid = '' WHERE template_oid = 'bar'"
        )

        task1.setTemplateOID.assert_called_once()
        task2.setTemplateOID.assert_called_once()

    def test_on_cdbpcs_reinit_position_now(self):
        "calls reinitPosition"
        prj = MagicMock(spec=Project)
        self.assertIsNone(Project.on_cdbpcs_reinit_position_now(prj, "foo"))
        prj.reinitPosition.assert_called_once_with("foo")

    @patch.object(projects.transactions, "Transaction")
    def test_reinitPosition(self, Transaction):
        "resets top task positions"
        task1 = MagicMock(spec=Task)
        task2 = MagicMock(spec=Task)

        def toptasks(prj):
            "iterator for the TopTasks mock"
            yield task1
            yield task2

        prj = MagicMock(
            spec=Project,
            TopTasks=MagicMock(__iter__=toptasks),
        )
        self.assertIsNone(Project.reinitPosition(prj, None))

        Transaction.assert_called_once_with()
        prj.TopTasks.Update.assert_called_once_with(position=0)
        task1.setPosition.assert_called_once_with()
        task1.reinitPosition.assert_called_once_with()
        task2.setPosition.assert_called_once_with()
        task2.reinitPosition.assert_called_once_with()

    @patch.object(Project, "DefaultCalendarProfileName", return_value="bar")
    @patch.object(projects.fCalendarProfile, "get_by_name")
    @patch.object(projects.auth, "get_department", return_value="foo_division")
    def test_setDefaults(self, get_department, getCalendar, DefaultCalendarProfileName):
        prj = Project()
        prj.cdb_project_id = None
        prj.division = None
        prj.calendar_profile_id = None

        getCalendar.return_value = MagicMock(cdb_object_id="foo_oid")
        # since name is an argument to the Mock constructor we have to set
        # name as property seperately
        getCalendar.return_value.name = "foo_name"

        mock_ctx = MagicMock()
        mock_ctx.get_current_mask = MagicMock(return_value="initial")
        prj.setDefaults(mock_ctx)
        self.assertListEqual(
            [prj.cdb_project_id, prj.division, prj.calendar_profile_id],
            ["", "foo_division", "foo_oid"],
        )
        getCalendar.assert_called_once_with(DefaultCalendarProfileName)
        mock_ctx.set.assert_called_once_with("mapped_calendar_profile", "foo_name")

    @patch.object(Project, "getReadOnlyFields", return_value="foo")
    def test_setInitValues(self, getReadOnlyFields):
        prj = Project()
        mock_ctx = MagicMock(action="bar")

        prj.setInitValues(mock_ctx)

        mock_ctx.set_focus.assert_called_once_with("project_name")
        mock_ctx.set_fields_readonly.assert_called_once_with("foo")
        getReadOnlyFields.assert_called_once_with(action="bar")

    def test_resetValues(self):
        prj = Project()
        mock_ctx = MagicMock(action="bar")
        prj.resetValues(mock_ctx)
        mock_ctx.set.assert_has_calls(
            [
                call("msp_z_nummer", ""),
                call("taskboard_oid", ""),
            ]
        )

    @patch.object(projects.Project, "calculateTimeFrame", return_value=(1, 2, 4))
    def test_get_days_actual(self, calculateTimeFrame):
        prj = projects.Project()
        result = prj.get_days_actual("foo", "bass")
        calculateTimeFrame.assert_called_once_with(start="foo", end="bass")
        self.assertEqual(result, 4)

    @patch.object(projects.Project, "Update")
    @patch.object(projects.Project, "get_days_actual", return_value="bass")
    def test_validate_and_update_days_act_no_exception(self, get_days_actual, Update):
        prj = projects.Project()
        prj.start_time_act = datetime.date(2021, 6, 21)
        prj.end_time_act = datetime.date(2021, 6, 22)
        prj.validate_and_update_days_act("foo")
        get_days_actual.assert_called_once_with(prj.start_time_act, prj.end_time_act)
        Update.assert_called_once_with(days_act="bass")

    @patch.object(projects.util, "get_label", return_value="error")
    def test_validate_and_update_days_act_exception_1(self, get_label):
        prj = projects.Project()
        prj.start_time_act = datetime.date(2021, 6, 22)
        prj.end_time_act = datetime.date(2021, 6, 21)
        with self.assertRaises(projects.ue.Exception) as e:
            prj.validate_and_update_days_act("foo")
        self.assertEqual(str(e.exception), "error")
        get_label.assert_called_once_with("pcs_days_act_end_before_start")

    @patch.object(projects.util, "get_label", return_value="error")
    def test_validate_and_update_days_act_exception_2(self, get_label):
        prj = projects.Project()
        prj.start_time_act = None
        prj.end_time_act = datetime.date(2021, 6, 22)
        with self.assertRaises(projects.ue.Exception) as e:
            prj.validate_and_update_days_act("foo")
        self.assertEqual(str(e.exception), "error")
        get_label.assert_called_once_with("pcs_start_act_present_when_end_act")

    @patch.object(Project, "ByKeys", return_value="foo")
    def test_checkProjectId_pid_already_exists(self, ByKeys):
        "exception is thrown if pid already exists"
        prj = Project(cdb_project_id="bar")
        mock_ctx = MagicMock()
        mock_ctx.get_current_mask = MagicMock(return_value="initial")

        with self.assertRaises(projects.ue.Exception):
            prj.checkProjectId(mock_ctx)
        ByKeys.assert_called_once_with(cdb_project_id="bar")

    @patch.object(Project, "ByKeys")
    def test_checkProjectId_pid_not_existing(self, ByKeys):
        "no exception is thrown if pid not set yet (placeholder '#' or '')"
        prj = Project(cdb_project_id="#")
        mock_ctx = MagicMock()
        mock_ctx.get_current_mask = MagicMock(return_value="initial")

        # does not raise exception
        prj.checkProjectId(mock_ctx)
        # ByKeys not called since pid is not set yet
        ByKeys.assert_not_called()

    @patch.object(
        projects.ProjectCategory, "ByKeys", return_value=MagicMock(workflow="foo")
    )
    def test_setWorkflow_category_set(self, ByKeys):
        prj = Project(category="bar", cdb_objektart=None)
        mock_ctx = MagicMock()
        mock_ctx.get_current_mask = MagicMock(return_value="initial")
        prj.setWorkflow(mock_ctx)
        self.assertEqual(prj.cdb_objektart, "foo")
        ByKeys.assert_called_once_with(name="bar")

    @patch.object(
        projects.ProjectCategory, "ByKeys", return_value=MagicMock(workflow="foo")
    )
    def test_setWorkflow_category_not_set(self, ByKeys):
        prj = Project(category=None, cdb_objektart=None)
        mock_ctx = MagicMock()
        mock_ctx.get_current_mask = MagicMock(return_value="initial")
        prj.setWorkflow(mock_ctx)
        self.assertEqual(prj.cdb_objektart, "cdbpcs_project")
        ByKeys.assert_not_called()

    def test_checkProjectLevel(self):
        "checkProjectLevel is an empty method for Project"
        pass

    def test_setProjectManager_with_error(self):
        "setProjectManager does nothing if there is an error"
        prj = Project()
        prj.createBasicRoles = MagicMock()
        mock_ctx = MagicMock(error=1)
        prj.setProjectManager(mock_ctx)
        # assert that the following method is not called
        prj.createBasicRoles.assert_not_called()

    @patch.object(projects.org.Person, "ByKeys", return_value="foo_pm")
    def test_setProjectManager_without_project_manager(self, ByKeys):
        "setProjectManager only sets default roles, if project manager is not set"
        prj = Project(project_manager=None)
        prj.createBasicRoles = MagicMock()
        prj.assignTeamMember = MagicMock()
        prj.createRole = MagicMock()
        prj.assignDefaultRoles = MagicMock()

        mock_ctx = MagicMock(error=0)

        prj.setProjectManager(mock_ctx)

        # assert that only the following method is called
        prj.createBasicRoles.assert_called_once_with(mock_ctx)
        ByKeys.assert_not_called()
        prj.assignTeamMember.assert_not_called()
        prj.createRole.assert_not_called()
        prj.assignDefaultRoles.assert_not_called()

    @patch.object(projects.org.Person, "ByKeys", return_value="foo_pm")
    def test_setProjectManager_with_project_manager(self, ByKeys):
        """
        setProjectManager assign project manager to project
        and outfits him/her with default roles
        """
        prj = Project(project_manager="foo_init_pm")
        prj.createBasicRoles = MagicMock()
        prj.assignTeamMember = MagicMock()
        prj.createRole = MagicMock()
        prj.assignDefaultRoles = MagicMock()

        mock_ctx = MagicMock(error=0)

        prj.setProjectManager(mock_ctx)

        prj.createBasicRoles.assert_called_once_with(mock_ctx)
        ByKeys.assert_called_once_with(personalnummer="foo_init_pm")
        prj.assignTeamMember.assert_called_once_with("foo_pm")
        prj.createRole.assert_called_once_with(projects.kProjectManagerRole)
        prj.createRole.return_value.assignSubject("foo_pm", mock_ctx)
        prj.assignDefaultRoles.assert_called_once_with("foo_pm", mock_ctx)

    def test_recalculate(self):
        """
        Method recaluclate resides in task_schedule
        and is therefore not tested here
        """
        pass

    @patch.object(projects, "getattr", return_value="bam")
    def test_createFollowUp_ctx_error_or_msp(self, getAttribute):
        """
        createFollowUp is not executed, if ctx has an error
        or cad_system is 'MS-Project' or webUI is used
        """
        prj = Project()
        mock_ctx_error = MagicMock(error=1)
        mock_ctx_msp = MagicMock(cad_system="MS-Project")
        mock_ctx_webui = MagicMock(uses_webui=True)

        prj.createFollowUp(mock_ctx_error)
        prj.createFollowUp(mock_ctx_msp)
        prj.createFollowUp(mock_ctx_webui)
        # assert nothing else is done
        getAttribute.assert_not_called()

    @patch.object(projects, "getattr", return_value="bam")
    def test_createFollowUp(self, getAttribute):
        prj = Project()
        mock_ctx = MagicMock(
            error=0, cad_system="foo", action="copy", sys_args="baz", uses_webui=False
        )
        mock_ctx.set_followUpOperation = MagicMock()

        prj.createFollowUp(mock_ctx)

        getAttribute.assert_called_once_with("baz", "structurerootaction", "")
        mock_ctx.set_followUpOperation.assert_called_once_with(
            "cdbpcs_project_overview", 1
        )

    @patch.object(projects.Project, "check_project_role_assignments")
    @patch.object(projects.Project, "check_project_role_needed")
    def test_adjust_role_assignments(
        self, check_project_role_needed, check_project_role_assignments
    ):
        prj = Project()
        mock_ctx = MagicMock()

        prj.adjust_role_assignments(mock_ctx)

        check_project_role_needed.assert_called_once_with(mock_ctx)
        check_project_role_assignments.assert_called_once_with(mock_ctx)

    @patch.object(calendar.CalendarProfile, "ByKeys")
    def test__correctCalendarDates_no_calendar_profile_id(self, ByKeys):
        prj = Project(calendar_profile_id="")
        mock_ctx = MagicMock()
        prj._correctCalendarDates(mock_ctx)
        ByKeys.assert_not_called()

    @patch("cdb.util.CDBMsg", autospec=True)
    @patch.object(
        projects,
        "to_legacy_date_format",
        side_effect=["foo_p_sd", "foo_p_ed", "foo_cp_sd", "foo_cp_ed"],
    )
    @patch.object(
        calendar.CalendarProfile,
        "ByKeys",
        return_value=MagicMock(
            valid_from=datetime.date(2021, 6, 2),
            valid_until=datetime.date(2021, 6, 3),
        ),
    )
    def test__correctCalendarDates_invalid_project_start(
        self, ByKeys, to_legacy_date_format, CDBMsg
    ):
        """
        throws error if project start is either before calendar start
        or beyond calendar end
        """
        prj = Project(
            calendar_profile_id="foo",
            start_time_fcast=datetime.date(2021, 6, 1),
            end_time_fcast=datetime.date(2021, 6, 3),
        )
        mock_ctx = MagicMock()

        with self.assertRaises(projects.ue.Exception):
            self.assertIsNone(prj._correctCalendarDates(mock_ctx))

        ByKeys.assert_called_once_with(cdb_object_id="foo")
        to_legacy_date_format.assert_has_calls(
            [
                call(datetime.date(2021, 6, 1), full=False),
                call(datetime.date(2021, 6, 3), full=False),
                call(datetime.date(2021, 6, 2), full=False),
                call(datetime.date(2021, 6, 3), full=False),
            ]
        )

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdb_proj_cal_prof")
        CDBMsg.return_value.addReplacement.assert_has_calls(
            [call("foo_p_sd"), call("foo_p_ed"), call("foo_cp_sd"), call("foo_cp_ed")]
        )
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 4)

    @patch("cdb.util.CDBMsg", autospec=True)
    @patch.object(
        projects,
        "to_legacy_date_format",
        side_effect=["foo_p_sd", "foo_p_ed", "foo_cp_sd", "foo_cp_ed"],
    )
    @patch.object(
        calendar.CalendarProfile,
        "ByKeys",
        return_value=MagicMock(
            valid_from=datetime.date(2021, 6, 2), valid_until=datetime.date(2021, 6, 3)
        ),
    )
    def test__correctCalendarDates_invalid_project_end(
        self, ByKeys, to_legacy_date_format, CDBMsg
    ):
        """
        throws error if project end is either before calendar start
        or beyond calendar end
        """
        prj = Project(
            calendar_profile_id="foo",
            start_time_fcast=datetime.date(2021, 6, 2),
            end_time_fcast=datetime.date(2021, 6, 4),
        )
        mock_ctx = MagicMock()

        with self.assertRaises(projects.ue.Exception):
            self.assertIsNone(prj._correctCalendarDates(mock_ctx))

        ByKeys.assert_called_once_with(cdb_object_id="foo")
        to_legacy_date_format.assert_has_calls(
            [
                call(datetime.date(2021, 6, 2), full=False),
                call(datetime.date(2021, 6, 4), full=False),
                call(datetime.date(2021, 6, 2), full=False),
                call(datetime.date(2021, 6, 3), full=False),
            ]
        )

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdb_proj_cal_prof")
        CDBMsg.return_value.addReplacement.assert_has_calls(
            [call("foo_p_sd"), call("foo_p_ed"), call("foo_cp_sd"), call("foo_cp_ed")]
        )
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 4)

    def test_get_time_completion(self):
        start_time = datetime.date(2021, 6, 2)
        end_time = datetime.date(2021, 6, 4)
        prj = Project(
            calendar_profile_id="foo",
            start_time_fcast=start_time,
            end_time_fcast=end_time,
            days=1,
        )
        (
            start,
            end,
            myDate,
            days_done,
            days_total,
            done_percent,
        ) = prj.get_time_completion(None)
        self.assertEqual(start, start_time)
        self.assertEqual(end, end_time)
        self.assertEqual(myDate, datetime.date.today())
        self.assertEqual(days_done, 1)
        self.assertEqual(days_total, 1)
        self.assertEqual(done_percent, 100)

    def test_get_time_completion_empty_start_end(self):
        prj = Project(
            start_time_fcast="",
            end_time_fcast="",
        )
        (
            start,
            end,
            myDate,
            days_done,
            days_total,
            done_percent,
        ) = prj.get_time_completion(None)
        self.assertEqual(start, None)
        self.assertEqual(end, None)
        self.assertEqual(myDate, datetime.date.today())
        self.assertEqual(days_done, 0)
        self.assertEqual(days_total, 0)
        self.assertEqual(done_percent, 0)

    def test_on_create_pre_mask(self):
        prj = Project(parent_project="foo", template=0)
        prj.checkProjectLevel = MagicMock()
        prj.setPosition = MagicMock()
        parent = MagicMock(autospec=Project)
        parent.template = 1
        mock_ctx = MagicMock()

        with patch.object(Project, "ParentProject", parent):
            prj.on_create_pre_mask(mock_ctx)

        self.assertEqual(prj.template, 1)
        prj.checkProjectLevel.assert_called_once()
        prj.setPosition.assert_called_once()

    # unit test for all UserExits of Project Copy (without the ones already tested)
    @patch.object(projects.fTask, "_copy_taskrels_by_mapping")
    @patch.object(Project, "ByKeys")
    @patch.object(projects.transactions, "Transaction")
    def test_copyAllTasksWithRelations(
        self, Transaction, ByKeys, _copy_taskrels_by_mapping
    ):
        prj = Project(cdb_project_id="foo")
        prj.getPersistentObject = MagicMock(return_value=prj)
        prj.Reload = MagicMock()
        prj.initTaskRelationOIDs = MagicMock()
        mock_ctx = MagicMock(
            cdbtemplate=MagicMock(cdb_project_id="bar", ce_baseline_id="baz")
        )
        mock_Task_1 = MagicMock(
            _copy_task=MagicMock(return_value=({"foo_table_1": "1"}, "foo_new_task_1"))
        )
        mock_Task_2 = MagicMock(
            _copy_task=MagicMock(return_value=({"foo_table_2": "2"}, "foo_new_task_2"))
        )
        mock_project_template = MagicMock(
            TopTasks=[mock_Task_1, mock_Task_2], copyRelatedObjects=MagicMock()
        )
        ByKeys.return_value = mock_project_template

        prj.copyAllTasksWithRelations(mock_ctx)

        Transaction.assert_called_once()
        prj.getPersistentObject.assert_called_once()
        ByKeys.assert_called_once_with(cdb_project_id="bar", ce_baseline_id="baz")
        mock_Task_1._copy_task.assert_called_once_with(
            mock_ctx, "foo", "", clear_msp_task_ids=False
        )
        mock_Task_2._copy_task.assert_called_once_with(
            mock_ctx, "foo", "", clear_msp_task_ids=False
        )
        _copy_taskrels_by_mapping.assert_called_once_with(
            "bar", "foo", {"foo_table_1": "1", "foo_table_2": "2"}
        )
        mock_project_template.copyRelatedObjects.assert_called_once_with(prj)
        prj.Reload.assert_called_once()
        prj.initTaskRelationOIDs.assert_called_once()

    def test_approximate_to_forecast(self):
        prj = Project(start_time_fcast="01.01.2020")
        prj.reset_start_time = MagicMock()
        mock_ctx = MagicMock(cdbtemplate=MagicMock(start_time_fcast="02.01.2020"))

        prj.approximate_to_forecast(mock_ctx)

        prj.reset_start_time.assert_called_once_with(
            start_time_old="02.01.2020",
            start_time_new=datetime.date(2020, 1, 1),
        )

    @patch.object(projects, "getattr", return_value="1")
    def test_on_copy_pre_mask(self, getAttribute):
        prj = Project(template=1, project_manager="foo")
        prj.getReadOnlyFields = MagicMock(return_value="bar")
        prj.set_parent_project = MagicMock()
        mock_ctx = MagicMock(
            action="bam1", cdbtemplate={"cdb_project_id": "bam2"}, sys_args="bam3"
        )
        mock_ctx.set = MagicMock()
        mock_ctx.set_fields_readonly = MagicMock()

        prj.on_copy_pre_mask(mock_ctx)

        self.assertEqual(prj.project_manager, "")
        mock_ctx.set.assert_has_calls(
            [
                call("start_time_act", ""),
                call("end_time_act", ""),
                call("days_act", ""),
                call("effort_act", 0),
                call("percent_complet", 0),
            ]
        )
        mock_ctx.set_fields_readonly.assert_called_once_with("bar")
        prj.getReadOnlyFields.assert_called_once_with(action="bam1")
        getAttribute.assert_called_once_with(
            "bam3", "create_project_from_template", "0"
        )
        prj.set_parent_project.assert_called_once_with(mock_ctx)

    def test_on_copy_post_error(self):
        prj = Project()
        prj.createFollowUp = MagicMock()
        mock_ctx = MagicMock(error=1)

        prj.on_copy_post(mock_ctx)

        prj.createFollowUp.assert_not_called()

    def test_on_copy_post(self):
        prj = Project()
        prj.createFollowUp = MagicMock()
        prj.Update = MagicMock()
        mock_ctx = MagicMock(error=0)
        mock_ctx.refresh_caches = MagicMock()

        prj.on_copy_post(mock_ctx)

        prj.Update.assert_called_once_with(
            start_time_act="",
            end_time_act="",
            days_act="",
            effort_act=0,
            percent_complet=0,
        )
        mock_ctx.refresh_caches.assert_called_once_with(
            projects.util.kCGAccessSystemRuntimeCaches,
            projects.util.kSynchronizedReload,
        )
        prj.createFollowUp.assert_called_once_with(mock_ctx)

    # unit test for all UserExits of Project Delete (without the ones already tested)
    # Test all functions called on delete user exit
    @patch("cdb.util.CDBMsg", autospec=True)
    def test_on_delete_pre_subprojects(self, CDBMsg):
        "throw error if there are SubProjects"
        prj = Project()
        mock_ctx = MagicMock()

        with self.assertRaises(projects.ue.Exception):
            with patch.object(Project, "Subprojects", "foo"):
                prj.on_delete_pre(mock_ctx)

        CDBMsg.assert_has_calls(
            [
                call(CDBMsg.kFatal, "pcs_err_del_proj4"),
            ]
        )
        CDBMsg.return_value.addReplacement.assert_not_called()
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)

    @patch("cdb.util.CDBMsg", autospec=True)
    def test_on_delete_pre_timesheets(self, CDBMsg):
        "throw error if there are TimeSheets"
        prj = Project()
        mock_ctx = MagicMock()

        with self.assertRaises(projects.ue.Exception):
            with patch.object(Project, "TimeSheets", "foo"):
                prj.on_delete_pre(mock_ctx)

        CDBMsg.assert_has_calls([call(CDBMsg.kFatal, "pcs_err_del_proj1")])
        CDBMsg.return_value.addReplacement.assert_not_called()
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)

    @patch.object(projects.transactions, "Transaction")
    def test_on_delete_post_error(self, transaction):
        "do nothing on delete_post if context has an error"
        prj = Project()
        mock_ctx = MagicMock(error=1)
        prj.on_delete_post(mock_ctx)
        # assert, that nothing is done by checking,
        # that transaction was not started
        transaction.assert_not_called()

    @patch.object(projects.sqlapi, "SQLdelete")
    @patch.object(projects.ddl, "Table")
    @patch.object(projects.transactions, "Transaction")
    def test_on_delete_post(self, transaction, ddl_table, sql_delete):
        prj = Project(cdb_project_id="foo", ce_baseline_id="foo2")
        mock_ctx = MagicMock(error=0)
        ddl_table.retrun_value = MagicMock(hasColumn=MagicMock(return_value=True))

        prj.on_delete_post(mock_ctx, ["bar", "baz"])

        transaction.assert_called_once()
        # check that ddl_table was called twice for each fixed and given relation
        ddl_table.assert_has_calls(
            [
                call("cdbpcs_cl_prot"),
                call("cdbpcs_doc2cl"),
                call("cdbpcs_cli_prot"),
                call("cdbpcs_doc2cli"),
                call("cdbpcs_doc2iss"),
                call("cdbpcs_iss_prot"),
                call("cdbpcs_iss_log"),
                call("cdbpcs_doc2task"),
                call("bar"),
                call("baz"),
                call("cdbpcs_cl_prot"),
                call("cdbpcs_doc2cl"),
                call("cdbpcs_cli_prot"),
                call("cdbpcs_doc2cli"),
                call("cdbpcs_doc2iss"),
                call("cdbpcs_iss_prot"),
                call("cdbpcs_iss_log"),
                call("cdbpcs_doc2task"),
                call("bar"),
                call("baz"),
            ],
            any_order=True,  # ignore all calls which check for existence
        )
        sql_delete.assert_has_calls(
            [
                # two calls per relation and project (one if column has cdb_object_id and one in general)
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_cl_prot where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_cl_prot where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_doc2cl where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_doc2cl where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_cli_prot where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_cli_prot where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_doc2cli where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_doc2cli where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_doc2iss where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_doc2iss where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_iss_prot where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_iss_prot where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_iss_log where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_iss_log where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from cdbpcs_doc2task where cdb_project_id = 'foo')"
                ),
                call("from cdbpcs_doc2task where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from bar where cdb_project_id = 'foo')"
                ),
                call("from bar where cdb_project_id = 'foo'"),
                call(
                    "from cdb_object where id in "
                    + "(select cdb_object_id from baz where cdb_project_id = 'foo')"
                ),
                call("from baz where cdb_project_id = 'foo'"),
            ]
        )

    # unit test for all UserExits of Project Modify (without the ones already tested)
    def test_recalculate_preparation(self):
        """
        Method recalculate_preparation resides in task_schedule
        and is therefore not tested here
        """
        pass

    # Test all functions called on modify user exit
    @patch.object(Project, "setPosition")
    def test_on_modify_post_mask(self, setPosition):
        """
        call setPosition if object.parent_project does
        not match dialog.parent_project
        """
        prj = Project()
        mock_ctx = MagicMock(
            object=MagicMock(parent_project="foo"),
            dialog=MagicMock(parent_project="bar"),
        )
        prj.on_modify_post_mask(mock_ctx)
        setPosition.assert_called_once_with(mock_ctx)

    @patch.object(Project, "getReadOnlyFields", return_value="bar")
    def test_on_modify_pre_mask(self, getReadOnlyFields):
        "set read only fields on_modify_pre_mask"
        prj = Project()
        mock_ctx = MagicMock(action="foo")
        mock_ctx.set_fields_readonly = MagicMock()

        prj.on_modify_pre_mask(mock_ctx)

        mock_ctx.set_fields_readonly.assert_called_once_with("bar")
        getReadOnlyFields.assert_called_once_with(action="foo")

    @patch("cs.pcs.projects.tasks.Task")
    @patch.object(projects.sig, "emit")
    def test_adjustDependingObjects_adjust(self, emit, Task):
        project = MagicMock(spec=Project)
        self.assertIsNone(Project.adjustDependingObjects(project, True))
        Task.adjustDependingObjects_many.assert_called_once_with(project.AllTasks)
        emit.assert_called_once_with(Project, "adjustDependingObjects")
        emit.return_value.assert_called_once_with(project)

    @patch("cs.pcs.projects.tasks.Task")
    @patch.object(projects.sig, "emit")
    def test_adjustDependingObjects_dont_adjust(self, emit, Task):
        project = MagicMock(spec=Project)
        self.assertIsNone(Project.adjustDependingObjects(project, False))
        Task.adjustDependingObjects_many.assert_not_called()
        emit.assert_called_once_with(Project, "adjustDependingObjects")
        emit.return_value.assert_called_once_with(project)


@pytest.mark.parametrize(
    "action,temp_prj_id,dragdrop_id,drag_obj_prj_id,expected_val",
    [
        ("create", "foo", None, None, "P000005"),
        ("create", "bar", None, None, "foo"),
        ("copy", "foo", None, None, "P000005"),
        ("copy", "bar", None, None, "foo"),
        ("create", None, "dragged_id", "foo", "P000005"),
        ("create", None, "dragged_id", "bar", "foo"),
        ("another_action", None, None, None, "foo"),
    ],
)
@patch.object(projects.util, "nextval", return_value=5)
def test_setProjectId_copy_create(
    _, action, temp_prj_id, dragdrop_id, drag_obj_prj_id, expected_val
):
    prj = Project()
    prj.cdb_project_id = "foo"
    cdbtemplate = MagicMock(cdb_project_id=temp_prj_id)
    dragged_obj = MagicMock(cdb_project_id=drag_obj_prj_id)
    mock_ctx = MagicMock(
        action=action,
        cdbtemplate=cdbtemplate,
        dragdrop_action_id=dragdrop_id,
        dragged_obj=dragged_obj,
    )
    prj.setProjectId(mock_ctx)
    assert prj.cdb_project_id == expected_val


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
