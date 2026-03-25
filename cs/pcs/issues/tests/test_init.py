#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import testcase, ue
from mock import MagicMock, Mock, call, patch

from cs.pcs import issues
from cs.pcs.projects.project_status import Project
from cs.pcs.projects.tasks import Task


@pytest.mark.unit
class WithFrozen(testcase.RollbackTestCase):
    def test_set_frozen_missing_attr(self):
        "nothing happens if cdbpcs_frozen is missing"
        obj = issues.WithFrozen()
        obj.Project = MagicMock(spec=Project)
        obj.Project.status = obj.Project.FROZEN.status
        self.assertIsNone(obj.set_frozen(None))
        self.assertFalse(hasattr(obj, "cdbpcs_frozen"))

    def test_set_frozen_missing_project(self):
        "nothing happens if project is missing"
        obj = issues.WithFrozen()
        obj.cdbpcs_frozen = 1
        self.assertIsNone(obj.set_frozen(None))
        self.assertFalse(hasattr(obj, "Project"))
        self.assertEqual(obj.cdbpcs_frozen, 1)

    def test_set_frozen_0(self):
        "cdbpcs_frozen is not set if Project is not FROZEN"
        obj = issues.WithFrozen()
        obj.cdbpcs_frozen = 1
        obj.Project = MagicMock(spec=Project)
        obj.Project.status = "not frozen"
        self.assertIsNone(obj.set_frozen(None))
        self.assertEqual(obj.cdbpcs_frozen, 0)

    def test_set_frozen_1(self):
        "cdbpcs_frozen is set if Project is FROZEN"
        obj = issues.WithFrozen()
        obj.cdbpcs_frozen = 0
        obj.Project = MagicMock(spec=Project)
        obj.Project.status = obj.Project.FROZEN.status
        self.assertIsNone(obj.set_frozen(None))
        self.assertEqual(obj.cdbpcs_frozen, 1)

    def test_event_map(self):
        "make sure handlers are registered for events"
        self.assertEqual(
            issues.WithFrozen.event_map,
            {
                (("create", "copy"), "pre"): "set_frozen",
            },
        )


@pytest.mark.unit
class Issue(testcase.RollbackTestCase):
    def test_event_map(self):
        "make sure handlers are registered for events"
        self.assertEqual(
            issues.Issue.event_map,
            {
                (("create", "copy"), "pre"): (
                    "validate_responsibility",
                    "set_defaults",
                    "setIssueID",
                ),
                (("create", "copy", "modify"), "post"): (
                    "newChangeLog",
                    "check_project_role_needed",
                ),
                (("create"), "pre_mask"): (
                    "setRelshipFieldsReadOnly",
                    "prevent_creating_issue",
                ),
                (("create", "copy", "modify"), "pre"): ("prevent_creating_issue"),
                (("modify", "info"), "pre_mask"): ("setFields"),
                (("delete", "state_change", "cs_tasks_delegate"), "post"): (
                    "check_project_role_needed"
                ),
                ("wf_step", ("pre_mask", "dialogitem_change")): ("handle_waiting_for"),
            },
        )

    def test_getIssueID(self):
        self.assertEqual(
            issues.Issue.getIssueID(123),
            "ISS00000123",
        )

    @patch("cdb.util.nextval")
    def test_setIssueID(self, nextval):
        issue = MagicMock(spec=issues.Issue)
        issues.Issue.setIssueID(issue, "unused_ctx")
        self.assertEqual(issue.issue_id, issue.getIssueID.return_value)
        issue.getIssueID.assert_called_once_with(nextval.return_value)

    @patch("cs.pcs.issues.auth", persno="foo")
    @patch("cdb.util.nextval", return_value=0)
    @patch("cs.pcs.issues.IssueChangeLog", autospec=True)
    def test_newChangeLog_first_changelog(self, issueChangeLog, nextval, mocked_auth):
        "Issue, add the first new Changelog -> add all data"
        issue = MagicMock(spec=issues.Issue)
        issue.cdb_mdate = None
        # set attribute accessable from issue
        real_dict = {"attr_for_changelog": None}
        issue.__getitem__.side_effect = real_dict.__getitem__

        issue._change_log_attrs = ["attr_for_changelog"]
        issue._key_dict = Mock(return_value={"key_1": "value_1"})

        # set Reference to changelogs
        issue.ChangeLogs = []

        mocked_ctx = Mock(spec=["error"])
        mocked_ctx.error = 0
        expected_parameters = {
            "key_1": "value_1",
            "id": 0,
            "changed_by": "foo",
            "changed_at": None,
            "attr_for_changelog": None,
        }

        issues.Issue.newChangeLog(issue, mocked_ctx)
        issueChangeLog.Create.assert_called_once_with(**expected_parameters)

    @patch("cs.pcs.issues.auth", persno="foo")
    @patch("cdb.util.nextval", return_value=0)
    @patch("cs.pcs.issues.IssueChangeLog", autospec=True)
    def test_newChangeLog_second_or_later_changelog(
        self, issueChangeLog, nextval, mocked_auth
    ):
        "Issue add a new Changelog if there is already one -> add only changed data"
        issue = MagicMock(spec=issues.Issue)
        issue.cdb_mdate = None
        issue._key_dict = Mock(return_value={"key_1": "value_1"})
        # set Reference to changelogs
        issue.ChangeLogs = ["previous_changelog_entry"]

        mocked_ctx = MagicMock()
        # there is no error in ctx
        mocked_ctx.error = 0
        # the only changed param is 'bar'
        mocked_sa = MagicMock()
        real_sys_args_dict = {"changed_attrs": "bar"}
        mocked_sa.__getitem__.side_effect = real_sys_args_dict.__getitem__
        mocked_ctx.sys_args = mocked_sa
        # new value for 'bar' is 'baz'
        mocked_d = MagicMock()
        real_dialog_dict = {"bar": "baz"}
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d

        expected_parameters = {
            "key_1": "value_1",
            "id": 0,
            "changed_by": "foo",
            "changed_at": None,
            "bar": "baz",
        }

        issues.Issue.newChangeLog(issue, mocked_ctx)
        issueChangeLog.Create.assert_called_once_with(**expected_parameters)

    @patch("cs.pcs.issues.auth", persno="foo")
    @patch("cdb.util.nextval", return_value=0)
    @patch("cs.pcs.issues.IssueChangeLog", autospec=True)
    def test_newChangeLog_to_waiting_for_changelog(
        self, issueChangeLog, nextval, mocked_auth
    ):
        "Issue add a new Changelog if there is already one -> add only changed data"
        issue = MagicMock(spec=issues.Issue)
        issue.cdb_mdate = None
        issue.add_waiting_for_changelog.return_value = "foo"
        issue._key_dict = Mock(return_value={"key_1": "value_1"})
        # set Reference to changelogs
        issue.ChangeLogs = ["previous_changelog_entry"]

        mocked_ctx = MagicMock()
        # there is no error in ctx
        mocked_ctx.error = 0
        mocked_ctx.action = "state_change"

        expected_parameters = {
            "key_1": "value_1",
            "id": 0,
            "changed_by": "foo",
            "changed_at": None,
        }
        issues.Issue.newChangeLog(issue, mocked_ctx)
        issue.add_waiting_for_changelog.assert_called_once_with(
            mocked_ctx, expected_parameters
        )

    @patch("cs.pcs.issues.IssueChangeLog", autospec=True)
    def test_add_waiting_for_changelog(
        self,
        issueChangeLog,
    ):
        issue = MagicMock(spec=issues.Issue)
        issue.cdb_mdate = None
        issue.status = 70
        issue.reason = "the reason"
        issue.waiting_for = "person"
        given_parameters = {
            "foo": "bar",
        }
        mocked_ctx = MagicMock()
        issues.Issue.add_waiting_for_changelog(issue, mocked_ctx, given_parameters)
        expected_parameters = {
            "foo": "bar",
            "reason": "the reason",
            "waiting_for": "person",
        }
        issueChangeLog.Create.assert_called_once_with(**expected_parameters)

    @patch("cs.pcs.issues.IssueChangeLog", autospec=True)
    def test_add_waiting_for_changelog_remove_reason(
        self,
        issueChangeLog,
    ):
        issue = MagicMock(spec=issues.Issue)
        issue.cdb_mdate = None
        given_parameters = {
            "foo": "bar",
        }
        mocked_ctx = MagicMock()
        mocked_ctx.old._fields = {"status": 70}
        issues.Issue.add_waiting_for_changelog(issue, mocked_ctx, given_parameters)
        expected_parameters = {
            "foo": "bar",
            "reason": "",
            "waiting_for": "",
        }
        issueChangeLog.Create.assert_called_once_with(**expected_parameters)

    def test_check_project_role_needed(self):
        "Issue, check_project_role_needed of referenced project is called correctly"
        project = MagicMock(spec=Project)
        issue = MagicMock(spec=issues.Issue)
        # mock Reference to Project
        issue.Project = project
        issues.Issue.check_project_role_needed(issue, "test_ctx")
        project.check_project_role_needed.assert_called_once_with("test_ctx")

    def test_setFields(self):
        "Issue, test if setFields calls functions correctly"
        issue = MagicMock(spec=issues.Issue)
        issue.getReadOnlyFields = Mock(return_value="foo")
        mocked_ctx = MagicMock(spec=["set_fields_readonly", "action"])
        mocked_ctx.action = "bar"

        issues.Issue.setFields(issue, mocked_ctx)

        mocked_ctx.set_fields_readonly.assert_called_once_with("foo")
        issue.getReadOnlyFields.assert_called_once_with(action="bar")

    def test_on_modify_pre_no_whitelisted_attr_changed_in_dialog(self):
        "Issue, dialog contains no attribute whitelisted for changelog"
        issue = MagicMock(spec=issues.Issue)
        # whitelisted attributes
        issue._change_log_attrs = ["attr_for_changelog"]
        mocked_ctx = Mock(spec=["dialog", "set"])

        # dialog contains no attribute from whitelist
        mocked_d = MagicMock(autospec=dict)
        del mocked_d.attr_for_changelog
        mocked_ctx.dialog = mocked_d

        # object does not contain attribute from dialog, but from whitelist
        mocked_o = MagicMock()
        real_object_dict = {"attr_for_changelog": "foo"}
        mocked_o.__getitem__.side_effect = real_object_dict.__getitem__
        mocked_ctx.object = mocked_o

        issues.Issue.on_modify_pre(issue, mocked_ctx)
        mocked_ctx.set.assert_called_once_with("cdb::argument.changed_attrs", "")

    def test_on_modify_pre_attr_changed_in_dialog_not_in_object(self):
        "Issue, dialog contains contains changed attribute, thats not in object"
        issue = MagicMock(spec=issues.Issue)
        # whitelisted attributes
        issue._change_log_attrs = ["attr_for_changelog"]
        mocked_ctx = Mock(spec=["dialog", "set"])

        # dialog contains attribute from whitelist
        mocked_d = MagicMock()
        real_dialog_dict = {"attr_for_changelog": "bar"}
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d

        # object does not contain attribute from dialog
        mocked_o = MagicMock()
        real_object_dict = {"attr_not_in_dialog": "bar"}
        mocked_o.__getitem__.side_effect = real_object_dict.__getitem__
        mocked_ctx.object = mocked_o

        with self.assertRaises(KeyError):
            issues.Issue.on_modify_pre(issue, mocked_ctx)

    def test_on_modify_pre_attr_changed_in_dialog_and_in_object(self):
        "Issue, store attributes changed in dialog for changelog"
        issue = MagicMock(spec=issues.Issue)
        # whitelisted attributes
        issue._change_log_attrs = ["attr_for_changelog"]
        mocked_ctx = Mock(spec=["dialog", "set"])

        # dialog contains attribute from whitelist
        mocked_d = MagicMock()
        real_dialog_dict = {"attr_for_changelog": "bar"}
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d

        # object does not contain attribute from dialog
        mocked_o = MagicMock()
        real_object_dict = {"attr_for_changelog": "foo"}
        mocked_o.__getitem__.side_effect = real_object_dict.__getitem__
        mocked_ctx.object = mocked_o

        issues.Issue.on_modify_pre(issue, mocked_ctx)
        mocked_ctx.set.assert_called_once_with(
            "cdb::argument.changed_attrs", "attr_for_changelog"
        )

    @mock.patch.object(issues.IssueCategory, "KeywordQuery")
    @mock.patch.object(issues.IssuePriority, "KeywordQuery")
    def test_get_create_defaults_with_default_set(
        self, KeywordQueryPrio, KeywordQueryCat
    ):
        "Issue, apply defaults on create with defaults already set"

        KeywordQueryCat.return_value = [mock.MagicMock(category="Cat1")]
        KeywordQueryPrio.return_value = [mock.MagicMock(priority="Prio1")]
        issue = MagicMock(spec=issues.Issue)
        self.assertEqual(
            issues.Issue.get_create_defaults(issue),
            {"category": "Cat1", "priority": "Prio1"},
        )

    @mock.patch.object(issues.IssueCategory, "KeywordQuery")
    @mock.patch.object(issues.IssuePriority, "KeywordQuery")
    def test_get_create_defaults_with_default_not_set(
        self, KeywordQueryPrio, KeywordQueryCat
    ):
        "Issue, apply defaults on create with not defaults set"

        KeywordQueryPrio.return_value = []
        KeywordQueryCat.return_value = []
        issue = MagicMock(spec=issues.Issue)
        self.assertEqual(
            issues.Issue.get_create_defaults(issue),
            {"category": None, "priority": None},
        )

    @mock.patch("cdb.auth.get_department", return_value="foo")
    def test_on_create_pre_mask(self, get_department):
        "Issue, apply defaults on create"

        ctx = MagicMock()
        issue = MagicMock(spec=issues.Issue)
        issue.get_create_defaults.return_value = {
            "category": "Cat1",
            "priority": "Prio1",
        }
        issues.Issue.on_create_pre_mask(issue, ctx)
        ctx.set.assert_has_calls(
            [
                mock.call("category", "Cat1"),
                mock.call("priority", "Prio1"),
            ]
        )
        ctx.keep.assert_has_calls(
            [
                mock.call(issue.CREATE_DEFAULTS_APPLIED, 1),
            ]
        )
        # assert get_department was called
        self.assertEqual(issue.division, "foo")
        get_department.assert_called_once()

    def test_attach_issue_to_completed_project_no_exception(self):
        "Issue, attached to a project which is not discarded or completed"
        ctx = MagicMock()
        issue = MagicMock(
            spec=issues.Issue,
            Task=MagicMock(spec=Task),
            Project=MagicMock(spec=Project),
        )
        self.assertIsNone(issues.Issue.prevent_creating_issue(issue, ctx))

    def test_attach_issue_to_completed_project(self):
        "Issue, attached to a project which is completed, should raise a exception"
        ctx = MagicMock()
        project = MagicMock(spec=Project, status=200)
        issue = MagicMock(spec=issues.Issue, Project=project)
        with self.assertRaises(ue.Exception) as error:
            issues.Issue.prevent_creating_issue(issue, ctx)
        self.assertEqual(
            str(error.exception),
            str(ue.Exception("open_issue_to_completed_project")),
        )

    def test_attach_issue_to_completed_task(self):
        "Issue, attached to a task which is completed, should raise a exception"
        ctx = MagicMock()
        issue = MagicMock(spec=issues.Issue)
        task = MagicMock(spec=Task, status=200)
        issue.Task = task
        with self.assertRaises(ue.Exception) as error:
            issues.Issue.prevent_creating_issue(issue, ctx)
        self.assertEqual(
            str(error.exception),
            str(ue.Exception("open_issue_to_completed_task")),
        )

    def test_on_copy_pre_mask(self):
        "Issue, apply defaults on copy"

        ctx = MagicMock()
        issue = MagicMock(spec=issues.Issue)
        issue.get_copy_defaults.return_value = {
            "issue_id": "",
            "reason": "foo",
            "cdbpcs_isss_txt": "bar",
        }
        issues.Issue.on_copy_pre_mask(issue, ctx)
        ctx.set.assert_has_calls(
            [
                mock.call("issue_id", ""),
                mock.call("reason", "foo"),
                mock.call("cdbpcs_isss_txt", "bar"),
            ]
        )
        ctx.keep.assert_has_calls(
            [
                mock.call(issue.COPY_DEFAULTS_APPLIED, 1),
            ]
        )

    def test_set_defaults_create_defaults_already_applied(self):
        "Issue, with CREATE_DEFAULTS_APPLIED flag"

        ctx = MagicMock(action="create")
        issue = MagicMock(spec=issues.Issue)
        issue.get_create_defaults.return_value = {"reason": "foo"}
        ctx.ue_args.get_attribute_names.return_value = {
            issue.CREATE_DEFAULTS_APPLIED: 1
        }
        issues.Issue.set_defaults(issue, ctx)
        ctx.set.assert_not_called()

    @mock.patch("cdb.auth.get_department", return_value="foo")
    def test_set_defaults_create_defaults_not_applied_no_rest_api(self, get_department):
        "Issue, without CREATE_DEFAULTS_APPLIED flag and without REST API"

        ctx = MagicMock(action="create", uses_restapi=False)
        issue = MagicMock(spec=issues.Issue)
        issue.get_create_defaults.return_value = {"reason": "bar"}
        ctx.ue_args.get_attribute_names.return_value = {}
        issues.Issue.set_defaults(issue, ctx)
        ctx.set.assert_has_calls(
            [
                mock.call("reason", "bar"),
                mock.call("division", "foo"),
            ]
        )
        get_department.assert_called_once()

    @mock.patch("cdb.auth.get_department", return_value="foo")
    def test_set_defaults_create_defaults_not_applied_rest_api(self, get_department):
        "Issue, without CREATE_DEFAULTS_APPLIED flag and with REST API"

        ctx = MagicMock(action="create", uses_restapi=True)
        issue = MagicMock(spec=issues.Issue)
        issue.get_create_defaults.return_value = {"reason": "bar", "reason2": "baz"}
        ctx.ue_args.get_attribute_names.return_value = {}
        dialog = mock.MagicMock()
        dialog.__getitem__.return_value = "bam"
        del dialog.reason
        del dialog.division
        ctx.dialog = dialog
        issues.Issue.set_defaults(issue, ctx)
        # reason2 is not overwritten by default
        ctx.set.assert_has_calls(
            [
                mock.call("reason", "bar"),
                mock.call("division", "foo"),
            ]
        )
        get_department.assert_called_once()

    def test_set_defaults_copy_defaults_already_applied(self):
        "Issue, with COPY_DEFAULTS_APPLIED flag"

        ctx = MagicMock(action="copy")
        issue = MagicMock(spec=issues.Issue)
        issue.get_copy_defaults.return_value = {"reason": "foo"}
        ctx.ue_args.get_attribute_names.return_value = {issue.COPY_DEFAULTS_APPLIED: 1}
        issues.Issue.set_defaults(issue, ctx)
        ctx.set.assert_not_called()

    def test_set_defaults_copy_defaults_not_applied_no_rest_api(self):
        "Issue, without COPY_DEFAULTS_APPLIED flag and without REST API"

        ctx = MagicMock(action="copy", uses_restapi=False)
        issue = MagicMock(spec=issues.Issue)
        issue.get_copy_defaults.return_value = {"reason": "bar"}
        ctx.ue_args.get_attribute_names.return_value = {}
        issues.Issue.set_defaults(issue, ctx)
        ctx.set.assert_called_once_with("reason", "bar")

    def test_set_defaults_copy_defaults_not_applied_rest_api(self):
        "Issue, without COPY_DEFAULTS_APPLIED flag and with REST API"

        ctx = MagicMock(action="copy", uses_restapi=True)
        issue = MagicMock(spec=issues.Issue)
        issue.get_copy_defaults.return_value = {"reason": "bar", "reason2": "baz"}
        ctx.ue_args.get_attribute_names.return_value = {}
        dialog = mock.MagicMock()
        dialog.__getitem__.return_value = "bam"
        del dialog.reason
        ctx.dialog = dialog
        issues.Issue.set_defaults(issue, ctx)
        # reason2 is not overwritten by default
        ctx.set.assert_has_calls([mock.call("reason", "bar")])

    def test_on_cdb_show_responsible_now(self):
        "Issue, test if openSubject is called"
        issue = MagicMock(spec=issues.Issue)
        issue.openSubject = Mock(return_value="foo")

        result = issues.Issue.on_cdb_show_responsible_now(issue, "unused_ctx")
        issue.openSubject.assert_called_once()
        self.assertEqual(result, "foo")

    def test_on_delete_post(self):
        "Issue, test if changelog reference delete is called"
        issue = MagicMock(spec=issues.Issue)
        issue.ChangeLogs = MagicMock()
        issue.ChangeLogs.Delete = MagicMock()
        issues.Issue.on_delete_post(issue, "unused_ctx")
        issue.ChangeLogs.Delete.assert_called_once()

    def test_on_wf_step_handle_waitingfor(self):
        issue = MagicMock(spec=issues.Issue)
        mocked_ctx = MagicMock(
            spec=[
                "set_fields_readonly",
                "set_fields_writeable",
                "set_mandatory",
                "set_optional",
            ]
        )
        dialog_mock = MagicMock()
        dialog_mock.zielstatus_int = "70"
        mocked_ctx.dialog = dialog_mock
        issues.Issue.handle_waiting_for(issue, mocked_ctx)
        mocked_ctx.set_fields_readonly.assert_not_called()
        mocked_ctx.set_fields_writeable.assert_called_once_with(
            ["waiting_for_name", "waiting_reason"]
        )
        mocked_ctx.set_mandatory.assert_has_calls(
            [
                call("waiting_for_name"),
                call("waiting_reason"),
            ]
        )
        mocked_ctx.set_optional.assert_not_called()

    def test_on_wf_step_handle_not_waitingfor(self):
        issue = MagicMock(spec=issues.Issue)
        mocked_ctx = MagicMock(
            spec=[
                "set_fields_readonly",
                "set_fields_writeable",
                "set_mandatory",
                "set_optional",
            ]
        )
        dialog_mock = MagicMock()
        dialog_mock.zielstatus_int = "not 70"
        mocked_ctx.dialog = dialog_mock
        issues.Issue.handle_waiting_for(issue, mocked_ctx)
        mocked_ctx.set_fields_readonly.assert_called_once_with(
            ["waiting_for_name", "waiting_reason"]
        )
        mocked_ctx.set_optional.assert_has_calls(
            [
                call("waiting_for_name"),
                call("waiting_reason"),
            ]
        )
        mocked_ctx.set_fields_writeable.assert_not_called()
        mocked_ctx.set_mandatory.assert_not_called()


class IssueUpdater(testcase.RollbackTestCase):
    @pytest.mark.unit
    def test__init__(self):
        updater = issues.IssueUpdater(1, 2, 3)
        self.assertEqual(updater._regexp.pattern, r"([a-zA-Z]+)(\d+)")

    @pytest.mark.integration
    def test_collect_attributes(self):
        issue = issues.Issue.Create(
            issue_id="ISS00000123",
            cdb_project_id="test-issue",
            cdb_object_id="test-issue",
        )
        updater = issues.IssueUpdater(1, issue.cdb_object_id, False)
        updater._add_field = Mock()
        self.assertIsNone(updater._collect_attributes())
        updater._add_field.assert_has_calls(
            [
                call("identifying", "00000123"),
                call("identifying", "ISS123"),
            ]
        )

    @pytest.mark.unit
    @patch.object(issues.updaters, "IndexUpdaterFactory")
    def test_add_to_factory(self, IndexUpdaterFactory):
        issues.IssueUpdater.setup()
        IndexUpdaterFactory.assert_called_once_with()
        IndexUpdaterFactory.return_value.add_updater.assert_called_once_with(
            "cdbpcs_issue",
            issues.IssueUpdater,
        )


@pytest.mark.unit
class IssueCategory(testcase.RollbackTestCase):
    def test_event_map(self):
        "make sure handlers are registered for events"
        self.assertEqual(
            issues.IssueCategory.event_map,
            {
                (("create", "modify"), "post"): ("reset_is_default"),
            },
        )

    @patch.object(issues.sqlapi, "SQLupdate")
    def test_reset_is_default_true(self, SQLupdate):
        ctx = MagicMock()
        issue_category = MagicMock(
            spec=issues.IssueCategory,
            __maps_to__="cdbpcs_iss_cat",
            is_default=1,
            category="foo",
        )
        issues.IssueCategory.reset_is_default(issue_category, ctx)
        SQLupdate.assert_called_once_with(
            "cdbpcs_iss_cat SET is_default=0 WHERE category!='foo'"
        )

    @patch.object(issues.sqlapi, "SQLupdate")
    def test_reset_is_default_false(self, SQLupdate):
        ctx = MagicMock()
        issue_category = MagicMock(
            spec=issues.IssueCategory,
            __maps_to__="cdbpcs_iss_cat",
            is_default=0,
            category="foo",
        )
        issues.IssueCategory.reset_is_default(issue_category, ctx)
        SQLupdate.assert_not_called()


@pytest.mark.unit
class IssuePriority(testcase.RollbackTestCase):
    def test_event_map(self):
        "make sure handlers are registered for events"
        self.assertEqual(
            issues.IssuePriority.event_map,
            {
                (("create", "modify"), "post"): ("reset_is_default"),
            },
        )

    @patch.object(issues.sqlapi, "SQLupdate")
    def test_reset_is_default_true(self, SQLupdate):
        ctx = MagicMock()
        issue_priority = MagicMock(
            spec=issues.IssuePriority,
            __maps_to__="cdbpcs_iss_prio",
            is_default=1,
            priority="foo",
        )
        issues.IssuePriority.reset_is_default(issue_priority, ctx)
        SQLupdate.assert_called_once_with(
            "cdbpcs_iss_prio SET is_default=0 WHERE priority!='foo'"
        )

    @patch.object(issues.sqlapi, "SQLupdate")
    def test_reset_is_default_false(self, SQLupdate):
        ctx = MagicMock()
        issue_priority = MagicMock(
            spec=issues.IssuePriority,
            __maps_to__="cdbpcs_iss_prio",
            is_default=0,
            priority="foo",
        )
        issues.IssuePriority.reset_is_default(issue_priority, ctx)
        SQLupdate.assert_not_called()


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
