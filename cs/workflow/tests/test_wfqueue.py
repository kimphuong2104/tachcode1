#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock

from cdb import dberrors
from cdb import testcase
# NOTE: cs.workflow.wfqueue directly accesses the DB on import, defer import
from cs.workflow.processes import Process
from cs.workflow.systemtasks import InfoMessage
from cs.workflow.tasks import FilterParameter, SystemTask
from cs.workflow.tests.test_systemtasks import GENERATE_INFO


def setup_module():
    testcase.run_level_setup()


class Main(testcase.RollbackTestCase):
    def test_database_reconnect(self):
        from cs.workflow import wfqueue
        with mock.patch.object(wfqueue.mq.Queue, "cli", side_effect=[
            dberrors.DBConnectionLost(1, 2, 3),
            dberrors.DBConnectionLost(4, 5, 6),
            KeyboardInterrupt,
        ]), mock.patch.object(wfqueue.logging, "warning") as warning:
            wfqueue.main(None)
            self.assertEqual(warning.call_count, 2)


class SystemTaskJob(testcase.RollbackTestCase):
    def _create_job(self):
        from cs.workflow import wfqueue

        self.process = Process.Create(
            cdb_process_id="test_wfqueue",
            subject_id="caddok",
            subject_type="Person",
        )
        self.task = SystemTask.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id="info_task",
            task_definition_id=GENERATE_INFO,
            parent_id="",
        )
        for name, value in [("subject_id", "caddok"),
                            ("subject_type", "Person")]:
            FilterParameter.Create(
                cdb_process_id=self.process.cdb_process_id,
                task_id="info_task",
                name=name,
                value=value,
        )
        self.process.activate_process()
        jobs = wfqueue.wfqueue.query_jobs(
            "cdb_process_id='{}'".format(
                self.process.cdb_process_id))
        for job in jobs:
            return wfqueue.wfqueue.job_by_id(job.cdbmq_id)

    def test_run(self):
        "make sure worker processes are started correctly"
        from cs.workflow import wfqueue

        with mock.patch.object(wfqueue, "SCRIPT", "ext_process"),\
            mock.patch.object(wfqueue.killableprocess,
                              "check_output") as check_output,\
            mock.patch.object(wfqueue.rte,
                              "runtime_tool") as runtime_tool:

            job = self._create_job()
            job.run()
            check_output.assert_called_once_with([
                runtime_tool.return_value,
                '--program-name', 'WFQUEUE',
                '--user', 'caddok',
                '--language', 'de',
                "ext_process",
                self.task.cdb_process_id, self.task.task_id,
            ])

    def test_fail(self):
        "make sure workflow is paused when system task encounters a runtime error"
        job = self._create_job()
        job.fail(self.process, "bad things happened")
        self.process.Reload()
        self.assertEqual(self.process.status, self.process.ONHOLD.status)
        info = InfoMessage.KeywordQuery(cdb_process_id=self.process.cdb_process_id)
        self.assertEqual(
            (info.subject_id, info.title, info.description),
            (["caddok"], ["Systemaufgabe fehlgeschlagen"], ["bad things happened"])
        )
