#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=too-many-lines

import datetime
import unittest
from collections import OrderedDict, defaultdict

import mock
import pytest
from cdb import ElementsError, sqlapi, testcase, util
from cdb.classbody import classbody
from cdb.constants import kOperationCopy, kOperationModify, kOperationNew
from cdb.objects import ByID
from cdb.objects.operations import SimpleArguments, operation
from cdb.objects.org import Person
from cs.actions import Action
from cs.calendar import CalendarProfile
from cs.platform.web.root import Root
from cs.taskboard import internal
from cs.taskboard.interfaces import BoardAdapter
from cs.taskboard.internal import _change_card, _change_cards, adjust_new_card_on_board
from cs.taskboard.interval_board import INTERVAL_BOARD_TYPE
from cs.taskboard.objects import Board, get_personal_board
from cs.taskboard.sprint_board import SPRINT_BOARD_TYPE
from webtest import TestApp as Client

from cs.pcs.issues import Issue
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.taskboards.tests.integration import util as test_util

CALLS = 0


class Request:
    def __init__(self, **kwargs):
        self.json = defaultdict(str, **kwargs)
        self.link = lambda *args, **kwargs: None
        self.view = lambda *args, **kwargs: None
        self.app = mock.Mock()
        self.app.root = "https://www.example.org"
        self.params = {}


@classbody
class BoardAdapter:
    def update_board_test(self):
        # pylint: disable=global-statement
        global CALLS
        CALLS += 1
        self.update_board_backup()


class UpdateCount:
    def __enter__(self):
        # pylint: disable=global-statement
        global CALLS
        CALLS = 0
        BoardAdapter.update_board_backup = BoardAdapter.update_board
        BoardAdapter.update_board = BoardAdapter.update_board_test

    def __exit__(self, exception_type, exception_value, traceback):
        BoardAdapter.update_board = BoardAdapter.update_board_backup


def setUpModule():
    testcase.run_level_setup()


class TestBoards(testcase.RollbackTestCase):
    number_of_tasks = 1
    test_date = datetime.date(2020, 5, 15)

    def _setup_project(self, no=None):
        cal = CalendarProfile.KeywordQuery(name="Standard")[0]
        self.project = operation(
            kOperationNew,
            Project,
            cdb_project_id="#1",
            ce_baseline_id="",
            project_name="project name",
            calendar_profile_id=cal.cdb_object_id,
        )
        if no is None:
            no = self.number_of_tasks
        for i in range(0, no):
            current_task = self.create_task(i)
            setattr(self, f"task_{i}", current_task)

    def copy_project(self):
        self.project_copy = operation(
            kOperationCopy, self.project, cdb_project_id="#2", ce_baseline_id=""
        )

    def create_task(self, i, **kwargs):
        args = {}
        args.update(
            cdb_project_id=self.project.cdb_project_id,
            task_id=f"task_id_{i}",
            ce_baseline_id=self.project.ce_baseline_id,
            task_name=f"task_name_{i}",
            subject_id="caddok",
            subject_type="Person",
            constraint_type="0",
            parent_task="",
        )
        args.update(**kwargs)
        return operation(kOperationNew, Task, **args)

    def create_issue(self, i, **kwargs):
        args = {}
        args.update(
            cdb_project_id=self.project.cdb_project_id,
            issue_id=10000 + i,
            task_id="",
            issue_name=f"issue_name_{i}",
            subject_id="caddok",
            subject_type="Person",
        )
        args.update(**kwargs)
        return operation(kOperationNew, Issue, **args)

    def copy_task(self, task):
        i = 1 + len(self.project.Tasks)
        return operation(
            kOperationCopy,
            task,
            cdb_project_id=self.project.cdb_project_id,
            ce_baseline_id="",
            task_name=f"Task name {i}",
        )

    def create_taskrelation(self, task1, task2, rel_type):
        return operation(
            kOperationNew,
            TaskRelation,
            cdb_project_id2=task1.cdb_project_id,
            task_id2=task1.task_id,
            cdb_project_id=task2.cdb_project_id,
            task_id=task2.task_id,
            rel_type=rel_type,
        )

    def create_issue(self, i, **kwargs):
        args = {}
        args.update(
            cdb_project_id=self.project.cdb_project_id,
            task_id="",
            issue_name=f"Issue name {i}",
            subject_id="caddok",
            subject_type="Person",
        )
        args.update(**kwargs)
        return operation(kOperationNew, Issue, **args)

    def create_action(self, i, **kwargs):
        args = {}
        args.update(
            cdb_project_id=self.project.cdb_project_id,
            task_id="",
            name=f"Action name {i}",
            subject_id="caddok",
            subject_type="Person",
        )
        args.update(**kwargs)
        return operation(kOperationNew, Action, **args)

    def create_taskboard(self, context_object, board_type, **kwargs):
        board_tmpl = Board.KeywordQuery(
            board_type=board_type, is_template=True, available=True
        )
        if not board_tmpl:
            return None
        op_args = {}
        op_args.update(interval_type=2, interval_length=2, start_date=self.test_date)
        op_args.update(**kwargs)
        operation(
            "cs_taskboard_create_board",
            context_object,
            SimpleArguments(template_object_id=board_tmpl[0].cdb_object_id, **op_args),
        )
        context_object.Taskboard.updateBoard()
        return context_object.Taskboard

    def check_access_rights(self, obj, user):
        create = obj.CheckAccess("create", user.personalnummer)
        read = obj.CheckAccess("read", user.personalnummer)
        save = obj.CheckAccess("save", user.personalnummer)
        delete = obj.CheckAccess("delete", user.personalnummer)
        return create, read, save, delete


# INTERVAL BOARDS


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestIntervalBoard(TestBoards):
    def test_board_on_project_by_project_leader(self):
        "Create an Interval Board on project by project leader."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )
        test_util.assign_user_project_role(user, self.project, role_id="Projektleiter")

        board_1 = self.create_taskboard(self.project, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project leader.")
        self.assertTrue(r, "Taskboard should be readable by project leader.")
        self.assertTrue(s, "Taskboard should be modifiable by project leader.")
        self.assertTrue(d, "Taskboard should be deletable by project leader.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Interval should be creatable by project leader.")
        self.assertTrue(r, "Interval should be readable by project leader.")
        self.assertTrue(s, "Interval should be modifiable by project leader.")
        self.assertTrue(d, "Interval should be deletable by project leader.")

    def test_board_on_task_by_project_leader(self):
        "Create an Interval Board on task by project leader."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )
        test_util.assign_user_project_role(user, self.project, role_id="Projektleiter")

        board_1 = self.create_taskboard(task, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project leader.")
        self.assertTrue(r, "Taskboard should be readable by project leader.")
        self.assertTrue(s, "Taskboard should be modifiable by project leader.")
        self.assertTrue(d, "Taskboard should be deletable by project leader.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Interval should be creatable by project leader.")
        self.assertTrue(r, "Interval should be readable by project leader.")
        self.assertTrue(s, "Interval should be modifiable by project leader.")
        self.assertTrue(d, "Interval should be deletable by project leader.")

    def test_board_on_project_by_project_member(self):
        "Create an Interval Board on project by project member."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )

        board_1 = self.create_taskboard(self.project, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by project member.")
        self.assertTrue(r, "Taskboard should be readable by project member.")
        self.assertFalse(s, "Taskboard should not be modifiable by project member.")
        self.assertFalse(d, "Taskboard should not be deletable by project member.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should not be creatable by project member.")
        self.assertTrue(r, "Interval should be readable by project member.")
        self.assertFalse(s, "Interval should not be modifiable by project member.")
        self.assertFalse(d, "Interval should not be deletable by project member.")

    def test_board_on_task_by_project_member(self):
        "Create an Interval Board on task by project member."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )

        board_1 = self.create_taskboard(task, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project member.")
        self.assertTrue(r, "Taskboard should be readable by project member.")
        self.assertTrue(s, "Taskboard should be modifiable by project member.")
        self.assertTrue(d, "Taskboard should be deletable by project member.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Interval should be creatable by project member.")
        self.assertTrue(r, "Interval should be readable by project member.")
        self.assertTrue(s, "Interval should be modifiable by project member.")
        self.assertTrue(d, "Interval should be deletable by project member.")

    def test_board_on_project_by_teamboard_manager(self):
        "Create an Interval Board on project by Teamboard Manager."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Teamboard Manager")

        board_1 = self.create_taskboard(self.project, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Taskboard should be readable by Teamboard Manager.")
        self.assertFalse(s, "Taskboard should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Taskboard should not be deletable by Teamboard Manager.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should be creatable by Teamboard Manager.")
        self.assertTrue(r, "Interval should be readable by Teamboard Manager.")
        self.assertFalse(s, "Interval should be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Interval should be deletable by Teamboard Manager.")

    def test_board_on_task_by_teamboard_manager(self):
        "Create an Interval Board on task by Teamboard Manager."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Teamboard Manager")

        board_1 = self.create_taskboard(task, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Taskboard should be readable by Teamboard Manager.")
        self.assertFalse(s, "Taskboard should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Taskboard should not be deletable by Teamboard Manager.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Interval should be readable by Teamboard Manager.")
        self.assertFalse(s, "Interval should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Interval should not be deletable by Teamboard Manager.")

    def test_board_on_project_by_taskboard_administrator(self):
        "Create an Interval Board on project by Taskboard Administrator."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Taskboard Administrator")

        board_1 = self.create_taskboard(self.project, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(
            c, "Taskboard should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Taskboard should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Taskboard should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Taskboard should not be deletable by Taskboard Administrator."
        )

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should be creatable by Taskboard Administrator.")
        self.assertTrue(r, "Interval should be readable by Taskboard Administrator.")
        self.assertFalse(s, "Interval should be modifiable by Taskboard Administrator.")
        self.assertFalse(d, "Interval should be deletable by Taskboard Administrator.")

    def test_board_on_task_by_taskboard_administrator(self):
        "Create an Interval Board on task by Taskboard Administrator."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Taskboard Administrator")

        board_1 = self.create_taskboard(task, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(
            c, "Taskboard should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Taskboard should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Taskboard should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Taskboard should not be deletable by Taskboard Administrator."
        )

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(
            c, "Interval should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Interval should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Interval should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Interval should not be deletable by Taskboard Administrator."
        )

    def test_board_on_project_by_public_user(self):
        "Create an Interval Board on project by public user."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)

        board_1 = self.create_taskboard(self.project, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by public user.")
        self.assertTrue(r, "Taskboard should be readable by public user.")
        self.assertFalse(s, "Taskboard should not be modifiable by public user.")
        self.assertFalse(d, "Taskboard should not be deletable by public user.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should be creatable by public user.")
        self.assertTrue(r, "Interval should be readable by public user.")
        self.assertFalse(s, "Interval should be modifiable by public user.")
        self.assertFalse(d, "Interval should be deletable by public user.")

    def test_board_on_task_by_public_user(self):
        "Create an Interval Board on task by public user."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)

        board_1 = self.create_taskboard(task, INTERVAL_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by public user.")
        self.assertTrue(r, "Taskboard should be readable by public user.")
        self.assertFalse(s, "Taskboard should not be modifiable by public user.")
        self.assertFalse(d, "Taskboard should not be deletable by public user.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Interval should not be creatable by public user.")
        self.assertTrue(r, "Interval should be readable by public user.")
        self.assertFalse(s, "Interval should not be modifiable by public user.")
        self.assertFalse(d, "Interval should not be deletable by public user.")

    def prepare_data(self, no):
        self._setup_project(no)
        operation(
            kOperationModify,
            self.project,
            start_time_fcast="17.09.2018",
            end_time_fcast="25.09.2018",
            days_fcast=7,
        )
        if len(self.project.Tasks):
            self.task = self.project.Tasks[0]
            operation(
                kOperationModify,
                self.task,
                automatic=0,
                auto_update_time=0,
                days_fcast=0,
                start_time_fcast=None,
                end_time_fcast=None,
            )

    def test_assign_card_to_interval_01(self):
        "Interval board for project: task card assigned to interval  (Access rights given)"
        setUpModule()
        # prepare project, parent and sub tasks and interval board
        self.prepare_data(no=1)
        task = self.create_task(1, parent_task=self.task.task_id)
        board = self.create_taskboard(
            self.project, INTERVAL_BOARD_TYPE, start_date="17.09.2018"
        )
        card = board.Cards[0]
        iteration = board.Iterations[0]

        # only one card, not assigned to interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 0)
        task.Reload()
        self.assertEqual(task.end_time_fcast, None)

        # card is moved to interval
        self.move_cards(board, card, iteration=iteration)

        # only one card, assigned to first interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        task.Reload()
        self.assertEqual(task.end_time_fcast, None)

    def test_assign_card_to_interval_02(self):
        "Interval board for project: issue card assigned to interval  (Access rights given)"
        setUpModule()
        # prepare project and issue and interval board
        self.prepare_data(no=0)
        issue = self.create_issue(1, task_id="")
        board = self.create_taskboard(
            self.project, INTERVAL_BOARD_TYPE, start_date="17.09.2018"
        )
        card = board.Cards[0]
        iteration = board.Iterations[0]

        # only one card, not assigned to interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 0)
        issue.Reload()
        self.assertEqual(issue.target_date, None)

        # card is moved to interval
        self.move_cards(board, card, iteration=iteration)

        # only one card, assigned to first interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        issue.Reload()
        self.assertEqual(issue.target_date, None)

    def test_assign_card_to_interval_03(self):
        "Interval board for task: task card assigned to interval  (Access rights given)"
        setUpModule()
        # prepare project, parent and sub tasks and interval board
        self.prepare_data(no=1)
        task = self.create_task(1, parent_task=self.task.task_id)

        board = self.create_taskboard(
            self.project.Tasks[0], INTERVAL_BOARD_TYPE, start_date="17.09.2018"
        )
        card = board.Cards[0]
        iteration = board.Iterations[0]

        # only one card, not assigned to interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 0)
        task.Reload()
        self.assertEqual(task.end_time_fcast, None)

        # card is moved to interval
        self.move_cards(board, card, iteration=iteration)

        # only one card, assigned to first interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        task.Reload()
        self.assertEqual(task.end_time_fcast, None)

    def test_assign_card_to_interval_04(self):
        "Interval board for task: issue card assigned to interval  (Access rights given)"
        setUpModule()
        # prepare project, parent and sub tasks and interval board
        self.prepare_data(no=1)
        issue = self.create_issue(1, task_id=self.task.task_id)
        board = self.create_taskboard(
            self.project.Tasks[0], INTERVAL_BOARD_TYPE, start_date="17.09.2018"
        )
        card = board.Cards[0]
        iteration = board.Iterations[0]

        # only one card, not assigned to interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 0)
        issue.Reload()
        self.assertEqual(issue.target_date, None)

        # card is moved to interval
        self.move_cards(board, card, iteration=iteration)

        # only one card, assigned to first interval
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        issue.Reload()
        self.assertEqual(issue.target_date, None)

    @staticmethod
    def move_card(board, card, iteration=None, column=None):
        kwargs = {}
        if iteration:
            kwargs.update(sprint_object_id=iteration.cdb_object_id)
        if column:
            row = board.Rows[0]
            kwargs.update(
                column_object_id=column.cdb_object_id, row_object_id=row.cdb_object_id
            )
        client = Client(Root())
        url = f"/internal/cs.taskboard/card/{card.cdb_object_id}"
        client.post_json(url, kwargs)
        card.Reload()

    @staticmethod
    def move_cards(board, card, iteration=None, column=None):
        kwargs = {"cards": [card.cdb_object_id]}
        if iteration:
            kwargs.update(sprint_object_id=iteration.cdb_object_id)
        if column:
            row = board.Rows[0]
            kwargs.update(
                column_object_id=column.cdb_object_id, row_object_id=row.cdb_object_id
            )

        client = Client(Root())
        url = f"/internal/cs.taskboard/board/{board.cdb_object_id}/+move_cards"
        client.post_json(url, kwargs)

    def test_starting_interval_01(self):
        "Interval board for project: starting iteration  (project status is NEW, task status remains NEW)"
        setUpModule()
        # prepare project, parent and sub tasks and interval board
        self.prepare_data(no=0)
        task = self.create_task(1)
        task.Update(
            start_time_fcast=datetime.date(2020, 9, 11),
            end_time_fcast=datetime.date(2020, 9, 11),
            days_fcast=1,
        )
        board = self.create_taskboard(
            self.project, INTERVAL_BOARD_TYPE, start_date="10.09.2020"
        )
        iteration = board.Iterations[0]

        self.assertEqual(self.project.status, 0)
        self.assertEqual(task.status, 0)
        with self.assertRaises(ElementsError):
            operation("taskboard_start_sprint", iteration)
            task.Reload()
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        self.assertEqual(task.status, 0)

    def test_starting_interval_02(self):
        """Interval board for project: starting iteration (project status
        is EXECUTION, task status is set to READY)"""
        setUpModule()
        # prepare project, parent and sub tasks and interval board
        self.prepare_data(no=0)
        self.project.Update(status=50)
        task = self.create_task(1, automatic=0)
        task.Update(
            start_time_fcast=datetime.date(2020, 9, 11),
            end_time_fcast=datetime.date(2020, 9, 11),
            days_fcast=1,
        )
        self.project.recalculate()
        board = self.create_taskboard(
            self.project, INTERVAL_BOARD_TYPE, start_date="10.09.2020"
        )
        iteration = board.Iterations[0]

        self.assertEqual(self.project.status, 50)
        self.assertEqual(task.status, 0)
        operation("taskboard_start_sprint", iteration)
        task.Reload()
        self.assertEqual(len(board.Cards), 1)
        self.assertEqual(len(iteration.Cards), 1)
        self.assertEqual(task.status, 20)

    def prepare_project_for_moving_cards(self):
        setUpModule()
        # prepare data and board
        self.prepare_data(no=1)
        self.project.Update(status=50)
        board = self.create_taskboard(
            self.project, INTERVAL_BOARD_TYPE, start_date="01.09.2020"
        )
        operation("taskboard_start_sprint", board.Iterations[0])
        board.Cards[0].sprint_object_id = board.Iterations[0].cdb_object_id
        board.Cards[0].column_object_id = board.Columns[0].cdb_object_id

    def test_moving_cards_for_tasks_01(self):
        "Interval board for project: moving card between columns  from READY to DOING"
        self.prepare_project_for_moving_cards()
        board = self.project.Taskboard
        card = board.Cards[0]
        self.task.ChangeState(20)
        card.Reload()
        self.task.Reload()

        # previous check
        self.assertEqual(card.column_object_id, board.Columns[0].cdb_object_id)
        self.assertEqual(self.task.status, 20)
        self.assertEqual(self.task.start_time_fcast, None)
        self.assertEqual(self.task.end_time_fcast, None)
        # move from column READY to DOING
        self.move_card(board, card, column=board.Columns[1])
        # subsequent check
        self.task.Reload()
        self.assertEqual(card.column_object_id, board.Columns[1].cdb_object_id)
        self.assertEqual(self.task.status, 20)
        self.assertEqual(self.task.start_time_fcast, datetime.date(2020, 9, 14))
        self.assertEqual(self.task.end_time_fcast, datetime.date(2020, 9, 14))

    def test_moving_cards_for_tasks_02(self):
        "Interval board for project: moving card between columns  from READY to DONE"
        self.prepare_project_for_moving_cards()
        board = self.project.Taskboard
        card = board.Cards[0]
        self.task.ChangeState(20)
        card.Reload()
        self.task.Reload()

        # previous check
        self.assertEqual(card.column_object_id, board.Columns[0].cdb_object_id)
        self.assertEqual(self.task.status, 20)
        self.assertEqual(self.task.start_time_fcast, None)
        self.assertEqual(self.task.end_time_fcast, None)
        # move from column DOING to DONE
        self.move_card(board, card, column=board.Columns[2])
        # subsequent check
        self.task.Reload()
        self.assertEqual(card.column_object_id, board.Columns[2].cdb_object_id)
        self.assertEqual(self.task.status, 200)
        self.assertEqual(self.task.start_time_fcast, None)
        self.assertEqual(self.task.end_time_fcast, None)

    def test_moving_cards_for_tasks_03(self):
        "Interval board for project: moving card between columns  from DOING to DONE"
        self.prepare_project_for_moving_cards()
        board = self.project.Taskboard
        card = board.Cards[0]
        self.task.ChangeState(20)
        self.move_card(board, card, column=board.Columns[1])
        card.Reload()
        self.task.Reload()

        # previous check
        self.assertEqual(card.column_object_id, board.Columns[1].cdb_object_id)
        self.assertEqual(self.task.status, 20)
        self.assertEqual(self.task.start_time_fcast, datetime.date(2020, 9, 14))
        self.assertEqual(self.task.end_time_fcast, datetime.date(2020, 9, 14))
        # move from column DOING to DONE
        self.move_card(board, card, column=board.Columns[2])
        # subsequent check
        self.task.Reload()
        self.assertEqual(self.task.status, 200)
        self.assertEqual(self.task.start_time_fcast, datetime.date(2020, 9, 14))
        self.assertEqual(self.task.end_time_fcast, datetime.date(2020, 9, 14))


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestIntervalBoardWithIssues(TestBoards):
    def setup_necessary_objects(self, **kwargs):
        profile = CalendarProfile.KeywordQuery(name="Standard")[0]
        self.project = test_util.create_project(
            "bass", calendar_profile_id=profile.cdb_object_id, status=50
        )
        self.task = self.create_task(1, status=50)
        self.issue = self.create_issue(1, task_id=self.task.task_id)
        self.issue.Update(**kwargs)

    def setup_board(self, obj, board_type):
        self.board = self.create_taskboard(
            obj,
            board_type,
            interval_type=3,
            interval_length=1,
            start_date=datetime.date(2020, 9, 1),
        )
        self.iteration = self.board.Iterations[0]

    def start_sprint(self):
        operation("taskboard_start_sprint", self.board.NextIteration)

    def move_to_column(self, card, column_name):
        column = self.board.Columns.KeywordQuery(column_name=column_name)[0]
        c = Client(Root())
        url = f"/internal/cs.taskboard/card/{card.cdb_object_id}"
        c.post_json(
            url,
            {
                "column_object_id": column.cdb_object_id,
                "row_object_id": self.board.Rows[0].cdb_object_id,
            },
        )

    def call_board_update(self):
        c = Client(Root())
        url = f"/internal/cs.taskboard/board/{self.board.cdb_object_id}?group_by="
        c.get(url)

    @testcase.without_error_logging
    def test_issue_assignment_start_iteration_01(self):
        "Interval Board on task: issue with status NEW and target date ...Start iteration"
        # create project, task with interval board and issue
        self.setup_necessary_objects(status=0, target_date=datetime.date(2020, 9, 3))
        self.setup_board(self.task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""

        # update board
        self.call_board_update()

        self.issue.Reload()
        self.assertEqual(self.issue.status, 0)

        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

        # start iteration
        self.start_sprint()

        self.issue.Reload()
        self.assertEqual(self.issue.status, 30)

        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_moving_issue_cards_01(self):
        """Interval Board on task: move issue  (status EVALUATION, without target date)
        ...Move issue from READY to DOING"""
        # create project, task with interval board and issue
        self.setup_necessary_objects(status=30, target_date=None)
        self.setup_board(self.task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id

        # update board
        self.call_board_update()
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

        # start iteration
        self.move_to_column(card, "DOING")
        self.issue.Reload()
        self.assertEqual(self.issue.status, 30)
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_moving_issue_cards_02(self):
        """Interval Board on task: move issue  (status EVALUATION, with target date)
        ...Move issue from DOING to DONE"""
        # create project, task with interval board and issue
        self.setup_necessary_objects(
            status=30,
            target_date=datetime.date(2020, 9, 3),
            completion_date=datetime.date(2020, 9, 3),
        )
        self.setup_board(self.task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id

        # update board
        self.call_board_update()
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

        # start iteration
        self.move_to_column(card, "DONE")
        self.issue.Reload()
        self.assertEqual(self.issue.status, 200)
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_moving_issue_cards_03(self):
        """Interval Board on task: move issue  (status EXECUTION, with target date)
        ...Move issue from DOING to DONE"""
        # create project, task with interval board and issue
        self.setup_necessary_objects(
            status=50,
            target_date=datetime.date(2020, 9, 3),
            completion_date=datetime.date(2020, 9, 3),
        )
        self.setup_board(self.task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id

        # update board
        self.call_board_update()
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

        # start iteration
        self.move_to_column(card, "DONE")
        self.issue.Reload()
        self.assertEqual(self.issue.status, 200)
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def update_board_check_issue(
        self, assigned, status, column, target_date, in_iteration=True
    ):
        # create project, task with interval board and issue
        self.setup_necessary_objects(status=status, target_date=target_date)
        self.setup_board(self.task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        if assigned:
            card.sprint_object_id = self.iteration.cdb_object_id
        else:
            card.sprint_object_id = ""
        # update board
        self.call_board_update()
        card.Reload()
        if column:
            self.assertEqual(card.Column.column_name, column)
            self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(int(in_iteration), len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_update_board_check_issue_01(self):
        "Interval Board on task: issue assigned to interval  (status NEW, without target date)"
        self.update_board_check_issue(
            assigned=True, status=0, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_02(self):
        """Interval Board on task: issue assigned to interval
        (status EVALUATION, without target date)"""
        self.update_board_check_issue(
            assigned=True, status=30, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_03(self):
        """Interval Board on task: issue assigned to interval
        (status EXECUTION, without target date)"""
        self.update_board_check_issue(
            assigned=True, status=50, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_04(self):
        """Interval Board on task: issue assigned to interval
        (status DEFERRED, without target date)"""
        self.update_board_check_issue(
            assigned=True, status=60, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_05(self):
        """Interval Board on task: issue assigned to interval
        (status WAITING, without target date)"""
        self.update_board_check_issue(
            assigned=True, status=70, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_06(self):
        """Interval Board on task: issue assigned to interval
        (status READY, without target date)"""
        self.update_board_check_issue(
            assigned=True, status=100, column="READY", target_date=None
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_07(self):
        """Interval Board on task: issue not assigned to interval
        (status NEW, without target date)"""
        self.update_board_check_issue(
            assigned=False, status=0, column=None, target_date=None, in_iteration=False
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_08(self):
        """Interval Board on task: issue not assigned to interval
        (status EVALUATION, without target date)"""
        self.update_board_check_issue(
            assigned=False, status=30, column=None, target_date=None, in_iteration=False
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_09(self):
        """Interval Board on task: issue not assigned to interval
        (status EXECUTION, without target date)"""
        self.update_board_check_issue(
            assigned=False, status=50, column=None, target_date=None, in_iteration=False
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_10(self):
        """Interval Board on task: issue not assigned to interval
        (status DEFERRED, without target date)"""
        self.update_board_check_issue(
            assigned=False, status=60, column=None, target_date=None, in_iteration=False
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_11(self):
        """Interval Board on task: issue not assigned to interval
        (status WAITING, without target date)"""
        self.update_board_check_issue(
            assigned=False, status=70, column=None, target_date=None, in_iteration=False
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_12(self):
        """Interval Board on task: issue not assigned to interval
        (status REVIEW, without target date)"""
        self.update_board_check_issue(
            assigned=False,
            status=100,
            column=None,
            target_date=None,
            in_iteration=False,
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_13(self):
        """Interval Board on task: issue assigned to interval
        (status NEW, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=0,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_14(self):
        """Interval Board on task: issue assigned to interval
        (status EVALUATION, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=30,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_15(self):
        """Interval Board on task: issue assigned to interval
        (status EXECUTION, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=50,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_16(self):
        """Interval Board on task: issue assigned to interval
        (status DEFERRED, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=60,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_17(self):
        """Interval Board on task: issue assigned to interval
        (status WAITING, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=70,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_18(self):
        """Interval Board on task: issue assigned to interval
        (status REVIEW, target date within interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=100,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_19(self):
        """Interval Board on task: issue not assigned to interval
        (status NEW, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=0,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_20(self):
        """Interval Board on task: issue assigned to interval
        (status EVALUATION, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=30,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_21(self):
        """Interval Board on task: issue assigned to interval
        (status EXECUTION, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=50,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_22(self):
        """Interval Board on task: issue assigned to interval
        (status DEFERRED, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=60,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_23(self):
        """Interval Board on task: issue assigned to interval
        (status WAITING, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=70,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_24(self):
        """Interval Board on task: issue assigned to interval
        (status REVIEW, target date within interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=100,
            column="DOING",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_25(self):
        """Interval Board on task: issue assigned to interval
        (status NEW, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=0,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_26(self):
        """Interval Board on task: issue assigned to interval
        (status EVALUATION, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=30,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_27(self):
        """Interval Board on task: issue assigned to interval
        (status EXECUTION, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=50,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_28(self):
        """Interval Board on task: issue assigned to interval
        (status DEFERRED, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=60,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_29(self):
        """Interval Board on task: issue assigned to interval
        (status WAITING, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=70,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_30(self):
        """Interval Board on task: issue assigned to interval
        (status REVIEW, target date before interval)"""
        self.update_board_check_issue(
            assigned=True,
            status=100,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_31(self):
        """Interval Board on task: issue not assigned to interval
        (status NEW, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=0,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_32(self):
        """Interval Board on task: issue assigned to interval
        (status EVALUATION, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=30,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_33(self):
        """Interval Board on task: issue assigned to interval
        (status EXECUTION, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=50,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_34(self):
        """Interval Board on task: issue assigned to interval
        (status DEFERRED, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=60,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_35(self):
        """Interval Board on task: issue assigned to interval
        (status WAITING, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=70,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_36(self):
        """Interval Board on task: issue assigned to interval
        (status REVIEW, target date before interval)"""
        self.update_board_check_issue(
            assigned=False,
            status=100,
            column="DOING",
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_37(self):
        """Interval Board on task: issue assigned to interval
        (status DISCARDED, target date within iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=180,
            column="DONE",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_38(self):
        """Interval Board on task: issue assigned to interval
        (status COMPLETED, target date within iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=200,
            column="DONE",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_39(self):
        """Interval Board on task: issue not assigned to interval
        (status DISCARDED, target date within iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=180,
            column="DONE",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_40(self):
        """Interval Board on task: issue not assigned to interval
        (status COMPLETED, target date within iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=200,
            column="DONE",
            target_date=datetime.date(2020, 9, 30),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_41(self):
        """Interval Board on task: issue assigned to interval
        (status DISCARDED, target date before iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=180,
            column=None,
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_42(self):
        """Interval Board on task: issue assigned to interval
        (status COMPLETED, target date before iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=200,
            column=None,
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_43(self):
        """Interval Board on task: issue not assigned to interval
        (status DISCARDED, target date before iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=180,
            column=None,
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_44(self):
        """Interval Board on task: issue not assigned to interval
        (status COMPLETED, target date before iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=200,
            column=None,
            target_date=datetime.date(2020, 8, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_45(self):
        """Interval Board on task: issue assigned to interval
        (status DISCARDED, target date after iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=180,
            column=None,
            target_date=datetime.date(2020, 10, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_46(self):
        """Interval Board on task: issue assigned to interval
        (status COMPLETED, target date after iteration)"""
        self.update_board_check_issue(
            assigned=True,
            status=200,
            column=None,
            target_date=datetime.date(2020, 10, 31),
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_47(self):
        """Interval Board on task: issue not assigned to interval
        (status DISCARDED, target date after iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=180,
            column=None,
            target_date=datetime.date(2020, 10, 31),
            in_iteration=False,
        )

    @testcase.without_error_logging
    def test_update_board_check_issue_48(self):
        """Interval Board on task: issue not assigned to interval
        (status COMPLETED, target date after iteration)"""
        self.update_board_check_issue(
            assigned=False,
            status=200,
            column=None,
            target_date=datetime.date(2020, 10, 31),
            in_iteration=False,
        )


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestIntervalBoardTasksAssignmentToInterval(TestBoards):
    def setup_necessary_objects(self, **kwargs):
        profile = CalendarProfile.KeywordQuery(name="Standard")[0]
        attrs = {
            "start_time_fcast": datetime.date(2020, 8, 17),
            "end_time_fcast": datetime.date(2020, 9, 25),
            "start_time_plan": datetime.date(2020, 8, 17),
            "end_time_plan": datetime.date(2020, 9, 25),
            "auto_update_time": 1,
            "status": 50,
            "days_fcast": 30,
            "days": 30,
        }
        self.project = test_util.create_project(
            "bass", is_group=1, calendar_profile_id=profile.cdb_object_id, **attrs
        )
        attrs.update(constraint_type="0", automatic=0)
        self.top_task = self.create_task(
            "top",
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            is_group=1,
            parent_task="",
            **attrs,
        )
        self.sub_task = self.create_task(
            "sub",
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            is_group=0,
            parent_task=self.top_task.task_id,
            **attrs,
        )
        self.sub_task.Update(**kwargs)

    def setup_board(self, obj, board_type):
        self.board = self.create_taskboard(
            obj,
            board_type,
            interval_type=3,
            interval_length=1,
            start_date=datetime.date(2020, 9, 1),
        )
        self.iteration = self.board.Iterations[0]

    def call_board_update(self):
        c = Client(Root())
        url = f"/internal/cs.taskboard/board/{self.board.cdb_object_id}?group_by="
        c.get(url)

    @testcase.without_error_logging
    def test_task_assignment_to_interval_01(self):
        "Interval Board on task: sub task assigned to iteration  (status NEW, without end date)"
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_02(self):
        "Interval Board on task: sub task assigned to iteration  (status READY, without end date)"
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_03(self):
        """Interval Board on task: sub task assigned to iteration
        (status EXECUTION, without end date)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_04(self):
        """Interval Board on task: sub task not assigned to iteration
        (status NEW, without end date)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_05(self):
        """Interval Board on task: sub task not assigned to iteration
        (status READY, without end date)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_06(self):
        """Interval Board on task: sub task not assigned to iteration
        (status EXECUTION, without end date)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50, days_fcast=20, start_time_fcast=None, end_time_fcast=None
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "READY")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_07(self):
        """Interval Board on task: sub task assigned to iteration
        (status NEW, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0,
            days_fcast=12,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 1),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()
        # self.board.getAdapter().update_board()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_08(self):
        """Interval Board on task: sub task assigned to iteration
        (status READY, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20,
            days_fcast=13,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 2),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_09(self):
        """Interval Board on task: sub task assigned to iteration
        (status EXECUTION, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50,
            days_fcast=14,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 3),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_10(self):
        """Interval Board on task: sub task not assigned to iteration
        (status NEW, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0,
            days_fcast=15,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 4),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_11(self):
        """Interval Board on task: sub task not assigned to iteration
        (status READY, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20,
            days_fcast=16,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 5),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_12(self):
        """Interval Board on task: sub task not assigned to iteration
        (status EXECUTION, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50,
            days_fcast=17,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 6),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_13(self):
        """Interval Board on task: sub task assigned to iteration
        (status NEW, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0,
            days_fcast=11,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 31),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_14(self):
        """Interval Board on task: sub task assigned to iteration
        (status READY, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20,
            days_fcast=10,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 28),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_15(self):
        """Interval Board on task: sub task assigned to iteration
        (status EXECUTION, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50,
            days_fcast=9,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 27),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_16(self):
        """Interval Board on task: sub task not assigned to iteration
        (status NEW, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=0,
            days_fcast=8,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 26),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_17(self):
        """Interval Board on task: sub task not assigned to iteration
        (status READY, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=20,
            days_fcast=7,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 25),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_18(self):
        """Interval Board on task: sub task not assigned to iteration
        (status EXECUTION, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=50,
            days_fcast=6,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 24),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DOING")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_19(self):
        """Interval Board on task: sub task assigned to iteration
        (status FINISHED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=200,
            days_fcast=12,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 1),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_20(self):
        """Interval Board on task: sub task assigned to iteration
        (status DISCARDED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=180,
            days_fcast=13,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 2),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_21(self):
        """Interval Board on task: sub task assigned to iteration
        (status COMPLETED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=250,
            days_fcast=14,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 3),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_22(self):
        """Interval Board on task: sub task not assigned to iteration
        (status FINISHED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=200,
            days_fcast=15,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 4),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_23(self):
        """Interval Board on task: sub task not assigned to iteration
        (status DISCARDED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=180,
            days_fcast=16,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 5),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_24(self):
        """Interval Board on task: sub task not assigned to iteration
        (status COMPLETED, end date within interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=250,
            days_fcast=17,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 9, 6),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_25(self):
        """Interval Board on task: sub task assigned to iteration
        (status FINISHED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=200,
            days_fcast=11,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 31),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_26(self):
        """Interval Board on task: sub task assigned to iteration
        (status DISCARDED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=180,
            days_fcast=10,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 28),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_27(self):
        """Interval Board on task: sub task assigned to iteration
        (status COMPLETED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=250,
            days_fcast=9,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 27),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = self.iteration.cdb_object_id
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_28(self):
        """Interval Board on task: sub task not assigned to iteration
        (status FINISHED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=200,
            days_fcast=8,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 26),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_29(self):
        """Interval Board on task: sub task not assigned to iteration
        (status DISCARDED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=180,
            days_fcast=7,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 25),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_assignment_to_interval_30(self):
        """Interval Board on task: sub task not assigned to iteration
        (status COMPLETED, end date before interval)"""
        # create project, top task with interval board and sub task
        self.setup_necessary_objects(
            status=250,
            days_fcast=6,
            start_time_fcast=datetime.date(2020, 8, 17),
            end_time_fcast=datetime.date(2020, 8, 24),
        )
        self.setup_board(self.top_task, INTERVAL_BOARD_TYPE)
        # assign card
        self.assertEqual(1, len(self.board.Cards))
        card = self.board.Cards[0]
        card.sprint_object_id = ""
        self.call_board_update()

        # check card
        card.Reload()
        self.assertEqual(card.Column.column_name, "DONE")
        self.assertEqual(False, bool(card.is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestTasksOnIntervalBoard(TestBoards):
    def setup_necessary_objects(self, board_type, status):
        self.project = test_util.create_project("bass")
        self.create_task(
            1,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=status,
            days_fcast=1,
            start_time_fcast=self.test_date,
            end_time_fcast=self.test_date,
        )
        self.board = self.create_taskboard(
            self.project, board_type, start_time=self.test_date
        )
        self.iteration = self.board.Iterations[0]

    @testcase.without_error_logging
    def test_task_on_interval_board_1(self):
        "Interval Board: place task in status NEW"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 0)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_on_interval_board_2(self):
        "Interval Board: place task in status READY"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 20)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_on_interval_board_3(self):
        "Interval Board: place task in status EXECUTION"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 50)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_on_interval_board_4(self):
        "Interval Board: place task in status DISCARDED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 180)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_on_interval_board_5(self):
        "Interval Board: place task in status FINISHED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 200)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    @testcase.without_error_logging
    def test_task_on_interval_board_6(self):
        "Interval Board: place task in status COMPLETED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 250)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_no_baseline_task_on_interval_board(self):
        "Interval Board: No baseline task present on interval board"
        self.project = test_util.create_project("bass")
        self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=50
        )
        kwargs = {
            "ce_baseline_name": "interval board baseline",
            "ce_baseline_comment": "",
        }
        operation("ce_baseline_create", self.project, **kwargs)
        self.board = self.create_taskboard(
            self.project, SPRINT_BOARD_TYPE, start_time=self.test_date
        )
        # There is only one none baseline task card on the board
        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual("", self.board.Cards[0].TaskObject.ce_baseline_id)


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestIssuesOnIntervalBoard(TestBoards):
    def setup_necessary_objects(self, board_type, status):
        self.project = test_util.create_project("bass")
        self.create_issue(
            1,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=status,
            target_date=self.test_date,
            completion_date=self.test_date,
        )
        self.board = self.create_taskboard(
            self.project, board_type, start_time=self.test_date
        )
        self.iteration = self.board.Iterations[0]

    def test_issue_on_interval_board_1(self):
        "Interval Board: place issue in status NEW"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 0)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_2(self):
        "Interval Board: place issue in status EVALUATION"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 30)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_3(self):
        "Interval Board: place issue in status EXECUTION"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 50)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_4(self):
        "Interval Board: place issue in status DEFERRED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 60)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_5(self):
        "Interval Board: place issue in status WAITING"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 70)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_6(self):
        "Interval Board: place issue in status REVIEW"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 100)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_7(self):
        "Interval Board: place issue in status DISCARDED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 180)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))

    def test_issue_on_interval_board_8(self):
        "Interval Board: place issue in status COMPLETED"
        self.setup_necessary_objects(INTERVAL_BOARD_TYPE, 200)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(1, len(self.iteration.Cards))


# SPRINT BOARDS


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestSprintBoard(TestBoards):
    def test_board_on_project_by_project_leader(self):
        "Create a Sprint Board on project by project leader."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )
        test_util.assign_user_project_role(user, self.project, role_id="Projektleiter")

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project leader.")
        self.assertTrue(r, "Taskboard should be readable by project leader.")
        self.assertTrue(s, "Taskboard should be modifiable by project leader.")
        self.assertTrue(d, "Taskboard should be deletable by project leader.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Sprint should be creatable by project leader.")
        self.assertTrue(r, "Sprint should be readable by project leader.")
        self.assertTrue(s, "Sprint should be modifiable by project leader.")
        self.assertTrue(d, "Sprint should be deletable by project leader.")

    def test_board_on_task_by_project_leader(self):
        "Create a Sprint Board on task by project leader."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )
        test_util.assign_user_project_role(user, self.project, role_id="Projektleiter")

        board_1 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project leader.")
        self.assertTrue(r, "Taskboard should be readable by project leader.")
        self.assertTrue(s, "Taskboard should be modifiable by project leader.")
        self.assertTrue(d, "Taskboard should be deletable by project leader.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Sprint should be creatable by project leader.")
        self.assertTrue(r, "Sprint should be readable by project leader.")
        self.assertTrue(s, "Sprint should be modifiable by project leader.")
        self.assertTrue(d, "Sprint should be deletable by project leader.")

    def test_board_on_project_by_project_member(self):
        "Create a Sprint Board on project by project member."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by project member.")
        self.assertTrue(r, "Taskboard should be readable by project member.")
        self.assertFalse(s, "Taskboard should not be modifiable by project member.")
        self.assertFalse(d, "Taskboard should not be deletable by project member.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Sprint should not be creatable by project member.")
        self.assertTrue(r, "Sprint should be readable by project member.")
        self.assertFalse(s, "Sprint should not be modifiable by project member.")
        self.assertFalse(d, "Sprint should not be deletable by project member.")

    def test_board_on_task_by_project_member(self):
        "Create a Sprint Board on task by project member."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )

        board_1 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertTrue(c, "Taskboard should be creatable by project member.")
        self.assertTrue(r, "Taskboard should be readable by project member.")
        self.assertTrue(s, "Taskboard should be modifiable by project member.")
        self.assertTrue(d, "Taskboard should be deletable by project member.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertTrue(c, "Sprint should be creatable by project member.")
        self.assertTrue(r, "Sprint should be readable by project member.")
        self.assertTrue(s, "Sprint should be modifiable by project member.")
        self.assertTrue(d, "Sprint should be deletable by project member.")

    def test_board_on_project_by_teamboard_manager(self):
        "Create a Sprint Board on project by Teamboard Manager."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Teamboard Manager")

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Taskboard should be readable by Teamboard Manager.")
        self.assertFalse(s, "Taskboard should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Taskboard should not be deletable by Teamboard Manager.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Sprint should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Sprint should be readable by Teamboard Manager.")
        self.assertFalse(s, "Sprint should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Sprint should not be deletable by Teamboard Manager.")

    def test_board_on_task_by_teamboard_manager(self):
        "Create a Sprint Board on task by Teamboard Manager."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Teamboard Manager")

        board_1 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Taskboard should be readable by Teamboard Manager.")
        self.assertFalse(s, "Taskboard should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Taskboard should not be deletable by Teamboard Manager.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Sprint should not be creatable by Teamboard Manager.")
        self.assertTrue(r, "Sprint should be readable by Teamboard Manager.")
        self.assertFalse(s, "Sprint should not be modifiable by Teamboard Manager.")
        self.assertFalse(d, "Sprint should not be deletable by Teamboard Manager.")

    def test_board_on_project_by_taskboard_administrator(self):
        "Create a Sprint Board on project by Taskboard Administrator."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Taskboard Administrator")

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(
            c, "Taskboard should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Taskboard should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Taskboard should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Taskboard should not be deletable by Taskboard Administrator."
        )

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(
            c, "Sprint should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Sprint should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Sprint should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Sprint should not be deletable by Taskboard Administrator."
        )

    def test_board_on_task_by_taskboard_administrator(self):
        "Create a Sprint Board on task by Taskboard Administrator."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_global_role(user, "Taskboard Administrator")

        board_1 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(
            c, "Taskboard should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Taskboard should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Taskboard should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Taskboard should not be deletable by Taskboard Administrator."
        )

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(
            c, "Sprint should not be creatable by Taskboard Administrator."
        )
        self.assertTrue(r, "Sprint should be readable by Taskboard Administrator.")
        self.assertFalse(
            s, "Sprint should not be modifiable by Taskboard Administrator."
        )
        self.assertFalse(
            d, "Sprint should not be deletable by Taskboard Administrator."
        )

    def test_board_on_project_by_public_user(self):
        "Create a Sprint Board on project by public user."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by public user.")
        self.assertTrue(r, "Taskboard should be readable by public user.")
        self.assertFalse(s, "Taskboard should not be modifiable by public user.")
        self.assertFalse(d, "Taskboard should not be deletable by public user.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Sprint should not be creatable by public user.")
        self.assertTrue(r, "Sprint should be readable by public user.")
        self.assertFalse(s, "Sprint should not be modifiable by public user.")
        self.assertFalse(d, "Sprint should not be deletable by public user.")

    def test_board_on_task_by_public_user(self):
        "Create a Sprint Board on task by public user."
        self.project = test_util.create_project("bass")
        self.assertIsNotNone(self.project, "Project has not been created.")
        task = self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=20
        )
        self.assertIsNotNone(task, "Task has not been created.")

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)

        board_1 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard has not been created.")

        c, r, s, d = self.check_access_rights(board_1, user)
        self.assertFalse(c, "Taskboard should not be creatable by public user.")
        self.assertTrue(r, "Taskboard should be readable by public user.")
        self.assertFalse(s, "Taskboard should not be modifiable by public user.")
        self.assertFalse(d, "Taskboard should not be deletable by public user.")

        iteration_1 = board_1.Iterations[0]
        self.assertIsNotNone(iteration_1, "Iteration has not been created.")

        c, r, s, d = self.check_access_rights(iteration_1, user)
        self.assertFalse(c, "Sprint should not be creatable by public user.")
        self.assertTrue(r, "Sprint should be readable by public user.")
        self.assertFalse(s, "Sprint should not be modifiable by public user.")
        self.assertFalse(d, "Sprint should not be deletable by public user.")

    def test_sprint_board_remove_board_on_copied_projects_and_tasks(self):
        "Assignment to project boards have to be removed on copies of projects and tasks."
        self._setup_project()
        self.assertIsNotNone(self.project, "Project has not been created.")

        task = self.create_task(1)
        self.assertIsNotNone(task, "Task has not been created.")

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard for project has not been created.")

        oid = self.project.taskboard_oid
        self.assertTrue(bool(oid), "Created project has no taskboard assigned.")

        board_2 = self.create_taskboard(task, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_2, "Taskboard for task has not been created.")

        oid = task.taskboard_oid
        self.assertTrue(bool(oid), "First task has no taskboard assigned.")

        task = self.copy_task(task)
        self.assertIsNotNone(task, "Second task has not been created.")

        oid = task.taskboard_oid
        self.assertFalse(bool(oid), "Second task has taskboard assigned.")

        self.copy_project()
        self.assertIsNotNone(self.project_copy, "Project has not been copied.")

        oid = self.project_copy.taskboard_oid
        self.assertFalse(bool(oid), "Copied project has taskboard assigned.")

        for t in self.project_copy.Tasks:
            oid = t.taskboard_oid
            self.assertFalse(bool(oid), "Copied task has taskboard assigned.")

    def test_sprint_board_task_changed_status_refreshes_board(self):
        "After indirect status changes of tasks project boards have to be refreshed."
        self._setup_project()
        self.assertIsNotNone(self.project, "Project has not been created.")

        predecessor = self.project.Tasks[0]
        self.assertIsNotNone(predecessor, "Predecessor task has not been created.")

        successor = self.create_task(2)
        self.assertIsNotNone(successor, "Successor task has not been created.")

        task_rel = self.create_taskrelation(predecessor, successor, "EA")
        self.assertIsNotNone(task_rel, "EA-TaskRelation has not been created.")

        board_1 = self.create_taskboard(self.project, SPRINT_BOARD_TYPE)
        self.assertIsNotNone(board_1, "Taskboard for project has not been created.")

        oid = self.project.taskboard_oid
        self.assertTrue(bool(oid), "Created project has no taskboard assigned.")

        c = len(board_1.Iterations)
        self.assertTrue(c == 1, f"Found {c} instead of 1 Iteration on board.")

        iteration_1 = board_1.Iterations[0]
        for c in board_1.Cards:
            c.sprint_object_id = iteration_1.cdb_object_id
        self.project.ChangeState(Project.EXECUTION.status, check_access=False)
        predecessor.Reload()
        successor.Reload()
        self.assertTrue(
            predecessor.status == 20, "Predecessor task should be in status Ready."
        )
        self.assertTrue(
            successor.status == 0, "Successor task should be in status New."
        )

        card_1 = board_1.Cards.KeywordQuery(
            context_object_id=predecessor.cdb_object_id
        )[0]
        card_2 = board_1.Cards.KeywordQuery(context_object_id=successor.cdb_object_id)[
            0
        ]
        self.assertTrue(
            card_1.Column.column_name == "READY",
            "Task is not assigned to Column READY. "
            f"Assigned to Column {card_1.Column.column_name} instead.",
        )
        self.assertTrue(
            card_2.Column.column_name == "READY",
            "Task is not assigned to Column READY. "
            f"Assigned to Column {card_2.Column.column_name} instead.",
        )

        predecessor.ChangeState(Task.EXECUTION.status, check_access=False)
        predecessor.ChangeState(Task.FINISHED.status, check_access=False)
        successor.Reload()
        self.assertTrue(
            predecessor.status == 200, "Predecessor task should be in status Finished."
        )
        self.assertTrue(
            successor.status == 20, "Successor task should be in status Ready."
        )

        card_1.Reload()
        card_2.Reload()
        self.assertTrue(
            card_1.Column.column_name == "DONE",
            "Task is not assigned to Column DONE. Assigned to "
            f"Column {card_1.Column.column_name} instead.",
        )
        self.assertTrue(
            card_2.Column.column_name == "READY",
            "Task is not assigned to Column READY. "
            f"Assigned to Column {card_2.Column.column_name} instead.",
        )


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestTasksOnSprintBoard(TestBoards):
    def setup_necessary_objects(self, board_type, status):
        self.project = test_util.create_project("bass")
        self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=status
        )
        self.board = self.create_taskboard(
            self.project, board_type, start_time=self.test_date
        )
        self.iteration = self.board.Iterations[0]

    def test_task_on_sprint_board_1(self):
        "Sprint Board: place task in status NEW"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 0)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_task_on_sprint_board_2(self):
        "Sprint Board: place task in status READY"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 20)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_task_on_sprint_board_3(self):
        "Sprint Board: place task in status EXECUTION"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 50)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_task_on_sprint_board_4(self):
        "Sprint Board: place task in status DISCARDED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 180)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(True, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_task_on_sprint_board_5(self):
        "Sprint Board: place task in status FINISHED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 200)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(True, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_task_on_sprint_board_6(self):
        "Sprint Board: place task in status COMPLETED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 250)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(True, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_no_baseline_task_on_sprint_board(self):
        "Sprint Board: No baseline task present on sprint board"
        self.project = test_util.create_project("bass")
        self.create_task(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=50
        )
        kwargs = {
            "ce_baseline_name": "sprint board baseline",
            "ce_baseline_comment": "",
        }
        operation("ce_baseline_create", self.project, **kwargs)
        self.board = self.create_taskboard(
            self.project, SPRINT_BOARD_TYPE, start_time=self.test_date
        )
        # There is only one none baseline task card on the board
        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual("", self.board.Cards[0].TaskObject.ce_baseline_id)


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestIssuesOnSprintBoard(TestBoards):
    def setup_necessary_objects(self, board_type, status):
        self.project = test_util.create_project("bass")
        self.create_issue(
            1, subject_id="Projektmitglied", subject_type="PCS Role", status=status
        )
        self.board = self.create_taskboard(
            self.project, board_type, start_time=self.test_date
        )
        self.iteration = self.board.Iterations[0]

    def test_issue_on_sprint_board_1(self):
        "Sprint Board: place issue in status NEW"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 0)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_2(self):
        "Sprint Board: place issue in status EVALUATION"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 30)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_3(self):
        "Sprint Board: place issue in status EXECUTION"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 50)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_4(self):
        "Sprint Board: place issue in status DEFERRED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 60)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_5(self):
        "Sprint Board: place issue in status WAITING"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 70)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_6(self):
        "Sprint Board: place issue in status REVIEW"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 100)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(False, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_7(self):
        "Sprint Board: place issue in status DISCARDED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 180)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(True, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))

    def test_issue_on_sprint_board_8(self):
        "Sprint Board: place issue in status COMPLETED"
        self.setup_necessary_objects(SPRINT_BOARD_TYPE, 200)

        self.assertEqual(1, len(self.board.Cards))
        self.assertEqual(True, bool(self.board.Cards[0].is_hidden))
        self.assertEqual(0, len(self.iteration.Cards))


# PERSONAL BOARDS


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestPersonalBoard(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.request = Client(Root())
        # Important:
        # first test user has to be "caddok",
        # because personal boards only may be evaluated for logged on user
        self.user1 = self.create_board_user("caddok")
        self.user2 = self.create_board_user("second_user")
        for table in ["cdbpcs_task", "cdbpcs_issue"]:
            sqlapi.SQLupdate(
                f"{table} SET subject_id = 'deactivated'"
                f" WHERE subject_id IN ('{self.user1.personalnummer}', "
                f" '{self.user2.personalnummer}') AND subject_type = 'Person'"
            )
        self.create_substitute(self.user2, self.user1)
        self.project = test_util.create_project("#test", self.user2)
        test_util.assign_user_project_role(self.user2, self.project, "Projektmitglied")
        self.assertIsNotNone(self.project, "Project has not been created.")

    def create_board_user(self, username):
        p = Person.ByKeys(personalnummer=username)
        if p:
            return p
        return Person.Create(
            login=username, personalnummer=username, active_account="1"
        )

    def create_substitute(self, user, substitute):
        test_util.create_userSubstitution(
            user=user,
            substitute=substitute,
            fromDate=datetime.date.today() - datetime.timedelta(days=1),
            toDate=datetime.date.today() + datetime.timedelta(days=10),
        )

    def request_board(self, board):
        return self.request.get(f"/internal/cs.taskboard/board/{board.cdb_object_id}")

    def get_card(self, board, task):
        cards = board.Cards.KeywordQuery(context_object_id=task.cdb_object_id)
        if len(cards):
            return cards[0]
        return None

    def create_task(self, person, i):
        with util.SkipAccessCheck():
            return operation(
                kOperationNew,
                Task,
                cdb_project_id=self.project.cdb_project_id,
                task_id="#1",
                ce_baseline_id=self.project.ce_baseline_id,
                task_name=f"Task name {i}",
                subject_id=person.personalnummer,
                subject_type="Person",
                constraint_type="0",
                parent_task="",
                is_group=0,
            )

    def create_issue(self, person, i):
        with util.SkipAccessCheck():
            return operation(
                kOperationNew,
                Issue,
                cdb_project_id=self.project.cdb_project_id,
                issue_name=f"Issue name {i}",
                subject_id=person.personalnummer,
                subject_type="Person",
            )

    def test_personal_board_creating_task_creates_card_for_taskboard(self):
        "Creating a new task creates a corresponding card for personal board."
        user1_task1 = self.create_task(self.user1, 1)
        self.assertIsNotNone(user1_task1, "Task has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        user1_task1.Reload()
        self.assertEqual(
            user1_task1.status, 20, "Task status has not been set to 'Ready'"
        )
        personal_board = get_personal_board(self.user1.cdb_object_id)
        self.request_board(personal_board)
        self.assertIsNotNone(
            self.get_card(personal_board, user1_task1), "Task Card not found"
        )

    def test_personal_board_task_has_to_be_done_by_substitute(self):
        "Tasks that have to be done by an substitute user, have to emerge on this users personal board."
        user2_task1 = self.create_task(self.user2, 1)
        self.assertIsNotNone(user2_task1, "Task has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        user2_task1.Reload()
        self.assertEqual(
            user2_task1.status, 20, "Task status has not been set to 'Ready'"
        )
        personal_board = get_personal_board(self.user1.cdb_object_id)
        self.request_board(personal_board)
        self.assertIsNotNone(
            self.get_card(personal_board, user2_task1), "Substitute Task Card not found"
        )

    def test_personal_board_creating_issue_creates_card_for_taskboard(self):
        "Creating a new issue creates a corresponding card for personal board."
        user1_issue1 = self.create_issue(self.user1, 1)
        self.assertIsNotNone(user1_issue1, "Issue has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        user1_issue1.ChangeState(30, check_access=False)
        self.assertEqual(
            user1_issue1.status, 30, "Issue status has not been set to 'Evaluation'"
        )
        personal_board = get_personal_board(self.user1.cdb_object_id)
        self.request_board(personal_board)
        self.assertIsNotNone(
            self.get_card(personal_board, user1_issue1), "Issue Card not found"
        )

    def test_personal_board_issue_has_to_be_done_by_substitute(self):
        """Issues that have to be done by an substitute user,
        have to emerge on this users personal board."""
        user2_issue1 = self.create_issue(self.user2, 1)
        self.assertIsNotNone(user2_issue1, "Issue has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        user2_issue1.ChangeState(30, check_access=False)
        self.assertEqual(
            user2_issue1.status, 30, "Issue status has not been set to 'Evaluation'"
        )
        personal_board = get_personal_board(self.user1.cdb_object_id)
        self.request_board(personal_board)
        self.assertIsNotNone(
            self.get_card(personal_board, user2_issue1),
            "Substitute Issue Card not found",
        )

    def test_no_baseline_task_on_personal_board(self):
        "Personal Board: No baseline task present on personal board"
        task = self.create_task(self.user1, 1)
        self.assertIsNotNone(task, "Task has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        task.Reload()
        self.assertEqual(task.status, 20, "Issue status has not been set to 'Ready'")
        kwargs = {
            "ce_baseline_name": "personal board baseline",
            "ce_baseline_comment": "",
        }
        operation("ce_baseline_create", self.project, **kwargs)
        baseline = [
            p
            for p in Project.KeywordQuery(cdb_project_id=self.project.cdb_project_id)
            if p.ce_baseline_id != ""
        ][0]
        self.assertIsNotNone(baseline, "Baseline has not been created.")
        personal_board = get_personal_board(self.user1.cdb_object_id)
        personal_board.updateBoard()
        # There is only one none baseline task card on the board
        pers_cards = len(personal_board.Cards)
        self.assertEqual(
            1, pers_cards, f"Personal Board has {pers_cards} cards, expected 1"
        )
        self.assertEqual(
            "",
            personal_board.Cards[0].TaskObject.ce_baseline_id,
            "Baseline Task on Personal Board",
        )

    def test_no_baseline_task_on_personal_board(self):
        "Personal Board: No baseline task present on personal board"
        task = self.create_task(self.user1, 1)
        self.assertIsNotNone(task, "Task has not been created.")
        self.project.ChangeState(50)
        self.assertEqual(
            self.project.status, 50, "Project status has not been set to 'Execution'"
        )
        task.Reload()
        self.assertEqual(task.status, 20, "Issue status has not been set to 'Ready'")
        kwargs = {
            "ce_baseline_name": "personal board baseline",
            "ce_baseline_comment": "",
        }
        operation("ce_baseline_create", self.project, **kwargs)
        baseline = [
            p
            for p in Project.KeywordQuery(cdb_project_id=self.project.cdb_project_id)
            if p.ce_baseline_id != ""
        ][0]
        self.assertIsNotNone(baseline, "Baseline has not been created.")
        personal_board = get_personal_board(self.user1.cdb_object_id)
        personal_board.updateBoard()
        # There is only one none baseline task card on the board
        pers_cards = len(personal_board.Cards)
        self.assertEqual(
            1, pers_cards, f"Personal Board has {pers_cards} cards, expected 1"
        )
        self.assertEqual(
            "",
            personal_board.Cards[0].TaskObject.ce_baseline_id,
            "Baseline Task on Personal Board",
        )


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestBoardUpdate(TestBoards):
    """
    This test is created to check that any change on cards an a board
    results in exactly one call of the method "update_board"
    (which refreshes the board data).
    Especially when performing a status change by moving a card between
    columns of an active iteration, this might result in follow up
    status changes but may only trigger one update call.
    """

    status_map = OrderedDict()

    def check_status_entry(self, obj, status=None):
        obj.Reload()
        if status is None:
            status = obj.status
        self.status_map[obj.cdb_object_id] = status
        self.assertEqual(
            obj.status,
            status,
            f"Object '{obj.GetDescription()}': status is '{obj.status}', should be '{status}'",
        )

    def check_status_entries(self):
        for key, value in self.status_map.items():
            obj = ByID(key)
            self.check_status_entry(obj, value)

    def get_card(self, obj):
        result = self.board.Cards.KeywordQuery(context_object_id=obj.cdb_object_id)
        return result[0] if result else None

    def get_iteration(self, pos=0):
        result = self.board.OpenIterations
        if len(result) > pos:
            return result[pos]
        return None

    def get_column(self, name):
        result = self.board.Columns.KeywordQuery(column_name=name)
        return result[0] if result else None

    def get_row(self):
        return self.board.Rows[0] if self.board.Rows else None

    def prepare_for_board_update(self, board_type):
        """
        *** data structure ***
        project
            task_1
                issue_1
                action_1
                    action_1_1
            task_2
                task_2_1
            issue_2
        """
        self.status_map.clear()
        self.number_of_tasks = 0
        self._setup_project()
        self.project.ChangeState(50)
        self.task_1 = self.create_task(
            101, subject_id="Projektmitglied", subject_type="PCS Role", status=50
        )
        self.task_2 = self.create_task(
            102, subject_id="Projektmitglied", subject_type="PCS Role", status=0
        )
        self.task_2_1 = self.create_task(
            103,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=0,
            parent_task=self.task_2.task_id,
        )
        self.create_taskrelation(self.task_1, self.task_2, "EA")
        self.action_1 = self.create_action(
            1,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=20,
            task_id=self.task_1.task_id,
        )
        self.action_1_1 = self.create_action(
            2,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=20,
            parent_object_id=self.action_1.cdb_object_id,
        )
        self.issue_1 = self.create_issue(
            1,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=50,
            task_id=self.task_1.task_id,
        )
        self.issue_2 = self.create_issue(
            2, subject_id="Projektmitglied", subject_type="PCS Role", status=50
        )

        self.check_status_entry(self.task_1)
        self.check_status_entry(self.task_2)
        self.check_status_entry(self.task_2_1)
        self.check_status_entry(self.action_1)
        self.check_status_entry(self.action_1_1)
        self.check_status_entry(self.issue_1)
        self.check_status_entry(self.issue_2)

        user = test_util.create_user("foo")
        test_util.assign_user_role_public(user)
        test_util.assign_user_project_role(
            user, self.project, role_id="Projektmitglied"
        )
        test_util.assign_user_project_role(user, self.project, role_id="Projektleiter")

        board = self.create_taskboard(self.project, board_type)
        self.assertIsNotNone(board, "Taskboard has not been created.")
        self.assertEqual(len(board.Cards), 6)
        self.board = board

    @mock.patch.object(internal, "get_collection_app", return_value=None)
    @mock.patch.object(internal, "opdata_view", return_value={})
    @mock.patch.object(internal, "_get_task_view", return_value={})
    def test_sprint_board_update_for__change_card(self, *args):
        "Update Board may only be called once by '_change_card':  Iteration changed"
        self.prepare_for_board_update(SPRINT_BOARD_TYPE)
        card = self.board.Cards[0]
        iteration = self.board.Iterations[0]
        request = Request(sprint_object_id=iteration.cdb_object_id)
        with UpdateCount():
            _change_card(card, request)
            self.assertEqual(CALLS, 1)

    @mock.patch.object(internal, "get_collection_app", return_value=None)
    @mock.patch.object(internal, "opdata_view", return_value={})
    @mock.patch.object(internal, "_get_task_view", return_value={})
    def test_sprint_board_update_for__change_cards(self, *args):
        "Update Board may only be called once by '_change_cards':  Iteration changed"
        self.prepare_for_board_update(SPRINT_BOARD_TYPE)
        cards = self.board.Cards[0:6]
        iteration = self.board.Iterations[0]
        request = Request(sprint_object_id=iteration.cdb_object_id)
        request.json["cards"] = list(map(lambda x: x.cdb_object_id, cards))
        with UpdateCount():
            _change_cards(self.board, request)
            self.assertEqual(CALLS, 1)
            self.assertEqual(len(request.json["cards"]), 6)

    @mock.patch.object(internal, "get_collection_app", return_value=None)
    @mock.patch.object(internal, "opdata_view", return_value={})
    @mock.patch.object(internal, "_get_task_view", return_value={})
    def test_sprint_board_update_for_adjust_new_card_on_board(self, *args):
        "Update Board may only be called once by 'adjust_new_card_on_board'"
        self.prepare_for_board_update(SPRINT_BOARD_TYPE)
        request = Request()
        with UpdateCount():
            adjust_new_card_on_board(self.board, request)
            self.assertEqual(CALLS, 1)

    @mock.patch.object(internal, "get_collection_app", return_value=None)
    @mock.patch.object(internal, "opdata_view", return_value={})
    @mock.patch.object(internal, "_get_task_view", return_value={})
    def move_card(self, card, column_name, *args):
        request = Request()
        if column_name:
            row = self.get_row()
            column = self.get_column(column_name)
            request.json.update(
                column_object_id=column.cdb_object_id, row_object_id=row.cdb_object_id
            )
        else:
            iteration = self.get_iteration()
            request.json.update(sprint_object_id=iteration.cdb_object_id)
        with UpdateCount():
            _change_card(card, request)
            self.assertEqual(CALLS, 1)

    def test_sprint_board_update_after_status_change_action(self):
        "Update Board may only be called once after call of ChangeState on action"
        self.prepare_for_board_update(SPRINT_BOARD_TYPE)
        card = self.get_card(self.action_1_1)

        # move action into sprint
        self.move_card(card, None)
        # no changes on status
        self.check_status_entries()

        # move action into column DONE
        self.move_card(card, "DONE")
        # action has status 200
        self.check_status_entry(self.action_1_1, 200)
        self.check_status_entries()

    def test_sprint_board_update_after_status_change_issue(self):
        "Update Board may only be called once after call of ChangeState on issue"
        self.prepare_for_board_update(SPRINT_BOARD_TYPE)
        card_task_1 = self.get_card(self.task_1)
        card_task_2 = self.get_card(self.task_2)
        card_task_2_1 = self.get_card(self.task_2_1)
        card_issue_1 = self.get_card(self.issue_1)

        # check if card exists (task groups task_2 should not appear)
        self.assertTrue(bool(card_task_1))
        self.assertFalse(bool(card_task_2))
        self.assertTrue(bool(card_task_2_1))
        self.assertTrue(bool(card_issue_1))

        # move action into sprint
        self.move_card(card_task_1, None)
        self.move_card(card_task_2_1, None)
        self.move_card(card_issue_1, None)
        # no changes on status
        self.check_status_entries()

        # move issue into column DONE
        self.move_card(card_issue_1, "DONE")
        # evaluate changes on status
        self.check_status_entry(self.issue_1, 200)
        self.check_status_entry(self.task_1, 200)
        self.check_status_entry(self.task_2, 20)
        self.check_status_entry(self.task_2_1, 20)
        self.check_status_entries()


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
