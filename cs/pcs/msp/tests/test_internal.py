#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest
from collections import defaultdict

import mock
import pytest
from cdb import testcase

from cs.pcs.msp import internal
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task, TaskRelation


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class ProjectConsistency(unittest.TestCase):
    @mock.patch.object(internal.ProjectConsistency, "initData")
    @mock.patch.object(internal.ProjectConsistency, "init_consistency_checks")
    def test__init__(self, init_consistency_checks, initData):
        project = mock.MagicMock(spec=Project)
        tasks = []
        internal_relations = []
        external_relations = []
        pc = internal.ProjectConsistency(
            project, tasks, internal_relations, external_relations
        )
        initData.assert_called_once_with()
        init_consistency_checks.assert_called_once_with()
        self.assertEqual(pc.project, project)
        self.assertEqual(pc.tasks, tasks)
        self.assertEqual(pc.internal_relations, internal_relations)
        self.assertEqual(pc.external_relations, external_relations)

    @mock.patch("cs.pcs.msp.internal.OBJECTS", defaultdict())
    @mock.patch("cs.pcs.msp.internal.SUBTASKS", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATION", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATIONS_EXTERNAL", set())
    @mock.patch.object(internal.ProjectConsistency, "initDeletable")
    @mock.patch.object(internal.ProjectConsistency, "initModifiable")
    @mock.patch.object(internal.ProjectConsistency, "initFinalized")
    @mock.patch.object(internal.ProjectConsistency, "addSubItem")
    @mock.patch.object(internal.ProjectConsistency, "addItem")
    def test_initData_with_tasks_interal_relations_external_relations_same(
        self, addItem, addSubItem, initFinalized, initModifiable, initDeletable
    ):

        project = mock.MagicMock(autospec=Project)
        project.cdb_project_id = "TEST"
        project.ce_baseline_id = "bass id"
        tasks = ["foo", "bar"]
        tr = mock.MagicMock(autospec=TaskRelation)
        tr.task_id = "1"
        tr.task_id2 = "2"
        internal_relations = [tr]
        etr = mock.MagicMock(autospec=TaskRelation)
        etr.cdb_project_id = "p1"
        etr.cdb_project_id2 = "p1"
        external_relations = [etr]
        with mock.patch.object(internal.ProjectConsistency, "init_consistency_checks"):
            internal.ProjectConsistency(
                project, tasks, internal_relations, external_relations
            )
            addItem_calls = [mock.call(project), mock.call("foo"), mock.call("bar")]
            addItem.assert_has_calls(addItem_calls)
            addSubItem_calls = [mock.call("foo"), mock.call("bar")]
            addSubItem.assert_has_calls(addSubItem_calls)
            self.assertEqual(internal.TASKRELATION["1"], [tr])
            self.assertEqual(internal.TASKRELATION["2"], [tr])
            self.assertEqual(internal.TASKRELATIONS_EXTERNAL, set())
            initFinalized.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initModifiable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initDeletable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )

    @mock.patch("cs.pcs.msp.internal.OBJECTS", defaultdict())
    @mock.patch("cs.pcs.msp.internal.SUBTASKS", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATION", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATIONS_EXTERNAL", set())
    @mock.patch.object(internal.ProjectConsistency, "initDeletable")
    @mock.patch.object(internal.ProjectConsistency, "initModifiable")
    @mock.patch.object(internal.ProjectConsistency, "initFinalized")
    @mock.patch.object(internal.ProjectConsistency, "addSubItem")
    @mock.patch.object(internal.ProjectConsistency, "addItem")
    def test_initData_with_tasks_interal_relations_external_relations(
        self, addItem, addSubItem, initFinalized, initModifiable, initDeletable
    ):
        project = mock.MagicMock(autospec=Project)
        project.cdb_project_id = "TEST"
        project.ce_baseline_id = "bass id"
        tasks = ["foo", "bar"]
        tr = mock.MagicMock(autospec=TaskRelation)
        tr.task_id = "1"
        tr.task_id2 = "2"
        internal_relations = [tr]
        etr = mock.MagicMock(autospec=TaskRelation)
        etr.cdb_project_id = "p1"
        etr.cdb_project_id2 = "p2"
        external_relations = [etr]
        with mock.patch.object(internal.ProjectConsistency, "init_consistency_checks"):
            internal.ProjectConsistency(
                project, tasks, internal_relations, external_relations
            )
            addItem_calls = [mock.call(project), mock.call("foo"), mock.call("bar")]
            addItem.assert_has_calls(addItem_calls)
            addSubItem_calls = [mock.call("foo"), mock.call("bar")]
            addSubItem.assert_has_calls(addSubItem_calls)
            self.assertEqual(internal.TASKRELATION["1"], [tr])
            self.assertEqual(internal.TASKRELATION["2"], [tr])
            self.assertEqual(internal.TASKRELATIONS_EXTERNAL, set([etr]))
            initFinalized.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initModifiable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initDeletable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )

    @mock.patch("cs.pcs.msp.internal.OBJECTS", defaultdict())
    @mock.patch("cs.pcs.msp.internal.SUBTASKS", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATION", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATIONS_EXTERNAL", set())
    @mock.patch.object(internal.ProjectConsistency, "initDeletable")
    @mock.patch.object(internal.ProjectConsistency, "initModifiable")
    @mock.patch.object(internal.ProjectConsistency, "initFinalized")
    @mock.patch.object(internal.ProjectConsistency, "addSubItem")
    @mock.patch.object(internal.ProjectConsistency, "addItem")
    def test_initData_with_tasks_interal_relations(
        self, addItem, addSubItem, initFinalized, initModifiable, initDeletable
    ):
        project = mock.MagicMock(autospec=Project)
        project.cdb_project_id = "TEST"
        project.ce_baseline_id = "bass id"
        tasks = ["foo", "bar"]
        tr = mock.MagicMock(autospec=TaskRelation)
        tr.task_id = "1"
        tr.task_id2 = "2"
        internal_relations = [tr]
        external_relations = []
        with mock.patch.object(internal.ProjectConsistency, "init_consistency_checks"):
            internal.ProjectConsistency(
                project, tasks, internal_relations, external_relations
            )
            addItem_calls = [mock.call(project), mock.call("foo"), mock.call("bar")]
            addItem.assert_has_calls(addItem_calls)
            addSubItem_calls = [mock.call("foo"), mock.call("bar")]
            addSubItem.assert_has_calls(addSubItem_calls)
            self.assertEqual(internal.TASKRELATION["1"], [tr])
            self.assertEqual(internal.TASKRELATION["2"], [tr])
            self.assertEqual(internal.TASKRELATIONS_EXTERNAL, set())
            initFinalized.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initModifiable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initDeletable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )

    @mock.patch("cs.pcs.msp.internal.OBJECTS", defaultdict())
    @mock.patch("cs.pcs.msp.internal.SUBTASKS", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATION", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATIONS_EXTERNAL", set())
    @mock.patch.object(internal.ProjectConsistency, "initDeletable")
    @mock.patch.object(internal.ProjectConsistency, "initModifiable")
    @mock.patch.object(internal.ProjectConsistency, "initFinalized")
    @mock.patch.object(internal.ProjectConsistency, "addSubItem")
    @mock.patch.object(internal.ProjectConsistency, "addItem")
    def test_initData_with_tasks(
        self, addItem, addSubItem, initFinalized, initModifiable, initDeletable
    ):
        project = mock.MagicMock(autospec=Project)
        project.cdb_project_id = "TEST"
        project.ce_baseline_id = "bass id"
        tasks = ["foo", "bar"]
        internal_relations = []
        external_relations = []
        with mock.patch.object(internal.ProjectConsistency, "init_consistency_checks"):
            internal.ProjectConsistency(
                project, tasks, internal_relations, external_relations
            )
            addItem_calls = [mock.call(project), mock.call("foo"), mock.call("bar")]
            addItem.assert_has_calls(addItem_calls)
            addSubItem_calls = [mock.call("foo"), mock.call("bar")]
            addSubItem.assert_has_calls(addSubItem_calls)
            self.assertEqual(internal.TASKRELATION, defaultdict(list))
            self.assertEqual(internal.TASKRELATIONS_EXTERNAL, set())
            initFinalized.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initModifiable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initDeletable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )

    @mock.patch("cs.pcs.msp.internal.OBJECTS", defaultdict())
    @mock.patch("cs.pcs.msp.internal.SUBTASKS", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATION", defaultdict(list))
    @mock.patch("cs.pcs.msp.internal.TASKRELATIONS_EXTERNAL", set())
    @mock.patch.object(internal.ProjectConsistency, "initDeletable")
    @mock.patch.object(internal.ProjectConsistency, "initModifiable")
    @mock.patch.object(internal.ProjectConsistency, "initFinalized")
    @mock.patch.object(internal.ProjectConsistency, "addSubItem")
    @mock.patch.object(internal.ProjectConsistency, "addItem")
    def test_initData(
        self, addItem, addSubItem, initFinalized, initModifiable, initDeletable
    ):
        project = mock.MagicMock(autospec=Project)
        project.cdb_project_id = "TEST"
        project.ce_baseline_id = "bass id"
        tasks = []
        internal_relations = []
        external_relations = []
        with mock.patch.object(internal.ProjectConsistency, "init_consistency_checks"):
            internal.ProjectConsistency(
                project, tasks, internal_relations, external_relations
            )
            addItem_calls = [mock.call(project)]
            addItem.assert_has_calls(addItem_calls)
            addSubItem.assert_not_called()
            self.assertEqual(internal.TASKRELATION, defaultdict(list))
            self.assertEqual(internal.TASKRELATIONS_EXTERNAL, set())
            initFinalized.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initModifiable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )
            initDeletable.assert_called_once_with(
                prj_id=project.cdb_project_id, ce_baseline_id="bass id"
            )

    def _check_status_with_exception(self, parent_status, obj_status):
        message = "just a replacement"
        parent = Task(status=parent_status)
        obj = Task(status=obj_status)
        with self.assertRaises(internal.ue.Exception) as error:
            internal.ProjectConsistency._check_status(obj, parent, message)
        self.assertEqual(str(error.exception), str(internal.ue.Exception(message)))

    def test_check_status_with_exception(self):
        invalid = {
            0: [20, 50, 60, 200, 250],
            20: [50, 60, 200, 250],
            50: [60, 250],
            60: [60, 250],
            180: [0, 20, 50, 60, 250],
            200: [0, 20, 50, 60, 180, 200, 250],
            250: [0, 20, 50, 60, 180, 200, 250],
        }
        for parent_status, tasks_status in invalid.items():
            for status in tasks_status:
                self._check_status_with_exception(parent_status, status)

    def _check_status_without_exception(self, parent_status, obj_status):
        parent = Task(status=parent_status)
        obj = Task(status=obj_status)
        internal.ProjectConsistency._check_status(
            obj, parent, "cdbpcs_parenttask_completion_invalid"
        )

    def test_check_status_without_exception(self):
        valid = {
            0: [0],
            20: [0, 20],
            50: [0, 20, 50, 180, 200],
            60: [0, 20, 50, 180, 200],
            180: [180, 200],
            200: [],
            250: [],
        }
        for parent_status, tasks_status in valid.items():
            for status in tasks_status:
                self._check_status_without_exception(parent_status, status)

    @mock.patch.object(internal, "OBJECTS", {"foo": "old_obj"})
    @mock.patch.object(internal.ProjectConsistency, "isDeletable", return_value=False)
    @mock.patch.object(internal.ProjectConsistency, "getID", return_value="foo")
    def test_checkTaskDeletable_fail(self, getID, isDeletable):
        obj = mock.Mock()

        with self.assertRaises(internal.ue.Exception) as exc:
            internal.ProjectConsistency.checkTaskDeletable(obj)

        self.assertEqual(
            str(exc.exception), "Sie sind nicht berechtigt, diese Aufgabe zu löschen."
        )

    @mock.patch.object(internal, "OBJECTS", {"foo": "old_obj"})
    @mock.patch.object(internal.ProjectConsistency, "isDeletable", return_value=True)
    @mock.patch.object(internal.ProjectConsistency, "getID", return_value="foo")
    def test_checkTaskDeletable_ok(self, getID, isDeletable):
        obj = mock.Mock()

        self.assertIsNone(internal.ProjectConsistency.checkTaskDeletable(obj))

    @mock.patch.object(internal, "OBJECTS", {"foo": "old_obj"})
    @mock.patch.object(internal.ProjectConsistency, "isModifiable", return_value=False)
    @mock.patch.object(internal.ProjectConsistency, "getID", return_value="foo")
    def test_checkTaskModifiable_fail(self, getID, isModifiable):
        obj = mock.Mock()

        with self.assertRaises(internal.ue.Exception) as exc:
            internal.ProjectConsistency.checkTaskModifiable(obj)

        self.assertEqual(
            str(exc.exception), "Sie sind nicht berechtigt, diese Aufgabe zu ändern."
        )

    @mock.patch.object(internal, "OBJECTS", {"foo": "old_obj"})
    @mock.patch.object(internal.ProjectConsistency, "isModifiable", return_value=True)
    @mock.patch.object(internal.ProjectConsistency, "getID", return_value="foo")
    def test_checkTaskModifiable_ok(self, getID, isModifiable):
        obj = mock.Mock()

        self.assertIsNone(internal.ProjectConsistency.checkTaskModifiable(obj))


if __name__ == "__main__":
    unittest.main()
