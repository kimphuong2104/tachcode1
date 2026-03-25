#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import contextlib
import logging
import mock
from cdb import sig
from cdb import sqlapi
from cdb import testcase
from cdb import util
from cdb.objects import ByID
from cs.workflow import run_loop
from cs.workflow.briefcases import Briefcase, BriefcaseContentWhitelist
from cs.workflow.briefcases import BriefcaseLink, FolderContent
from cs.workflow.tasks import Task
from cs.workflow.systemtasks import CloseTaskAsynchronously
from cs.workflow.systemtasks import TaskCancelledException


def setup_module():
    testcase.run_level_setup()


@contextlib.contextmanager
def disconnected_signal(_callable, *sig_args):
    disconnected = None
    for slot in sig.find_slots(*sig_args):
        if slot.__name__ == _callable.__name__:
            sig.disconnect(slot)
            disconnected = slot
            break
    yield
    if disconnected:
        sig.SMAP.connect(sig_args, disconnected)
    else:
        logging.error(
            "disconnected_signal: was not connected (%s, %s)",
            _callable, sig_args)


class DummyObject(object):
    def __init__(self, cdb_object_id):
        self.cdb_object_id = cdb_object_id


def get_loop_task(start_cycle=False):
    """
    ATTENTION: This writes to the database! Only call from within a
    RollbackTestCase!
    """
    task = ByID("464892cf-c86a-11e8-9558-5cc5d4123f3b")
    cycle = task.ReplaceTaskWithCycle()
    if start_cycle:
        cycle.Process.activate_process()
        cycle.Reload()
    return cycle


def get_attachments(process):
    return process.AllBriefcases.KeywordQuery(briefcase_id=0)[0]


class UtilityTestCase(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(UtilityTestCase, cls).setUpClass()
        BriefcaseContentWhitelist.Query().Delete()

    def test_get_briefcases_by_name(self):
        with self.assertRaises(TypeError):
            run_loop.get_briefcases_by_name(None)

        for empty_value in ["", []]:
            self.assertEqual(
                run_loop.get_briefcases_by_name(empty_value),
                {}
            )

        for value in ["A", Task.Query(max_rows=2)]:
            with self.assertRaises(AttributeError):
                run_loop.get_briefcases_by_name(value)

        briefcases = Briefcase.KeywordQuery(
            cdb_process_id="JSON_TEST"
        )
        self.assertEqual(
            set(run_loop.get_briefcases_by_name(briefcases).keys()),
            set([
                u"Testformular 1",
                u"Anhänge",
                u"Info",
            ])
        )

    def test_add_activity_topic(self):
        topic_posting_table = "cdbblog_topic2posting"
        topic_one = "TEST_TOPIC_1"
        topic_two = "TEST_TOPIC_2"

        sqlapi.Record(
            topic_posting_table,
            posting_id="TEST_POSTING",
            topic_id=topic_one,
        ).insert()

        def _get_t2p(topic_id):
            return len(
                sqlapi.RecordSet2(
                    topic_posting_table,
                    "topic_id='{}'".format(topic_id)
                )
            )

        run_loop.add_activity_topic(
            DummyObject(topic_two),
            DummyObject(topic_one),
        )
        self.assertEqual(_get_t2p(topic_one), 1)
        self.assertEqual(_get_t2p(topic_two), 0)

        run_loop.add_activity_topic(
            DummyObject(topic_one),
            DummyObject(topic_two),
        )
        self.assertEqual(_get_t2p(topic_one), 1)
        self.assertEqual(_get_t2p(topic_two), 1)

        run_loop.add_activity_topic(
            DummyObject(topic_one),
            DummyObject(topic_two),
        )
        self.assertEqual(_get_t2p(topic_one), 1)
        self.assertEqual(_get_t2p(topic_two), 1)

    def test_copy_briefcase_content(self):
        task = ByID("464892cf-c86a-11e8-9558-5cc5d4123f3b")
        briefcase_one = ByID("e0a0e70f-c86a-11e8-a02e-5cc5d4123f3b")
        briefcase_two = ByID("6ce9a462-c86a-11e8-9e38-5cc5d4123f3b")

        self.assertEqual(len(briefcase_one.Content), 0)
        self.assertEqual(len(briefcase_two.Content), 0)

        run_loop.copy_briefcase_content(task, briefcase_one, None)
        self.assertEqual(len(briefcase_one.Content), 0)
        self.assertEqual(len(briefcase_two.Content), 0)

        run_loop.copy_briefcase_content(task, briefcase_one, briefcase_two)
        self.assertEqual(len(briefcase_one.Content), 0)
        self.assertEqual(len(briefcase_two.Content), 0)

        content_one = "0a68595e-4239-11e8-92a7-5cc5d4123f3b"
        content_two = "917a52f0-2956-11e9-863b-68f7284ff046"

        briefcase_one.AddObject(content_one)
        briefcase_one.AddObject(content_two)
        briefcase_two.AddObject(content_two)
        self.assertEqual(len(briefcase_one.Content), 2)
        self.assertEqual(len(briefcase_two.Content), 1)

        run_loop.copy_briefcase_content(task, briefcase_one, briefcase_two)
        briefcase_one.Reload()
        briefcase_two.Reload()
        self.assertEqual(len(briefcase_one.Content), 2)
        self.assertEqual(len(briefcase_two.Content), 2)

    def assertContents(self, briefcase, amount):
        briefcase.Reload()
        self.assertEqual(len(briefcase.FolderContents), amount)

    def _prepare_sync(self):
        # cycle = process, parent = task
        task = ByID("464892cf-c86a-11e8-9558-5cc5d4123f3b")
        process = ByID("ed4eda01-e90b-11e8-a2d9-68f7284ff046")

        self.assertEqual(len(process.Briefcases), 1)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.AllForms), 0)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 0)
        self.assertContents(task.Briefcases[0], 0)
        self.assertContents(get_attachments(task.Process), 0)

        return process, task

    def _prepare_sync_to(self):
        process, task = self._prepare_sync()

        with disconnected_signal(FolderContent.check_valid_content,
                                 FolderContent, "create", "pre"):
            task.Briefcases[0].AddObject("DUMMY")
            get_attachments(task.Process).AddObject("DUMMY")

        self.assertContents(task.Briefcases[0], 1)
        self.assertContents(get_attachments(task.Process), 1)
        return process, task

    def _sync(self, sync, *args):
        sync(*args)
        for arg in args:
            arg.Reload()

    @mock.patch.object(run_loop, "sync_global_briefcases", return_value=False)
    def test_syncBriefcasesToCycle_only_locals(self, sync_global):
        process, task = self._prepare_sync_to()

        self._sync(run_loop.syncBriefcasesToCycle, task, process)
        sync_global.assert_called_once_with()

        self.assertEqual(len(process.Briefcases), 2)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 0)
        self.assertContents(process.Briefcases[1], 1)
        self.assertContents(task.Briefcases[0], 1)
        self.assertContents(get_attachments(task.Process), 1)

    @mock.patch.object(run_loop, "sync_global_briefcases", return_value=True)
    def test_syncBriefcasesToCycle_globals_also(self, sync_global):
        process, task = self._prepare_sync_to()

        self._sync(run_loop.syncBriefcasesToCycle, task, process)
        sync_global.assert_called_once_with()

        self.assertEqual(len(process.Briefcases), 2)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 1)
        self.assertContents(process.Briefcases[1], 1)
        self.assertContents(task.Briefcases[0], 1)
        self.assertContents(get_attachments(task.Process), 1)

    def _prepare_sync_from(self):
        process, task = self._prepare_sync()
        process.Update(status=0)

        # add content to global attachments bc
        with disconnected_signal(FolderContent.check_valid_content,
                                 FolderContent, "create", "pre"):
            get_attachments(process).AddObject("DUMMY")
            # add content to bc named like one in task
            content_synced = process.CreateBriefcase(
                task.Briefcases[0].name
            )
            BriefcaseLink.Create(
                briefcase_id=content_synced.briefcase_id,
                cdb_process_id=content_synced.cdb_process_id,
                task_id="",
                iotype=0,
                extends_rights=0,
            )
            content_synced.AddObject("DUMMY")

        self.assertEqual(len(process.Briefcases), 2)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 1)
        self.assertContents(process.Briefcases[1], 1)
        self.assertContents(task.Briefcases[0], 0)
        self.assertContents(get_attachments(task.Process), 0)

        return process, task

    @mock.patch.object(run_loop, "sync_global_briefcases", return_value=False)
    def test_syncBriefcasesFromCycle_only_locals(self, sync_global):
        process, task = self._prepare_sync_from()
        run_loop.syncBriefcasesFromCycle(process, task)
        sync_global.assert_called_once_with()

        self.assertEqual(len(process.Briefcases), 2)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 1)
        self.assertContents(process.Briefcases[1], 1)
        self.assertContents(task.Briefcases[0], 1)
        self.assertContents(get_attachments(task.Process), 0)

    @mock.patch.object(run_loop, "sync_global_briefcases", return_value=True)
    def test_syncBriefcasesFromCycle_globals_also(self, sync_global):
        process, task = self._prepare_sync_from()
        self._sync(run_loop.syncBriefcasesFromCycle, process, task)
        sync_global.assert_called_once_with()

        self.assertEqual(len(process.Briefcases), 2)
        self.assertEqual(len(task.Briefcases), 1)
        self.assertEqual(len(task.Process.Briefcases), 1)
        self.assertContents(get_attachments(process), 1)
        self.assertContents(process.AllBriefcases[1], 1)
        self.assertContents(task.Briefcases[0], 1)
        self.assertContents(get_attachments(task.Process), 1)


class RunLoopTestCase(testcase.RollbackTestCase):
    def test_illegal_parameters(self):
        with self.assertRaises(ValueError):
            run_loop.RunLoopSystemTaskImplementation(None, "", "1")

        with self.assertRaises(ValueError):
            run_loop.RunLoopSystemTaskImplementation(None, "1", "")

        with self.assertRaises(AttributeError):
            run_loop.RunLoopSystemTaskImplementation("No Task", "1", "1")

    def test_run_task_not_running(self):
        task = get_loop_task()
        impl = run_loop.RunLoopSystemTaskImplementation(task, 1, 1)
        with self.assertRaises(util.ErrorMessage):
            impl.run()

    def test_run_start_subworkflow(self):
        task = get_loop_task(True)
        impl = run_loop.RunLoopSystemTaskImplementation(task, 1, 1)

        with self.assertRaises(CloseTaskAsynchronously):
            impl.run()

        self.assertEqual(
            task.CurrentCycle.status,
            10
        )

    def test_run_missing_success_condition(self):
        task = get_loop_task(True)
        impl = run_loop.RunLoopSystemTaskImplementation(task, 2, 2)

        task.AllParameters.KeywordQuery(name="success_condition").Delete()

        with self.assertRaises(TaskCancelledException):
            impl.run()

    def test_run_start_new_cycle(self):
        task = get_loop_task(True)
        impl = run_loop.RunLoopSystemTaskImplementation(task, 2, 2)

        self.assertEqual(task.CurrentCycle.current_cycle, 1)
        old_cycle = task.CurrentCycle

        with self.assertRaises(CloseTaskAsynchronously):
            impl.run()

        task.Reload()
        self.assertNotEqual(
            old_cycle.cdb_process_id,
            task.CurrentCycle.cdb_process_id
        )
        self.assertEqual(task.CurrentCycle.current_cycle, 2)
        self.assertEqual(task.CurrentCycle.status, 10)

    def test_run_max_cycles_reached(self):
        task = get_loop_task(True)
        impl = run_loop.RunLoopSystemTaskImplementation(task, 2, 1)

        with self.assertRaises(TaskCancelledException):
            impl.run()

    def test_checkMaxCycles(self):
        task = get_loop_task()

        for cycle, max_cycles in [
                (-2, -1),
                (2, 2),
        ]:
            impl = run_loop.RunLoopSystemTaskImplementation(
                task,
                cycle,
                max_cycles
            )
            impl.checkMaxCycles()

        impl = run_loop.RunLoopSystemTaskImplementation(
            task,
            3,
            2
        )

        with self.assertRaises(TaskCancelledException):
            impl.checkMaxCycles()

    def test_checkSuccessConditions(self):
        task = get_loop_task()
        impl = run_loop.RunLoopSystemTaskImplementation(task, 0, 0)

        self.assertEqual(
            impl.checkSuccessConditions(),
            False
        )

        task.CurrentCycle.Update(status=20)
        task.CurrentCycle.Reload()

        self.assertEqual(
            impl.checkSuccessConditions(),
            True
        )

        task.AllParameters.KeywordQuery(
            name="success_condition"
        ).Delete()

        with self.assertRaises(TaskCancelledException):
            impl.checkSuccessConditions()

    def test_checkFailureConditions(self):
        task = get_loop_task()
        impl = run_loop.RunLoopSystemTaskImplementation(task, 0, 0)

        self.assertEqual(
            impl.checkFailureConditions(),
            None
        )

        task.CurrentCycle.Update(status=30)
        task.CurrentCycle.Reload()

        with self.assertRaises(TaskCancelledException):
            impl.checkFailureConditions()

        task.AllParameters.KeywordQuery(
            name="failure_condition"
        ).Delete()

        self.assertEqual(
            impl.checkFailureConditions(),
            None
        )

    def test_synch_child_process_briefcases(self):
        task = get_loop_task()

        b1 = Briefcase.Create(
            cdb_process_id=task.cdb_process_id,
            briefcase_id=0,
            name="NewBriefcase",
        )
        b2 = Briefcase.Create(
            cdb_process_id=task.cdb_process_id,
            briefcase_id=1,
            name="NewBriefcase2",
        )
        # add briefcase to CurrentCycle of the task to avoid duplicate entries
        Briefcase.Create(
            cdb_process_id=task.CurrentCycle.cdb_process_id,
            briefcase_id=0,
            name="NewBriefcase2",
        )

        old_briefcase_names = set(task.CurrentCycle.AllBriefcases.name)

        # b1 should be added to CurrentCyle of the task
        task.add_briefcase_to_cycle(b1)

        # b2 should not be added because briefcase of
        # same name is already there
        task.add_briefcase_to_cycle(b2)

        task.CurrentCycle.Reload()

        new_briefcase_names = set(task.CurrentCycle.AllBriefcases.name)

        self.assertEqual(new_briefcase_names, old_briefcase_names.union({"NewBriefcase"}))
