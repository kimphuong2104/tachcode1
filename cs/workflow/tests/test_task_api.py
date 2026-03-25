#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from cdb import testcase
from cdb.objects import operations
from cdb.constants import kOperationNew
from cs.workflow.processes import Process
from cs.workflow.tasks import ApprovalTask

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class TestTaskAPI(testcase.RollbackTestCase):
    """
    Test the API for tasks.
    """

    def setUp(self):
        super(TestTaskAPI, self).setUp()
        self.createProcess()
        self.task1 = self.createApprovalTask()
        self.task2 = self.createForwardableApprovalTask()
        self.task3 = self.createApprovalTask()

    def createProcess(self):
        from cdb import auth
        process_data = {
            "cdb_process_id": Process.new_process_id(),
            "title": "Test",
            "is_template": "0",
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_objektart": "cdbwf_process",
            "status": 0,
        }
        self.process = operations.operation(kOperationNew,
                                            Process,
                                            operations.form_input(Process, **process_data))

    def createApprovalTask(self):
        return self.process.CreateTask(title="approval task",
                                       ttype=ApprovalTask._getClassname(),
                                       subject_id=self.process.subject_id,
                                       subject_type=self.process.subject_type)

    def createForwardableApprovalTask(self):
        task = self.createApprovalTask()
        task.Update(finish_option=1)
        return task

    def startProcess(self):
        operations.operation("cdbwf_start_workflow", self.process)

    def CloseTask1(self, comment="comment"):
        self.startProcess()
        self.task1.Reload()
        self.task1.CloseTask(remark=comment)
        self.task1.Reload()
        self.task2.Reload()

    def test_CloseTask(self):
        comment = "closing task"
        self.CloseTask1(comment)
        self.assertEqual(ApprovalTask.COMPLETED.status, self.task1.status,
                         "Failed to close task.")
        self.assertEqual(ApprovalTask.EXECUTION.status, self.task2.status,
                         "Failed to activate the next task.")
        protocols = self.process.Protocols.Query("task_id='%s'" % self.task1.task_id, order_by="cdbprot_sortable_id desc")
        if protocols:
            prot = protocols[0]
            self.assertIn(comment, prot.description, "Comment not found in protocol.")

    def test_RefuseTask(self):
        self.startProcess()
        self.task1.Reload()
        comment = "refusing task"
        self.task1.RefuseTask(remark=comment)
        self.task1.Reload()
        self.assertEqual(ApprovalTask.REJECTED.status, self.task1.status,
                         "Failed to refuse task.")
        protocols = self.process.Protocols.Query("task_id='%s'" % self.task1.task_id, order_by="cdbprot_sortable_id desc")
        if protocols:
            prot = protocols[0]
            self.assertIn(comment, prot.description, "Comment not found in protocol.")

    def test_ForwardTask(self):
        self.CloseTask1()
        comment = "forwarding task"
        self.task2.ForwardTask(remark=comment)
        self.task2.Reload()
        self.task3.Reload()
        self.assertEqual(ApprovalTask.COMPLETED.status, self.task2.status,
                         "Failed to close forwarded task.")
        protocols = self.process.Protocols.Query("task_id='%s'" % self.task2.task_id, order_by="cdbprot_sortable_id desc")
        if protocols:
            prot0 = protocols[0]
            self.assertIn(comment, prot0.description, "Comment not found in protocol.")
        self.assertEqual(ApprovalTask.EXECUTION.status, self.task3.status,
                         "Failed to forward task to the next task.")
