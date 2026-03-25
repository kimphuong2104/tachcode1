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
from cdb import testcase

from cs.pcs.projects.project_structure import views
from cs.pcs.projects.tests.common_data import create_project, create_structured_project


@pytest.mark.integration
class TreeViewIntegrationTestCase(testcase.RollbackTestCase):
    @mock.patch.object(views.sqlapi, "RecordSet2")
    def test__get_first_nodes(self, RecordSet2):
        # NOTE: Purposely mocking the DB entry to reduce boilerplate
        params = {"subprojects": "0"}
        req = mock.Mock()
        req.params = params
        tview = views.TreeView("some_project_oid", req)
        tview.adjacency_list = {"0": ["1", "3"], "1": ["2"], "3": ["4", "5", "6"]}
        tview.flat_nodes = [
            {"rest_key": "0", "id": 10},
            {"rest_key": "1", "id": 11},
            {"rest_key": "2", "id": 12},
            {"rest_key": "3", "id": 13},
            {"rest_key": "4", "id": 14},
            {"rest_key": "5", "id": 15},
            {"rest_key": "6", "id": 16},
        ]

        RecordSet2.return_value = [
            {
                "json_value": '{"selectedRestKey": "/1", "0": {"expanded": true}, "1": {"expanded": true}}'
            }
        ]
        # Process of collecting nodes:
        # 1) traversing down: starting at "1" go down to collect "2" and "3"
        # 2) traversing up: starting at "0" and stop there, because reched top
        # 3) BFS from root ("0"), skipping "1" and "3", as well as "2", because
        # they were already encountered; collect "4" and stop because reached
        # max size of 5
        result = tview._get_first_nodes(first=5)

        self.assertEqual(
            result,
            (
                [
                    {"rest_key": "0", "id": 10},
                    {"rest_key": "1", "id": 11},
                    {"rest_key": "2", "id": 12},
                    {"rest_key": "3", "id": 13},
                    {"rest_key": "4", "id": 14},
                ],
                [{"rest_key": "5", "id": 15}, {"rest_key": "6", "id": 16}],
            ),
        )

    PROJECT_ID = "test_tree_drop"
    SUBPROJECT_1 = "test_tree_drop_sub1"
    SUBPROJECT_2 = "test_tree_drop_sub2"
    maxDiff = None

    def _task_structure(self, project):
        project.Reload()
        result = []

        def add_task(task, level=0):
            task.Reload()
            result.append(f"{'  ' * level}{level} {task.task_name} {task.position}")
            for subtask in task.OrderedSubTasks:
                add_task(subtask, level + 1)

        for task in project.TopTasks:
            add_task(task)

        for subproject in project.OrderedSubProjects:
            result.append(f"{subproject.project_name} {subproject.position}")

        return result

    def _create_test_project(self):
        project, _ = create_structured_project(
            self.PROJECT_ID, tasks_per_level=2, depth=1
        )
        for index, sub_id in enumerate([self.SUBPROJECT_1, self.SUBPROJECT_2]):
            subproject, _ = create_project(sub_id)
            subproject.Update(
                parent_project=project.cdb_project_id,
                position=10 * (index + 1),
            )
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00000 10",
                "  1 test_tree_drop_00001 20",
                "  1 test_tree_drop_00002 30",
                "0 test_tree_drop_00003 40",
                "  1 test_tree_drop_00004 50",
                "  1 test_tree_drop_00005 60",
                "test_tree_drop_sub1 10",
                "test_tree_drop_sub2 20",
            ],
        )
        return project

    def _task_rest_id(self, task_no):
        return f"foo/project_task/{self.PROJECT_ID}@{self.PROJECT_ID}_0000{task_no}@"

    def test_persist_drop_move_task_children(self):
        "TreeView, children: move task 0 in between 4 and 5"
        project = self._create_test_project()
        target = self._task_rest_id(0)
        parent = self._task_rest_id(3)
        children = [
            self._task_rest_id(4),
            self._task_rest_id(0),
            self._task_rest_id(5),
        ]
        views.TreeView.persist_drop(target, parent, children, None, True)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00003 40",
                "  1 test_tree_drop_00004 10",
                "  1 test_tree_drop_00000 20",
                "    2 test_tree_drop_00001 20",
                "    2 test_tree_drop_00002 30",
                "  1 test_tree_drop_00005 30",
                "test_tree_drop_sub1 10",
                "test_tree_drop_sub2 20",
            ],
        )

    def test_persist_drop_move_task_pred(self):
        "TreeView, predecessor: move task 0 in between 4 and 5"
        project = self._create_test_project()
        target = self._task_rest_id(0)
        parent = self._task_rest_id(3)
        pred = self._task_rest_id(4)
        views.TreeView.persist_drop(target, parent, None, pred, True)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00003 40",
                "  1 test_tree_drop_00004 10",
                "  1 test_tree_drop_00000 20",
                "    2 test_tree_drop_00001 20",
                "    2 test_tree_drop_00002 30",
                "  1 test_tree_drop_00005 30",
                "test_tree_drop_sub1 10",
                "test_tree_drop_sub2 20",
            ],
        )

    def test_persist_drop_move_project_children(self):
        "TreeView, children: move project 1 after 2"
        project = self._create_test_project()
        target = f"foo/project/{self.SUBPROJECT_1}@"
        parent = f"foo/project/{project.cdb_project_id}@"
        children = [
            self._task_rest_id(0),
            self._task_rest_id(3),
            f"foo/project/{self.SUBPROJECT_2}@",
            f"foo/project/{self.SUBPROJECT_1}@",
        ]
        views.TreeView.persist_drop(target, parent, children, None, True)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00000 10",
                "  1 test_tree_drop_00001 20",
                "  1 test_tree_drop_00002 30",
                "0 test_tree_drop_00003 20",
                "  1 test_tree_drop_00004 50",
                "  1 test_tree_drop_00005 60",
                "test_tree_drop_sub2 30",
                "test_tree_drop_sub1 40",
            ],
        )

    def test_persist_drop_move_project_pred(self):
        "TreeView, pred: move project 1 after 2"
        project = self._create_test_project()
        target = f"foo/project/{self.SUBPROJECT_1}@"
        parent = f"foo/project/{project.cdb_project_id}@"
        pred = f"foo/project/{self.SUBPROJECT_2}@"
        views.TreeView.persist_drop(target, parent, None, pred, True)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00000 10",
                "  1 test_tree_drop_00001 20",
                "  1 test_tree_drop_00002 30",
                "0 test_tree_drop_00003 20",
                "  1 test_tree_drop_00004 50",
                "  1 test_tree_drop_00005 60",
                "test_tree_drop_sub2 30",
                "test_tree_drop_sub1 40",
            ],
        )

    def test_persist_drop_copy_missing_child(self):
        with self.assertRaises(ValueError) as error:
            views.TreeView.persist_drop("target", "parent", ["target"], None, False)

        self.assertEqual(
            str(error.exception),
            "target 'target#COPY' is missing in children: ['target']",
        )

    def test_persist_drop_copy_task_children(self):
        "TreeView, children: copy task 5 above 4"
        project = self._create_test_project()
        target = self._task_rest_id(5)
        parent = self._task_rest_id(3)
        children = [
            f"{self._task_rest_id(5)}#COPY",
            self._task_rest_id(4),
            self._task_rest_id(5),
        ]
        views.TreeView.persist_drop(target, parent, children, None, False)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00000 10",
                "  1 test_tree_drop_00001 20",
                "  1 test_tree_drop_00002 30",
                "0 test_tree_drop_00003 40",
                "  1 test_tree_drop_00005 (Kopie) 10",
                "  1 test_tree_drop_00004 20",
                "  1 test_tree_drop_00005 30",
                "test_tree_drop_sub1 10",
                "test_tree_drop_sub2 20",
            ],
        )

    def test_persist_drop_copy_task_pred(self):
        "TreeView, pred: copy task 5 above 4"
        project = self._create_test_project()
        target = self._task_rest_id(5)
        parent = self._task_rest_id(3)
        pred = None
        views.TreeView.persist_drop(target, parent, None, pred, False)
        self.assertEqual(
            self._task_structure(project),
            [
                "0 test_tree_drop_00000 10",
                "  1 test_tree_drop_00001 20",
                "  1 test_tree_drop_00002 30",
                "0 test_tree_drop_00003 40",
                "  1 test_tree_drop_00005 (Kopie) 10",
                "  1 test_tree_drop_00004 20",
                "  1 test_tree_drop_00005 30",
                "test_tree_drop_sub1 10",
                "test_tree_drop_sub2 20",
            ],
        )


if __name__ == "__main__":
    unittest.main()
