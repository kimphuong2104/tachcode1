#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


import unittest

import mock
import pytest
from cdb import sig, sqlapi, testcase

from cs.pcs.projects import baselining
from cs.pcs.projects.tasks import Task


def method_is_connected(module, name, *slot):
    slot_names = [(x.__module__, x.__name__) for x in sig.find_slots(*slot)]
    return (module, name) in slot_names


@pytest.mark.unit
class ModificationPre(unittest.TestCase):
    def _is_connected(self, cls, action, mode):
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects.baselining",
                "modification_pre",
                cls,
                action,
                mode,
            )
        )

    def test_connected_proj_create_pre(self):
        self._is_connected(baselining.Project, "create", "pre")

    def test_connected_proj_copy_pre(self):
        self._is_connected(baselining.Project, "copy", "pre")

    def test_connected_proj_modify_pre(self):
        self._is_connected(baselining.Project, "modify", "pre")

    def test_connected_proj_delete_pre(self):
        self._is_connected(baselining.Project, "delete", "pre")

    def test_connected_proj_state_change_pre(self):
        self._is_connected(baselining.Project, "state_change", "pre")

    def test_connected_proj_create_pre_mask(self):
        self._is_connected(baselining.Project, "create", "pre_mask")

    def test_connected_proj_copy_pre_mask(self):
        self._is_connected(baselining.Project, "copy", "pre_mask")

    def test_connected_proj_modify_pre_mask(self):
        self._is_connected(baselining.Project, "modify", "pre_mask")

    def test_connected_proj_delete_pre_mask(self):
        self._is_connected(baselining.Project, "delete", "pre_mask")

    def test_connected_proj_wf_step_pre_mask(self):
        self._is_connected(baselining.Project, "wf_step", "pre_mask")

    def test_connected_task_create_pre(self):
        self._is_connected(baselining.Task, "create", "pre")

    def test_connected_task_copy_pre(self):
        self._is_connected(baselining.Task, "copy", "pre")

    def test_connected_task_modify_pre(self):
        self._is_connected(baselining.Task, "modify", "pre")

    def test_connected_task_delete_pre(self):
        self._is_connected(baselining.Task, "delete", "pre")

    def test_connected_task_state_change_pre(self):
        self._is_connected(baselining.Task, "state_change", "pre")

    def test_connected_task_create_pre_mask(self):
        self._is_connected(baselining.Task, "create", "pre_mask")

    def test_connected_task_copy_pre_mask(self):
        self._is_connected(baselining.Task, "copy", "pre_mask")

    def test_connected_task_modify_pre_mask(self):
        self._is_connected(baselining.Task, "modify", "pre_mask")

    def test_connected_task_delete_pre_mask(self):
        self._is_connected(baselining.Task, "delete", "pre_mask")

    def test_connected_task_wf_step_pre_mask(self):
        self._is_connected(baselining.Task, "wf_step", "pre_mask")

    def test_modification_pre_ok(self):
        obj = mock.Mock(ce_baseline_id="")
        self.assertIsNone(baselining.modification_pre(obj, None))

    def test_modification_pre_fail(self):
        obj = mock.Mock(ce_baseline_id="foo")
        ctx = mock.Mock(action="delete")
        with self.assertRaises(baselining.util.ErrorMessage) as error:
            baselining.modification_pre(obj, ctx)
        self.assertEqual(
            str(error.exception),
            "Projekt-Baselines und ihre Daten können nur aus den "
            '"Baseline Details" des Originalprojekts gelöscht werden.',
        )


@pytest.mark.unit
class EnhancedSearch(unittest.TestCase):
    def _is_connected(self, cls, action, mode):
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects.baselining",
                "enhance_search_condition",
                cls,
                action,
                mode,
            )
        )

    def test_connected_project_query_pre(self):
        self._is_connected(baselining.Project, "query", "pre")

    def test_connected_project_requery_pre(self):
        self._is_connected(baselining.Project, "requery", "pre")

    def test_connected_task_query_pre(self):
        self._is_connected(baselining.Task, "query", "pre")

    def test_connected_task_requery_pre(self):
        self._is_connected(baselining.Task, "requery", "pre")

    def test_enhance_search_condition(self):
        ctx = mock.Mock()
        ctx.dialog.get_attribute_names.return_value = []
        self.assertIsNone(baselining.enhance_search_condition(None, ctx))
        ctx.set.assert_called_once_with("ce_baseline_id", '=""')

    def test_enhance_search_condition_in_dialog(self):
        ctx = mock.Mock()
        ctx.dialog.get_attribute_names.return_value = ["ce_baseline_id"]
        self.assertIsNone(baselining.enhance_search_condition(None, ctx))
        ctx.set.assert_not_called()


@pytest.mark.integration
class Project(testcase.RollbackTestCase):
    def test_copy_baseline_elements_restore(self):
        project = mock.Mock(spec=baselining.Project)
        with self.assertRaises(NotImplementedError):
            baselining.Project.copy_baseline_elements(project, "BL", True)

    def test_copy_baseline_elements(self):
        project_id = "test_copy_baseline"
        for table in ["cdbpcs_project", "cdbpcs_task"]:
            sqlapi.SQLdelete(f"FROM {table} WHERE cdb_project_id = '{project_id}'")
        project = baselining.Project.Create(
            cdb_project_id=project_id,
            ce_baseline_id="",
        )
        for task_id in ["task-1", "task-2"]:
            Task.Create(
                cdb_project_id=project.cdb_project_id,
                ce_baseline_id="",
                task_id=task_id,
            )

        result = baselining.Project.copy_baseline_elements(project, "BL")

        self.assertEqual(result.cdb_project_id, project.cdb_project_id)
        self.assertEqual(result.ce_baseline_id, "BL")
        self.assertEqual(result.AllTasks.task_id, project.AllTasks.task_id)
        self.assertEqual(result.AllTasks.ce_baseline_id, ["BL", "BL"])

    def test_create_baseline_pre_mask_is_connected(self):
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects.baselining",
                "create_baseline_pre_mask",
                baselining.Project,
                "ce_baseline_create",
                "pre_mask",
            )
        )

    @mock.patch.object(baselining.BaselineTools, "is_baseline", return_value=False)
    def test_create_baseline_pre_mask_pass(self, is_baseline):
        project = mock.Mock(spec=baselining.Project)
        self.assertIsNone(baselining.Project.create_baseline_pre_mask(project, None))

    @mock.patch.object(baselining.BaselineTools, "is_baseline", return_value=True)
    def test_create_baseline_pre_mask_fail(self, is_baseline):
        project = mock.Mock(spec=baselining.Project)
        with self.assertRaises(baselining.util.ErrorMessage):
            baselining.Project.create_baseline_pre_mask(project, None)

    def test_create_baseline_post_mask_is_connected(self):
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects.baselining",
                "create_baseline_post_mask",
                baselining.Project,
                "ce_baseline_create",
                "post_mask",
            )
        )

    @mock.patch.object(baselining.BaselineTools, "is_baseline", return_value=False)
    def test_create_baseline_post_mask_name_set(self, is_baseline):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        ctx.dialog.ce_baseline_name = "foo"
        self.assertIsNone(baselining.Project.create_baseline_post_mask(project, ctx))
        ctx.set.assert_not_called()

    @mock.patch.object(
        baselining.typeconversion, "to_user_repr_date_format", return_value="DEFAULT"
    )
    @mock.patch.object(baselining.BaselineTools, "is_baseline", return_value=False)
    def test_create_baseline_post_mask_name_not_set(self, is_baseline, _):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        ctx.dialog.ce_baseline_name = ""
        self.assertIsNone(baselining.Project.create_baseline_post_mask(project, ctx))
        ctx.set.assert_called_once_with("ce_baseline_name", "DEFAULT")

    @mock.patch.object(baselining.sqlapi, "RecordSet2")
    def test_check_baseline_name_unique_name_empty(self, RecordSet2):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        ctx.dialog.ce_baseline_name = ""
        self.assertIsNone(baselining.Project.check_baseline_name_unique(project, ctx))
        RecordSet2.assert_not_called()

    @mock.patch.object(baselining.sqlapi, "RecordSet2", return_value=[])
    def test_check_baseline_name_unique_pass(self, RecordSet2):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        self.assertIsNone(baselining.Project.check_baseline_name_unique(project, ctx))
        RecordSet2.assert_called_once()

    @mock.patch.object(baselining.sqlapi, "RecordSet2", return_value=[1])
    def test_check_baseline_name_unique_fail(self, RecordSet2):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        with self.assertRaises(baselining.util.ErrorMessage):
            baselining.Project.check_baseline_name_unique(project, ctx)
        RecordSet2.assert_called_once()

    def test_create_baseline_is_connected(self):
        self.assertTrue(
            method_is_connected(
                "cs.pcs.projects.baselining",
                "create_baseline",
                baselining.Project,
                "ce_baseline_create",
                "now",
            )
        )

    @mock.patch.object(
        baselining.BaselineTools, "create_baseline", return_value=["foo", "bar"]
    )
    def test_create_baseline(self, create_baseline):
        project = mock.Mock(spec=baselining.Project)
        ctx = mock.Mock()
        ctx.dialog.ce_baseline_name = "BL"
        ctx.dialog.ce_baseline_comment = "bl"

        self.assertIsNone(baselining.Project.create_baseline(project, ctx))

        create_baseline.assert_called_once_with(
            obj=project,
            name="BL",
            comment="bl",
        )
        ctx.set_object_result.assert_called_once_with("bar")
        project.check_baseline_name_unique.assert_called_once_with(ctx)

    @mock.patch.object(baselining.sqlapi, "SQLdelete")
    def test_remove_all_baseline_elements(self, SQLdelete):
        project = mock.Mock(spec=baselining.Project, cdb_project_id="foo")
        self.assertIsNone(
            baselining.Project.remove_all_baseline_elements(project, "bar", True)
        )
        SQLdelete.assert_has_calls(
            [
                mock.call(
                    "FROM cdbpcs_task "
                    "WHERE cdb_project_id = 'foo' AND ce_baseline_id = 'bar'"
                ),
                mock.call(
                    "FROM cdbpcs_project "
                    "WHERE cdb_project_id = 'foo' AND ce_baseline_id = 'bar'"
                ),
            ]
        )
        self.assertEqual(SQLdelete.call_count, 2)

    def _assert_baseline(self, project_id, should_exist):
        projects = baselining.Project.KeywordQuery(cdb_project_id=project_id)
        baseline_ids = [x for x in projects.ce_baseline_id if x != ""]
        baselines = baselining.fBaselineHead.KeywordQuery(cdb_object_id=baseline_ids)

        expected = 1 if should_exist else 0
        self.assertEqual(
            (len(baseline_ids), len(baselines)),
            (expected, expected),
        )

    def test_delete_baselines(self):
        project = baselining.Project.ByKeys("Ptest.baselining")
        self._assert_baseline(project.cdb_project_id, True)
        project.delete_baselines(mock.Mock(error=0))
        self._assert_baseline(project.cdb_project_id, False)

    def test_delete_baselines_error(self):
        project = baselining.Project.ByKeys("Ptest.baselining")
        self._assert_baseline(project.cdb_project_id, True)
        project.delete_baselines(mock.Mock(error=1))
        self._assert_baseline(project.cdb_project_id, True)


if __name__ == "__main__":
    unittest.main()
