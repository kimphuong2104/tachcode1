#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import datetime
import unittest

import mock
import pytest
from cdb import ElementsError, constants, rte, testcase, ue
from cdb.objects.operations import operation
from cdb.typeconversion import from_legacy_date_format

from cs.pcs.projects import tasks
from cs.pcs.projects.tests import common

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
TOMORROW = TODAY + datetime.timedelta(days=1)
OP = "CDB_Modify"


class TaskIntegrationOverdueTestCase(testcase.RollbackTestCase):
    """isOverdue checks whether the task is overdue"""

    def task_isOverdue(self, task_status, end_time_fcast, expected):
        project = common.generate_project(status=0)
        task = common.generate_task(
            project=project,
            task_id="test_overdue_task",
            status=task_status,
            start_time_fcast=datetime.date(2021, 7, 1),
            end_time_fcast=end_time_fcast,
        )
        self.assertEqual(
            task.time_overdue,
            expected,
            f"Task time_overdue is {task.time_overdue} (should be {expected})",
        )


@pytest.mark.integration
class TaskOverdueTestCase(TaskIntegrationOverdueTestCase):
    # just test large differences since the virtual attribute "time_overdue"
    # is calculated by the DB server and its clock is not necessarily synced
    # with the test runner's

    def test_overdue_task_0_yesterday(self):
        self.task_isOverdue(0, YESTERDAY, 1)

    def test_overdue_task_200_yesterday(self):
        self.task_isOverdue(200, YESTERDAY, 0)

    def test_overdue_task_0_tomorrow(self):
        self.task_isOverdue(0, TOMORROW, 0)

    def test_overdue_task_0_today(self):
        # risk of being flaky when run close to midnight
        self.task_isOverdue(0, TODAY, 0)


@pytest.mark.integration
class TaskIntegrationStatusTestCase(testcase.RollbackTestCase):
    @mock.patch.object(tasks.utils, "unregister_from_change_stack")
    @mock.patch.object(tasks.utils, "add_to_change_stack")
    def test_ChangeState(self, add_to_change_stack, unregister):
        "ChangeState registers task for status change"
        project = common.generate_project(status=50)
        task = common.generate_task(project, "task1", status=0)
        task.ChangeState(20)
        add_to_change_stack.assert_called_once_with(task)
        unregister.assert_called_once_with(task)

    @mock.patch.object(tasks.Task, "ChangeState", side_effect=ElementsError("foo"))
    def test_on_cdbpcs_cancel_task_now_nested_error(self, ChangeState):
        project = common.generate_project(status=50)
        t1 = common.generate_task(project, "T1", status=0)
        t2 = common.generate_task(project, "T2", status=0, parent_task=t1.task_id)
        common.generate_task(project, "T3", status=0, parent_task=t2.task_id)

        with self.assertRaises(tasks.util.ErrorMessage) as error:
            with testcase.error_logging_disabled():
                t1.on_cdbpcs_cancel_task_now(None)

        self.assertEqual(
            str(error.exception),
            "T2: T3: foo",
        )
        self.assertEqual(ChangeState.call_count, 1)


@pytest.mark.integration
class TaskIntegrationTestCase(testcase.RollbackTestCase):
    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://foo"})
    def test_email_notification_body(self):
        project = common.generate_project(cdb_project_id="TEST_TASK_PROJECT")
        task = common.generate_task(project, "TASK-1")
        templ_file = task._getNotificationTemplateFile(None)
        self.assertEqual(
            task._render_mail_template(None, templ_file),
            (
                '<meta charset="UTF-8" />\n'
                "<div>\n"
                "    <p>\n"
                "        Aufgabe/Task:&nbsp;\n"
                "        <a\n"
                '            href="http://foo/info/project_task/TEST_TASK_PROJECT@TASK-1@">'
                "TASK-1 (Browser)</a>\n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_task/'
                "CDB_Modify/interactive?"
                "cdbpcs_task.cdb_project_id=TEST_TASK_PROJECT&amp;"
                "cdbpcs_task.task_id=TASK-1&amp;"
                "cdbpcs_task.ce_baseline_id="
                '">TASK-1 (Client)</a>\n'
                "    </p>\n"
                "\n"
                "    <p>\n"
                "        Projekt/Project:&nbsp;\n"
                "        <a\n"
                '            href="http://foo/info/project/TEST_TASK_PROJECT@">'
                "project name (Browser)</a>\n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_project/'
                "cdbpcs_project_overview/interactive?"
                "cdbpcs_project.cdb_project_id=TEST_TASK_PROJECT&amp;"
                "cdbpcs_project.ce_baseline_id="
                '">project name (Client)</a>\n'
                "    </p>\n"
                "</div>\n"
            ),
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_set_frozen_in_event_map(self):
        "Task event map contains 'set_frozen'"
        self.assertIn(
            "set_frozen", tasks.Task.GetEventMap()[(("create", "copy"), "pre")]
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_derived_from_WithFrozen(self):
        "Task is derived from WithFrozen"
        self.assertIn(tasks.WithFrozen, tasks.Task.mro())

    def test_set_act_date(self):
        project = common.generate_project(status=0)
        task = common.generate_task(
            project=project,
            task_id="test_set_act_date",
            start_time_act=datetime.date(2022, 8, 1),
            end_time_act=datetime.date(2022, 8, 4),
        )
        ctx = mock.Mock(
            dialog=mock.Mock(
                start_time_act="2022-08-08",
                end_time_act="2022-08-10",
            ),
        )
        task.set_act_date(ctx)
        self.assertDictContainsSubset(
            {
                "start_time_act": datetime.date(2022, 8, 8),
                "end_time_act": datetime.date(2022, 8, 10),
            },
            dict(task),
        )

    def test_set_act_date_no_changes(self):
        project = common.generate_project(status=0)
        task = common.generate_task(
            project=project,
            task_id="test_set_act_date",
            start_time_act=datetime.date(2022, 8, 1),
            end_time_act=datetime.date(2022, 8, 4),
        )
        old_mdate = datetime.datetime(2022, 8, 1, 10, 11, 12)
        task.cdb_mdate = old_mdate
        ctx = mock.Mock(
            dialog=mock.Mock(
                start_time_act="2022-08-01",
                end_time_act="",
            ),
        )
        task.set_act_date(ctx)
        self.assertDictContainsSubset(
            {
                "start_time_act": datetime.date(2022, 8, 1),
                "end_time_act": datetime.date(2022, 8, 4),
            },
            dict(task),
        )
        self.assertEqual(task.cdb_mdate, old_mdate)

    def test_set_invalid_percentage_complete(self):
        "Set %Complete to invalid value: over 100"
        project = common.generate_project(status=50)
        task = common.generate_task(
            project=project,
            task_id="test_set_act_date",
            start_time_act=datetime.date(2023, 7, 1),
            end_time_act=datetime.date(2023, 7, 3),
            status=50,
            percent_complet=1,
        )
        with self.assertRaises(ElementsError) as error:
            task = operation(
                constants.kOperationModify,
                task,
                percent_complet=123,
            )
        self.assertEqual(
            str(error.exception), str(ue.Exception("cdbpcs_task_percentage_validation"))
        )

    def test_set_invalid_percentage_complete(self):
        "Set %Complete to invalid value: values < 1"
        project = common.generate_project(status=50)
        task = common.generate_task(
            project=project,
            task_id="test_set_act_date",
            start_time_act=datetime.date(2023, 7, 1),
            end_time_act=datetime.date(2023, 7, 3),
            status=50,
            percent_complet=1,
        )
        with self.assertRaises(ElementsError) as error:
            task = operation(
                constants.kOperationModify,
                task,
                percent_complet=-1,
            )
        self.assertEqual(
            str(error.exception), str(ue.Exception("cdbpcs_task_percentage_validation"))
        )

    def test_set_valid_percentage_complete(self):
        "Set %Complete to acceptable values"
        project = common.generate_project(status=50)
        task = common.generate_task(
            project=project,
            task_id="test_set_act_date",
            start_time_act=datetime.date(2023, 7, 1),
            end_time_act=datetime.date(2023, 7, 3),
            status=50,
            percent_complet=1,
        )
        task = operation(
            constants.kOperationModify,
            task,
            percent_complet=31,
        )


@pytest.mark.integration
class TaskSortTestCase(testcase.RollbackTestCase):
    def test_recalculation_successful(self):
        """Test if projects, tasks and task relships are correct after recalculate

        Project Structures:
            P1
            - T1 1.11.2021 - 3.11.2021
            - T2 4.11.2021 - 8.11.2021
            P2
            - T3 2.11.2021 - 4.11.2021
            - T4 5.11.2021 - 9.11.2021
        Task Relships:
            TR1: T1-FS-T2 - not violated
            TR2: T1-FS-T3 - not violated
            TR3: T2-FS-T4 - violated
            TR4: T3-FS-T4 - violated

        """

        # two different projects
        p1 = common.generate_project(
            cdb_project_id="p_sort_1",
            project_name="sort_1",
            start_time_fcast=datetime.date(2021, 11, 1),
            end_time_fcast=datetime.date(2021, 11, 1),
            days_fcast=1,
            auto_update_time=0,
        )
        p2 = common.generate_project(
            cdb_project_id="p_sort_2",
            project_name="sort_2",
            start_time_fcast=datetime.date(2021, 11, 2),
            end_time_fcast=datetime.date(2021, 11, 2),
            days_fcast=1,
            auto_update_time=0,
        )

        # each project has two tasks
        kwargs = {"days_fcast": 3, "automatic": 1}
        t1 = common.generate_task(p1, "t1", **kwargs)
        t2 = common.generate_task(p1, "t2", **kwargs)
        t3 = common.generate_task(p2, "t3", **kwargs)
        t4 = common.generate_task(p2, "t4", **kwargs)

        # tasks of projects are connected
        tr1 = common.generate_task_relation(t1, t2)
        tr2 = common.generate_task_relation(t3, t4)

        # connections between projects
        tr3 = common.generate_task_relation(t2, t4)
        tr4 = common.generate_task_relation(t1, t3)

        # schedule projects
        p1.recalculate()
        p2.recalculate()

        # reload tasks and relations
        t1.Reload()
        t2.Reload()
        t3.Reload()
        t4.Reload()
        tr1.Reload()
        tr2.Reload()
        tr3.Reload()
        tr4.Reload()

        # check if tasks are placed correctly
        self.assertEqual(t1.start_time_fcast, datetime.date(2021, 11, 1))
        self.assertEqual(t1.end_time_fcast, datetime.date(2021, 11, 3))
        self.assertEqual(t2.start_time_fcast, datetime.date(2021, 11, 4))
        self.assertEqual(t2.end_time_fcast, datetime.date(2021, 11, 8))
        self.assertEqual(t3.start_time_fcast, datetime.date(2021, 11, 2))
        self.assertEqual(t3.end_time_fcast, datetime.date(2021, 11, 4))
        self.assertEqual(t4.start_time_fcast, datetime.date(2021, 11, 5))
        self.assertEqual(t4.end_time_fcast, datetime.date(2021, 11, 9))
        self.assertEqual(tr1.violation, 0)
        self.assertEqual(tr2.violation, 0)
        self.assertEqual(tr3.violation, 1)
        self.assertEqual(tr4.violation, 1)


class TaskRoleIntegrationTestCase(testcase.RollbackTestCase):

    ROLE_ID = "Projektmitglied"
    SUBJECT_ID = "Projektmitglied"
    PERSNO = "test_user_00"

    def change_task(self, task_status, **rights):
        p = common.generate_project(status=50)
        common.generate_user(self.PERSNO)
        common.assign_person_to_project(self.ROLE_ID, p, self.PERSNO)
        task = common.generate_project_task(
            p,
            task_id="task1",
            status=task_status,
            subject_id=self.SUBJECT_ID,
            subject_type="PCS Role",
        )
        for name, right in rights.items():
            check = task.CheckAccess(name, persno=self.PERSNO)
            self.assertEqual(
                right,
                check,
                f"Access right '{name}': {check} (should be {right})",
            )


@pytest.mark.integration
class RoleTestCase_01(TaskRoleIntegrationTestCase):

    ROLE_ID = "Projektleiter"
    SUBJECT_ID = "Projektleiter"
    PERSNO = "test_user_01"

    def test_change_task_01(self):
        "Task access rights: " "project manager changes new task assigned to project manager"
        self.change_task(0, read=True, pcstask_wf_step=True, delete=True, save=True)

    def test_change_task_02(self):
        "Task access rights: " "project manager changes ready task assigned to project manager"
        self.change_task(20, read=True, pcstask_wf_step=True, delete=True, save=True)

    def test_change_task_03(self):
        "Task access rights: " "project manager changes executing task assigned to project manager"
        self.change_task(50, read=True, pcstask_wf_step=True, delete=True, save=True)

    def test_change_task_04(self):
        "Task access rights: " "project manager changes finished task assigned to project manager"
        self.change_task(200, read=True, pcstask_wf_step=True, delete=True, save=True)

    def test_change_task_05(self):
        "Task access rights: " "project manager changes completed task assigned to project manager"
        self.change_task(250, read=True, pcstask_wf_step=True, delete=False, save=False)


@pytest.mark.integration
class RoleTestCase_02(TaskRoleIntegrationTestCase):

    ROLE_ID = "Projektmitglied"
    SUBJECT_ID = "Projektleiter"
    PERSNO = "test_user_02"

    def test_change_task_01(self):
        "Task access rights: " "project member changes new task assigned to project manager"
        self.change_task(0, read=True, pcstask_wf_step=False, delete=False, save=False)

    def test_change_task_02(self):
        "Task access rights: " "project member changes ready task assigned to project manager"
        self.change_task(20, read=True, pcstask_wf_step=False, delete=False, save=False)

    def test_change_task_03(self):
        "Task access rights: " "project member changes executing task assigned to project manager"
        self.change_task(50, read=True, pcstask_wf_step=False, delete=False, save=False)

    def test_change_task_04(self):
        "Task access rights: " "project member changes finished task assigned to project manager"
        self.change_task(
            200, read=True, pcstask_wf_step=False, delete=False, save=False
        )

    def test_change_task_05(self):
        "Task access rights: " "project member changes completed task assigned to project manager"
        self.change_task(
            250, read=True, pcstask_wf_step=False, delete=False, save=False
        )


@pytest.mark.integration
class RoleTestCase_03(TaskRoleIntegrationTestCase):

    ROLE_ID = "Projektmitglied"
    SUBJECT_ID = "Projektmitglied"
    PERSNO = "test_user_03"

    def test_change_task_01(self):
        "Task access rights: " "project member changes new task assigned to project member"
        self.change_task(0, read=True, pcstask_wf_step=True, delete=False, save=False)

    def test_change_task_02(self):
        "Task access rights: " "project member changes ready task assigned to project member"
        self.change_task(20, read=True, pcstask_wf_step=True, delete=False, save=True)

    def test_change_task_03(self):
        "Task access rights: " "project member changes executing task assigned to project member"
        self.change_task(50, read=True, pcstask_wf_step=True, delete=False, save=True)

    def test_change_task_04(self):
        "Task access rights: " "project member changes finished task assigned to project member"
        self.change_task(200, read=True, pcstask_wf_step=True, delete=False, save=False)

    def test_change_task_05(self):
        "Task access rights: " "project member changes completed task assigned to project member"
        self.change_task(250, read=True, pcstask_wf_step=True, delete=False, save=False)


@pytest.mark.integration
class TaskIntegrationPreventingParentSubCycles(testcase.RollbackTestCase):
    def _create_structure(self):
        project = common.generate_project()
        tasks = {
            "parent1": common.generate_task(project, "parent1", parent_task=""),
            "parent2": common.generate_task(project, "parent2", parent_task=""),
            "sub1": common.generate_task(project, "sub1", parent_task="parent1"),
            "sub2": common.generate_task(project, "sub2", parent_task="parent1"),
            "sub3": common.generate_task(project, "sub3", parent_task="parent2"),
            "sub4": common.generate_task(project, "sub4", parent_task="parent2"),
        }
        common.generate_task_relation(tasks["sub1"], tasks["sub2"])
        common.generate_task_relation(tasks["sub3"], tasks["sub4"])
        return tasks

    def check_error(self, error):
        self.assertEqual(
            str(error.exception), str(ue.Exception("cdbpcs_parent_sub_cycle_detected"))
        )

    def test_cycle_check_passed_01(self):
        tasks = self._create_structure()
        operation(OP, tasks["parent1"], parent_task="sub4")
        # operation successfully passed

    def test_cycle_check_failed_01(self):
        tasks = self._create_structure()
        common.generate_task_relation(tasks["parent1"], tasks["parent2"])
        with self.assertRaises(ElementsError) as error:
            operation(OP, tasks["parent1"], parent_task="sub4")
        # operation failed due to cycle
        self.check_error(error)

    def test_cycle_check_failed_02(self):
        tasks = self._create_structure()
        common.generate_task_relation(tasks["parent1"], tasks["parent2"])
        with self.assertRaises(ElementsError) as error:
            operation(OP, tasks["parent1"], parent_task="parent2")
        # operation failed due to cycle
        self.check_error(error)

    def test_cycle_check_failed_03(self):
        tasks = self._create_structure()
        common.generate_task_relation(tasks["sub2"], tasks["sub4"])
        with self.assertRaises(ElementsError) as error:
            operation(OP, tasks["parent1"], parent_task="sub4")
        # operation failed due to cycle
        self.check_error(error)

    def test_cycle_check_failed_04(self):
        tasks = self._create_structure()
        common.generate_task_relation(tasks["sub2"], tasks["sub3"])
        with self.assertRaises(ElementsError) as error:
            operation(OP, tasks["parent1"], parent_task="sub4")
        # operation successfully passed
        self.check_error(error)


@pytest.mark.integration
class TaskIntegrationCalculateForecast(testcase.RollbackTestCase):

    TARGET_START = datetime.date(2022, 2, 14)
    TARGET_END = datetime.date(2022, 2, 16)
    TARGET_DAYS = 3
    FCAST_START = datetime.date(2022, 2, 15)
    FCAST_END = datetime.date(2022, 2, 18)
    FCAST_DAYS = 4
    ACT_START = datetime.date(2022, 2, 17)
    ACT_END = datetime.date(2022, 2, 22)
    ACT_DAYS = 4

    def create_project(self, **kwargs):
        project = common.generate_project(**kwargs)
        return project, self.add_task(project)

    def add_task(self, project, **kwargs):
        values = {
            # status and percent_complet: make target dates immutable
            "status": 50,
            "percent_complet": 1,
            "auto_update_time": 1,
            "start_time_fcast": self.TARGET_START,
            "end_time_fcast": self.TARGET_END,
            "days_fcast": self.TARGET_DAYS,
            "start_time_plan": self.FCAST_START,
            "end_time_plan": self.FCAST_END,
            "days": self.FCAST_DAYS,
            "start_time_act": self.ACT_START,
        }
        values.update(**kwargs)
        return common.generate_task(project, "task1", **values)

    def check_error(self, error, label):
        self.assertEqual(str(error.exception), str(ue.Exception(label)))

    def get_changed_values(self, task):
        result = {}
        # check target dates
        if task.start_time_fcast != self.TARGET_START:
            result.update(start_time_fcast=task.start_time_fcast)
        if task.end_time_fcast != self.TARGET_END:
            result.update(end_time_fcast=task.end_time_fcast)
        if task.days_fcast != self.TARGET_DAYS:
            result.update(days_fcast=task.days_fcast)

        # check forecast dates
        if task.start_time_plan != self.FCAST_START:
            result.update(start_time_plan=task.start_time_plan)
        if task.end_time_plan != self.FCAST_END:
            result.update(end_time_plan=task.end_time_plan)
        if task.days != self.FCAST_DAYS:
            result.update(days=task.days)

        # check actual dates
        if task.start_time_act != self.ACT_START:
            result.update(start_time_act=task.start_time_act)
        if task.end_time_act is not None:
            result.update(end_time_act=task.end_time_act)
        if task.days_act != 0:
            result.update(days_act=task.days_act)

        return result

    def test_calculate_forecast_01(self):
        "calculate_forecast_01: op successful and values changed"
        _, t = self.create_project()

        operation("cdbpcs_calculate_forecast", t)
        t.Reload()

        # values changed
        self.assertEqual(
            self.get_changed_values(t),
            {"start_time_plan": self.ACT_START, "end_time_plan": self.ACT_END},
        )

    def test_calculate_forecast_02(self):
        "calculate_forecast_02: op fails due to auto_update_time = 0"
        _, t = self.create_project()
        t.auto_update_time = 0

        with self.assertRaises(ElementsError) as error:
            operation("cdbpcs_calculate_forecast", t)
        self.check_error(error, "cdbpcs_forecast_adjustment_failed")
        t.Reload()

        # values unchanged
        self.assertEqual(self.get_changed_values(t), {})

    def test_calculate_forecast_03(self):
        "calculate_forecast_03: op successful, no changes for finished tasks"
        p, t = self.create_project()
        t_180 = self.add_task(p, status=180)
        t_200 = self.add_task(p, status=200)
        t_250 = self.add_task(p, status=250)

        # op fails: no changes for finished tasks
        operation("cdbpcs_calculate_forecast", t)
        t.Reload()
        t_180.Reload()
        t_200.Reload()
        t_250.Reload()

        # values changed
        self.assertEqual(
            self.get_changed_values(t),
            {"start_time_plan": self.ACT_START, "end_time_plan": self.ACT_END},
        )
        self.assertEqual(self.get_changed_values(t_180), {})
        self.assertEqual(self.get_changed_values(t_200), {})
        self.assertEqual(self.get_changed_values(t_250), {})

    def test_calculate_forecast_04(self):
        "calculate_forecast_04: op fails for multiple tasks"
        p, t = self.create_project()
        t2 = self.add_task(p)
        t2.auto_update_time = 0

        with self.assertRaises(ElementsError) as error:
            operation("cdbpcs_calculate_forecast", [t, t2])
        self.check_error(error, "cdbpcs_forecast_adjustment_failed")
        t.Reload()
        t2.Reload()

        self.assertEqual(
            self.get_changed_values(t),
            {"start_time_plan": self.ACT_START, "end_time_plan": self.ACT_END},
        )
        self.assertEqual(self.get_changed_values(t2), {})


@pytest.mark.integration
class TaskMoveStartDateTestCase(testcase.RollbackTestCase):
    # mock __name__ to work around E073093
    @mock.patch.object(tasks, "logging")
    @mock.patch.object(tasks.Task, "checkStructureLock", __name__="checkStructureLock")
    def test_move_start_date_now__with_empty_start_date(
        self, checkStructureLock, logging
    ):
        ctx = mock.MagicMock(dialog={})
        project = common.generate_project()
        task = common.generate_task(project, "task1")
        try:
            task.on_cdbpcs_task_reset_start_time_now(ctx)
        except AttributeError:
            logging.error.assert_called_once()
        checkStructureLock.assert_called_with(ctx=ctx)

    @mock.patch.object(tasks.Task, "reset_start_time")
    @mock.patch.object(tasks.Task, "checkStructureLock", __name__="checkStructureLock")
    def test_move_start_date(self, checkStructureLock, reset_start_time):
        ctx = mock.MagicMock(
            dialog=mock.MagicMock(
                start_time_new="01.01.2022 00:00:00",
                start_time_old="01.01.2023 00:00:00",
            )
        )
        project = common.generate_project()
        task = common.generate_task(project, "task1")
        task.on_cdbpcs_task_reset_start_time_now(ctx)
        checkStructureLock.assert_called_with(ctx=ctx)
        newsd = from_legacy_date_format(ctx.dialog.start_time_new).date()
        self.assertTrue(isinstance(newsd, datetime.date))
        reset_start_time.assert_called_once_with(ctx, newsd)

    @mock.patch.object(tasks, "ensure_date", return_value="01.01.2023 00:00:00")
    def test_reset_start_time(self, ensure_date):
        project = common.generate_project()
        task = common.generate_task(project, "task1")
        newsd = datetime.datetime.strptime(
            "01.01.2022 00:00:00", "%d.%m.%Y %H:%M:%S"
        ).date()
        ctx = mock.MagicMock()
        task.reset_start_time(ctx, newsd)
        ensure_date.assert_called_once()


if __name__ == "__main__":
    unittest.main()
