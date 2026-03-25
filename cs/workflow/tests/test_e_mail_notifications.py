#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock

from cdb import auth
from cdb import sqlapi
from cdb import testcase
from cdb import util
from cdb.objects.org import User

from cs.workflow.processes import Process
from cs.workflow.tasks import ExecutionTask
from cs.workflow.tasks import Task
from cs.workflow.systemtasks import InfoMessage


def setup_module():
    testcase.run_level_setup()


class DummyContext(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TaskNotificationSenderTestCase(testcase.RollbackTestCase):
    def test_getNotificationSender(self):
        task = ExecutionTask.Create(
            cdb_process_id="WF-TEST",
            task_id="WF-TEST")

        with self.assertRaises(AttributeError):
            task.getNotificationSender()

        wf = Process.Create(cdb_process_id=task.cdb_process_id)
        task.Reload()

        self.assertEqual(task.getNotificationSender(), ("", ""))

        user = User.Create(personalnummer="TEST-WF",
                           name="WF Testuser",
                           e_mail="wftest@example.com")
        wf.Update(started_by=user.personalnummer)
        wf.Reload()
        self.assertEqual(task.getNotificationSender(),
                         (user.e_mail, user.name))

    def test_sendNotification(self):
        task = Task(
            cdb_process_id="WF-TEST",
            task_id="WF-TEST",
            status=Task.EXECUTION.status,
        )

        baseClass = mock.MagicMock()
        task.Super = mock.MagicMock(return_value=baseClass)
        task.sendNotification()

        task.Super.assert_called_once_with(Task)
        baseClass.sendNotification.assert_called_with(None)


class NotificationReceiverBase(testcase.RollbackTestCase):
    @property
    def user(self):
        return User.ByKeys(auth.persno)

    user_id = 0

    def next_user_id(self):
        self.user_id += 1
        return self.user_id

    def _create_user(self, receive, setting, **kwargs):
        vals = {
            "personalnummer": "WFTEST-{}".format(self.next_user_id()),
        }
        vals.update(kwargs)
        user = User.Create(**vals)
        self._receive_mails(user, setting, receive)
        return user

    def _receive_mails(self, user, setting, receive=True):
        # Regular API does not support setting values for other users
        sqlapi.SQLdelete(
            "FROM cdb_usr_setting "
            "WHERE personalnummer='{}' AND setting_id='{}'".format(
                user.personalnummer, setting))
        sqlapi.SQLinsert(
            "INTO cdb_usr_setting "
            "(setting_id, setting_id2, personalnummer, value) "
            "VALUES ('{}', '', '{}', '{}')".format(
                setting, user.personalnummer, "1" if receive else "0"))
        util.PersonalSettings().invalidate()

    def _setup_ctx(self, **kwargs):
        return DummyContext(**kwargs)

    def _create_task(self):
        return ExecutionTask.Create(
            cdb_process_id="WF-TEST",
            task_id="WF-TEST")

    def _create_msg(self):
        return InfoMessage.Create()


class TaskNotificationReceiverTestCase(NotificationReceiverBase):
    def test_task_receiver_modifier(self):
        ctx = self._setup_ctx(modified_task_attrs=1)
        task = self._create_task()
        user = self._create_user(
            receive=True,
            setting="user.email_with_task",
            active_account=1,
            e_mail="something",
        )
        self.assertTrue(task.isNotificationReceiver(user, ctx))

    def test_task_receiver_changer(self):
        ctx = self._setup_ctx(content_change_bobject=1)
        task = self._create_task()

        user = self._create_user(
            receive=True,
            setting="user.email_with_task",
            active_account=1,
            e_mail="something",
        )
        self.assertTrue(task.isNotificationReceiver(user, ctx))

    def test_task_receiver_unsupported_ctx(self):
        ctx = self._setup_ctx()
        task = self._create_task()
        with self.assertRaises(util.ErrorMessage):
            self.assertFalse(task.isNotificationReceiver(None, ctx))

        user = self._create_user(receive=False, setting="user.email_with_task")
        with self.assertRaises(util.ErrorMessage):
            self.assertFalse(task.isNotificationReceiver(user, ctx))

    def test_task_receiver_inactive(self):
        task = self._create_task()
        user = self._create_user(
            receive=True,
            setting="user.email_with_task",
            active_account=0,
        )
        self.assertFalse(task.isNotificationReceiver(user, None))

        user = self._create_user(
            receive=True,
            setting="user.email_with_task",
            active_account=1,
        )
        self.assertFalse(task.isNotificationReceiver(user, None))

        user = self._create_user(
            receive=False,
            setting="user.email_with_task",
            active_account=1,
            e_mail="something",
        )
        self.assertFalse(task.isNotificationReceiver(user, None))


class InfoMessageNotificationReceiverTestCase(NotificationReceiverBase):
    def test_task_receiver_inactive(self):
        msg = self._create_msg()

        user = self._create_user(
            receive=False,
            setting="user.email_wf_info",
            active_account=0,
        )
        self.assertFalse(msg.isNotificationReceiver(user, None))

        user = self._create_user(
            receive=True,
            setting="user.email_wf_info",
            active_account=1,
        )
        self.assertFalse(msg.isNotificationReceiver(user, None))

        user = self._create_user(
            receive=False,
            setting="user.email_wf_info",
            active_account=1,
            e_mail="something",
        )

        self.assertFalse(msg.isNotificationReceiver(user, None))

    def test_task_receiver_active(self):
        msg = self._create_msg()
        user = self._create_user(
            receive=True,
            setting="user.email_wf_info",
            active_account=1,
            e_mail="something",
        )

        self.assertTrue(msg.isNotificationReceiver(user, None))
        self.assertTrue(msg.isNotificationReceiver(user, DummyContext()))
