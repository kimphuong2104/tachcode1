#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


import datetime
import unittest

import mock
import pytest
from cdb import testcase, ue
from mock import call

from cs.pcs import projects
from cs.pcs.projects import SubjectAssignment
from cs.pcs.projects.tasks import Task


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TestProject(unittest.TestCase):
    @pytest.mark.unit
    @mock.patch.object(projects.Project, "checkStructureLock")
    @mock.patch.object(projects.Project, "start_time_fcast")
    def test_on_cdpcs_prj_reset_start_time_pre_mask(
        self, start_time_fcast, checkStructureLock
    ):
        """Testing the modifying of the start time of a project. This only tests the pre function, with
        a defined start_time_fcast"""
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        project = projects.Project()
        project.on_cdbpcs_prj_reset_start_time_pre_mask(ctx)
        checkStructureLock.assert_called_once_with(ctx=ctx)
        ctx.set.assert_called_once_with("start_time_old", start_time_fcast)

    @pytest.mark.unit
    @mock.patch.object(projects.Project, "checkStructureLock")
    def test_no_fcast_on_cdpcs_prj_reset_start_time_pre_mask(self, checkStructureLock):
        """Test of modifying the start time of a project. This only tests the pre function, without
        a defined start_time_fcast and start_time_plan."""
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        with self.assertRaises(ue.Exception):
            project = projects.Project()
            project.on_cdbpcs_prj_reset_start_time_pre_mask(ctx)
        checkStructureLock.assert_called_once_with(ctx=ctx)

    @pytest.mark.unit
    def test_remove_prj_mgr_from_team(self):

        teamMember = mock.MagicMock(spec=projects.TeamMember, cdb_person_id=1)
        teamMember.Project.project_manager = 1
        teamMember.Person.getSubjectName.return_value = "Administrator"

        with self.assertRaises(projects.ue.Exception) as e:
            projects.TeamMember.keep_at_least_the_project_manager(teamMember, None)

        self.assertEqual(
            str(e.exception),
            (
                "\\nAdministrator ist als verantwortlicher Projektleiter "
                "in den Stammdaten definiert.\\nDer verantwortliche "
                "Projektleiter muss Mitglied der Rolle Projektleiter sein.\\n"
                "Sie müssen einen neuen Projektleiter in den Stammdaten des "
                "Projekts eintragen, um Administrator aus dieser Rolle zu "
                "entfernen."
            ),
        )

    @pytest.mark.unit
    def test_remove_prj_mgr_from_role_project_manager(self):

        subjectAssignment = mock.MagicMock(
            spec=projects.SubjectAssignment,
            role_id=projects.kProjectManagerRole,
            subject_id=1,
        )
        subjectAssignment.Project.project_manager = 1
        subjectAssignment.getSubjectName.return_value = "Administrator"

        with self.assertRaises(projects.ue.Exception) as e:
            projects.SubjectAssignment.keep_at_least_the_project_manager(
                subjectAssignment, None
            )

        self.assertEqual(
            str(e.exception),
            (
                "\\nAdministrator ist als verantwortlicher Projektleiter "
                "in den Stammdaten definiert.\\nDer verantwortliche "
                "Projektleiter muss Mitglied der Rolle Projektleiter sein.\\n"
                "Sie müssen einen neuen Projektleiter in den Stammdaten des "
                "Projekts eintragen, um Administrator aus dieser Rolle zu "
                "entfernen."
            ),
        )

    @pytest.mark.unit
    def test_set_parent_project_batch(self):
        project = mock.MagicMock(spec=projects.Project)
        ctx = mock.MagicMock(uses_webui=False)

        # set_parent_project not called when interactive
        ctx.interactive = 1
        projects.Project.set_parent_project_batch(project, ctx)
        project.set_parent_project.assert_not_called()

        # set_parent_project called when not interactive
        ctx.interactive = 0
        projects.Project.set_parent_project_batch(project, ctx)
        project.set_parent_project.assert_called_once_with(ctx)

    @pytest.mark.unit
    @mock.patch.object(projects.Project, "ByKeys")
    def test_on_copy_pre_mask(self, ByKeys):
        project = mock.MagicMock(spec=projects.Project)
        ctx = mock.MagicMock()
        parentProject = mock.MagicMock(spec=projects.Project)
        ByKeys.return_value = parentProject

        # set_parent_project not called when not from template
        projects.Project.on_copy_pre_mask(project, ctx)
        project.set_parent_project.assert_not_called()

        # set_parent_project not called when not from template
        ctx.sys_args.create_project_from_template = "0"
        projects.Project.on_copy_pre_mask(project, ctx)
        project.set_parent_project.assert_not_called()

        # set_parent_project called when from template
        ctx.sys_args.create_project_from_template = "1"
        projects.Project.on_copy_pre_mask(project, ctx)
        project.set_parent_project.assert_called_once_with(ctx)

    @pytest.mark.unit
    @mock.patch.object(projects.Project, "ByKeys")
    def test_set_parent_project(self, ByKeys):
        project = mock.MagicMock(spec=projects.Project, ce_baseline_id="")
        ctx = mock.MagicMock(uses_webui=False)
        parentProject = mock.MagicMock(
            spec=projects.Project, cdb_project_id="Foo", project_name="Bar"
        )
        ByKeys.return_value = parentProject

        # 1.TestCase: clear parent, because there is none
        ctx.parent.get_attribute_names.return_value = ()
        projects.Project.set_parent_project(project, ctx)
        project.Update.assert_called_once_with(
            template=0, parent_project="", parent_project_name=""
        )

        # 2.TestCase: set parent when this is a subproject
        # mocking acess of attributes via index
        ctx.parent = mock.MagicMock()
        real_parent = {"cdb_project_id": "Foo"}

        def getitem(name):
            return real_parent[name]

        ctx.parent.__getitem__.side_effect = getitem
        ctx.parent.get_attribute_names.return_value = "cdb_project_id"

        projects.Project.set_parent_project(project, ctx)

        project.Update.assert_has_calls(
            [
                mock.call(template=0, parent_project="", parent_project_name=""),
                mock.call(template=0, parent_project="Foo", parent_project_name="Bar"),
            ]
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="Foo",
        )

    @pytest.mark.unit
    @mock.patch.object(projects.Project, "ByKeys")
    def test_set_parent_project_webui(self, ByKeys):
        project = mock.MagicMock(spec=projects.Project, ce_baseline_id="")
        ctx = mock.MagicMock(
            uses_webui=True, dialog=mock.MagicMock(parent_project="Foo")
        )
        parentProject = mock.MagicMock(
            spec=projects.Project, cdb_project_id="Foo", project_name="Bar"
        )
        ByKeys.return_value = parentProject

        # clear parent, because there is none
        ctx.parent.get_attribute_names.return_value = ()
        projects.Project.set_parent_project(project, ctx)
        project.Update.assert_called_once_with(
            template=0, parent_project="Foo", parent_project_name="Bar"
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="Foo",
        )

    @mock.patch.object(projects.utils, "add_interactive_call")
    def test_init_status_change(self, add_interactive_call):
        "Init status change by adding project to status change stack"
        project = projects.Project()
        project.init_status_change()
        add_interactive_call.assert_called_once_with(project)

    @mock.patch.object(projects.Project, "do_status_updates")
    @mock.patch.object(projects.utils, "remove_from_change_stack", return_value="foo")
    def test_end_status_change_00(self, remove_from_change_stack, do_status_updates):
        "Remove project from status change stack and execute updates"
        project = projects.Project()
        ctx = mock.Mock()
        project.end_status_change(ctx)
        remove_from_change_stack.assert_called_once_with(project, ctx)
        do_status_updates.assert_called_once_with("foo")

    @mock.patch.object(projects.Project, "do_status_updates")
    @mock.patch.object(projects.utils, "remove_from_change_stack", return_value=None)
    def test_end_status_change_01(self, remove_from_change_stack, do_status_updates):
        "Remove project from status change stack; no updates executed"
        project = projects.Project()
        ctx = mock.Mock()
        project.end_status_change(ctx)
        remove_from_change_stack.assert_called_once_with(project, ctx)
        do_status_updates.assert_not_called()

    def test_get_ev_pv_for_project_oracle_without_tasks(self):
        project = mock.MagicMock(spec=projects.Project)
        project.cdb_project_id = "bar"
        project.getWorkCompletion.return_value = 50.0
        project.getForeCast.return_value = 2.0
        project.getPlanTimeCompletion.return_value = 1.0
        result = projects.Project.get_ev_pv_for_project(project)
        self.assertEqual(result, (1.0, 2.0))

    def test_get_ev_pv_for_project_mssql_without_tasks(self):
        project = mock.MagicMock(spec=projects.Project)
        project.cdb_project_id = "bar"
        project.getWorkCompletion.return_value = 50.0
        project.getForeCast.return_value = 2.0
        project.getPlanTimeCompletion.return_value = 1.0
        result = projects.Project.get_ev_pv_for_project(project)
        self.assertEqual(result, (1.0, 2.0))

    @mock.patch.object(projects.sqlapi, "RecordSet2")
    def test_get_ev_pv_for_project_oracle_with_one_task(self, RecordSet2):
        project = mock.MagicMock(spec=projects.Project)
        project.cdb_project_id = "bar"
        task = Task(
            task_id="task_id",
            status=0,
            milestone=0,
            percent_complet=50,
            effort_fcast=2.0,
            days_fcast=1,
            end_time_fcast=datetime.date.today(),
            start_time_fcast=datetime.date.today(),
            parent_task="",
        )
        RecordSet2.return_value = [task]
        result = projects.Project.get_ev_pv_for_project(project)
        self.assertEqual(result, (1.0, 2.0))

    @mock.patch.object(projects.sqlapi, "RecordSet2")
    def test_get_ev_pv_for_project_oracle_with_one_invalid_task(self, RecordSet2):
        project = mock.MagicMock(spec=projects.Project)
        project.cdb_project_id = "bar"
        task = Task(
            task_id="task_id",
            status=projects.tasks.Task.DISCARDED.status,
            milestone=0,
            percent_complet=50,
            effort_fcast=2.0,
            days_fcast=1,
            end_time_fcast=datetime.date.today(),
            start_time_fcast=datetime.date.today(),
            parent_task="",
        )
        RecordSet2.return_value = [task]
        result = projects.Project.get_ev_pv_for_project(project)
        self.assertEqual(result, (0.0, 0.0))

    @mock.patch.object(projects.sqlapi, "RecordSet2")
    def test_get_ev_pv_for_project_oracle_with_several_tasks(self, RecordSet2):
        project = mock.MagicMock(spec=projects.Project)
        project.cdb_project_id = "bar"
        milestone = Task(
            task_id="ohm",
            status=0,
            is_group=0,
            milestone=1,
            percent_complet=30,
            effort_fcast=0.0,
            days_fcast=0,
            end_time_fcast=datetime.date.today(),
            start_time_fcast=datetime.date.today(),
            parent_task="foo",
        )
        task = Task(
            task_id="bar",
            status=0,
            is_group=0,
            milestone=0,
            percent_complet=50,
            effort_fcast=2.0,
            days_fcast=1,
            end_time_fcast=datetime.date.today(),
            start_time_fcast=datetime.date.today(),
            parent_task="foo",
        )
        parent_task = Task(
            task_id="foo",
            status=0,
            is_group=1,
            milestone=0,
            percent_complet=50,
            effort_fcast=2.0,
            days_fcast=1,
            end_time_fcast=datetime.date.today(),
            start_time_fcast=datetime.date.today(),
            parent_task="",
        )
        RecordSet2.return_value = [milestone, task, parent_task]
        result = projects.Project.get_ev_pv_for_project(project)
        self.assertEqual(result, (1.0, 2.0))

    @mock.patch.object(
        projects.Project,
        "MakeChangeControlAttributes",
        return_value={"cdb_mpersno": "foo", "cdb_mdate": "bar"},
    )
    @mock.patch.object(projects.Project, "Update")
    def test_mark_as_changed(self, Update, MCCA):
        "Project.mark_as_changed"
        project = projects.Project()
        project.mark_as_changed()

        # check calls
        MCCA.assert_called_once_with()
        Update.assert_called_once_with(cdb_apersno="foo", cdb_adate="bar")


@pytest.mark.unit
class TestPerson(unittest.TestCase):
    @pytest.mark.unit
    def test_manage_resource_input_fields_mandatory(self):
        """
        Test if set_mandatory is called correct on the context_object
        """
        ctx = mock.MagicMock()
        projects.Person.manage_resource_input_fields(1, ctx)
        self.assertEqual(
            ctx.set_mandatory.call_count,
            2,
            "Wrong amount of calls for method 'set_mandatory'",
        )
        self.assertEqual(
            ctx.set_optional.call_count,
            0,
            "Wrong amount of calls for method 'set_optional'",
        )
        ctx.set_mandatory.assert_has_calls(
            [call(".mapped_calendar_profile"), call("angestellter.capacity")]
        )

    @pytest.mark.unit
    def test_manage_resource_input_fields_optional(self):
        """
        Test if set_optional is called correct on the context_object
        """
        ctx = mock.MagicMock()
        projects.Person.manage_resource_input_fields(0, ctx)
        self.assertEqual(
            ctx.set_mandatory.call_count,
            0,
            "Wrong amount of calls for method 'set_mandatory'",
        )
        self.assertEqual(
            ctx.set_optional.call_count,
            2,
            "Wrong amount of calls for method 'set_optional'",
        )
        ctx.set_optional.assert_has_calls(
            [call(".mapped_calendar_profile"), call("angestellter.capacity")]
        )

    @pytest.mark.unit
    @mock.patch.object(projects.fCalendarProfile, "get_by_name")
    def test_manage_default_calendar_profile_nothing(self, get_by_name):
        """
        Test if If the person has been tagged as resource and the calendar
        profile was set or has been untagged as resource, then nothing is
        executed.
        """
        for is_resource in range(2):
            ctx = mock.MagicMock()
            projects.Person.manage_default_calendar_profile(
                is_resource, "Test" if is_resource else "", ctx
            )

            self.assertEqual(
                get_by_name.call_count,
                0,
                "Wrong amount of calls for method 'get_by_name'",
            )
            self.assertEqual(
                ctx.set.call_count, 0, "Wrong amount of calls for method 'set'"
            )

    @pytest.mark.unit
    @mock.patch.object(projects.fCalendarProfile, "get_by_name")
    def test_manage_default_calendar_profile_set_calender_profile(self, get_by_name):
        """
        Test if If the person has been tagged as resource and the calendar
        profile was not set, then the default calendar profile is set.
        """
        ctx = mock.MagicMock()
        projects.Person.manage_default_calendar_profile(1, "", ctx)

        self.assertEqual(
            get_by_name.call_count, 1, "Wrong amount of calls for method 'get_by_name'"
        )
        self.assertEqual(
            ctx.set.call_count, 2, "Wrong amount of calls for method 'set'"
        )
        ctx.set.assert_has_calls(
            [
                call("angestellter.calendar_profile_id", get_by_name().cdb_object_id),
                call(".mapped_calendar_profile", get_by_name().name),
            ]
        )


@pytest.mark.integration
class TestSubjectAssignment(testcase.RollbackTestCase):
    def test_get_further_role_member(self):
        SubjectAssignment.Create(
            role_id="Projektleiter",
            subject_id2="",
            subject_id="caddok",
            subject_type="Person",
            cdb_project_id="project",
            cdb_classname="cdbpcs_subject_per",
        )
        self.assertEqual(
            len(
                projects.SubjectAssignment.get_further_role_member("project", "subject")
            ),
            1,
        )

    def test_get_further_role_member_with_injection(self):
        SubjectAssignment.Create(
            role_id="Projektleiter",
            subject_id2="",
            subject_id="caddok",
            subject_type="Person",
            cdb_project_id="project",
            cdb_classname="cdbpcs_subject_per",
        )
        self.assertEqual(
            len(
                projects.SubjectAssignment.get_further_role_member(
                    "project' and cdb_classname='cdbpcs_subject_per", "subject"
                )
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
