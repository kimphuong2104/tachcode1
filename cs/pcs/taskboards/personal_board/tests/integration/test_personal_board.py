#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
import unittest

import mock
import pytest
from cdb import testcase, typeconversion
from cdb.constants import kOperationModify
from cdb.objects.operations import operation
from cdb.objects.org import User
from cs.actions import Action
from cs.taskboard.objects import Sprint, get_personal_board

from cs.pcs.issues import Issue
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.tests import common

LOGIN = "caddok"
LOGIN_OID = "99504583-76e1-11de-a2d5-986f0c508d59"  # oid of caddok
SUBJECT_PARAMS = {"subject_id": LOGIN, "subject_type": "Person"}
SPRINT_BOARD = "sprint_board"
INTERVAL_BOARD = "interval_board"
ACTION_0 = "Action_0"
ACTION_1 = "Action_1"
ISSUE_0 = "Issue_0"
ISSUE_1 = "Issue_1"
ISSUES = [ISSUE_0, ISSUE_1]
ACTIONS = [ACTION_0, ACTION_1]


def setUpModule():
    testcase.run_level_setup()


def _get_date_days_ago(days):
    date = datetime.date.today() - datetime.timedelta(days=int(days))
    return typeconversion.to_legacy_date_format(date)


@pytest.mark.integration
class PersonalBoardCardVisibilityCompletionDatesTestCase(testcase.RollbackTestCase):
    """
    Check Taskboard Card visibility on personal board depending on the
    completion dates of the associated objects (issues and actions).
    """

    def _setup_project_and_user(self):
        # create project with LOGIN as project manager
        self.user = User.KeywordQuery(personalnummer=LOGIN)
        self.prj = common.generate_project(**{"project_manager": LOGIN})

    def _setup_issues(self):
        # setup Project with a task, that has two issues assigned
        self.task = common.generate_task(self.prj, "myTask", **SUBJECT_PARAMS)
        self.issues = []
        for issue_name in ISSUES:
            iss = common.generate_issue(
                self.prj.cdb_project_id, self.task.task_id, issue_name, **SUBJECT_PARAMS
            )
            self.issues.append(iss)

    def _setup_actions(self):
        # setup Project with two actions
        self.actions = []
        for action_name in ACTIONS:
            act = common.generate_action(
                context_object=self.prj, name=action_name, **SUBJECT_PARAMS
            )
            self.actions.append(act)

    def _setup_board_for_project(self, board_type):
        self.board = common.create_taskboard(
            self.prj, board_type, **{"start_date": datetime.date.today()}
        )
        self.board.setupBoard()

    def _setup_board_for_project_task(self, board_type):
        self.board = common.create_taskboard(
            self.task, board_type, **{"start_date": datetime.date.today()}
        )
        self.board.setupBoard()

    def _move_cards(self, amount):
        # Get first iteration iteration
        iteration = self.board.Iterations[0]

        for x in range(amount):
            # Get card from the board
            card = self.board.Cards[x]
            # Move the two issue to the first iteration
            card.sprint_object_id = iteration.cdb_object_id

    def _start_iteration(self):
        # Mock on_taskboard_start_sprint_now to circumvent user input via dialog
        def _start_sprint(sprint, ctx):
            operation(
                kOperationModify,
                sprint,
                start_date=sprint.start_date,
                end_date=sprint.end_date,
            )
            sprint.Super(Sprint).on_taskboard_start_sprint_now(ctx)

        _start_sprint.__name__ = "on_taskboard_start_sprint_now"  # work around E073093

        # start iteration
        with mock.patch.object(
            Sprint,
            "on_taskboard_start_sprint_now",
            new=_start_sprint,
        ):
            operation("taskboard_start_sprint", self.board.Iterations[0])

    def _setup_personal_board(self):
        self.personal_board = get_personal_board(LOGIN_OID)
        self.personal_board.setupBoard()
        self.personal_board.Reload()

    def _setup_board_for_issues(self, board_type):
        self._setup_project_and_user()
        self._setup_issues()
        self.prj.ChangeState(Project.EXECUTION.status)  # alternative ChangeState(50)
        self._setup_board_for_project_task(board_type)
        self._move_cards(len(self.issues))
        self._start_iteration()

    def _setup_board_for_actions(self, board_type):
        self._setup_project_and_user()
        self._setup_actions()
        self.prj.ChangeState(Project.EXECUTION.status)  # alternative ChangeState(50)
        self._setup_board_for_project(board_type)
        self._move_cards(len(self.actions))
        self._start_iteration()

    def _check_personal_board(self, expected_ids, not_expected_ids):
        self._setup_personal_board()
        visible_card_ids = [
            v.context_object_id for v in self.personal_board.VisibleCards
        ]
        for exp_id in expected_ids:
            assert (
                exp_id in visible_card_ids
            ), f"expected card with id {exp_id} not in visible cards {str(visible_card_ids)}"
        for n_exp_id in not_expected_ids:
            assert (
                n_exp_id not in visible_card_ids
            ), f"not expected card with id {n_exp_id} in visible cards {str(visible_card_ids)}"

    def _complete_actions_some_time_ago(
        self,
        board_type,
        actions_to_mod,  # list of names
        expected_actions,  # list of names
        not_expected_actions,  # list of names
        date=None,
    ):
        """
        Setup Board and complete a number of actions with a protocol date
        """
        # setup project with actions assigned to the board of board_type and start the
        # iteration
        self._setup_board_for_actions(board_type)
        # complete actions
        for action in self.actions:
            action.ChangeState(Action.IN_WORK.status)
            action.ChangeState(Action.FINISHED.status)

        if date:
            date_without_time = date.split(" ")[0]
            # modify end date of actions
            for a in self.actions:
                if a.name in actions_to_mod:
                    a.end_time_act = date_without_time

        # check if actions with modified end date are not on the personal board
        self._check_personal_board(
            [a.cdb_object_id for a in self.actions if a.name in expected_actions],
            [a.cdb_object_id for a in self.actions if a.name in not_expected_actions],
        )

    def _complete_issues_some_time_ago(
        self,
        board_type,
        issues_to_mod,  # list of names
        expected_issues,  # list of names
        not_expected_issues,  # list of names
        date=None,
    ):
        """
        Setup Board and complete a number of issues with a protocol date
        """
        # setup project with issues assigned to the board of board_type and start the
        # iteration
        self._setup_board_for_issues(board_type)
        # complete issues
        for issue in self.issues:
            issue.ChangeState(Issue.COMPLETED.status)

        if date:
            # modify completion date of issues
            for i in self.issues:
                if i.issue_name in issues_to_mod:
                    i.completion_date = date

        # check if issues with modified protocol are not on the personal board
        self._check_personal_board(
            [i.cdb_object_id for i in self.issues if i.issue_name in expected_issues],
            [
                i.cdb_object_id
                for i in self.issues
                if i.issue_name in not_expected_issues
            ],
        )

    # TESTING ACTIONS

    def test_actions_on_sprint_board_visible_on_personal_board(self):
        """
        Actions are on a Sprint Board and are visible on the personal board
        """
        # setup project with actions assigned to the sprint board and start the
        # iteration
        self._setup_board_for_actions(SPRINT_BOARD)
        # check if all actions are on the personal board
        self._check_personal_board([a.cdb_object_id for a in self.actions], [])

    def test_actions_on_interval_board_visible_on_personal_board(self):
        """
        Actions are on an interval Board and are visible on the personal board
        """
        # setup project with actions assigned to the sprint board and start the
        # iteration
        self._setup_board_for_actions(INTERVAL_BOARD)
        # check if all actions are on the personal board
        self._check_personal_board([a.cdb_object_id for a in self.actions], [])

    def test_completed_actions_on_interval_board_01(self):
        """
        On Interval Board: - Complete both actions
                                  - modify no protocol date,
                                  - expect both actions to be on the personal board
        """
        self._complete_actions_some_time_ago(INTERVAL_BOARD, [], ACTIONS, [])

    def test_completed_actions_on_interval_board_02(self):
        """
        On Interval Board: - Complete both actions
                           - set first's protocol date to over a week ago,
                           - expect second action to be on the personal board
        """
        date = _get_date_days_ago(7)
        actions_to_mod = [ACTION_0]
        expected_actions = [ACTION_1]
        self._complete_actions_some_time_ago(
            INTERVAL_BOARD, actions_to_mod, expected_actions, actions_to_mod, date
        )

    def test_completed_actions_on_interval_board_03(self):
        """
        On Interval Board: - Complete both actions
                           - set first's protocol date to under a week ago,
                           - expect both actions to be on the personal board
        """
        date = _get_date_days_ago(6)
        actions_to_mod = [ACTION_0]
        self._complete_actions_some_time_ago(
            INTERVAL_BOARD, actions_to_mod, ACTIONS, [], date
        )

    def test_completed_actions_on_interval_board_04(self):
        """
        On Interval Board: - Complete both actions
                           - set both's protocol date to over a week ago,
                           - expect no action to be on the personal board
        """
        date = _get_date_days_ago(7)
        self._complete_actions_some_time_ago(INTERVAL_BOARD, ACTIONS, [], ACTIONS, date)

    def test_completed_actions_on_interval_board_05(self):
        """
        On Interval Board: - Complete both actions
                           - set both's protocol date to under a week ago,
                           - expect both action to be on the personal board
        """
        date = _get_date_days_ago(6)
        self._complete_actions_some_time_ago(INTERVAL_BOARD, ACTIONS, ACTIONS, [], date)

    def test_completed_actions_on_sprint_board_01(self):
        """
        On Sprint Board: - Complete both actions
                           - modify no protocol date,
                           - expect both actions to be on the personal board
        """
        self._complete_actions_some_time_ago(SPRINT_BOARD, [], ACTIONS, [])

    def test_completed_actions_on_sprint_board_02(self):
        """
        On Sprint Board: - Complete both actions
                           - set first's protocol date to over a week ago,
                           - expect second action to be on the personal board
        """
        date = _get_date_days_ago(7)
        actions_to_mod = [ACTION_0]
        expected_actions = [ACTION_1]
        self._complete_actions_some_time_ago(
            SPRINT_BOARD, actions_to_mod, expected_actions, actions_to_mod, date
        )

    def test_completed_actions_on_sprint_board_03(self):
        """
        On Sprint Board: - Complete both actions
                           - set first's protocol date to under a week ago,
                           - expect both actions to be on the personal board
        """
        date = _get_date_days_ago(6)
        actions_to_mod = [ACTION_0]
        self._complete_actions_some_time_ago(
            SPRINT_BOARD, actions_to_mod, ACTIONS, [], date
        )

    def test_completed_actions_on_sprint_board_04(self):
        """
        On Sprint Board: - Complete both actions
                           - set both's protocol date to over a week ago,
                           - expect no action to be on the personal board
        """
        date = _get_date_days_ago(7)
        self._complete_actions_some_time_ago(SPRINT_BOARD, ACTIONS, [], ACTIONS, date)

    def test_completed_actions_on_sprint_board_05(self):
        """
        On Sprint Board: - Complete both actions
                           - set both's protocol date to under a week ago,
                           - expect both action to be on the personal board
        """
        date = _get_date_days_ago(6)
        self._complete_actions_some_time_ago(SPRINT_BOARD, ACTIONS, ACTIONS, [], date)

    # TESTING ISSUES

    def test_issues_on_sprint_board_visible_on_personal_board(self):
        """
        Issues are on a Sprint Board and are visible on the personal board
        """
        # setup project with issues assigned to the sprint board and start the
        # iteration
        self._setup_board_for_issues(SPRINT_BOARD)
        # check if all issues are on the personal board
        self._check_personal_board([i.cdb_object_id for i in self.issues], [])

    def test_issues_on_interval_board_visible_on_personal_board(self):
        """
        Issues are on an interval Board and are visible on the personal board
        """
        # setup project with issues assigned to the interval board and start the
        # iteration
        self._setup_board_for_issues(INTERVAL_BOARD)
        # check if all issues are on the personal board
        self._check_personal_board([i.cdb_object_id for i in self.issues], [])

    def test_completed_issues_on_interval_board_01(self):
        """
        On Interval Board: - Complete both issues
                           - modify no protocol date,
                           - expect both issues to be on the personal board
        """
        self._complete_issues_some_time_ago(INTERVAL_BOARD, [], ISSUES, [])

    def test_completed_issues_on_interval_board_02(self):
        """
        On Interval Board: - Complete both issues
                           - set first's protocol date to over a week ago,
                           - expect second issue to be on the personal board
        """
        date = _get_date_days_ago(7)
        issues_to_mod = [ISSUE_0]
        expected_issues = [ISSUE_1]
        self._complete_issues_some_time_ago(
            INTERVAL_BOARD, issues_to_mod, expected_issues, issues_to_mod, date
        )

    def test_completed_issues_on_interval_board_03(self):
        """
        On Interval Board: - Complete both issues
                           - set first's protocol date to under a week ago,
                           - expect both issues to be on the personal board
        """
        date = _get_date_days_ago(6)
        issues_to_mod = [ISSUE_0]
        self._complete_issues_some_time_ago(
            INTERVAL_BOARD, issues_to_mod, ISSUES, [], date
        )

    def test_completed_issues_on_interval_board_04(self):
        """
        On Interval Board: - Complete both issues
                           - set both's protocol date to over a week ago,
                           - expect no issue to be on the personal board
        """
        date = _get_date_days_ago(7)
        self._complete_issues_some_time_ago(INTERVAL_BOARD, ISSUES, [], ISSUES, date)

    def test_completed_issues_on_interval_board_05(self):
        """
        On Interval Board: - Complete both issues
                           - set both's protocol date to under a week ago,
                           - expect both issues to be on the personal board
        """
        date = _get_date_days_ago(6)
        self._complete_issues_some_time_ago(INTERVAL_BOARD, ISSUES, ISSUES, [], date)

    def test_completed_issues_on_sprint_board_01(self):
        """
        On Sprint Board: - Complete both issues
                           - modify no protocol date,
                           - expect both issues to be on the personal board
        """
        self._complete_issues_some_time_ago(SPRINT_BOARD, [], ISSUES, [])

    def test_completed_issues_on_sprint_board_02(self):
        """
        On Sprint Board: - Complete both issues
                           - set first's protocol date to over a week ago,
                           - expect second issue to be on the personal board
        """
        date = _get_date_days_ago(7)
        issues_to_mod = [ISSUE_0]
        expected_issues = [ISSUE_1]
        self._complete_issues_some_time_ago(
            SPRINT_BOARD, issues_to_mod, expected_issues, issues_to_mod, date
        )

    def test_completed_issues_on_sprint_board_03(self):
        """
        On Sprint Board: - Complete both issues
                           - set first's protocol date to under a week ago,
                           - expect both issues to be on the personal board
        """
        date = _get_date_days_ago(6)
        issues_to_mod = [ISSUE_0]
        self._complete_issues_some_time_ago(
            SPRINT_BOARD, issues_to_mod, ISSUES, [], date
        )

    def test_completed_issues_on_sprint_board_04(self):
        """
        On Sprint Board: - Complete both issues
                           - set both's protocol date to over a week ago,
                           - expect no issues to be on the personal board
        """
        date = _get_date_days_ago(7)
        self._complete_issues_some_time_ago(SPRINT_BOARD, ISSUES, [], ISSUES, date)

    def test_completed_issues_on_sprint_board_05(self):
        """
        On Sprint Board: - Complete both issues
                           - set both's protocol date to under a week ago,
                           - expect both issues to be on the personal board
        """
        date = _get_date_days_ago(6)
        self._complete_issues_some_time_ago(SPRINT_BOARD, ISSUES, ISSUES, [], date)

    def test_complete_issues_twice_on_sprint_board(self):
        """
        On Sprint Board: - Complete both issues twice and
                           set first's completion date to over a week ago
                           after second status change to completion
                         - expect only second issue to be on the personal board
        """

        # setup project with issues assigned to a sprint board and start the
        # iteration
        self._setup_board_for_issues(SPRINT_BOARD)

        # complete issues twice by changing states multiple times and
        # changing protocol dates after second status change to completion
        for issue in self.issues:
            issue.ChangeState(Issue.COMPLETED.status)
        self.task.ChangeState(Task.EXECUTION.status)
        for issue in self.issues:
            issue.ChangeState(Issue.EXECUTION.status)
        for issue in self.issues:
            issue.ChangeState(Issue.COMPLETED.status)

        # modify completion date of issues
        date = _get_date_days_ago(7)
        for i in self.issues:
            if i.issue_name == ISSUE_0:
                i.completion_date = date

        # check if only second issue is on the personal board
        self._check_personal_board(
            [i.cdb_object_id for i in self.issues if i.issue_name == ISSUE_1],
            [i.cdb_object_id for i in self.issues if i.issue_name == ISSUE_0],
        )

    def test_complete_issues_twice_on_interval_board(self):
        """
        On Interval Board: - Complete both issues twice and\
                            after second status change to completion\
                            set first's completion date to over a week ago\
                           - expect only second issue to be on the personal board
        """

        # setup project with issues assigned to a interval board and start the
        # iteration
        self._setup_board_for_issues(INTERVAL_BOARD)

        # complete issues twice by changing states multiple times and
        # change completion date of first issue after second status change
        for issue in self.issues:
            issue.ChangeState(Issue.COMPLETED.status)
        self.task.ChangeState(Task.EXECUTION.status)
        for issue in self.issues:
            # Note: Resetting to non final status resets completion date
            issue.ChangeState(Issue.EXECUTION.status)
        for issue in self.issues:
            issue.ChangeState(Issue.COMPLETED.status)

        # modify completion date of issues
        date = _get_date_days_ago(7)
        for i in self.issues:
            if i.issue_name == ISSUE_0:
                i.completion_date = date

        # check if only second issue is on the personal board
        self._check_personal_board(
            [i.cdb_object_id for i in self.issues if i.issue_name == ISSUE_1],
            [i.cdb_object_id for i in self.issues if i.issue_name == ISSUE_0],
        )


if __name__ == "__main__":
    unittest.main()
