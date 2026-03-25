#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock, os

from cdb import constants, rte, testcase, util
from cdb.objects.org import User
from cdb.objects.cdb_file import CDB_File

from cs.workflow.processes import Process
from cs.workflow.tasks import ExecutionTask
from cs.workflow.systemtasks import InfoMessage


def setup_module():
    testcase.run_level_setup()


class DummyContext(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class EmailContentTestCase(testcase.RollbackTestCase):
    maxDiff = None

    def _getExpectedMail(self, key):
        filepath = os.path.join(
            os.path.dirname(__file__), "expected_emails", key + ".html")

        with open(filepath, "r", encoding="utf-8") as myfile:
            return myfile.read().replace("http://www.example.org", rte.environ.get(constants.kEnvWWWServiceURL, u""))

    def _buildTask(self, uuid, info=False):
        wf = Process.Create(
            cdb_process_id="mailTest",
            title="WF-Title",
            description="WF-Description",
            is_template=0,
            status=0,
        )
        user = User.KeywordQuery(personalnummer="caddok")[0]
        user["firstname"] = "myFirstName"
        wf.make_attachments_briefcase()
        wf.AddAttachment(user.cdb_object_id)

        task = ExecutionTask.Create(
            cdb_object_id=uuid,
            cdb_process_id=wf.cdb_process_id,
            task_id="mailTask",
            title="myTask",
            description="This is a Task Description",
        )
        if info:
            return InfoMessage.Create(
                cdb_object_id=uuid,
                cdb_process_id=wf.cdb_process_id,
                task_id=task.task_id,
                title="myTask",
                description="This is a Task Description",
            )
        else:
            return task

    def _testMailContent(self, task, ctx, mailKey, lang):
        util.PersonalSettings().invalidate()
        util.PersonalSettings().setValue('notification_template_language', '', lang)
        template = task._getNotificationTemplateFile(ctx)
        received_mail = task._render_mail_template(ctx, template)

        expected_mail = self._getExpectedMail(mailKey + "_" + lang)
        self.assertEqual(received_mail, expected_mail)

    def _test_cdbwf_task_ready(self, lang):
        task = self._buildTask("cdbwf_task_ready_task_object_id")
        ctx = DummyContext(task_delegated=True)
        self._testMailContent(task, ctx, "cdbwf_task_ready", lang)

    def test_cdbwf_task_ready_de(self):
        self._test_cdbwf_task_ready("de")

    def test_cdbwf_task_ready_en(self):
        self._test_cdbwf_task_ready("en")

    def _test_cdbwf_task_modified(self, lang):
        task = self._buildTask("cdbwf_task_modified_task_object_id")
        modified = mock.MagicMock()
        modified.values.return_value = [
            {"label": "Label 0", "value": 12345},
            {"label": "Label 1", "value": "Lorem Ipsum"},
        ]
        ctx = DummyContext(modified_task_attrs=modified)
        self._testMailContent(task, ctx, "cdbwf_task_modified", lang)

    def test_cdbwf_task_modified_de(self):
        self._test_cdbwf_task_modified("de")

    def test_cdbwf_task_modified_en(self):
        self._test_cdbwf_task_modified("en")

    def _test_cdbwf_content_change(self, lang):
        task = self._buildTask("cdbwf_task_content_change_object_id")
        user = User.Create(personalnummer="myUserId")
        fileobj = CDB_File.Create(
            cdbf_object_id=user.cdb_object_id,
            cdbf_name="Content change file Name",
        )
        ctx = DummyContext(
            content_change_bobject=user,
            content_change_file=fileobj,
            action="create",
        )
        self._testMailContent(task, ctx, "cdbwf_content_change", lang)

    def test_cdbwf_content_change_de(self):
        self._test_cdbwf_content_change("de")

    def test_cdbwf_content_change_en(self):
        self._test_cdbwf_content_change("en")

    def _test_cdbwf_info_message(self,lang):
        task = self._buildTask(
            "cdbwf_info_message_infomessage_object_id",
            info=True,
        )
        ctx = DummyContext()
        self._testMailContent(task, ctx, "cdbwf_info_message", lang)

    def test_cdbwf_info_message_de(self):
        self._test_cdbwf_info_message("de")

    def test_cdbwf_info_message_en(self):
        self._test_cdbwf_info_message("en")
