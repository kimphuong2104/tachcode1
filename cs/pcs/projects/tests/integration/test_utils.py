#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime

import mock
import pytest
from cdb import sig, testcase, ue
from cdb.objects.operations import operation
from cs.taskboard.objects import Sprint
from cs.taskboard.sprint_board import SPRINT_BOARD_TYPE

from cs.pcs import projects
from cs.pcs.projects import utils
from cs.pcs.projects.tests import common


@sig.connect(projects.tasks.Task, "state_change", "pre")
def throw_exception(self, ctx):
    if self.task_name == "task_throw_exception":
        raise ue.Exception("task_throw_exception")


@pytest.mark.integration
class UtilsRegisteringObjects(testcase.RollbackTestCase):
    def setup_board(self, obj, board_type):
        self.board = common.create_taskboard(obj, board_type)
        self.iteration = self.board.NextIteration
        self.board.updateBoard()
        self.board.Cards.Update(sprint_object_id=self.iteration.cdb_object_id)

    def start_sprint(self):
        # calling directly on class Iteration to avoid evaluation of dialog
        super(Sprint, self.iteration).on_taskboard_start_sprint_now(None)

    @staticmethod
    def refresh_data(*args):
        for obj in args:
            obj.Reload()

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_00(self, *args):
        """
        Change project status by CDB_Workflow --> two tasks fail on
        status change due to status or exception.
        """
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task_throw_exception")
        t3 = common.generate_task(project, "task3")
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        t1.status = 20
        operation("CDB_Workflow", project)

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {project.cdb_object_id: (0, 50), t3.cdb_object_id: (0, 20)}
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_01(self, *args):
        "Change project status by ChangeState --> no task fails on status change"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task2")
        t3 = common.generate_task(project, "task3")
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.ChangeState(50)

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {
                project.cdb_object_id: (0, 50),
                t1.cdb_object_id: (0, 20),
                t2.cdb_object_id: (0, 20),
                t3.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_02(self, *args):
        "Change project status by ChangeState --> one task fails on status change" " due to status"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task2")
        t3 = common.generate_task(project, "task3")
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        t2.status = 20
        project.ChangeState(50)

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {
                project.cdb_object_id: (0, 50),
                t1.cdb_object_id: (0, 20),
                t3.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_03(self, *args):
        "Change project status by ChangeState --> one task fails on status change" " due to exception"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task_throw_exception")
        t3 = common.generate_task(project, "task3")
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.ChangeState(50)

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {
                project.cdb_object_id: (0, 50),
                t1.cdb_object_id: (0, 20),
                t3.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_04(self, *args):
        "Change top task status by ChangeState --> no task fails on status change"
        # create test data
        project = common.generate_project(is_group=1)
        top = common.generate_task(project, "top_task1")
        t1 = common.generate_task(project, "task1", parent_task=top.task_id)
        t2 = common.generate_task(project, "task2", parent_task=top.task_id)
        t3 = common.generate_task(project, "task3", parent_task=top.task_id)
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(top.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.status = 50
        t3.status = 20
        top.ChangeState(20)

        # post check
        self.refresh_data(project, top, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(top.status, 20)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {
                top.cdb_object_id: (0, 20),
                t1.cdb_object_id: (0, 20),
                t2.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_05(self, *args):
        "Change top task status by ChangeState --> one task fails on status change" " due to status"
        # create test data
        project = common.generate_project(is_group=1)
        top = common.generate_task(project, "top_task1")
        t1 = common.generate_task(project, "task1", parent_task=top.task_id)
        t2 = common.generate_task(project, "task2", parent_task=top.task_id)
        t3 = common.generate_task(project, "task3", parent_task=top.task_id)
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(top.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.status = 50
        t3.status = 20
        top.ChangeState(20)

        # post check
        self.refresh_data(project, top, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(top.status, 20)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        project.do_status_updates.assert_called_once_with(
            {
                top.cdb_object_id: (0, 20),
                t1.cdb_object_id: (0, 20),
                t2.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_06(self, *args):
        "Change top task status by ChangeState --> one task fails on status change" " due to exception"
        # create test data
        project = common.generate_project(is_group=1)
        top = common.generate_task(project, "top_task1")
        t1 = common.generate_task(project, "task1", parent_task=top.task_id)
        t2 = common.generate_task(project, "task2", parent_task=top.task_id)
        t3 = common.generate_task(
            project, "task_throw_exception", parent_task=top.task_id
        )
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(top.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.status = 50
        top.ChangeState(20)

        # post check
        self.refresh_data(project, top, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(top.status, 20)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 0)
        project.do_status_updates.assert_called_once_with(
            {
                top.cdb_object_id: (0, 20),
                t1.cdb_object_id: (0, 20),
                t2.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_07(self, *args):
        "Change predecessor task status by ChangeState --> " "no task fails on status change"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task2")
        common.generate_task_relation(t1, t2)
        project.recalculate()

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)

        # execute test
        project.status = 50
        t1.status = 50
        t1.ChangeState(200)

        # post check
        self.refresh_data(project, t1, t2)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 200)
        self.assertEqual(t2.status, 20)
        project.do_status_updates.assert_called_once_with(
            {t1.cdb_object_id: (50, 200), t2.cdb_object_id: (0, 20)}
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_08(self, *args):
        "Change tasks status by starting sprint --> " "all three task status will be changed"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task2")
        t3 = common.generate_task(project, "task3")
        project.recalculate()
        self.setup_board(project, SPRINT_BOARD_TYPE)

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.status = 50
        self.start_sprint()

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        self.assertEqual(len(self.iteration.Cards), 3)
        project.do_status_updates.assert_called_once_with(
            {
                self.iteration.cdb_object_id: (None, 50),
                t1.cdb_object_id: (0, 20),
                t2.cdb_object_id: (0, 20),
                t3.cdb_object_id: (0, 20),
            }
        )

    @mock.patch.object(projects.Project, "do_status_updates")
    def test_registering_09(self, *args):
        "Change tasks status by starting sprint --> " "only two of three task status will be changed"
        # create test data
        project = common.generate_project(is_group=1)
        t1 = common.generate_task(project, "task1")
        t2 = common.generate_task(project, "task2")
        t3 = common.generate_task(project, "task3")
        project.recalculate()
        self.setup_board(project, SPRINT_BOARD_TYPE)

        # pre check
        self.assertEqual(project.status, 0)
        self.assertEqual(t1.status, 0)
        self.assertEqual(t2.status, 0)
        self.assertEqual(t3.status, 0)

        # execute test
        project.status = 50
        t1.status = 20
        self.start_sprint()

        # post check
        self.refresh_data(project, t1, t2, t3)
        self.assertEqual(project.status, 50)
        self.assertEqual(t1.status, 20)
        self.assertEqual(t2.status, 20)
        self.assertEqual(t3.status, 20)
        self.assertEqual(len(self.iteration.Cards), 3)
        project.do_status_updates.assert_called_once_with(
            {
                self.iteration.cdb_object_id: (None, 50),
                t1.cdb_object_id: (20, 20),
                t2.cdb_object_id: (0, 20),
                t3.cdb_object_id: (0, 20),
            }
        )


@pytest.mark.integration
class UtilsCalendarIndex(testcase.RollbackTestCase):

    # Standard Calendar valid from 2004-01-01 until 2029-12-31
    __calendar_profile_id__ = "1cb4cf41-0f40-11df-a6f9-9435b380e702"

    def test_get_calendar_index_for_dates_date_out_of_profile(self):
        date = datetime.date(1999, 1, 1)
        with self.assertRaises(ue.Exception):
            utils.get_calendar_index_for_dates(
                self.__calendar_profile_id__, [(date, True)]
            )

    def test_get_calendar_index_for_dates(self):
        date1 = datetime.date(2023, 3, 1)  # We: <late/early>_work_idx: 5000
        date2 = datetime.date(2023, 1, 1)  # Su: late: 4958, early: 4957
        self.assertListEqual(
            [5000, 4958],
            utils.get_calendar_index_for_dates(
                self.__calendar_profile_id__,
                [
                    (date1, False),  # get early_work_idx
                    (date2, True),  # get late_work_idx
                ],
            ),
        )
