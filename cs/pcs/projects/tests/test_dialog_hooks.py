#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from datetime import date, timedelta

import pytest
from cdb import auth, testcase
from cdb.objects.org import User
from mock import MagicMock, PropertyMock, call, patch

from cs.pcs.projects import dialog_hooks


def setup_module():
    testcase.run_level_setup()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("-1", True),
        (None, False),
        ("", False),
        ("0", True),
        ("1", False),
        ("99", False),
        ("100", True),
    ],
)
def test_percentage_is_invalid(value, expected):
    assert dialog_hooks.percentage_is_invalid(value) == expected


@pytest.mark.unit
class DialogHookTestCase(testcase.RollbackTestCase):
    @patch.object(dialog_hooks, "_change_days_fcast")
    @patch.object(dialog_hooks.Project, "Update")
    def test_changeDuration_for_project(self, Update, _change_days_fcast):
        _change_days_fcast.return_value = {"key": "val"}
        obj = MagicMock(autospec=dialog_hooks.Project, days_fcast="foo")
        dialog_hooks.changeDuration(obj, "bass")
        _change_days_fcast.assert_called_once_with(obj)
        obj.Update.assert_called_once_with(key="val")

    @patch.object(dialog_hooks, "_change_days_fcast")
    @patch.object(dialog_hooks.Task, "Update")
    def test_changeDuration_for_task(self, Update, _change_days_fcast):
        _change_days_fcast.return_value = {"key": "val"}
        obj = MagicMock(autospec=dialog_hooks.Task, days_fcast="foo")
        dialog_hooks.changeDuration(obj, "bass")
        _change_days_fcast.assert_called_once_with(obj)
        obj.Update.assert_called_once_with(key="val")

    @patch.object(
        dialog_hooks, "_change_start_time_plan", return_value={"key": "value"}
    )
    @patch.object(dialog_hooks.Project, "calculateTimeFrame", return_value=(1, 2, 3))
    def test__change_start_time_act(self, calculateTimeFrame, _change_start_time_plan):
        # mocking objects
        start = date(2021, 1, 1)
        end = date(2021, 1, 5)
        obj = dialog_hooks.Project(start_time_act=start, end_time_act=end)

        # calling method
        dialog_hooks._change_start_time_act(obj, "foo")

        # checking calls
        calculateTimeFrame.assert_called_once_with(start="foo", end=end)

    @patch.object(
        dialog_hooks, "_change_start_time_plan", return_value={"key": "value"}
    )
    @patch.object(dialog_hooks.Calendar, "calculateTimeFrame", return_value=(1, 2, 3))
    def test__change_start_time_act_milestone(
        self, calculateTimeFrame, _change_start_time_plan
    ):
        # mocking objects
        start = date(2021, 1, 1)
        end = date(2021, 1, 5)
        prj = MagicMock(spec=dialog_hooks.Project, calendar_profile_id="foo_cpid")
        obj = dialog_hooks.Task(start_time_act=start, end_time_act=end, milestone=True)

        # calling method
        with patch.object(dialog_hooks.Task, "Project", prj):
            dialog_hooks._change_start_time_act(obj, "foo")

        # checking calls
        calculateTimeFrame.assert_called_once_with("foo_cpid", start="foo", end=end)

    @patch.object(dialog_hooks.Project, "Update")
    @patch.object(dialog_hooks, "_change_start_time_act", return_value={"key": "value"})
    def test_change_start_time_act(self, _change_start_time_act, Update):
        # mocking objects
        start = dialog_hooks.datetime.date(2021, 1, 1)
        obj = dialog_hooks.Project(start_time_act=start)

        # calling method
        dialog_hooks.change_start_time_act(obj, "bass")

        # checking calls
        _change_start_time_act.assert_called_once_with(obj, start)
        Update.assert_called_once_with(key="value")

    @patch.object(dialog_hooks.Project, "calculateTimeFrame", return_value=(1, 2, 4))
    def test__change_end_time_act(self, calculateTimeFrame):
        # mocking objects
        start = date(2021, 1, 1)
        end = date(2021, 1, 5)
        obj = dialog_hooks.Project(start_time_act=start, end_time_act=end)

        # calling method
        result = dialog_hooks._change_end_time_act(obj, "foo")

        # checking calls
        calculateTimeFrame.assert_called_once_with(start=start, end="foo")
        self.assertEqual(result, {"days_act": 4, "end_time_act": "foo"})

    @patch.object(dialog_hooks.Calendar, "calculateTimeFrame", return_value=(1, 2, 4))
    def test__change_end_time_act_milestone(self, calculateTimeFrame):
        # mocking objects
        start = date(2021, 1, 1)
        end = date(2021, 1, 5)
        prj = MagicMock(spec=dialog_hooks.Project, calendar_profile_id="foo_cpid")
        obj = dialog_hooks.Task(start_time_act=start, end_time_act=end, milestone=True)

        # calling method
        with patch.object(dialog_hooks.Task, "Project", prj):
            result = dialog_hooks._change_end_time_act(obj, "foo")

        # checking calls
        calculateTimeFrame.assert_called_once_with("foo_cpid", start=start, end="foo")
        self.assertEqual(result, {"days_act": 4, "end_time_act": "foo"})

    def test__change_efforts_to_zero_value_for_single_task(self):
        obj = dialog_hooks.Project(effort_fcast=0, effort_plan=2, is_group=0)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {"effort_plan": 0.0})

    def test__change_efforts_to_negative_value_for_single_task(self):
        obj = dialog_hooks.Project(effort_fcast=-5, effort_plan=2, is_group=0)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {"effort_fcast": 0.0, "effort_plan": 0.0})

    def test__change_efforts_to_positive_value_for_single_task(self):
        obj = dialog_hooks.Project(effort_fcast=7, effort_plan=3, is_group=0)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {"effort_plan": 7.0})

    def test__change_efforts_to_zero_value_for_group_task(self):
        obj = dialog_hooks.Project(effort_fcast=0, effort_plan=2, is_group=1)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {})

    def test__change_efforts_to_negative_value_for_group_task(self):
        obj = dialog_hooks.Project(effort_fcast=-5, effort_plan=2, is_group=1)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {"effort_fcast": 0.0})

    def test__change_efforts_to_positive_value_for_group_task(self):
        obj = dialog_hooks.Project(effort_fcast=7, effort_plan=3, is_group=1)
        result = dialog_hooks._change_efforts(obj)
        self.assertEqual(result, {})

    @patch.object(dialog_hooks.Project, "Update")
    @patch.object(dialog_hooks, "_change_efforts", return_value={"a": "b"})
    def test_changeEffort(self, _change_efforts, Update):
        obj = dialog_hooks.Project()

        dialog_hooks.changeEffort(obj, "foo")

        _change_efforts.assert_called_once_with(obj)
        Update.assert_called_once_with(a="b")

    def test_changeTemplate_to_template(self):
        obj = dialog_hooks.Project(template=1)
        ctx = MagicMock()

        dialog_hooks.changeTemplate(obj, ctx)

        ctx.set.assert_has_calls(
            [call("mapped_project_manager", ""), call("project_manager", "")]
        )
        ctx.set_fields_readonly.assert_called_once_with(["mapped_project_manager"])
        ctx.set_optional.assert_called_once_with("mapped_project_manager")
        ctx.set_fields_writeable.assert_not_called()
        ctx.set_mandatory.assert_not_called()

    def test_changeTemplate_to_not_template(self):
        obj = dialog_hooks.Project(template=0)
        ctx = MagicMock()

        dialog_hooks.changeTemplate(obj, ctx)

        ctx.set_fields_readonly.assert_not_called()
        ctx.set_optional.assert_not_called()
        ctx.set_fields_writeable.assert_called_once_with(["mapped_project_manager"])
        ctx.set_mandatory.assert_called_once_with("mapped_project_manager")

    @patch.object(dialog_hooks, "_change_start_time_fcast")
    @patch.object(dialog_hooks.Task, "Update")
    def test_changeStartTime(self, Update, _change_start_time_fcast):
        ctx = MagicMock()
        task = dialog_hooks.Task()
        today = date.today()
        task.start_time_fcast = today
        _change_start_time_fcast.return_value = {"key": "val"}
        dialog_hooks.changeStartTime(task, ctx)
        _change_start_time_fcast.assert_called_once_with(task, today)
        Update.assert_called_once_with(key="val")

    @patch.object(dialog_hooks, "_change_end_time_fcast")
    @patch.object(dialog_hooks.Task, "Update")
    def test_changeEndTime(self, Update, _change_end_time_fcast):
        ctx = MagicMock()
        task = dialog_hooks.Task()
        today = date.today()
        task.end_time_fcast = today
        _change_end_time_fcast.return_value = {"key": "val"}
        dialog_hooks.changeEndTime(task, ctx)
        _change_end_time_fcast.assert_called_once_with(task, today)
        Update.assert_called_once_with(key="val")

    def test_changeMilestone_automatic_milestone(self):
        ctx = MagicMock()

        task = dialog_hooks.Task()
        task.milestone = 1
        task.automatic = True
        task.constraint_type = 0

        dialog_hooks.changeMilestone(task, ctx, True)

        self.assertEqual(task.milestone, 1)
        self.assertEqual(task.daytime, None)
        self.assertTrue(task.automatic)

        preferred_language = User.ByKeys(auth.persno).GetPreferredLanguage()
        fieldname = f".mapped_daytime_value_{preferred_language}"

        ctx.set_readonly.assert_called_with(fieldname)
        ctx.set_optional.assert_called_with(fieldname)

    @patch.object(dialog_hooks.Task, "calculateTimeFrame")
    @patch.object(dialog_hooks, "_enable_daytime")
    def test_changeMilestone_with_milestone(self, _enable_daytime, calculateTimeFrame):
        ctx = MagicMock()
        today = date.today()
        date_later = today + timedelta(days=2)
        calculateTimeFrame.return_value = [today, date_later, 2]

        task = dialog_hooks.Task()
        task.start_time_fcast = today
        task.end_time_fcast = date_later
        task.milestone = 1

        dialog_hooks.changeMilestone(task, ctx)

        self.assertEqual(task.start_time_fcast, today)
        self.assertEqual(task.start_time_plan, None)
        self.assertEqual(task.end_time_plan, None)
        self.assertEqual(task.days_fcast, 2)
        self.assertEqual(task.days, None)
        self.assertEqual(task.is_group, 0)
        self.assertEqual(task.effort_fcast, 0.0)

        ctx.set_fields_readonly.assert_called_once_with(
            [
                "cdbpcs_task.effort_fcast",
                "cdbpcs_task.days_fcast",
                "cdbpcs_task.start_time_fcast",
            ]
        )

    @patch.object(dialog_hooks, "_reset_daytime")
    def test_changeMilestone_with_automatic_milestone(self, disable_daytime):
        ctx = MagicMock()

        task = MagicMock()
        task.milestone = 1
        task.automatic = True
        task.start_time_fcast = "start_fcast"
        task.end_time_fcast = "end_fcast"
        task.calculateTimeFrame.return_value = ["start", "end", 2]

        dialog_hooks.changeMilestone(task, ctx, True)
        disable_daytime.assert_called_once()

    @patch.object(dialog_hooks.Task, "calculateTimeFrame")
    @patch.object(dialog_hooks.Task, "getEffortMax")
    @patch.object(dialog_hooks, "_reset_daytime")
    def test_changeMilestone_without_milestone(
        self, disable_daytime, getEffortMax, calculateTimeFrame
    ):
        ctx = MagicMock()
        getEffortMax.return_value = 90

        today = date.today()
        date_later = today + timedelta(days=2)
        calculateTimeFrame.return_value = [today, date_later, 2]

        task = dialog_hooks.Task(
            start_time_fcast=today,
            end_time_fcast=date_later,
            milestone=0,
            start_is_early=1,
            end_is_early=1,
        )

        dialog_hooks.changeMilestone(task, ctx)

        self.assertEqual(task.effort_fcast, 90)

        ctx.set_fields_writeable.assert_called_once_with(
            [
                "cdbpcs_task.effort_fcast",
                "cdbpcs_task.days_fcast",
                "cdbpcs_task.start_time_fcast",
            ]
        )
        disable_daytime.assert_called_once()

    @patch.object(dialog_hooks, "_change_autoUpdateEffort")
    def test_changeAutoUpdateEffort(self, _):
        task = dialog_hooks.Task()
        dialog_hooks.changeAutoUpdateEffort(task)
        dialog_hooks._change_autoUpdateEffort.assert_called_with(task)

    @patch.object(dialog_hooks.Task, "Update")
    def test_change_autoUpdateEffort(self, _):
        task = dialog_hooks.Task(is_group=1, auto_update_effort=True, effort_plan=1.00)
        dialog_hooks.changeAutoUpdateEffort(task)
        changes = {"effort_fcast": 1.00}
        task.Update.assert_called_once_with(**changes)

    @patch.object(dialog_hooks.Task, "Update")
    def test_change_autoUpdateEffort_reset_effort_fcast(self, _):
        task = dialog_hooks.Task(is_group=1, auto_update_effort=False)
        dialog_hooks.changeAutoUpdateEffort(task)
        changes = {"effort_fcast": 0.0}
        task.Update.assert_called_once_with(**changes)

    @patch.object(dialog_hooks, "inform_user")
    @patch.object(dialog_hooks.Task, "Update")
    def test_change_constraint_type_none(self, Update, inform_user):
        ctx = MagicMock()
        today = date.today()
        obj = dialog_hooks.Task(
            constraint_type=None,
            start_time_fcast=today,
        )
        # call
        dialog_hooks.change_constraint_type(obj, ctx)

        # checks
        ctx.set_optional.assert_called_once_with("constraint_date")
        ctx.set_mandatory.assert_not_called()
        Update.assert_called_once_with(constraint_type="0")
        inform_user.assert_called_once_with(ctx, "cdbpcs_constraint_type_needed")

    @patch.object(dialog_hooks, "inform_user")
    @patch.object(dialog_hooks.Task, "Update")
    def test_change_constraint_type_early(self, Update, inform_user):
        ctx = MagicMock()
        today = date.today()
        obj = dialog_hooks.Task(
            constraint_type="2",
            start_time_fcast=today,
        )
        # call
        dialog_hooks.change_constraint_type(obj, ctx)

        # checks
        ctx.set_optional.assert_not_called()
        ctx.set_mandatory.assert_called_once_with("constraint_date")
        Update.assert_called_once_with(constraint_date=today)
        inform_user.assert_not_called()

    @patch.object(dialog_hooks, "inform_user")
    @patch.object(dialog_hooks.Task, "Update")
    def test_change_constraint_type_late(self, Update, inform_user):
        ctx = MagicMock()
        today = date.today()
        obj = dialog_hooks.Task(constraint_type="3", end_time_fcast=today)
        # call
        dialog_hooks.change_constraint_type(obj, ctx)

        # checks
        ctx.set_optional.assert_not_called()
        ctx.set_mandatory.assert_called_once_with("constraint_date")
        Update.assert_called_once_with(constraint_date=today)
        inform_user.assert_not_called()

    def test_checkAutomatic_msp_active(self):
        project = MagicMock(autospec=dialog_hooks.Project, msp_active=1)
        with patch.object(
            dialog_hooks.Task,
            "Project",
            new_callable=PropertyMock,
            return_value=project,
        ):
            task = dialog_hooks.Task(automatic=0, auto_update_time=1)
            dialog_hooks.checkAutomatic(task, None)
            self.assertEqual(task.automatic, 0)
            self.assertEqual(task.auto_update_time, 2)

    def test_checkAutomatic_msp_inactive(self):
        project = MagicMock(autospec=dialog_hooks.Project, msp_active=0)
        with patch.object(
            dialog_hooks.Task,
            "Project",
            new_callable=PropertyMock,
            return_value=project,
        ):
            task = dialog_hooks.Task(automatic=0, auto_update_time=1)
            dialog_hooks.checkAutomatic(task, None)
            self.assertEqual(task.automatic, 1)
            self.assertEqual(task.auto_update_time, 1)

    def test_state_dialog_set_act_date_summary(self):
        start_time_act = date(2022, 3, 20)
        end_time_act = date(2022, 3, 30)
        task = MagicMock(start_time_act=start_time_act, end_time_act=end_time_act)
        ctx = MagicMock()
        t = dialog_hooks.Task
        for status in [
            t.NEW.status,
            t.READY.status,
            t.DISCARDED.status,
            t.EXECUTION.status,
        ]:
            ctx.reset_mock()
            dialog_hooks.state_dialog_set_act_date_summary(task, ctx, status)
            ctx.set_readonly.assert_has_calls(
                [call(dialog_hooks.start_time_field), call(dialog_hooks.end_time_field)]
            )
            ctx.set.assert_has_calls(
                [
                    call(dialog_hooks.start_time_field, None),
                    call(dialog_hooks.end_time_field, None),
                ]
            )

        # FINISHED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_summary(task, ctx, t.FINISHED.status)
        ctx.set_readonly.assert_has_calls(
            [call(dialog_hooks.start_time_field), call(dialog_hooks.end_time_field)]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, None),
            ]
        )
        # COMPLETED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_summary(task, ctx, t.COMPLETED.status)
        ctx.set_readonly.assert_has_calls(
            [call(dialog_hooks.start_time_field), call(dialog_hooks.end_time_field)]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, end_time_act),
            ]
        )

    @patch.object(dialog_hooks, "datetime")
    def test_state_dialog_set_act_date_single(self, _datetime):
        _today = _datetime.date.today.return_value
        start_time_act = date(2022, 3, 20)
        end_time_act = date(2022, 3, 30)
        task = MagicMock(start_time_act=start_time_act, end_time_act=end_time_act)
        ctx = MagicMock()
        t = dialog_hooks.Task

        for status in [t.NEW.status, t.READY.status, t.DISCARDED.status]:
            ctx.reset_mock()
            dialog_hooks.state_dialog_set_act_date_single(True, task, ctx, status)
            ctx.set_readonly.assert_has_calls(
                [
                    call(dialog_hooks.start_time_field),
                    call(dialog_hooks.end_time_field),
                ]
            )
            ctx.set.assert_has_calls(
                [
                    call(dialog_hooks.start_time_field, None),
                    call(dialog_hooks.end_time_field, None),
                ]
            )

        # EXECUTION
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_single(
            True, task, ctx, t.EXECUTION.status
        )
        ctx.set_writeable.assert_called_once_with(dialog_hooks.start_time_field)
        ctx.set_readonly.assert_called_once_with(dialog_hooks.end_time_field)

        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, _today),
                call(dialog_hooks.end_time_field, None),
            ]
        )

        # FINISHED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_single(
            True, task, ctx, t.FINISHED.status
        )
        ctx.set_writeable.assert_has_calls(
            [
                call(dialog_hooks.start_time_field),
                call(dialog_hooks.end_time_field),
            ]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, _today),
            ]
        )
        # COMPLETED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_single(
            True, task, ctx, t.COMPLETED.status
        )
        ctx.set_writeable.assert_has_calls(
            [call(dialog_hooks.start_time_field), call(dialog_hooks.end_time_field)]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, end_time_act),
            ]
        )

    @patch.object(dialog_hooks, "datetime")
    def test_state_dialog_set_act_date_single_string(self, _datetime):
        _today = _datetime.date.today.return_value
        start_time_act = date(2022, 3, 20)
        end_time_act = date(2022, 3, 30)
        start_time_input = "20.03.2022"
        end_time_input = "30.03.2022"
        task = MagicMock(start_time_act=start_time_input, end_time_act=end_time_input)
        ctx = MagicMock()
        t = dialog_hooks.Task
        # FINISHED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_single(
            True, task, ctx, t.FINISHED.status
        )
        ctx.set_writeable.assert_has_calls(
            [
                call(dialog_hooks.start_time_field),
                call(dialog_hooks.end_time_field),
            ]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, _today),
            ]
        )
        # COMPLETED
        ctx.reset_mock()
        dialog_hooks.state_dialog_set_act_date_single(
            True, task, ctx, t.COMPLETED.status
        )
        ctx.set_writeable.assert_has_calls(
            [call(dialog_hooks.start_time_field), call(dialog_hooks.end_time_field)]
        )
        ctx.set.assert_has_calls(
            [
                call(dialog_hooks.start_time_field, start_time_act),
                call(dialog_hooks.end_time_field, end_time_act),
            ]
        )

    @patch.object(dialog_hooks, "state_dialog_set_act_date")
    @patch.object(dialog_hooks.Project, "ByKeys")
    @patch.object(dialog_hooks.StateDefinition, "KeywordQuery")
    def test_task_changeTargetStatus(
        self, kwQuery, prj_ByKeys, state_dialog_set_act_date
    ):
        values = {".zielstatus": "Execution"}
        obj = MagicMock(cdb_objektart="cdbpcs_task", cdb_project_id="P1")
        hook = MagicMock()
        hook.get_new_values.return_value = values
        hook.get_operation_state_info().get_objects.return_value = [obj]
        kwQuery.return_value = [MagicMock(StateText={"": "Execution"}, statusnummer=50)]
        prj_ByKeys.return_value = MagicMock(act_vals_status_chng=True)
        dialog_hooks.Task.changeTargetStatus(hook)
        state_dialog_set_act_date.assert_called_once_with(True, obj, hook, 50)

    def test_get_dialog_attr_without_dialog(self):
        ctx = object()
        self.assertEqual(None, dialog_hooks.Task.get_dialog_attr(ctx, "foo"))

    def test_get_dialog_attr_with_dialog_without_attr(self):
        ctx = MagicMock()
        d = {"foo": ""}
        ctx.dialog = MagicMock()
        ctx.dialog.__getitem__.side_effect = d.__getitem__
        self.assertEqual(None, dialog_hooks.Task.get_dialog_attr(ctx, "foo"))

    def test_get_dialog_attr_with_dialog_and_attr(self):
        ctx = MagicMock()
        d = {"foo": "bar"}
        ctx.dialog = MagicMock()
        ctx.dialog.__getitem__.side_effect = d.__getitem__
        self.assertEqual("bar", dialog_hooks.Task.get_dialog_attr(ctx, "foo"))

    @staticmethod
    def state_dialog_pre_compare(start, end):
        ctx = MagicMock()
        d = {
            "start_time_act": start,
            "end_time_act": end,
        }
        ctx.dialog = MagicMock()
        ctx.dialog.__getitem__.side_effect = d.__getitem__

        cp = MagicMock()
        cp.valid_from = date(2023, 4, 1)
        cp.valid_until = date(2023, 4, 30)
        with patch.object(
            dialog_hooks.Project,
            "CalendarProfile",
            new_callable=PropertyMock,
            return_value=cp,
        ):
            project = dialog_hooks.Project()
            with patch.object(
                dialog_hooks.Task,
                "Project",
                new_callable=PropertyMock,
                return_value=project,
            ):
                task = dialog_hooks.Task()
                task.state_dialog_pre(ctx)

    def test_state_dialog_pre_dates_within_calendar(self):
        self.state_dialog_pre_compare(
            start="05.04.2023",
            end="15.04.2023",
        )

    def test_state_dialog_pre_start_outside_calendar(self):
        with self.assertRaises(dialog_hooks.ue.Exception) as e:
            self.state_dialog_pre_compare(
                start="05.03.2023",
                end="15.04.2023",
            )
            msg = dialog_hooks.ue.Exception("cdb_cal_outside_range", 1)
            self.assertEqual(str(e.exception), msg.msg.getText("", True))

    def test_state_dialog_pre_end_outside_calendar(self):
        with self.assertRaises(dialog_hooks.ue.Exception) as e:
            self.state_dialog_pre_compare(
                start="05.04.2023",
                end="01.05.2023",
            )
            msg = dialog_hooks.ue.Exception("cdb_cal_outside_range", 1)
            self.assertEqual(str(e.exception), msg.msg.getText("", True))

    def _check_daytime_values(self, m, a, d, legal=True):
        mock_ctx = MagicMock()
        mock_ctx.dialog = {"daytime": d}
        dialog_hooks.changeDaytime(MagicMock(milestone=m, automatic=a), mock_ctx)
        if not legal:
            mock_ctx.set.assert_called_once_with("daytime", "")
        else:
            mock_ctx.set.assert_not_called()

    def test_changeDaytime_legal(self):
        self._check_daytime_values(True, False, "0")
        self._check_daytime_values(True, False, "1")
        self._check_daytime_values(True, True, "")
        self._check_daytime_values(True, False, "")
        self._check_daytime_values(False, True, "")
        self._check_daytime_values(False, False, "")

    def test_changeDaytime_illegal(self):
        self._check_daytime_values(False, True, "0", False)
        self._check_daytime_values(False, False, "0", False)
        self._check_daytime_values(False, True, "1", False)
        self._check_daytime_values(False, False, "1", False)
        self._check_daytime_values(True, True, "0", False)
        self._check_daytime_values(True, True, "1", False)

    @patch.object(dialog_hooks, "_change_automatic")
    def test_changeAutomatic(self, _change_automatic):
        obj = MagicMock()
        _change_automatic.return_value = {"a": 1}

        dialog_hooks.changeAutomatic(obj, "ctx", False)

        _change_automatic.assert_called_once_with(obj, "ctx", False)
        obj.Update.assert_called_once_with(a=1)

    @patch.object(dialog_hooks, "_change_automatic")
    def test_changeAutomatic_no_changes(self, _change_automatic):
        obj = MagicMock()
        _change_automatic.return_value = {}

        dialog_hooks.changeAutomatic(obj, "ctx", True)

        _change_automatic.assert_called_once_with(obj, "ctx", True)
        obj.Update.assert_not_called()

    @patch.object(dialog_hooks, "_reset_daytime")
    @patch.object(dialog_hooks, "_enable_daytime")
    def test_change_automatic_web(self, enable_daytime, disable_daytime):
        def _permutation(web, auto, milestone, enable):
            obj.milestone = milestone
            obj.automatic = auto
            if enable:
                enable_calls.append(call(obj, "ctx"))
            else:
                if not web:
                    if auto:
                        disable_calls.append(call(obj, "ctx", readonly=False, value=""))
                    else:
                        disable_calls.append(call(obj, "ctx"))
                else:
                    disable_calls.append(call(obj, "ctx", readonly=True))

            changes = dialog_hooks._change_automatic(obj, "ctx", web)
            disable_daytime.assert_has_calls(disable_calls)
            enable_daytime.assert_has_calls(enable_calls)
            self.assertEquals({}, changes)

        obj = MagicMock()
        enable_daytime.return_value = {}
        disable_daytime.return_value = {}
        enable_calls = []
        disable_calls = []

        _permutation(True, True, True, False)
        _permutation(True, True, False, False)
        _permutation(True, False, False, False)
        _permutation(True, False, True, True)

    @patch.object(dialog_hooks, "_reset_daytime")
    def test_change_automatic_auto_update_time(
        self,
        disable_daytime,
    ):

        disable_daytime.return_value = None
        obj = MagicMock()
        ctx = MagicMock()

        obj.automatic = 0
        obj.auto_update_time = 1
        changes = dialog_hooks._change_automatic(obj, ctx, False)
        self.assertEquals({"auto_update_time": 2}, changes)

        obj.automatic = 1
        obj.auto_update_time = 1
        changes = dialog_hooks._change_automatic(obj, ctx, False)
        self.assertEquals({}, changes)
