#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import ue
from cdb.platform import gui

from cs.pcs.issues import Issue
from cs.pcs.projects.tasks import Task


@pytest.mark.unit
class IssuesStatus(unittest.TestCase):
    def test_endStatus_with___end_status_cls__(self):
        "Issue_Status endStatus with end_status_cls"
        Issue.__end_status_cls__ = "foo"
        Issue.__end_status_int__ = "bar"
        issue = Issue()

        result = issue.endStatus(True)
        self.assertEqual(result, "foo")

        result = issue.endStatus(False)
        self.assertEqual(result, "bar")

    def test_endStatus_without___end_status_cls__(self):
        "Issue_Status endStatus without end_status_cls"
        try:
            delattr(Issue, "__end_status_cls__")
        except AttributeError:
            pass
        issue = Issue()

        result = issue.endStatus(True)
        self.assertSetEqual(result, set([Issue.DISCARDED, Issue.COMPLETED]))

        result = issue.endStatus(False)
        self.assertSetEqual(result, set([180, 200]))

    def test_EXECUTION_Constraints(self):
        "Issue Execution Constraints"
        issue = Issue()
        execution = Issue.EXECUTION()
        task = "foo"
        with mock.patch.object(
            Issue,
            "Task",
            # a Reference is not called,
            # but accessed like a property
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            result = execution.Constraints(issue)
        self.assertListEqual(
            result,
            [
                (
                    "MatchStateList",
                    [
                        ["foo"],
                        [Task.READY, Task.NEW, Task.EXECUTION],
                        "pcstask_wf_rej_1",
                    ],
                )
            ],
        )

    def test_DISCARDED_FollowUpStateChanges_no_task(self):
        "IssueState Discarded: Issue has no Task -> No FollowUpStateChange"
        # issue has no task, so there are no followUp StateChanges
        issue = Issue()
        discarded = Issue.DISCARDED()
        resultStateChanges = discarded.FollowUpStateChanges(issue)
        self.assertListEqual([], resultStateChanges)

    def test_DISCARDED_FollowUpStateChanges_with_task_without_final_status(self):
        "IssueState Discarded: Issue has only tasks in final State -> No FollowUpStateChange"
        # issue has task, which will not change status, e.g. returns None
        # for Task.getFinalStatus()
        # in that case there are no followUp State Changes
        issue = Issue()
        discarded = Issue.DISCARDED()
        task = mock.MagicMock(autospec=Task)
        task.getFinalStatus = mock.Mock(return_value=None)
        # mock Reference to task
        with mock.patch.object(
            Issue,
            "Task",
            # a Reference is not called,
            # but accessed like a property
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            resultStateChanges = discarded.FollowUpStateChanges(issue)
        task.getFinalStatus.assert_called_once()
        self.assertListEqual([], resultStateChanges)

    def test_DISCARDED_FollowUpStateChanges_with_task_with_final_status(self):
        "IssueState Discarded: Issue has task not in final state -> FollowUpStateChange"
        # issue has task which will change status, e.g. can be transitioned
        # into a final state, return followUp StateChange
        issue = Issue()
        discarded = Issue.DISCARDED()
        task = mock.MagicMock(autospec=Task)
        task.getFinalStatus = mock.Mock(return_value="foo")
        # mock Reference to task
        with mock.patch.object(
            Issue,
            "Task",
            # a Reference is not called,
            # but accessed like a property
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            resultStateChanges = discarded.FollowUpStateChanges(issue)
        task.getFinalStatus.assert_called_once()
        self.assertListEqual([("foo", [task], 0, 0)], resultStateChanges)

    def test_COMPLETED_FollowUpStateChanges_no_task(self):
        "IssueState Completed: Issue has no Task -> No FollowUpStateChange"
        # issue has no task, so there are no followUp StateChanges
        issue = Issue()
        completed = Issue.COMPLETED()
        resultStateChanges = completed.FollowUpStateChanges(issue)
        self.assertListEqual([], resultStateChanges)

    def test_COMPLETED_FollowUpStateChanges_with_task_without_final_status(self):
        "IssueState Completed: Issue has only tasks in final State -> No FollowUpStateChange"
        # issue has task, which will not change status, e.g. returns None
        # for Task.getFinalStatus()
        # in that case there are no followUp State Changes
        issue = Issue()
        completed = Issue.COMPLETED()
        task = mock.MagicMock(autospec=Task)
        task.getFinalStatus = mock.Mock(return_value=None)
        # mock Reference to task
        with mock.patch.object(
            Issue,
            "Task",
            # a Reference is not called,
            # but accessed like a property
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            resultStateChanges = completed.FollowUpStateChanges(issue)
        task.getFinalStatus.assert_called_once()
        self.assertListEqual([], resultStateChanges)

    def test_COMPLETED_FollowUpStateChanges_with_task_with_final_status(self):
        "IssueState Completed: Issue has tasks not in final State -> FollowUpStateChange"
        # issue has task which will change status, return followUp StateChange
        issue = Issue()
        completed = Issue.COMPLETED()
        task = mock.MagicMock(autospec=Task)
        task.getFinalStatus = mock.Mock(return_value="foo")
        # mock Reference to task
        with mock.patch.object(
            Issue,
            "Task",
            # a Reference is not called,
            # but accessed like a property
            new_callable=mock.PropertyMock,
            return_value=task,
        ):
            resultStateChanges = completed.FollowUpStateChanges(issue)
        task.getFinalStatus.assert_called_once()
        self.assertListEqual([("foo", [task], 0, 0)], resultStateChanges)

    def test_WAITINGFOR_pre_fields_already_set(self):
        "IssueState WaitingFor reason and name already set in pre"
        issue = Issue()
        waitingfor = Issue.WAITINGFOR()

        mocked_ctx = mock.Mock(spec=["dialog"])
        # ctx attributes already set
        mocked_d = mock.MagicMock()
        real_dialog_dict = {"waiting_reason": "foo", "waiting_for_name": "bar"}
        mocked_d.get_attribute_names.return_value = list(real_dialog_dict)
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d
        # expect no exception
        waitingfor.pre(issue, mocked_ctx)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_WAITINGFOR_pre_fields_not_set_flag_set(self, CDBMSg):
        "IssueState WaitingFor reason and name not set in pre, but Flag -> Exception"
        issue = Issue()
        waitingfor = Issue.WAITINGFOR()
        mocked_ctx = mock.Mock(spec=["dialog", "active_integration"])
        # waiting reason and name not set
        mocked_d = mock.MagicMock()
        real_dialog_dict = {
            "waiting_reason": "",
            "waiting_for_name": "",
            "zielstatus": "baz",
        }
        mocked_d.get_attribute_names.return_value = list(real_dialog_dict)
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d
        # additionaly Flag set (this case can be removed if E049045 is fixed)
        # the following is a constant flag name
        mocked_ctx.active_integration = "cs.taskmanager.proceed"
        # expect ue.exception
        with self.assertRaises(ue.Exception):
            waitingfor.pre(issue, mocked_ctx)
        CDBMSg.assert_called_once_with(CDBMSg.kFatal, "pcs_err_iss_proceed")

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_WAITINGFOR_pre_fields_not_set_flag_not_set(self, CDBMSg):
        "IssueState WaitingFor reason and name not set in pre -> Exception"
        issue = Issue()
        waitingfor = Issue.WAITINGFOR()
        mocked_ctx = mock.Mock(spec=["dialog", "active_integration"])
        # waiting reason and name not set
        mocked_d = mock.MagicMock()
        real_dialog_dict = {
            "waiting_reason": "",
            "waiting_for_name": "",
            "zielstatus": "baz",
        }
        mocked_d.get_attribute_names.return_value = list(real_dialog_dict)
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d
        # additionaly Flag not set
        mocked_ctx.active_integration = ""
        # mock mask with corresponding labels
        mask = mock.MagicMock()
        label1 = mock.MagicMock()
        label1.Label = {"": "foo"}
        label2 = mock.MagicMock()
        label2.Label = {"": "bar"}
        mask.AttributesByName = {
            "waiting_for_name": [label1],
            "waiting_reason": [label2],
        }
        # expect ue.exception
        with mock.patch.object(gui.Mask, "ByName", return_value=[mask]):
            with self.assertRaises(ue.Exception):
                waitingfor.pre(issue, mocked_ctx)
        # check if correct error message is thrown
        CDBMSg.assert_called_once_with(CDBMSg.kFatal, "pcs_err_iss_state")
        # further check that the error msg is correct, e.g. was addReplacement
        # called with the correct parameters
        CDBMSg.return_value.addReplacement.assert_has_calls(
            [mock.call("baz"), mock.call("'foo', 'bar'")]
        )

    def test_WAITINGFOR_post(self):
        "IssueState WaitingFor: Set reason and name in post"
        # check if attributes of issue are set correctly
        issue = Issue()
        waitingfor = Issue.WAITINGFOR()
        mocked_ctx = mock.Mock(spec=["dialog", "error"])
        mocked_ctx.error = None
        # waiting reason and persno set
        mocked_d = mock.MagicMock()
        real_dialog_dict = {"waiting_reason": "foo", "waiting_for_persno": "bar"}
        mocked_d.get_attribute_names.return_value = list(real_dialog_dict)
        mocked_d.__getitem__.side_effect = real_dialog_dict.__getitem__
        mocked_ctx.dialog = mocked_d

        waitingfor.post(issue, mocked_ctx)
        self.assertEqual(issue.reason, "foo")
        self.assertEqual(issue.waiting_for, "bar")

    def test_FROM_WAITINGFOR_post(self):
        "IssueState From_WaitingFor: Set reason and name in post"
        # check if attributes of issue are set correctly
        issue = Issue()
        fromwaitingfor = Issue.FROM_WAITINGFOR()
        mocked_ctx = mock.Mock(spec=["error"])
        mocked_ctx.error = None
        fromwaitingfor.post(issue, mocked_ctx)
        self.assertEqual(issue.reason, "")
        self.assertEqual(issue.waiting_for, "")

    def test_TO_DISCARDED_OR_COMPLETED_post(self):
        "IssueState To Discarded or Completed: Set close_flag in post"
        # check if attributes of issue are set correctly
        issue = Issue()
        toDiscardedOrCompleted = Issue.TO_DISCARDED_OR_COMPLETED()
        mocked_ctx = mock.Mock(spec=["error"])
        mocked_ctx.error = None
        toDiscardedOrCompleted.post(issue, mocked_ctx)
        self.assertEqual(issue.close_flag, "ja")

    def test_TO_DEFERRED_post(self):
        "IssueState To Deferred: Set close_flag in post"
        # check if attributes of issue are set correctly
        issue = Issue()
        toDeferred = Issue.TO_DEFERRED()
        mocked_ctx = mock.Mock(spec=["error"])
        mocked_ctx.error = None
        toDeferred.post(issue, mocked_ctx)
        self.assertEqual(issue.close_flag, "offen")

    def test_TO_NOT_COMPLETED_post(self):
        "IssueState To Not Completed: Set close_flag in post"
        # check if attributes of issue are set correctly
        issue = Issue()
        toNotCompleted = Issue.TO_NOT_COMPLETED()
        mocked_ctx = mock.Mock(spec=["error"])
        mocked_ctx.error = None
        toNotCompleted.post(issue, mocked_ctx)
        self.assertEqual(issue.close_flag, "nein")
