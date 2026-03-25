#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter,too-many-lines

import unittest
from datetime import date, timedelta

import mock
import pytest
from cdb import constants, rte, testcase, transaction, ue, util
from cdb.constants import kOperationModify
from cdb.objects.operations import operation
from cdb.objects.references import ObjectCollection

from cs.pcs.projects import Project, tasks
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.scheduling import relships


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


def create_object_collection(cls, data):
    oc = ObjectCollection(cls, cls.__maps_to__, "1=1")
    oc._data = data
    return oc


@pytest.mark.unit
class TestTask(unittest.TestCase):
    def test__allParentTasks(self):
        "returns all parents of a task recursively"
        parent = mock.MagicMock(autospec=tasks.Task)
        parent._allParentTasks = mock.Mock(return_value=["grandpa", "grandma"])
        task = tasks.Task()

        with mock.patch.object(
            tasks.Task,
            "ParentTask",
            new_callable=mock.PropertyMock,
            return_value=parent,
        ):
            result = task._allParentTasks()

        self.assertEqual(result, [parent, "grandpa", "grandma"])
        parent._allParentTasks.assert_called_once()

    @mock.patch.object(tasks.Task, "Update")
    def test_Reset(self, Update):
        "re-initializes key attributes"
        byKeys = mock.Mock()
        task = tasks.Task()

        with mock.patch.object(
            tasks.olc.StateDefinition, "ByKeys", return_value=byKeys
        ):
            byKeys.StateText = {"": "foo"}
            task.Reset()

        Update.assert_called_once_with(
            status=0,
            cdb_status_txt="foo",
            start_time_act="",
            end_time_act="",
            effort_act=0,
            percent_complet=0,
            effort_fcast_a=0,
            days_act=0,
        )

    @mock.patch.object(tasks.Project, "KeywordQuery", return_value="bass")
    def test_get_projects_by_task_object_ids_01(self, prj_keyword_query):
        "Return projects by task object ids: tasks found"
        t = tasks.Task()
        t.cdb_project_id = "bar"
        ts = create_object_collection(tasks.Task, [t])
        with mock.patch.object(tasks.Task, "KeywordQuery", return_value=ts):
            result = tasks.Task.get_projects_by_task_object_ids(["foo"], "base_foo")
            # check calls
            self.assertEqual(result, "bass")
            tasks.Task.KeywordQuery.assert_called_once_with(cdb_object_id=["foo"])
            prj_keyword_query.assert_called_once_with(
                cdb_project_id=["bar"], ce_baseline_id="base_foo"
            )

    @mock.patch.object(tasks.Project, "KeywordQuery", return_value="bass")
    def test_get_projects_by_task_object_ids_02(self, prj_keyword_query):
        "Return projects by task object ids: no tasks found"
        ts = create_object_collection(tasks.Task, [])
        with mock.patch.object(tasks.Task, "KeywordQuery", return_value=ts):
            result = tasks.Task.get_projects_by_task_object_ids(["foo"], "base_foo")
            # check calls
            self.assertEqual(result, [])
            tasks.Task.KeywordQuery.assert_called_once_with(cdb_object_id=["foo"])
            prj_keyword_query.assert_not_called()

    @mock.patch.object(tasks.Project, "KeywordQuery", return_value="bass")
    def test_get_projects_by_task_object_ids_03(self, prj_keyword_query):
        "Return projects by task object ids: no object ids given"
        result = tasks.Task.get_projects_by_task_object_ids(None)

        # check calls
        self.assertEqual(result, [])
        prj_keyword_query.assert_not_called()

    @mock.patch("cdb.util.nextval", return_value=42)
    def test_makeTaskID(self, nextval):
        "generates next available task id"
        result = tasks.Task.makeTaskID()
        self.assertEqual(result, "T000000042")
        nextval.assert_called_once_with("cdbpcs_task")

    @mock.patch.object(tasks.sqlapi, "RecordSet2", return_value=None)
    def test_makePosition_no_siblings(self, RecordSet2):
        "initializes task position"
        task = tasks.Task()
        task.cdb_project_id = "project"
        task.parent_task = "parent task"
        task.ce_baseline_id = "baseline id"
        task.position_initial = "foo"
        result = task.makePosition()

        self.assertEqual(result, "foo")

        RecordSet2.assert_called_once()
        args, kwargs = RecordSet2.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], "cdbpcs_task")
        self.assertEqual(
            str(args[1]),
            "((cdb_project_id='project') AND "
            "(parent_task='parent task') AND "
            "(ce_baseline_id='baseline id'))",
        )
        self.assertEqual(kwargs, {"columns": ["MAX(position) p"]})

    @mock.patch.object(tasks.sqlapi, "RecordSet2", return_value="TODO")
    def test_makePosition_siblings_exist(self, RecordSet2):
        "initializes task position"
        self.skipTest("TODO")

    def test_on_cdbpcs_reinit_position_now(self):
        "calls reinitPosition"
        task = mock.MagicMock(spec=tasks.Task)
        self.assertIsNone(
            tasks.Task.on_cdbpcs_reinit_position_now(task, None),
        )
        task.reinitPosition.assert_called_once_with()

    @mock.patch.object(tasks.Project, "KeywordQuery")
    @mock.patch.object(tasks.Task, "KeywordQuery")
    @mock.patch.object(tasks, "hasattr")
    def test_on_deactivate_automatic_clean_pre_mask(
        self, _hasattr, KeywordQueryTask, KeywordQuery
    ):
        ctx = mock.MagicMock(uses_webui=True)
        ctx.objects.return_value = [{"cdb_project_id": "bar", "task_id": "foo"}]
        project = mock.MagicMock(cdb_project_id="foo", msp_active=False)
        KeywordQuery.return_value = [project]
        task = mock.MagicMock(RessourceAssignments="bass")
        KeywordQueryTask.return_value = [task]
        _hasattr.return_value = True

        with self.assertRaises(tasks.ue.Exception) as e:
            tasks.Task.on_deactivate_automatic_clean_pre_mask(ctx)
        msg = tasks.ue.Exception("pcs_err_task_resource_exist", 1)
        self.assertEqual(str(e.exception), msg.msg.getText("", True))

    def test_on_activate_automatic_now_project_not_saveable(self):
        "fails if projec is not saveable"
        task = tasks.Task()
        project = mock.MagicMock(spec=tasks.Project)
        project.CheckAccess.return_value = False

        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            with self.assertRaises(ue.Exception):
                task.on_activate_automatic_now(None)

    @mock.patch.object(tasks.Task, "_lastObjectOfMultiSelect")
    @mock.patch.object(tasks.Task, "Update")
    @mock.patch.object(tasks.Task, "MakeChangeControlAttributes")
    @mock.patch.object(tasks.Task, "raiseOnMSPProject")
    @mock.patch.object(tasks.Project, "KeywordQuery")
    def test_on_activate_automatic_now_project_saveable_not_automatic(
        self,
        KeywordQuery,
        raiseOnMSPProject,
        MakeChangeControlAttributes,
        Update,
        _lastObjectOfMultiSelect,
    ):
        "fails if project is saveable"
        task = tasks.Task()
        ctx = mock.MagicMock()
        ctx.objects = [mock.PropertyMock(cdb_project_id="bar")]
        project = mock.MagicMock(spec=tasks.Project)
        project.CheckAccess.return_value = True
        task.automatic = False
        cca = {"cdb_mdate": "date", "cdb_mpersno": "foo"}
        MakeChangeControlAttributes.return_value = cca
        _lastObjectOfMultiSelect.return_value = True
        project2 = mock.MagicMock(spec=tasks.Project)
        KeywordQuery.return_value = [project2]
        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            task.on_activate_automatic_now(ctx)
            raiseOnMSPProject.assert_called_once_with()
            MakeChangeControlAttributes.assert_called_once_with()
            Update.assert_called_once_with(
                automatic=1, cdb_mdate=cca["cdb_mdate"], cdb_mpersno=cca["cdb_mpersno"]
            )
            _lastObjectOfMultiSelect.assert_called_once_with(ctx=ctx)
            KeywordQuery.assert_called_once_with(
                cdb_project_id=set(["bar"]), ce_baseline_id=""
            )
            project2.recalculate.assert_called_once_with()

    @mock.patch.object(tasks.transactions, "Transaction")
    @mock.patch.object(
        tasks.Task,
        "MakeChangeControlAttributes",
        return_value={"cdb_mdate": "foo", "cdb_mpersno": "bar"},
    )
    def test_reinitPosition_parameters(self, MakeChangeControlAttributes, Transaction):
        "resets subtask positions using parameters"
        sub1 = mock.MagicMock(spec=tasks.Task)
        sub2 = mock.MagicMock(spec=tasks.Task)
        task = mock.MagicMock(
            spec=tasks.Task,
            OrderedSubTasks=[sub1, sub2],
            position_initial=9,
            position_increment=3,
        )
        self.assertIsNone(
            tasks.Task.reinitPosition(
                task,
                position_initial=1,
                position_increment=6,
                next_position="?",
            ),
        )

        Transaction.assert_called_once_with()
        MakeChangeControlAttributes.assert_called_once_with()
        sub1.Update.assert_called_once_with(
            cdb_mdate="foo", cdb_mpersno="bar", position=1
        )
        # potential bug? parameters are not passed down to recursive calls
        sub1.reinitPosition.assert_called_once_with()
        sub2.Update.assert_called_once_with(
            cdb_mdate="foo", cdb_mpersno="bar", position=7
        )
        sub2.reinitPosition.assert_called_once_with()
        self.assertEqual(task.current_position, 13)

    @mock.patch.object(tasks.transactions, "Transaction")
    @mock.patch.object(
        tasks.Task,
        "MakeChangeControlAttributes",
        return_value={"cdb_mdate": "foo", "cdb_mpersno": "bar"},
    )
    def test_reinitPosition(self, MakeChangeControlAttributes, Transaction):
        "resets subtask positions"
        sub1 = mock.MagicMock(spec=tasks.Task)
        sub2 = mock.MagicMock(spec=tasks.Task)
        task = mock.MagicMock(
            spec=tasks.Task,
            OrderedSubTasks=[sub1, sub2],
            position_initial=9,
            position_increment=3,
        )
        self.assertIsNone(tasks.Task.reinitPosition(task, next_position="?"))

        Transaction.assert_called_once_with()
        MakeChangeControlAttributes.assert_called_once_with()
        sub1.Update.assert_called_once_with(
            cdb_mdate="foo", cdb_mpersno="bar", position=9
        )
        # potential bug? parameters are not passed down to recursive calls
        sub1.reinitPosition.assert_called_once_with()
        sub2.Update.assert_called_once_with(
            cdb_mdate="foo", cdb_mpersno="bar", position=12
        )
        sub2.reinitPosition.assert_called_once_with()
        self.assertEqual(task.current_position, 15)

    def test_checkParent_proj(self):
        "Task.checkParent parent project"
        task = mock.MagicMock(spec=tasks.Task)
        parent = mock.MagicMock(spec=tasks.Project)
        task.getParent.return_value = parent
        task.ParentTask = None
        ctx = mock.MagicMock()
        self.assertIsNone(tasks.Task.checkParent(task, ctx))
        with self.assertRaises(AttributeError):
            parent.checkConstraints()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)

    def _setup_checkParent_task(self):
        """Test checkParent with a task"""
        task = mock.MagicMock(spec=tasks.Task)
        parent = mock.MagicMock(spec=tasks.Task)
        task.getParent.return_value = parent
        task.ParentTask = parent
        ctx = mock.MagicMock()
        return task, parent, ctx

    def test_checkParent_changed_parent_copy_no_milestone(self):
        "Task.checkParent changed parent no milestone"
        task, parent, ctx = self._setup_checkParent_task()
        parent.milestone = False
        self.assertIsNone(tasks.Task.checkParent(task, ctx))
        task.getParentIDs.assert_called_once_with()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)
        parent.checkConstraints.assert_called_once_with()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkParent_recursion(self, CDBMsg):
        "Task.checkParent recursion"
        task, parent, ctx = self._setup_checkParent_task()
        del ctx.object.parent_task
        task.getParentIDs.return_value = ["foo", "bar", task.task_id]

        with self.assertRaises(ue.Exception):
            self.assertIsNone(tasks.Task.checkParent(task, ctx))

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_rec")
        CDBMsg.return_value.addReplacement.assert_not_called()

        task.getParentIDs.assert_called_once_with()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)
        parent.checkConstraints.assert_not_called()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkParent_milestone(self, CDBMsg):
        "Task.checkParent milestone"
        task, parent, ctx = self._setup_checkParent_task()
        del ctx.object.parent_task
        parent.milestone = True

        with self.assertRaises(ue.Exception):
            self.assertIsNone(tasks.Task.checkParent(task, ctx))

        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_err_task_milestone",
        )
        CDBMsg.return_value.addReplacement.assert_not_called()

        task.getParentIDs.assert_called_once_with()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)
        parent.checkConstraints.assert_not_called()

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkParent_recursion2(self, CDBMsg):
        "Task.checkParent recursion 2"
        task, parent, ctx = self._setup_checkParent_task()
        del ctx.object.parent_task
        parent.milestone = False
        task.AllSubTasks = ["foo", "bar", parent]

        with self.assertRaises(ue.Exception):
            self.assertIsNone(tasks.Task.checkParent(task, ctx))

        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_task_recursion",
        )
        CDBMsg.return_value.addReplacement.assert_called_once_with(
            f"{parent.task_name}",
        )

        task.getParentIDs.assert_called_once_with()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)
        parent.checkConstraints.assert_not_called()

    @mock.patch("cdb.util.get_label", autospec=True)
    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkParent_reltype_not_allowed(self, CDBMsg, get_label):
        "Task.checkParent reltype not allowed"
        task, parent, ctx = self._setup_checkParent_task()
        del ctx.object.parent_task
        parent.milestone = False
        parent.PredecessorTaskRelations = [
            mock.MagicMock(rel_type="EA"),
            mock.MagicMock(rel_type="foo"),
        ]

        with self.assertRaises(util.ErrorMessage):
            self.assertIsNone(tasks.Task.checkParent(task, ctx))

        get_label.assert_called_once_with(
            "cdbpcs_task_group_rel_not_allowed2",
        )
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "just_a_replacement")
        CDBMsg.return_value.addReplacement.assert_called_once_with(
            f"{get_label.return_value % parent.task_name}",
        )

        task.getParentIDs.assert_called_once_with()
        task.check_for_valid_parent.assert_called_once_with(ctx, parent)
        parent.checkConstraints.assert_not_called()

    # start updateParentTask (long block)
    # pylint: disable=pointless-string-statement
    """
    updateParentTask contains a lot of branches to be tested:

    1) task parent is another task == task.ParentTask is truthy:
        Parameters are:
            1. final_status == task.ParentTask.getFinalStatus() is truthy
            2. parent_has_sub == len(task.ParentTask.OrderedSubTasks) is truthy
            3. parent_is_group == task.ParentTask.is_group is truthy
            4. old == updateParentTask called with truthy old_parent_task
            5. old_has_sub == len(old_parent_task.OrderedSubTasks) is truthy

        The only invalid combination is old 1 and old_has_sub 0 leaving
        2 ^ 5 - 2 ^ 3 = 24 valid combinations

    2) task parent is a project == task.Project is truthy:
        Parameters are:
            1. top_tasks == len(task.Project.TopTasks) is truthy
            2. is_group == task.Project.is_group is truthy
            3. old (see above)
            4. old_has_sub (see above)

        Again, the only invalid combination is old 1 and old_has_sub 0 leaving
        2 ^ 4 - 2 ^ 2 = 12 valid combinations

    In total, we have 36 test cases
    """

    def _updateParentTask_setup_old(self, old, old_has_sub):
        if old:
            old_parent = mock.MagicMock(spec=tasks.Task)

            if old_has_sub:
                old_parent.OrderedSubTasks = [1]
            else:
                old_parent.OrderedSubTasks = []

            return old_parent

        return None

    def _updateParentTask_task_setup(
        self, final_status, parent_has_sub, parent_is_group, old, old_has_sub
    ):
        task = mock.MagicMock(spec=tasks.Task)

        task.ParentTask.getFinalStatus.return_value = final_status
        task.ParentTask.is_group = parent_is_group
        if parent_has_sub:
            task.ParentTask.OrderedSubTasks = [1]
        else:
            task.ParentTask.OrderedSubTasks = []

        old_parent = self._updateParentTask_setup_old(old, old_has_sub)
        return task, old_parent

    def _updateParentTask_assert_old(self, old_parent, old, old_has_sub):
        if old:
            if old_has_sub:
                old_parent.updateObject.assert_not_called()
            else:
                old_parent.updateObject.assert_called_once_with(is_group=0)

    def _updateParentTask_task_assert(
        self,
        task,
        old_parent,
        final_status,
        parent_has_sub,
        parent_is_group,
        old,
        old_has_sub,
    ):
        task.ParentTask.getFinalStatus.assert_called_once_with()
        if final_status:
            task.ParentTask.ChangeState.assert_called_once_with(
                final_status,
                check_access=False,
            )
        else:
            task.ParentTask.ChangeState.assert_not_called()

        if parent_has_sub and not parent_is_group:
            task.ParentTask.updateObject.assert_called_once_with(is_group=1)
        elif not parent_has_sub and parent_is_group:
            task.ParentTask.updateObject.assert_called_once_with(is_group=0)
        else:
            task.ParentTask.updateObject.assert_not_called()

        self._updateParentTask_assert_old(old_parent, old, old_has_sub)

    def test_updateParentTask_task_1_1_1_1_1(self):
        args = (1, 1, 1, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_1_1_1_0(self):
        args = (1, 1, 1, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_1_1_0_0(self):
        args = (1, 1, 1, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_1_0_1_1(self):
        args = (1, 1, 0, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_1_0_1_0(self):
        args = (1, 1, 0, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_1_0_0_0(self):
        args = (1, 1, 0, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_1_1_1(self):
        args = (1, 0, 1, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_1_1_0(self):
        args = (1, 0, 1, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_1_0_0(self):
        args = (1, 0, 1, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_0_1_1(self):
        args = (1, 0, 0, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_0_1_0(self):
        args = (1, 0, 0, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_1_0_0_0_0(self):
        args = (1, 0, 0, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_1_1_1(self):
        args = (0, 1, 1, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_1_1_0(self):
        args = (0, 1, 1, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_1_0_0(self):
        args = (0, 1, 1, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_0_1_1(self):
        args = (0, 1, 0, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_0_1_0(self):
        args = (0, 1, 0, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_1_0_0_0(self):
        args = (0, 1, 0, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_1_1_1(self):
        args = (0, 0, 1, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_1_1_0(self):
        args = (0, 0, 1, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_1_0_0(self):
        args = (0, 0, 1, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_0_1_1(self):
        args = (0, 0, 0, 1, 1)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_0_1_0(self):
        args = (0, 0, 0, 1, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    def test_updateParentTask_task_0_0_0_0_0(self):
        args = (0, 0, 0, 0, 0)
        task, old_parent = self._updateParentTask_task_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_task_assert(task, old_parent, *args)

    # end updateParentTask

    def _updateParentTask_proj_setup(self, top_tasks, is_group, old, old_has_sub):
        task = mock.MagicMock(spec=tasks.Task)
        task.ParentTask = None

        if top_tasks:
            task.Project.TopTasks = [1]
        else:
            task.Project.TopTasks = []

        task.Project.is_group = is_group

        old_parent = self._updateParentTask_setup_old(old, old_has_sub)
        return task, old_parent

    def _updateParentTask_proj_assert(
        self, task, old_parent, top_tasks, is_group, old, old_has_sub
    ):
        if top_tasks and not is_group:
            task.Project.updateObject.assert_called_once_with(is_group=1)
        elif not top_tasks and is_group:
            task.Project.updateObject.assert_called_once_with(is_group=0)
        else:
            task.Project.updateObject.assert_not_called()

        self._updateParentTask_assert_old(old_parent, old, old_has_sub)

    def test_updateParentTask_proj_1_1_1_1(self):
        args = (1, 1, 1, 1)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_1_1_1_0(self):
        args = (1, 1, 1, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_1_1_0_0(self):
        args = (1, 1, 0, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_1_0_1_1(self):
        args = (1, 0, 1, 1)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_1_0_1_0(self):
        args = (1, 0, 1, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_1_0_0_0(self):
        args = (1, 0, 0, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_1_1_1(self):
        args = (0, 1, 1, 1)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_1_1_0(self):
        args = (0, 1, 1, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_1_0_0(self):
        args = (0, 1, 0, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_0_1_1(self):
        args = (0, 0, 1, 1)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_0_1_0(self):
        args = (0, 0, 1, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    def test_updateParentTask_proj_0_0_0_0(self):
        args = (0, 0, 0, 0)
        task, old_parent = self._updateParentTask_proj_setup(*args)
        self.assertIsNone(tasks.Task.updateParentTask(task, None, old_parent))
        self._updateParentTask_proj_assert(task, old_parent, *args)

    @mock.patch.object(tasks.ue, "Exception", autospec=True)
    def test_check_Project_State_no_proj(self, Exception_):
        "does nothing if task is missing a project"
        task = tasks.Task()
        self.assertIsNone(task.check_Project_State(None))
        self.assertEqual(Exception_.call_count, 0)

    @mock.patch.object(tasks.ue, "Exception", autospec=True)
    def test_check_Project_State_not_finalized(self, Exception_):
        "does nothing if project is not finalized"
        task = tasks.Task()
        project = mock.MagicMock(
            spec=tasks.Project,
            status="not completed or discarded",
        )
        project.isFinalized.return_value = None
        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            self.assertIsNone(task.check_Project_State(None))

        project.isFinalized.assert_called_once_with()
        self.assertEqual(Exception_.call_count, 0)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_check_Project_State_finalized(self, CDBMsg):
        "fails if project is finalized"
        task = tasks.Task()
        project = mock.MagicMock(
            spec=tasks.Project,
            status=tasks.Project.COMPLETED.status,
        )
        project.isFinalized.side_effect = tasks.ue.Exception("foo")
        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            with self.assertRaises(tasks.ue.Exception):
                task.check_Project_State(None)

        project.isFinalized.assert_called_once_with()

        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            with self.assertRaises(tasks.ue.Exception):
                task.check_Project_State(None)
        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "foo",
        )

    @pytest.mark.unit
    @mock.patch.object(tasks.Task, "checkStructureLock")
    def test_on_cdbpcs_task_reset_start_time_pre_mask(self, checkStructureLock):
        """Testing the modifying of the time of a project. This only tests the pre function, with
        a defined start_time_fcast and a defined start_time_fcast"""
        task = tasks.Task(
            start_time_fcast=date(2022, 12, 1), end_time_fcast=date(2022, 12, 5)
        )
        ctx = mock.MagicMock()
        task.on_cdbpcs_task_reset_start_time_pre_mask(ctx)
        checkStructureLock.assert_called_once_with(ctx=ctx)
        ctx.set.assert_has_calls(
            [
                mock.call("start_time_old", task.start_time_fcast),
                mock.call("end_time_old", task.end_time_fcast),
            ]
        )

    @pytest.mark.unit
    def test__check_percentage(self):
        """Testing the modifying of the %Completed of a project. This test only tests the case
        that the %Completed is below 100"""
        task = tasks.Task(
            start_time_fcast=date(2022, 12, 1),
            end_time_fcast=date(2022, 12, 5),
            percent_complet=99,
            status=50,
        )
        ctx = mock.MagicMock()
        mocked_module = mock.Mock()
        mocked_module.check_percentage = mock.Mock()
        with mock.patch.dict(
            "sys.modules", {"cs.pcs.projects.dialog_hooks": mocked_module}
        ):
            task._check_percentage(ctx=ctx)
            mocked_module.check_percentage.assert_called_once_with(task)

    @pytest.mark.unit
    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(tasks.Task, "checkStructureLock")
    def test_no_fcast_on_cdpcs_task_reset_start_time_pre_mask(
        self, checkStructureLock, CDBMsg
    ):
        """Test of modifying the start time of a task. This only tests the pre function, without
        a defined start_time_fcast and start_time_plan."""
        ctx = mock.MagicMock()
        ctx.set.return_value = None
        with self.assertRaises(ue.Exception):
            task = tasks.Task()
            task.on_cdbpcs_task_reset_start_time_pre_mask(ctx)
        checkStructureLock.assert_called_once_with(ctx=ctx)
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_move_task_error_01")

    @pytest.mark.unit
    def test_move_dates_start(self):
        """Testing the function which calculates the dates inside the mask, after
        changing start_time_new"""
        task = tasks.Task(
            start_time_fcast=date(2022, 12, 5),
            end_time_fcast=date(2022, 12, 16),
            days_fcast=10,
            cdb_project_id="Ptest.baselining",
            ce_baseline_id="",
        )
        start_time_new = date(2022, 12, 19)
        end_time_new = date(2022, 12, 30)
        start_time_input = date(2022, 12, 17)
        start, end = tasks.Task.move_dates(task, start_time_input, None)
        start = start.date()
        self.assertEqual(start, start_time_new)
        self.assertEqual(end, end_time_new)

    @pytest.mark.unit
    def test_move_dates_end(self):
        """Testing the function which calculates the dates inside the mask, after
        changing end_time_new"""
        task = tasks.Task(
            start_time_fcast=date(2022, 12, 5),
            end_time_fcast=date(2022, 12, 16),
            days_fcast=10,
            cdb_project_id="Ptest.baselining",
            ce_baseline_id="",
        )
        start_time_new = date(2022, 12, 19)
        end_time_new = date(2022, 12, 30)
        end_time_input = date(2023, 1, 1)
        start, end = tasks.Task.move_dates(task, None, end_time_input)
        end = end.date()
        self.assertEqual(start, start_time_new)
        self.assertEqual(end, end_time_new)

    @pytest.mark.unit
    def test_move_dates_no_change(self):
        """Testing the function which calculates the dates inside the mask, after
        no Change, to prevent unwanted exceptions"""
        task = tasks.Task(
            start_time_fcast=date(2022, 12, 5),
            end_time_fcast=date(2022, 12, 16),
            days_fcast=10,
            cdb_project_id="Ptest.baselining",
            ce_baseline_id="",
        )
        self.assertEqual(tasks.Task.move_dates(task, None, None), None)

    @mock.patch.object(tasks.utils, "add_interactive_call")
    def test_init_status_change(self, add_interactive_call):
        "Init status change by adding task to status change stack"
        task = tasks.Task()
        task.init_status_change()
        add_interactive_call.assert_called_once_with(task)

    @mock.patch.object(tasks.Project, "do_status_updates")
    @mock.patch.object(tasks.utils, "remove_from_change_stack", return_value="foo")
    def test_end_status_change_00(self, remove_from_change_stack, do_status_updates):
        "Remove task from status change stack and execute updates"
        task = tasks.Task()
        project = tasks.Project()
        ctx = mock.Mock()
        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            task.end_status_change(ctx)
        remove_from_change_stack.assert_called_once_with(task, ctx)
        do_status_updates.assert_called_once_with("foo")

    @mock.patch.object(tasks.Project, "do_status_updates")
    @mock.patch.object(tasks.utils, "remove_from_change_stack", return_value=None)
    def test_end_status_change_01(self, remove_from_change_stack, do_status_updates):
        "Remove task from status change stack; no updates executed"
        task = tasks.Task()
        project = tasks.Project()
        ctx = mock.Mock()
        with mock.patch.object(
            tasks.Task, "Project", new_callable=mock.PropertyMock, return_value=project
        ):
            task.end_status_change(ctx)
        remove_from_change_stack.assert_called_once_with(task, ctx)
        do_status_updates.assert_not_called()

    def test_checkSchedule(self):
        ctx = mock.MagicMock()
        project = mock.MagicMock()
        task = tasks.Task()
        with mock.patch.object(tasks.Task, "Project", project):
            task.checkSchedule(ctx)
        project.checkScheduleLock.assert_called_once()

    def test_setDefaults(self):
        ctx = mock.MagicMock()
        ctx.get_current_mask = mock.MagicMock(return_value="initial")
        ctx.action = "create"
        project = mock.MagicMock(project_name="pname")
        parent_task = mock.MagicMock(task_name="tname")
        task = tasks.Task()
        with mock.patch.object(tasks.Task, "Project", project), mock.patch.object(
            tasks.Task, "ParentTask", parent_task
        ):
            task.setDefaults(ctx)

        self.assertEqual(task.task_id, "#")
        ctx.set.assert_has_calls(
            [
                mock.call("project_name", project.project_name),
                mock.call("parent_task_name", parent_task.task_name),
            ]
        )

    @mock.patch.object(tasks.Task, "getReadOnlyFields")
    @mock.patch.object(tasks.Task, "initConstraintDate")
    @mock.patch.object(tasks.Task, "getEndTimeTopDown")
    @mock.patch.object(tasks.Task, "getStartTimeTopDown")
    @mock.patch.object(tasks.Task, "getEffortMax")
    @mock.patch.object(tasks.Task, "makePosition")
    def test_setInitValues_action_copy(
        self,
        makePosition,
        getEffortMax,
        getStartTimeTopDown,
        getEndTimeTopDown,
        initConstraintDate,
        getReadOnlyFields,
    ):
        ctx = mock.MagicMock()
        ctx.action = "copy"
        d = {
            "subject_id": "123",
            "subject_type": "person",
            "automatic": 0,
            "auto_update_time": 0,
        }

        ctx.cdbtemplate = mock.MagicMock()
        ctx.cdbtemplate.__getitem__.side_effect = d.__getitem__

        makePosition.return_value = 1000
        getEffortMax.return_value = 5
        getStartTimeTopDown.return_value = None
        getEndTimeTopDown.return_value = None
        getReadOnlyFields.return_value = [1, 2, 3]

        task = tasks.Task()

        task.setInitValues(ctx)

        self.assertEqual(task.percent_complet, 0)
        self.assertEqual(task.start_time_act, None)
        self.assertEqual(task.end_time_act, None)
        self.assertEqual(task.psp_code, "")
        self.assertEqual(task.automatic, 0)
        self.assertEqual(task.auto_update_time, 0)
        self.assertEqual(task.position, 1000)
        self.assertEqual(task.subject_id, "123")
        self.assertEqual(task.subject_type, "person")

        ctx.set.assert_has_calls(
            [
                mock.call("effort_ava", "5.00"),
                mock.call("start_time_ava", ""),
                mock.call("end_time_ava", ""),
            ]
        )

        ctx.set_fields_readonly.assert_called_once_with([1, 2, 3])

        initConstraintDate.assert_called_once_with(ctx)

    @mock.patch.object(tasks.Task, "getReadOnlyFields")
    @mock.patch.object(tasks.Task, "initConstraintDate")
    @mock.patch.object(tasks.Task, "getEndTimeTopDown")
    @mock.patch.object(tasks.Task, "getStartTimeTopDown")
    @mock.patch.object(tasks.Task, "getEffortMax")
    @mock.patch.object(tasks.Task, "makePosition")
    def test_setInitValues_action_create_parentTask(
        self,
        makePosition,
        getEffortMax,
        getStartTimeTopDown,
        getEndTimeTopDown,
        initConstraintDate,
        getReadOnlyFields,
    ):
        ctx = mock.MagicMock()
        ctx.action = "create"

        makePosition.return_value = 1000
        getEffortMax.return_value = 5
        getStartTimeTopDown.return_value = None
        getEndTimeTopDown.return_value = None
        getReadOnlyFields.return_value = [1, 2, 3]

        key_values = {
            "task_name": "name",
            "subject_id": "subj1",
            "subject_type": "subj_type1",
            "category": "cat1",
            "start_time_plan": None,
            "end_time_plan": None,
            "days": None,
            "division": "div1",
            "cdb_objektart": "obj_kart",
            "start_time_fcast": None,
            "end_time_fcast": None,
            "days_fcast": 5,
            "auto_update_effort": True,
            "auto_update_time": False,
            "constraint_type": "type1",
            "constraint_date": None,
        }

        parent_task = mock.MagicMock()
        parent_task.__iter__.return_value = key_values.keys()
        parent_task.__getitem__.side_effect = key_values.__getitem__

        task = tasks.Task()

        with mock.patch.object(tasks.Task, "ParentTask", parent_task):
            task.setInitValues(ctx)

        result = {key: task[key] for key in list(key_values.keys())}

        self.assertEqual(key_values, result)

    @mock.patch.object(tasks.Task, "getReadOnlyFields")
    @mock.patch.object(tasks.Task, "initConstraintDate")
    @mock.patch.object(tasks.Task, "getEndTimeTopDown")
    @mock.patch.object(tasks.Task, "getStartTimeTopDown")
    @mock.patch.object(tasks.Task, "getEffortMax")
    @mock.patch.object(tasks.Task, "makePosition")
    def test_setInitValues_action_create_project(
        self,
        makePosition,
        getEffortMax,
        getStartTimeTopDown,
        getEndTimeTopDown,
        initConstraintDate,
        getReadOnlyFields,
    ):
        ctx = mock.MagicMock()
        ctx.action = "create"

        makePosition.return_value = 1000
        getEffortMax.return_value = 5
        getStartTimeTopDown.return_value = None
        getEndTimeTopDown.return_value = None
        getReadOnlyFields.return_value = [1, 2, 3]

        key_values = {
            "start_time_plan": None,
            "end_time_plan": None,
            "days": None,
            "start_time_fcast": None,
            "end_time_fcast": None,
            "days_fcast": 5,
        }

        project = mock.MagicMock()
        project.__iter__.return_value = key_values.keys()
        project.__getitem__.side_effect = key_values.__getitem__

        task = tasks.Task()

        with mock.patch.object(tasks.Task, "Project", project):
            task.setInitValues(ctx)

        result = {key: task[key] for key in list(key_values.keys())}

        self.assertEqual(key_values, result)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(tasks.Task, "ByKeys")
    def test_checkTaskId(self, ByKeys, CDBMsg):
        ctx = mock.MagicMock()
        ByKeys.return_value = "task"
        ctx.get_current_mask.return_value = "initial"

        task = tasks.Task()
        task.task_id = 123
        with self.assertRaises(ue.Exception):
            task.checkTaskId(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_task_id_exists")

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkEfforts(self, CDBMsg):
        ctx = mock.MagicMock()
        task = tasks.Task()
        task.milestone = True
        task.effort_plan = 30

        with self.assertRaises(ue.Exception):
            task.checkEfforts(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_effort3")

    def test_checkEffortFields(self):
        ctx = mock.MagicMock()
        sub_tasks = []
        target_date = date(2021, 6, 7)
        planned_date = target_date + timedelta(days=2)
        task = tasks.Task()
        task.effort_plan = 0
        task.effort_fcast = 3
        task.start_time_fcast = target_date
        task.start_time_plan = planned_date
        task.end_time_fcast = target_date
        task.end_time_plan = planned_date

        with mock.patch.object(tasks.Task, "Subtasks", sub_tasks):
            task.checkEffortFields(ctx)

        self.assertEqual(task.effort_fcast, 3)
        self.assertEqual(task.effort_plan, 3)
        self.assertEqual(task.start_time_fcast, target_date)
        self.assertEqual(task.start_time_plan, planned_date)
        self.assertEqual(task.end_time_fcast, target_date)
        self.assertEqual(task.end_time_plan, planned_date)

    def test_setObjectart(self):
        ctx = mock.MagicMock()
        task = tasks.Task()
        task.setObjectart(ctx)
        self.assertEqual(task.cdb_objektart, "cdbpcs_task")

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(tasks.Baseline, "ByKeys")
    @mock.patch.object(tasks.Project, "ByKeys")
    def test_checkProjectID(self, ProjectByKeys, BaselineByKeys, CDBMsg):
        ctx = mock.MagicMock()
        ProjectByKeys.return_value = None
        BaselineByKeys.return_value = mock.MagicMock()
        task = tasks.Task()

        with self.assertRaises(ue.Exception):
            task.checkProjectID(ctx)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "pcs_err_prj_id")

    @mock.patch.object(tasks.Task, "makeTaskID")
    @mock.patch.object(tasks.Task, "Query")
    def test_setTaskID(self, Query, makeTaskID):
        ctx = mock.MagicMock()
        makeTaskID.return_value = "bar"
        Query.return_value = ["task"]

        task = tasks.Task()
        task.task_id = "foo"
        task.cdb_project_id = "project"

        task.setTaskID(ctx)
        makeTaskID.assert_called_once_with()
        Query.assert_called_once_with("task_id = 'foo'")
        self.assertEqual(task.task_id, "bar")

    @mock.patch.object(tasks.Task, "makePosition")
    def test_setPosition(self, makePosition):
        ctx = mock.MagicMock()
        makePosition.return_value = 120
        task = tasks.Task()
        task.task_id = "foo"
        task.position = None
        task.setPosition(ctx)

        makePosition.assert_called_once()
        self.assertEqual(task.position, 120)

    @mock.patch.object(tasks.Task, "Project")
    def test_check_project_role_needed(self, Project):
        ctx = mock.MagicMock()
        task = tasks.Task()
        task.check_project_role_needed(ctx)
        Project.check_project_role_needed.assert_called_once_with(ctx)

    @mock.patch.object(tasks.sqlapi, "SQLupdate")
    def test_setTemplateOID(self, SQLupdate):
        task = tasks.Task()
        task.cdb_object_id = "foo"
        task.setTemplateOID()

        SQLupdate.assert_called_once_with(
            "cdbpcs_task SET template_oid = '' WHERE template_oid = 'foo'"
            " AND ce_baseline_id = ''"
        )

    def _test_check_deepdelete(self, reason, expected_output):
        def get_obj(desc, **args):
            obj = mock.MagicMock(**args)
            obj.GetDescription = mock.MagicMock(return_value=desc)
            return obj

        def get_obj_pred_succ(desc):
            obj = get_obj(desc)

            obj_dict = {}
            obj_dict["AE"] = [obj]
            obj_dict["EA"] = []
            obj_dict["EE"] = []
            obj_dict["AA"] = []
            return_value = mock.MagicMock()
            return_value.__getitem__.side_effect = obj_dict.__getitem__
            return return_value

        pred = get_obj_pred_succ("foo")
        succ = get_obj_pred_succ("bar")

        timesheets = [get_obj(desc) for desc in ["ts-foo", "ts-bar"]]
        subChecklists = [get_obj("subcl-foo")]
        checkListItems = [
            get_obj("clitem-foo", SubChecklists=subChecklists, Rating="R")
        ]
        checklists = [
            get_obj("cl-foo", ChecklistItems=checkListItems),
            get_obj("cl-bar", ChecklistItems=checkListItems),
        ]

        subTasks = []

        task = tasks.Task()
        task.status = 10
        result = []
        with mock.patch.object(
            tasks.Task, "PredecessorTaskRelationsByType", pred
        ), mock.patch.object(
            tasks.Task, "SuccessorTaskRelationsByType", succ
        ), mock.patch.object(
            tasks.Task, "TimeSheets", timesheets
        ), mock.patch.object(
            tasks.Task, "Checklists", checklists
        ), mock.patch.object(
            tasks.Task, "Subtasks", subTasks
        ):
            result = task.check_deepdelete(reason)

        self.assertEqual(expected_output, result)

    @mock.patch.object(tasks.Task, "GetDescription")
    def test_check_deepdelete_no_reason(self, GetDescription):
        GetDescription.return_value = "task-desc"
        self._test_check_deepdelete(
            False,
            [
                "Task task-desc",
                "Vorgänger: foo",
                "Nachfolger: bar",
                "ts-foo",
                "ts-bar",
                "cl-foo",
                "cl-bar",
            ],
        )

    @mock.patch.object(tasks.util, "get_label")
    @mock.patch.object(tasks.Task, "GetDescription")
    def test_check_deepdelete_with_reason(self, GetDescription, get_label):
        get_label.side_effect = lambda x: x  # return the actual label
        GetDescription.return_value = "task-desc"
        self._test_check_deepdelete(
            True,
            [
                "Task task-desc (cdbpcs_notplanned)",
                "Vorgänger: foo (cdbpcs_delete_vnrels)",
                "Nachfolger: bar (cdbpcs_delete_vnrels)",
                "ts-foo",
                "ts-bar",
                "cl-foo (cdbpcs_hassubcl)",
                "cl-foo (cdbpcs_rated)",
                "cl-bar (cdbpcs_hassubcl)",
                "cl-bar (cdbpcs_rated)",
            ],
        )

    @mock.patch.object(
        tasks.Task,
        "MakeChangeControlAttributes",
        return_value={"cdb_mdate": "foo", "cdb_mpersno": "bar"},
    )
    @mock.patch.object(tasks.Task, "KeywordQuery", return_value="fol")
    def test_mark_as_changed(self, KeywordQuery, MakeChangeControlAttributes):
        "Task.mark_as_changed"
        result = mock.Mock()
        KeywordQuery.return_value = result
        task = tasks.Task()
        task.mark_as_changed(bal="dur")
        KeywordQuery.assert_called_once_with(bal="dur", ce_baseline_id="")
        MakeChangeControlAttributes.assert_called_once_with()
        result.Update.assert_called_once_with(cdb_adate="foo", cdb_apersno="bar")

    @mock.patch.object(tasks.Task, "_updateTaskRelations")
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery")
    def test__copy_taskrels_by_mapping(self, KeywordQuery, _updateTaskRelations):
        """Test copy task relations"""
        old_project_id = "1"
        new_project_id = "2"

        rel_copy = mock.MagicMock()

        task_rel1 = mock.MagicMock(
            Copy=rel_copy,
            cdb_project_id=old_project_id,
            cdb_project_id2=old_project_id,
            task_id="1",
            task_id2="2",
        )
        task_rel2 = mock.MagicMock(
            Copy=rel_copy,
            cdb_project_id=new_project_id,
            cdb_project_id2=new_project_id,
            task_id="3",
            task_id2="4",
        )
        task_id_mapping = {"1": "3", "2": "4"}
        task_rel_keys = list(task_id_mapping)
        KeywordQuery.return_value = [task_rel1, task_rel2]

        tasks.Task._copy_taskrels_by_mapping(
            old_project_id, new_project_id, task_id_mapping
        )
        KeywordQuery.assert_called_once_with(
            cdb_project_id=old_project_id,
            task_id=task_rel_keys,
            cdb_project_id2=old_project_id,
            task_id2=task_rel_keys,
        )

        rel_copy.assert_has_calls(
            [
                mock.call(
                    cdb_project_id=new_project_id,
                    cdb_project_id2=new_project_id,
                    task_id="3",
                    task_id2="4",
                ),
                mock.call(
                    cdb_project_id=new_project_id,
                    cdb_project_id2=new_project_id,
                    task_id="3",
                    task_id2="4",
                ),
            ]
        )

        _updateTaskRelations.assert_called_once_with(new_project_id)

    def test_on_cdbpcs_create_from_pre_mask_no_webui(self):
        skip_dialog = mock.MagicMock()
        ctx = mock.MagicMock(uses_webui=False, skip_dialog=skip_dialog)
        tasks.Task.on_cdbpcs_create_from_pre_mask(ctx)
        skip_dialog.assert_called_once()

    def test_on_cdbpcs_create_from_pre_mask(self):
        parent = mock.MagicMock(name="parent", cdb_project_id="p1", task_id="t1")
        set_func = mock.MagicMock(name="set")
        ctx = mock.MagicMock(uses_webui=True, set=set_func)
        ctx.parent = parent
        tasks.Task.on_cdbpcs_create_from_pre_mask(ctx)
        set_func.assert_has_calls(
            [mock.call("parent_project", "p1"), mock.call("parent_task", "t1")]
        )

    def test_generate_project_structure_URL(self):
        request = mock.MagicMock(application_url="application_url")
        task = tasks.Task()
        task.cdb_project_id = "cdb_project_id"
        self.assertEqual(
            task.generate_project_structure_URL(request, "rest_key"),
            "application_url/info/project/cdb_project_id@?active_tab_id=cs-pcs-projects-web-StructureView&selected=rest_key",  # noqa
        )

    def test_generate_project_structure_URL_no_request(self):
        task = tasks.Task()
        task.cdb_project_id = "cdb_project_id"
        task.task_id = "task_id"
        task.ce_baseline_id = ""
        expected_url = (
            f"{rte.environ.get(constants.kEnvWWWServiceURL, '')}/info/project/"
            "cdb_project_id@?active_tab_id=cs-pcs-projects-web"
            "-StructureView&selected=cdb_project_id@task_id@"
        )
        self.assertEqual(task.generate_project_structure_URL(), expected_url)


class TestRecalculate(testcase.RollbackTestCase):
    def get_tasks_for_milestones(self):
        proj = Project.Create(cdb_project_id="id")
        milestone_task = Task.Create(
            task_id="milestone",
            cdb_project_id=proj.cdb_project_id,
            automatic=0,
            milestone=1,
            daytime=1,
            constraint_type=0,
        )
        sucessor = Task.Create(
            task_id="sucessor",
            cdb_project_id=proj.cdb_project_id,
            constraint_type=0,
        )
        taskrel = TaskRelation.Create(
            cdb_project_id=proj.cdb_project_id,
            cdb_project_id2=proj.cdb_project_id,
            task_id2=milestone_task.task_id,
            task_id=sucessor.task_id,
            rel_type="EA",
        )
        return proj, milestone_task, sucessor, taskrel

    @mock.patch.object(Project, "recalculate")
    def test_recalculate_milestone_task_with_sucessor_same_project(self, _):
        proj, milestone_task, _, __ = self.get_tasks_for_milestones()
        with transaction.Transaction():
            operation(
                kOperationModify,
                milestone_task,
                daytime=0,
            )

        proj.recalculate.assert_called_once()

    @mock.patch.object(Project, "recalculate")
    @mock.patch.object(TaskRelation, "recalculate")
    def test_recalculate_milestone_task_with_sucessor_different_project(self, _, __):
        # only update the project of the changes task if predecessor and sucessor are in different projects
        # recalculate must be called exactly once
        _, milestone_task, sucessor, taskrel = self.get_tasks_for_milestones()
        proj1 = Project.Create(cdb_project_id="id1")

        sucessor.Update(cdb_project_id=proj1.cdb_project_id)
        taskrel.Update(cdb_project_id=proj1.cdb_project_id)
        with transaction.Transaction():
            operation(
                kOperationModify,
                milestone_task,
                daytime=0,
            )

        Project.recalculate.assert_called_once()

    def get_tasks_for_auto_update_effort(self):
        from cdb import auth
        from cdb.objects.org import User

        proj = Project.Create(
            cdb_project_id="id",
            calendar_profile_id=User.ByKeys(auth.persno).calendar_profile_id,
        )
        collection_task = Task.Create(
            task_id="t_id",
            cdb_project_id=proj.cdb_project_id,
            auto_update_effort=False,
            effort_fcast=0.00,
            constraint_type=0,
        )
        subtask = Task.Create(
            task_id="subtask_id",
            cdb_project_id=proj.cdb_project_id,
            auto_update_effort=False,
            effort_fcast=3.00,
            constraint_type=0,
        )
        with transaction.Transaction():
            operation(
                kOperationModify,
                subtask,
                parent_task=collection_task.task_id,
            )
        return collection_task, subtask

    def test_change_task_to_auto_update_effort(self):
        collection_task, _ = self.get_tasks_for_auto_update_effort()

        with transaction.Transaction():
            operation(
                kOperationModify,
                collection_task,
                auto_update_effort=True,
            )
        self.assertEqual(collection_task.effort_fcast, 3.00)

    @mock.patch.object(Project, "aggregate")
    def test_change_task_from_auto_update_effort(self, _):
        collection_task, _ = self.get_tasks_for_auto_update_effort()

        with transaction.Transaction():
            operation(
                kOperationModify,
                collection_task,
                auto_update_effort=True,
            )

        with transaction.Transaction():
            operation(
                kOperationModify,
                collection_task,
                auto_update_effort=False,
            )
        self.assertTrue(Project.aggregate.call_count >= 2)


@pytest.mark.unit
class TestTaskRel(unittest.TestCase):
    @mock.patch.object(tasks.sqlapi, "RecordSet2")
    @mock.patch.object(tasks.TaskRelation, "__graph_stmt__")
    def test_GetGraph(self, graph_stmt, RecordSet2):
        RecordSet2.return_value = [
            mock.MagicMock(succ_task_oid="S1", pred_task_oid="P1"),
            mock.MagicMock(succ_task_oid="S2", pred_task_oid="P3"),
            mock.MagicMock(succ_task_oid="S1", pred_task_oid="P2"),
            mock.MagicMock(succ_task_oid="S1", pred_task_oid="P1"),
        ]
        self.assertEqual(
            tasks.TaskRelation.GetGraph("foo"),
            {
                "S1": ["P1", "P2", "P1"],
                "S2": ["P3"],
            },
        )
        RecordSet2.assert_called_once_with(
            sql=graph_stmt.format("cdb_project_id = 'foo'")
        )

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getLateFinish_EA_no_start_time(self, next_day, SuccessorTask):
        "returns None if successor's start date not set and type is EA"
        taskrel = tasks.TaskRelation(rel_type="EA")
        taskrel.SuccessorTask.start_time_fcast = None
        self.assertIsNone(taskrel.getLateFinish())
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getLateFinish_EA_start_time(self, next_day, SuccessorTask):
        "returns successor's start date if set and type is EA"
        taskrel = tasks.TaskRelation(rel_type="EA")
        self.assertEqual(taskrel.getLateFinish(), next_day.return_value)
        next_day.assert_called_once_with(
            taskrel.SuccessorTask.start_time_fcast,
            -1,
        )

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getLateFinish_EE_no_end_time(self, next_day, SuccessorTask):
        "returns None if successor's end date not set and type is EE"
        taskrel = tasks.TaskRelation(rel_type="EE")
        taskrel.SuccessorTask.end_time_fcast = None
        self.assertIsNone(taskrel.getLateFinish())
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getLateFinish_EE_end_time(self, next_day, SuccessorTask):
        "returns successor's end date if set and type is EE"
        taskrel = tasks.TaskRelation(rel_type="EE")
        self.assertEqual(taskrel.getLateFinish(), taskrel.SuccessorTask.end_time_fcast)
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getLateFinish_no_reltype(self, next_day, SuccessorTask):
        "returns None if reltype is missing"
        taskrel = tasks.TaskRelation()
        self.assertIsNone(taskrel.getLateFinish())
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_getLateStart_AA_no_start_time(self, SuccessorTask):
        "returns None if successor's start date not set and type is AA"
        taskrel = tasks.TaskRelation(rel_type="AA")
        taskrel.SuccessorTask.start_time_fcast = None
        self.assertIsNone(taskrel.getLateStart())

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_getLateStart_AA_start_time(self, SuccessorTask):
        "returns successor's start date if set and type is AA"
        taskrel = tasks.TaskRelation(rel_type="AA")
        self.assertEqual(taskrel.getLateStart(), taskrel.SuccessorTask.start_time_fcast)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_getLateStart_AE_no_end_time(self, SuccessorTask):
        "returns None if successor's end date not set and type is AE"
        taskrel = tasks.TaskRelation(rel_type="AE")
        taskrel.SuccessorTask.end_time_fcast = None
        self.assertIsNone(taskrel.getLateStart())

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_getLateStart_AE_end_time(self, SuccessorTask):
        "returns successor's end date if set and type is AE"
        taskrel = tasks.TaskRelation(rel_type="AE")
        self.assertEqual(taskrel.getLateStart(), taskrel.SuccessorTask.end_time_fcast)

    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_getLateStart_no_reltype(self, SuccessorTask):
        "returns None if reltype is missing"
        taskrel = tasks.TaskRelation()
        self.assertIsNone(taskrel.getLateStart())

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    def test_getEarlyFinish_EE_no_end_time(self, PredecessorTask):
        "returns None if successor's end date not set and type is EE"
        taskrel = tasks.TaskRelation(rel_type="EE")
        taskrel.PredecessorTask.end_time_fcast = None
        self.assertIsNone(taskrel.getEarlyFinish())

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    def test_getEarlyFinish_EE_end_time(self, PredecessorTask):
        "returns successor's end date if set and type is EE"
        taskrel = tasks.TaskRelation(rel_type="EE")
        self.assertEqual(
            taskrel.getEarlyFinish(), taskrel.PredecessorTask.end_time_fcast
        )

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    def test_getEarlyFinish_AE_no_start_time(self, PredecessorTask):
        "returns None if successor's start date not set and type is AE"
        taskrel = tasks.TaskRelation(rel_type="AE")
        taskrel.PredecessorTask.start_time_fcast = None
        self.assertIsNone(taskrel.getEarlyFinish())

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    def test_getEarlyFinish_AE_start_time(self, PredecessorTask):
        "returns successor's start date if set and type is AE"
        taskrel = tasks.TaskRelation(rel_type="AE")
        self.assertEqual(
            taskrel.getEarlyFinish(), taskrel.PredecessorTask.start_time_fcast
        )

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    def test_getEarlyFinish_no_reltype(self, PredecessorTask):
        "returns None if reltype is missing"
        taskrel = tasks.TaskRelation()
        self.assertIsNone(taskrel.getEarlyFinish())

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getEarlyStart_EA_no_end_time(self, next_day, PredecessorTask):
        "returns None if successor's end date not set and type is EA"
        taskrel = tasks.TaskRelation(rel_type="EA")
        taskrel.PredecessorTask.end_time_fcast = None
        self.assertIsNone(taskrel.getEarlyStart())
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getEarlyStart_EA_end_time(self, next_day, PredecessorTask):
        "returns successor's end date if set and type is EA"
        taskrel = tasks.TaskRelation(rel_type="EA")
        self.assertEqual(taskrel.getEarlyStart(), next_day.return_value)
        next_day.assert_called_once_with(
            taskrel.PredecessorTask.end_time_fcast,
            1,
        )

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getEarlyStart_AA_no_start_time(self, next_day, PredecessorTask):
        "returns None if successor's start date not set and type is AA"
        taskrel = tasks.TaskRelation(rel_type="AA")
        taskrel.PredecessorTask.start_time_fcast = None
        self.assertIsNone(taskrel.getEarlyStart())
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getEarlyStart_AA_start_time(self, next_day, PredecessorTask):
        "returns successor's start date if set and type is AA"
        taskrel = tasks.TaskRelation(rel_type="AA")
        self.assertEqual(
            taskrel.getEarlyStart(), taskrel.PredecessorTask.start_time_fcast
        )
        self.assertEqual(next_day.call_count, 0)

    @mock.patch.object(tasks.TaskRelation, "PredecessorTask")
    @mock.patch.object(tasks.workday, "next_day", autospec=True)
    def test_getEarlyStart_no_reltype(self, next_day, PredecessorTask):
        "returns None if reltype is missing"
        taskrel = tasks.TaskRelation()
        self.assertIsNone(taskrel.getEarlyStart())
        self.assertEqual(next_day.call_count, 0)

    def test_checkTaskConstraints_OK(self):
        "no taskrel constraint violations - no error"
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        pred_v = taskrel.PredecessorTask.getTaskRelConstraintViolations
        succ_v = taskrel.SuccessorTask.getTaskRelConstraintViolations

        pred_v.return_value = []
        succ_v.return_value = []

        self.assertIsNone(tasks.TaskRelation.checkTaskConstraints(taskrel))

        pred_v.assert_called_once_with(taskrel)
        succ_v.assert_called_once_with(taskrel)

    def test_checkTaskConstraints_violated(self):
        "error if taskrel constraints are violated"
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        pred_v = taskrel.PredecessorTask.getTaskRelConstraintViolations
        succ_v = taskrel.SuccessorTask.getTaskRelConstraintViolations
        pred_v.return_value = ["P1", "P2"]
        succ_v.return_value = ["S1"]

        with self.assertRaises(tasks.util.ErrorMessage) as error:
            tasks.TaskRelation.checkTaskConstraints(taskrel)

        self.assertEqual(
            str(error.exception),
            "\n\n".join(["P1", "P2", "S1"]),
        )
        pred_v.assert_called_once_with(taskrel)
        succ_v.assert_called_once_with(taskrel)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_checkRelation_source_is_target(self, CDBMsg):
        "fails if source and target are the same task"
        taskrel = tasks.TaskRelation(
            cdb_project_id2="P",
            cdb_project_id="P",
            task_id2="T",
            task_id="T",
        )

        with self.assertRaises(tasks.ue.Exception):
            taskrel.checkRelation(None)

        CDBMsg.assert_called_once_with(
            CDBMsg.kFatal,
            "cdbpcs_taskrel_same_task",
        )
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 0)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(tasks.util, "get_label", autospec=True)
    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    @mock.patch.object(tasks, "ALLOWED_TASK_GROUP_DEPENDECIES", ["a", "b"])
    def test_checkRelation_group_successor_invalid(
        self, SuccessorTask, get_label, CDBMsg
    ):
        "fails if successor is group and reltype is not allowed"
        taskrel = tasks.TaskRelation(cdb_project_id2="P", rel_type="not allowed")
        SuccessorTask.is_group = 1

        with self.assertRaises(tasks.util.ErrorMessage):
            taskrel.checkRelation(None)

        get_label.assert_called_once_with("cdbpcs_task_group_rel_not_allowed")
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "just_a_replacement")
        CDBMsg.return_value.addReplacement.assert_has_calls(
            [
                mock.call(f"{get_label.return_value}"),
            ]
        )
        self.assertEqual(CDBMsg.return_value.addReplacement.call_count, 1)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery")
    @mock.patch.object(tasks.TaskRelation, "SuccessorTask")
    def test_checkRelation_reverse_exists(self, SuccessorTask, KeywordQuery, CDBMsg):
        "fails if a reverse relation between source and target already exists"
        taskrel = tasks.TaskRelation(cdb_project_id2="P")
        SuccessorTask.is_group = 0

        with self.assertRaises(tasks.ue.Exception):
            taskrel.checkRelation(None)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_taskrel_only_one")
        CDBMsg.return_value.addReplacement.assert_not_called()
        KeywordQuery.assert_called_once_with(
            cdb_project_id=taskrel.cdb_project_id2,
            task_id=taskrel.task_id2,
            cdb_project_id2=taskrel.cdb_project_id,
            task_id2=taskrel.task_id,
        )

    @mock.patch.object(tasks.TaskRelation, "ByKeys", return_value=None)
    def test_setOIDs_not_persistent(self, ByKeys):
        "does nothing if taskrel is not persistent yet"
        taskrel = tasks.TaskRelation()
        taskrel.Update = mock.MagicMock()
        self.assertIsNone(taskrel.setOIDs())
        ByKeys.assert_called_once_with(**taskrel)
        taskrel.Update.assert_not_called()

    @mock.patch.object(tasks.TaskRelation, "ByKeys")
    def test_setOIDs_no_update(self, ByKeys):
        "does nothing if persistent object is consistent with self"
        taskrel = tasks.TaskRelation(cross_project=1)
        obj = ByKeys.return_value = mock.MagicMock(
            pred_project_oid="PP",
            PredecessorProject=mock.MagicMock(cdb_object_id="PP"),
            succ_project_oid="SP",
            SuccessorProject=mock.MagicMock(cdb_object_id="SP"),
            pred_task_oid="PT",
            PredecessorTask=mock.MagicMock(cdb_object_id="PT"),
            succ_task_oid="ST",
            SuccessorTask=mock.MagicMock(cdb_object_id="ST"),
        )
        self.assertIsNone(taskrel.setOIDs())
        ByKeys.assert_called_once_with(**taskrel)
        obj.Update.assert_not_called()

    @mock.patch.object(tasks.TaskRelation, "ByKeys")
    def test_setOIDs_update(self, ByKeys):
        "fixes all inconsistencies"
        taskrel = tasks.TaskRelation()
        self.assertIsNone(taskrel.setOIDs())
        ByKeys.assert_called_once_with(**taskrel)
        obj = ByKeys.return_value
        obj.Update.assert_called_once_with(
            pred_project_oid=obj.PredecessorProject.cdb_object_id,
            succ_project_oid=obj.SuccessorProject.cdb_object_id,
            pred_task_oid=obj.PredecessorTask.cdb_object_id,
            succ_task_oid=obj.SuccessorTask.cdb_object_id,
            cross_project=1,
        )

    def test_isViolated(self):
        taskrel = tasks.TaskRelation(violation=815)
        self.assertEqual(taskrel.isViolated(), 815)

    @mock.patch.object(tasks, "operation", autospec=True)
    def test_createRelation(self, operation):
        self.assertEqual(
            tasks.TaskRelation.createRelation(foo="bar"), operation.return_value
        )
        operation.assert_called_once_with(
            tasks.kOperationNew,
            tasks.TaskRelation,
            foo="bar",
        )

    @mock.patch.object(tasks.TaskRelation, "KeywordQuery", return_value=["a", "b"])
    @mock.patch.object(tasks, "operation", autospec=True)
    def test_copyRelations(self, operation, KeywordQuery):
        self.assertIsNone(tasks.TaskRelation.copyRelations("old", "new"))
        KeywordQuery.assert_called_once_with(
            cdb_project_id="old",
            cdb_project_id2="old",
        )
        kwargs = {
            "cdb_project_id": "new",
            "cdb_project_id2": "new",
        }
        operation.assert_has_calls(
            [
                mock.call(tasks.kOperationCopy, "a", **kwargs),
                mock.call(tasks.kOperationCopy, "b", **kwargs),
            ]
        )
        self.assertEqual(operation.call_count, 2)

    @mock.patch.object(tasks.TaskRelation, "KeywordQuery", return_value=["a"])
    @mock.patch.object(tasks, "operation", autospec=True)
    def test_deleteRelations(self, operation, KeywordQuery):
        self.assertIsNone(tasks.TaskRelation.deleteRelations("foo"))
        KeywordQuery.assert_has_calls(
            [
                mock.call(cdb_project_id="foo"),
                mock.call(cdb_project_id2="foo"),
            ]
        )
        self.assertEqual(KeywordQuery.call_count, 2)
        operation.assert_has_calls(
            2
            * [
                mock.call(tasks.kOperationDelete, "a"),
            ]
        )
        self.assertEqual(operation.call_count, 2)

    @mock.patch.object(tasks.TaskRelationType, "composeTypes")
    def test_compose_no_rel(self, composeTypes):
        "does nothing if no relation between lhs and rhs exists"
        lhs = mock.MagicMock(spec=tasks.Task, SuccessorTask="foo")
        rhs = mock.MagicMock(spec=tasks.Task, PredecessorTask="bar")
        self.assertIsNone(tasks.TaskRelation.compose(lhs, rhs))
        composeTypes.assert_not_called()

    @mock.patch.object(tasks, "operation")
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery")
    @mock.patch.object(tasks.TaskRelationType, "composeTypes", return_value="AA")
    def test_compose_aa(self, composeTypes, KeywordQuery, operation):
        "does nothing if relationship is AA and..."
        successor = mock.MagicMock(ParentTask="foo")
        lhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            PredecessorTask=successor.ParentTask,
            SuccessorTask=successor,
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        rhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            PredecessorTask=successor,
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        self.assertIsNone(tasks.TaskRelation.compose(lhs, rhs))
        composeTypes.assert_called_once_with(lhs.rel_type, rhs.rel_type)
        KeywordQuery.assert_not_called()
        operation.assert_not_called()

    @mock.patch.object(tasks, "operation")
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery")
    @mock.patch.object(tasks.TaskRelationType, "composeTypes", return_value="EE")
    def test_compose_ee(self, composeTypes, KeywordQuery, operation):
        "does nothing if relationship is EE and..."
        successor = mock.MagicMock(ParentTask="foo")
        lhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            SuccessorTask=successor,
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        rhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            PredecessorTask=successor,
            SuccessorTask=successor.ParentTask,
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        self.assertIsNone(tasks.TaskRelation.compose(lhs, rhs))
        composeTypes.assert_called_once_with(lhs.rel_type, rhs.rel_type)
        KeywordQuery.assert_not_called()
        operation.assert_not_called()

    # does nothing if
    # composeTypes.return_value returns "AA" and lhs.PredecessorTask != lhs.SuccessorTask
    # composeTypes.return_value returns "EE" and rhs.SuccessorTask != lhs.SuccessorTask

    @mock.patch.object(tasks, "operation")
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery")
    @mock.patch.object(tasks.TaskRelationType, "composeTypes")
    def test_compose_exists(self, composeTypes, KeywordQuery, operation):
        "does nothing if relationship exists already"
        lhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            SuccessorTask="foo",
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        rhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            PredecessorTask="foo",
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        self.assertIsNone(tasks.TaskRelation.compose(lhs, rhs))
        composeTypes.assert_called_once_with(lhs.rel_type, rhs.rel_type)
        KeywordQuery.assert_called_once_with(
            cdb_project_id=rhs.cdb_project_id,
            cdb_project_id2=lhs.cdb_project_id,
            task_id2=lhs.task_id2,
            task_id=rhs.task_id,
        )
        operation.assert_not_called()

    @mock.patch.object(tasks, "operation")
    @mock.patch.object(tasks.TaskRelation, "KeywordQuery", return_value=None)
    @mock.patch.object(tasks.TaskRelationType, "composeTypes")
    def test_compose(self, composeTypes, KeywordQuery, operation):
        "creates relationship if it doesn't exist yet"
        lhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            SuccessorTask="foo",
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        rhs = mock.MagicMock(
            spec=tasks.TaskRelation,
            PredecessorTask="foo",
            cdb_project_id="p1",
            cdb_project_id2="p1",
        )
        self.assertIsNone(tasks.TaskRelation.compose(lhs, rhs))
        composeTypes.assert_called_once_with(lhs.rel_type, rhs.rel_type)
        KeywordQuery.assert_called_once_with(
            cdb_project_id=rhs.cdb_project_id,
            cdb_project_id2=lhs.cdb_project_id,
            task_id2=lhs.task_id2,
            task_id=rhs.task_id,
        )
        operation.assert_called_once_with(
            tasks.kOperationNew,
            tasks.TaskRelation,
            name="",
            cdb_project_id=rhs.cdb_project_id,
            cdb_project_id2=lhs.cdb_project_id,
            task_id2=lhs.task_id2,
            task_id=rhs.task_id,
            rel_type=composeTypes.return_value,
        )

    def test_get_all_subtask_ids_called_without_task_id_no_mock(self):
        "get all subtasks for given task: without task id, no mock"
        self.assertEqual(
            [], tasks.Task._get_all_subtask_ids(cdb_project_id="foo_project")
        )

    def test_get_all_subtask_ids_called_with_task_id_no_mock(self):
        "get all subtasks for given task: with task id, no mock"
        self.assertEqual(
            [],
            tasks.Task._get_all_subtask_ids(
                cdb_project_id="foo_project", task_id="foo_task"
            ),
        )

    @mock.patch.object(tasks.sqlapi, "SQLdbms", return_value=1)
    def test_get_all_subtask_ids_called_without_task_id(self, SQLdbms):
        "get all subtasks for given task: called without task id"
        task = mock.MagicMock(spec=tasks.Task, cdb_project_id="foo", task_id="bass")
        with mock.patch.object(tasks.sqlapi, "RecordSet2", return_value=[task]):
            result = tasks.Task._get_all_subtask_ids(
                cdb_project_id="foo_project", task_id=""
            )
            tasks.sqlapi.RecordSet2.assert_called_once()
            self.assertEqual(result, ["bass"])
        SQLdbms.assert_called_once_with()

    @mock.patch.object(tasks.sqlapi, "SQLdbms", return_value=1)
    def test_get_all_subtask_ids_called_with_task_id(self, SQLdbms):
        "get all subtasks for given task: called with task id"
        task = mock.MagicMock(spec=tasks.Task, cdb_project_id="foo", task_id="bass")
        with mock.patch.object(tasks.sqlapi, "RecordSet2", return_value=[task]):
            result = tasks.Task._get_all_subtask_ids(
                cdb_project_id="foo_project", task_id="foo_task"
            )
            tasks.sqlapi.RecordSet2.assert_called_once()
            self.assertEqual(result, ["bass"])
        SQLdbms.assert_called_once_with()

    @mock.patch.object(tasks.Task, "_get_all_subtask_ids", return_value=[])
    def test_check_task_rel_parent_cycles_without_cycle(self, _get_all_subtask_ids):
        "check for parent cycles: cycle does not exists"
        self.assertIsNone(
            tasks.Task._check_task_rel_parent_cycles(
                "foo_project_id", ("pred_task_id", "succ_task_id", "foo_rel")
            ),
        )
        _get_all_subtask_ids.assert_has_calls(
            [
                mock.call(cdb_project_id="foo_project_id", task_id="succ_task_id"),
                mock.call(cdb_project_id="foo_project_id", task_id="pred_task_id"),
            ]
        )

    @mock.patch.object(
        tasks.Task, "_get_all_subtask_ids", return_value=["succ_task_id"]
    )
    def test_check_task_rel_parent_cycles_with_cycle(self, _get_all_subtask_ids):
        "check for parent cycles: cycle exists"
        self.assertEqual(
            "parent circle found",
            tasks.Task._check_task_rel_parent_cycles(
                "foo_project_id", ("pred_task_id", "succ_task_id", "foo_rel")
            ),
        )
        _get_all_subtask_ids.assert_has_calls(
            [
                mock.call(cdb_project_id="foo_project_id", task_id="succ_task_id"),
                mock.call(cdb_project_id="foo_project_id", task_id="pred_task_id"),
            ]
        )

    @mock.patch.object(tasks.Task, "_check_task_rel_cycles")
    def test_check_for_taskrel_cycles_cross_proj(self, _check_task_rel_cycles):
        "does nothing for cross-project relationships"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="bar",
        )
        self.assertIsNone(
            tasks.TaskRelation.check_for_taskrel_cycles(taskrel, None),
        )
        _check_task_rel_cycles.assert_not_called()

    def _check_cycle_calls(self, taskrel, _check1, _check2, _check3):
        _check1.assert_called_once_with(
            taskrel.cdb_project_id,
            (taskrel.task_id2, taskrel.task_id, taskrel.rel_type),
        )
        _check2.assert_called_once_with(
            taskrel.cdb_project_id,
            (taskrel.task_id2, taskrel.task_id, taskrel.rel_type),
        )
        _check3.assert_called_once_with(
            taskrel.cdb_project_id,
            (taskrel.task_id2, taskrel.task_id, taskrel.rel_type),
        )

    @mock.patch.object(tasks.Task, "_check_task_rel_parent_cycles")
    @mock.patch.object(tasks.Task, "_check_task_rel_special_case")
    @mock.patch.object(tasks.Task, "_check_task_rel_cycles")
    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def _taskrel_cycle_detected(self, cycles, CDBMsg, _check1, _check2, _check3):
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )

        for check, result in zip([_check1, _check2, _check3], cycles):
            check.return_value = result

        with self.assertRaises(tasks.AbortMessage):
            tasks.TaskRelation.check_for_taskrel_cycles(taskrel, None)

        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_taskrel_cycle")
        CDBMsg.return_value.addReplacement.assert_not_called()

        self._check_cycle_calls(taskrel, _check1, _check2, _check3)

    def test_check_for_taskrel_cycles_111(self):
        "fails if all cycles detected"
        self._taskrel_cycle_detected([True, True, True])

    def test_check_for_taskrel_cycles_110(self):
        "fails if cycle and special cycle detected"
        self._taskrel_cycle_detected([True, True, False])

    def test_check_for_taskrel_cycles_101(self):
        "fails if cycle and parent cycle detected"
        self._taskrel_cycle_detected([True, False, True])

    def test_check_for_taskrel_cycles_100(self):
        "fails if cycle detected"
        self._taskrel_cycle_detected([True, False, False])

    def test_check_for_taskrel_cycles_011(self):
        "fails if special and parent cycle detected"
        self._taskrel_cycle_detected([False, True, True])

    def test_check_for_taskrel_cycles_010(self):
        "fails if special cycle detected"
        self._taskrel_cycle_detected([False, True, False])

    def test_check_for_taskrel_cycles_001(self):
        "fails if parent cycle detected"
        self._taskrel_cycle_detected([False, False, True])

    @mock.patch.object(tasks.Task, "_check_task_rel_parent_cycles", return_value=False)
    @mock.patch.object(tasks.Task, "_check_task_rel_special_case", return_value=False)
    @mock.patch.object(tasks.Task, "_check_task_rel_cycles", return_value=False)
    def test_check_for_taskrel_cycles(self, _check1, _check2, _check3):
        "does nothing if no cycle is detected"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        self.assertIsNone(
            tasks.TaskRelation.check_for_taskrel_cycles(taskrel, None),
        )
        self._check_cycle_calls(taskrel, _check1, _check2, _check3)

    def _fill_oid_fields(self, attrs, empty, ByKeys):
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        ctx = mock.MagicMock()
        ctx.dialog.get_attribute_names.return_value = attrs
        setattr(ctx.dialog, empty, None)
        self.assertIsNone(tasks.TaskRelation._fill_oid_fields(taskrel, ctx))
        ctx.dialog.get_attribute_names.assert_called_once_with()
        ctx.set.assert_called_once_with(
            empty,
            ByKeys.return_value.cdb_object_id,
        )
        return ctx

    @mock.patch.object(tasks.Project, "ByKeys")
    def test__fill_oid_fields_pp(self, ProjectByKeys):
        "sets OID of predecessor project"
        ctx = self._fill_oid_fields(
            [
                "cdb_project_id2",
                "ce_baseline_id",
                "pred_project_oid",
            ],
            "pred_project_oid",
            ProjectByKeys,
        )
        ProjectByKeys.assert_called_once_with(cdb_project_id=ctx.dialog.cdb_project_id2)

    @mock.patch.object(tasks.Task, "ByKeys")
    def test__fill_oid_fields_pt(self, TaskByKeys):
        "sets OID of predecessor task"
        ctx = self._fill_oid_fields(
            [
                "cdb_project_id2",
                "task_id2",
                "ce_baseline_id",
                "pred_task_oid",
            ],
            "pred_task_oid",
            TaskByKeys,
        )
        TaskByKeys.assert_called_once_with(
            cdb_project_id=ctx.dialog.cdb_project_id2,
            task_id=ctx.dialog.task_id2,
        )

    @mock.patch.object(tasks.Project, "ByKeys")
    def test__fill_oid_fields_sp(self, ProjectByKeys):
        "sets OID of successor project"
        ctx = self._fill_oid_fields(
            [
                "cdb_project_id",
                "ce_baseline_id",
                "succ_project_oid",
            ],
            "succ_project_oid",
            ProjectByKeys,
        )
        ProjectByKeys.assert_called_once_with(cdb_project_id=ctx.dialog.cdb_project_id)

    @mock.patch.object(tasks.Task, "ByKeys")
    def test__fill_oid_fields_st(self, TaskByKeys):
        "sets OID of successor task"
        ctx = self._fill_oid_fields(
            [
                "cdb_project_id",
                "task_id",
                "ce_baseline_id",
                "succ_task_oid",
            ],
            "succ_task_oid",
            TaskByKeys,
        )
        TaskByKeys.assert_called_once_with(
            cdb_project_id=ctx.dialog.cdb_project_id,
            task_id=ctx.dialog.task_id,
        )

    def test_checkStructureLock_no_pid(self):
        "does nothing if no project ID given"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id=None,
        )
        self.assertIsNone(
            tasks.TaskRelation.checkStructureLock(taskrel, "ctx"),
        )
        taskrel.PredecessorProject.checkStructureLock.assert_not_called()

    def test_checkStructureLock_cross_proj(self):
        "does nothing for cross-project relship"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="bar",
        )
        self.assertIsNone(
            tasks.TaskRelation.checkStructureLock(taskrel, "ctx"),
        )
        taskrel.PredecessorProject.checkStructureLock.assert_not_called()

    def test_checkStructureLock(self):
        "checks predecessor project's structure lock"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        self.assertIsNone(
            tasks.TaskRelation.checkStructureLock(taskrel, "ctx"),
        )
        taskrel.PredecessorProject.checkStructureLock.assert_called_once_with(
            ctx="ctx",
        )

    def test_adjustSuccessorStatus_error(self):
        "does nothing if ctx.error is truthy"
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks.TaskRelation.adjustSuccessorStatus(taskrel, ctx),
        )
        taskrel.PredecessorTask.adjustSuccessorStatus.assert_not_called()

    def test_adjustSuccessorStatus(self):
        "calls predecessor task's method"
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        ctx = mock.MagicMock(error=None)
        self.assertIsNone(
            tasks.TaskRelation.adjustSuccessorStatus(taskrel, ctx),
        )
        taskrel.PredecessorTask.adjustSuccessorStatus.assert_called_once_with()

    @mock.patch.object(
        tasks.Task, "MakeChangeControlAttributes", return_value={"a": "B"}
    )
    @mock.patch.object(
        tasks.Project,
        "MakeChangeControlAttributes",
        return_value={
            "cdb_mdate": "foo",
            "cdb_mpersno": "bar",
        },
    )
    def test_recalculate_create_same_project(self, ProjAttrs, TaskAttrs):
        "updates project if predecessor and sucessor are in the same project for action 'create'"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        # Predecessor and Successor project are the same
        mock_project = mock.MagicMock()
        taskrel.PredecessorProject = mock_project
        taskrel.SuccessorProject = mock_project
        ctx = mock.MagicMock(action="create")

        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_called_once_with()
        ProjAttrs.assert_called_once_with()

        taskrel.SuccessorTask.Update.assert_called_once_with(a="B")
        taskrel.PredecessorTask.Update.assert_called_once_with(a="B")

        mock_project.recalculate.assert_called_once_with()
        mock_project.Update.assert_called_once_with(
            cdb_mdate="foo",
            cdb_mpersno="bar",
        )

    @mock.patch.object(
        tasks.Task, "MakeChangeControlAttributes", return_value={"a": "B"}
    )
    @mock.patch.object(tasks.Project, "MakeChangeControlAttributes")
    def test_recalculate_create_across_projects(self, ProjAttrs, TaskAttrs):
        "does not update project if predecessor and sucessor are in different projects for action 'create'"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo2",
        )

        ctx = mock.MagicMock(action="create")

        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_called_once_with()
        ProjAttrs.assert_not_called()

        taskrel.SuccessorTask.Update.assert_called_once_with(a="B")
        taskrel.PredecessorTask.Update.assert_called_once_with(a="B")

        taskrel.PredecessorProject.recalculate.assert_not_called()
        taskrel.PredecessorProject.Update.assert_not_called()
        taskrel.SuccessorProject.recalculate.assert_not_called()
        taskrel.SuccessorProject.Update.assert_not_called()

    @mock.patch.object(
        tasks.Task, "MakeChangeControlAttributes", return_value={"a": "B"}
    )
    @mock.patch.object(
        tasks.Project,
        "MakeChangeControlAttributes",
        return_value={
            "cdb_mdate": "foo",
            "cdb_mpersno": "bar",
        },
    )
    def test_recalculate_delete_same_project(self, ProjAttrs, TaskAttrs):
        "updates project if predecessor and sucessor are in the same project for action 'delete'"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        # Predecessor and Successor project are the same
        mock_project = mock.MagicMock()
        taskrel.PredecessorProject = mock_project
        taskrel.SuccessorProject = mock_project
        ctx = mock.MagicMock(action="delete")
        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_called_once_with()
        ProjAttrs.assert_called_once_with()

        taskrel.SuccessorTask.Update.assert_called_once_with(a="B")
        taskrel.PredecessorTask.Update.assert_called_once_with(a="B")

        mock_project.recalculate.assert_called_once_with()
        mock_project.Update.assert_called_once_with(
            cdb_mdate="foo",
            cdb_mpersno="bar",
        )

    @mock.patch.object(
        tasks.Task, "MakeChangeControlAttributes", return_value={"a": "B"}
    )
    @mock.patch.object(tasks.Project, "MakeChangeControlAttributes")
    def test_recalculate_delete_across_projects(self, ProjAttrs, TaskAttrs):
        "does not update project if predecessor and sucessor are in different projects for action 'delete'"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo2",
        )

        ctx = mock.MagicMock(action="delete")

        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_called_once_with()
        ProjAttrs.assert_not_called()

        taskrel.SuccessorTask.Update.assert_called_once_with(a="B")
        taskrel.PredecessorTask.Update.assert_called_once_with(a="B")

        taskrel.PredecessorProject.recalculate.assert_not_called()
        taskrel.PredecessorProject.Update.assert_not_called()
        taskrel.SuccessorProject.recalculate.assert_not_called()
        taskrel.SuccessorProject.Update.assert_not_called()

    @mock.patch.object(tasks.Task, "MakeChangeControlAttributes")
    @mock.patch.object(
        tasks.Project,
        "MakeChangeControlAttributes",
        return_value={
            "cdb_mdate": "foo",
            "cdb_mpersno": "bar",
        },
    )
    def test_recalculate_others_same_project(self, ProjAttrs, TaskAttrs):
        "updates project if predecessor and sucessor are in the same project for other actions"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        # Predecessor and Successor project are the same
        mock_project = mock.MagicMock()
        taskrel.PredecessorProject = mock_project
        taskrel.SuccessorProject = mock_project
        ctx = mock.MagicMock(action=None)

        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_not_called()
        ProjAttrs.assert_called_once_with()

        mock_project.recalculate.assert_called_once_with()
        mock_project.Update.assert_called_once_with(
            cdb_mdate="foo",
            cdb_mpersno="bar",
        )

    @mock.patch.object(tasks.Task, "MakeChangeControlAttributes")
    @mock.patch.object(tasks.Project, "MakeChangeControlAttributes")
    def test_recalculate_others_across_projects(self, ProjAttrs, TaskAttrs):
        "does not update project if predecessor and sucessor are in different projects for other actions"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo2",
        )

        ctx = mock.MagicMock(action=None)

        self.assertIsNone(
            tasks.TaskRelation.recalculate(taskrel, ctx),
        )
        TaskAttrs.assert_not_called()
        ProjAttrs.assert_not_called()

        taskrel.PredecessorProject.recalculate.assert_not_called()
        taskrel.PredecessorProject.Update.assert_not_called()
        taskrel.SuccessorProject.recalculate.assert_not_called()
        taskrel.SuccessorProject.Update.assert_not_called()

    def test_recalculate_no_ctx(self):
        "hard-fails if no ctx is given"
        taskrel = mock.MagicMock(spec=tasks.TaskRelation)
        with self.assertRaises(AttributeError) as error:
            tasks.TaskRelation.recalculate(taskrel)

        self.assertEqual(
            str(error.exception), "'NoneType' object has no attribute 'action'"
        )

    def test_set_violation_across_project_same_project(self):
        "does nothing if predecessor and successor project are the same"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo",
        )
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks.TaskRelation.set_violation_cross_project(taskrel, ctx),
        )
        ctx.set.assert_not_called()

    @mock.patch.object(relships, "calculate_relship_gap")
    def test_set_violation_accross_project(self, calculate_relship_gap):
        "set violation if predecessor and successor project are different"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            cdb_project_id="foo",
            cdb_project_id2="foo2",
            minimal_gap=2,
        )
        calculate_relship_gap.return_value = 1
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks.TaskRelation.set_violation_cross_project(taskrel, ctx),
        )
        # Expect violation=1 since minimal_gap > actual gap
        ctx.set.assert_called_once_with("violation", 1)
        calculate_relship_gap.assert_called_once()

    @mock.patch.object(tasks.Project, "KeywordQuery", return_value=[1, 2])
    def test_is_task_selection_enabled_true(self, ProjectQuery):
        "true if more projects than constant exist"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            NUMBER_OF_PROJECTS_FOR_SETTING_TASK_SELECTION_READONLY=1,
        )
        self.assertEqual(
            tasks.TaskRelation.is_task_selection_enabled.__get__(taskrel), True
        )
        ProjectQuery.assert_called_once_with(ce_baseline_id="")

    @mock.patch.object(tasks.Project, "KeywordQuery", return_value=[])
    def test_is_task_selection_enabled_false(self, ProjectQuery):
        "false if less projects than constant exist"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            NUMBER_OF_PROJECTS_FOR_SETTING_TASK_SELECTION_READONLY=1,
        )
        self.assertEqual(
            tasks.TaskRelation.is_task_selection_enabled.__get__(taskrel), False
        )
        ProjectQuery.assert_called_once_with(ce_baseline_id="")

    def test_set_task_selection_readonly_disabled(self):
        "does nothing if task selection is disabled"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            is_task_selection_enabled=False,
            _ATTRIBUTES_FOR_TASK_SELECTION_READONLY={"foo": "bar"},
        )
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks.TaskRelation.set_task_selection_readonly(taskrel, ctx),
        )
        ctx.set_fields_readonly.assert_not_called()

    def test_set_task_selection_readonly(self):
        "sets changed field readonly if no value exists"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            is_task_selection_enabled=True,
            _ATTRIBUTES_FOR_TASK_SELECTION_READONLY={
                1: "foo",
                2: "bar",
            },
        )
        ctx = mock.MagicMock(changed_item="foo")
        self.assertIsNone(
            tasks.TaskRelation.set_task_selection_readonly(taskrel, ctx),
        )
        ctx.set_fields_readonly.assert_has_calls(
            [
                mock.call(["foo"]),
                mock.call(["bar"]),
            ]
        )
        self.assertEqual(ctx.set_fields_readonly.call_count, 2)

    def test_set_task_selection_false(self):
        "does nothing if task selection is disabled"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            is_task_selection_enabled=False,
            _ATTRIBUTES_FOR_TASK_SELECTION_READONLY={"foo": "bar"},
        )
        ctx = mock.MagicMock()
        self.assertIsNone(
            tasks.TaskRelation.set_task_selection(taskrel, ctx),
        )
        ctx.set_fields_writeable.assert_not_called()
        ctx.set_fields_readonly.assert_not_called()

    def test_set_task_selection_no_value(self):
        "sets changed field readonly if no value exists"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            is_task_selection_enabled=True,
            _ATTRIBUTES_FOR_TASK_SELECTION_READONLY={"foo": "bar"},
            foo=None,
        )
        ctx = mock.MagicMock(changed_item="foo")
        self.assertIsNone(
            tasks.TaskRelation.set_task_selection(taskrel, ctx),
        )
        ctx.set_fields_writeable.assert_not_called()
        ctx.set_fields_readonly.assert_called_once_with(["bar"])

    def test_set_task_selection(self):
        "sets changed field writable if value exists"
        taskrel = mock.MagicMock(
            spec=tasks.TaskRelation,
            is_task_selection_enabled=True,
            _ATTRIBUTES_FOR_TASK_SELECTION_READONLY={"foo": "bar"},
            foo="Foo!",
        )
        ctx = mock.MagicMock(changed_item="foo")
        self.assertIsNone(
            tasks.TaskRelation.set_task_selection(taskrel, ctx),
        )
        ctx.set_fields_writeable.assert_called_once_with(["bar"])
        ctx.set_fields_readonly.assert_not_called()

    @mock.patch.object(tasks.Task, "accept_new_parent_task")
    @mock.patch.object(tasks.Task, "accept_new_task")
    def test_check_for_valid_parent_1(self, *args):
        "Task.check_for_valid_parent: parent task, create action"
        task = tasks.Task()
        task.parent_task = "foo"
        parent = tasks.Task()
        ctx = mock.MagicMock(action="create")
        task.check_for_valid_parent(ctx, parent)
        task.accept_new_parent_task.assert_not_called()
        parent.accept_new_task.assert_called_once_with()

    @mock.patch.object(tasks.Task, "accept_new_parent_task")
    @mock.patch.object(tasks.Task, "accept_new_task")
    def test_check_for_valid_parent_2(self, *args):
        "Task.check_for_valid_parent: parent task, copy action"
        task = tasks.Task()
        task.parent_task = "foo"
        parent = tasks.Task()
        ctx = mock.MagicMock(action="copy")
        task.check_for_valid_parent(ctx, parent)
        task.accept_new_parent_task.assert_not_called()
        parent.accept_new_task.assert_called_once_with()

    @mock.patch.object(tasks.Task, "accept_new_parent_task")
    @mock.patch.object(tasks.Task, "accept_new_task")
    def test_check_for_valid_parent_3(self, *args):
        "Task.check_for_valid_parent: parent task, modify action, changes"
        task = tasks.Task()
        task.parent_task = "foo"
        parent = tasks.Task()
        ctx = mock.MagicMock(action="modify")
        ctx.object.parent_task = "foo"
        task.check_for_valid_parent(ctx, parent)
        task.accept_new_parent_task.assert_not_called()
        parent.accept_new_task.assert_not_called()

    @mock.patch.object(tasks.Task, "accept_new_parent_task")
    @mock.patch.object(tasks.Task, "accept_new_task")
    def test_check_for_valid_parent_4(self, *args):
        "Task.check_for_valid_parent: parent task, modify action, no changes"
        task = tasks.Task()
        task.parent_task = "foo"
        parent = tasks.Task()
        ctx = mock.MagicMock(action="modify")
        ctx.object.parent_task = "bar"
        task.check_for_valid_parent(ctx, parent)
        task.accept_new_parent_task.assert_called_once_with(parent)
        parent.accept_new_task.assert_called_once_with()


@mock.patch.object(tasks.util, "get_label", side_effect=lambda x: x)
def test_getTypeLabels(_):
    assert tasks.TaskRelationType.getTypeLabels() == {
        "AA": "web.timeschedule.taskrel-AA",
        "AE": "web.timeschedule.taskrel-AE",
        "EA": "web.timeschedule.taskrel-EA",
        "EE": "web.timeschedule.taskrel-EE",
    }


@pytest.mark.unit
def test_CriticalPath():
    unittest.skip("already removed in 15.4.4")


if __name__ == "__main__":
    unittest.main()
