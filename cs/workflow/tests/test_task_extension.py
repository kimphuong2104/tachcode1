#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest
from cdb import testcase
from cdb.objects import operations
from cdb.constants import kOperationNew
from cs.workflow.processes import Process
from cs.workflow.tasks import ApprovalTask

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


try:
    from cs.workflowtest.cdbwf_task_extension import SimpleTaskExtension
except ImportError:
    SimpleTaskExtension = None


@unittest.skipIf(not SimpleTaskExtension, "Skipped because cs.workflowtest.cdbwf_task_extension.SimpleTaskExtension is required")
class TestTaskExtension(testcase.RollbackTestCase):
    """
    Test the API for task extension.
    """

    def setUp(self):
        super(TestTaskExtension, self).setUp()
        self.createProcess()
        self.createExtendedTask()

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

    def createExtendedTask(self):
        self.task = self.process.CreateTask(title="extended task",
                                            ttype=ApprovalTask._getClassname(),
                                            subject_id=self.process.subject_id,
                                            subject_type=self.process.subject_type,
                                            cdb_extension_class=SimpleTaskExtension._getClassname())
        self.task_extension = self.task.getExtensionObject()

    def startProcess(self):
        operations.operation("cdbwf_start_workflow", self.process)

    def test_close_task_from_extension(self):
        self.startProcess()
        self.task.Reload()
        comment = "closing task"
        self.task_extension.close_task(comment=comment)
        self.task.Reload()
        self.assertEqual(ApprovalTask.COMPLETED.status, self.task.status,
                         "Failed to close task.")
        protocols = self.process.Protocols.Query("task_id='%s'" % self.task.task_id, order_by="cdbprot_sortable_id desc")
        if protocols:
            prot = protocols[0]
            self.assertIn(comment, prot.description, "Comment not found in protocol.")

    def test_refuse_task_from_extension(self):
        self.startProcess()
        self.task.Reload()
        comment = "refusing task"
        self.task_extension.refuse_task(comment=comment)
        self.task.Reload()
        self.assertEqual(ApprovalTask.REJECTED.status, self.task.status,
                         "Failed to refuse task.")
        protocols = self.process.Protocols.Query("task_id='%s'" % self.task.task_id, order_by="cdbprot_sortable_id desc")
        if protocols:
            prot = protocols[0]
            self.assertIn(comment, prot.description, "Comment not found in protocol.")
