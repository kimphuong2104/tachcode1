# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
import datetime

from cdb import testcase
from cdb import util

from cs.taskboard.constants import COLUMN_READY, COLUMN_DOING, COLUMN_DONE
from cs.taskboard.personal_board import PERSONAL_BOARD_TYPE
from cs.taskboardtest.tests.common import create_board_user
from cs.taskboardtest.tests.common import get_board_template
from cs.taskboardtest.tests.common import create_personal_board
from cs.taskboardtest.tests.common import SetupPersonalBoardTest
from cs.taskboardtest.tests.common import SetupPersonalBoardWithSprintTest
from cs.taskboard.objects import get_personal_board

try:
    from cs.taskboardtest.objects import Context as BoardContext, Foo
except ImportError:
    raise unittest.SkipTest("Test requires cs.taskboardtest")


class TestExistingTemplate(testcase.RollbackTestCase):
    """
    Checks whether the template exists.
    """

    def setUp(self):
        super(TestExistingTemplate, self).setUp()
        self.board_template = get_board_template(PERSONAL_BOARD_TYPE)

    def test_template_exists(self):
        self.assertIsNotNone(self.board_template, "Template not found.")

    def test_number_of_columns(self):
        self.assertEqual(len(self.board_template.Columns), 3,
                         "The template does not have three columns")

    def test_number_of_rows(self):
        self.assertEqual(len(self.board_template.Rows), 1,
                         "The template does not have one row")

    def test_number_of_iterations(self):
        self.assertEqual(len(self.board_template.Iterations), 0,
                         "The template has iterations")

    def test_number_of_members(self):
        self.assertEqual(len(self.board_template.TeamMembers), 0,
                         "The template has members")

    def test_number_of_cards(self):
        self.assertEqual(len(self.board_template.Cards), 0,
                         "The template has cards")

    def test_context(self):
        self.assertFalse(self.board_template.context_object_id,
                         "The template has a context object")

    def test_duration(self):
        self.assertTrue(not self.board_template.interval_length,
                        "The template does not have a duration")

    def test_time_unit(self):
        self.assertTrue(not self.board_template.interval_name,
                        "The template does not have a time unit")

    def test_import_board_adapter(self):
        module_name = ".".join(self.board_template.board_api.split(".")[:-1])
        cls_name = self.board_template.board_api.split(".")[-1]
        try:
            loaded_module = __import__(module_name, globals(), locals(), [cls_name])
            cls = getattr(loaded_module, cls_name)
        except ImportError:
            self.assertTrue(False, "Cannot import board adpater")


class TestCreatePersonalBoard(testcase.RollbackTestCase):
    """
    A class to test creating Personal Task Board.
    """

    def setUp(self):
        super(TestCreatePersonalBoard, self).setUp()
        self.board_template = get_board_template(PERSONAL_BOARD_TYPE)
        self.board_context = BoardContext.Create(title="Test Board Context")
        self.content_types = Foo._getClassname()

    def test_create_personal_board(self):
        self.test_person = create_board_user("tp1")  # Test Person#1
        board = get_personal_board(self.test_person.cdb_object_id)
        self.assertIsNotNone(board, "New Personal Board not found.")


class TestPersonalBoardCurrentPeriod(SetupPersonalBoardTest):
    """
    A class to test aggregation of tasks for Personal Board.
    Only tasks of the current period have to be shown.
    The tasks do not have any project board context.
    """
    def setUp(self):
        super(TestPersonalBoardCurrentPeriod, self).setUp()

    def test_cards_for_unassigned_tasks(self):
        with util.SkipAccessCheck():
            # create tasks
            self.create_tasks()

            # calling board URL to update board and create cards
            self.request_board(self.personal_board)

        should_cards = 2  # ready, doing
        self.assertEqual(len(self.personal_board.Cards), should_cards,
                         "Personal Board should contain %i cards instead of %s" % (
                             should_cards, len(self.personal_board.Cards)))
        visible_cards = 2  # ready, doing
        self.assertEqual(len(self.personal_board.VisibleCards), visible_cards,
                         "Personal Board should show %i visible cards instead of %s" % (
                             visible_cards, len(self.personal_board.VisibleCards)))


class TestPersonalBoardWithSprintCurrentPeriod(SetupPersonalBoardWithSprintTest):
    """
    A class to test aggregation of tasks for Personal Board.
    Only tasks of the current period have to be shown.
    The tasks do have sprint board context.
    """

    def setUp(self):
        super(TestPersonalBoardWithSprintCurrentPeriod, self).setUp()

    def test_cards_for_tasks_assigned_to_backlog(self):
        with util.SkipAccessCheck():
            # create tasks
            self.create_sprint_tasks()

            # calling board URL to update board and create cards
            self.request_board(self.sprint_board)
            self.request_board(self.personal_board)

        should_cards = 0  # tasks are assigned to sprint backlog
        self.assertEqual(len(self.personal_board.Cards), should_cards,
                         "Personal Board contains %i cards that "
                         "are assigned to Sprint Board Backlog" % (
                             len(self.personal_board.Cards)))

    def test_cards_for_tasks_assigned_to_sprint(self):
        with util.SkipAccessCheck():
            # create tasks
            self.create_sprint_tasks()

            # calling board URL to update board and create cards
            self.request_board(self.sprint_board)

            # assign cards to iteration
            sprint = self.sprint_board.Iterations[0]
            for card in self.sprint_board.Cards:
                self.assign_iteration(card, sprint)

            if sprint != self.sprint_board.ActiveIteration:
                sprint.ChangeState(50)
                self.sprint_board.Reload()

            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")

            # calling board URL to update board and create cards
            self.request_board(self.personal_board)

        should_cards = 4  # new, ready, doing, done
        self.assertEqual(len(self.personal_board.Cards), should_cards,
                         "Personal Board should contain %i cards instead of %s" % (
                             should_cards, len(self.personal_board.Cards)))
        visible_cards = 4  # new, ready, doing
        self.assertEqual(len(self.personal_board.VisibleCards), visible_cards,
                         "Personal Board should show %i visible cards instead of %s" % (
                             visible_cards, len(self.personal_board.VisibleCards)))


class TestMoveCard(SetupPersonalBoardTest):
    """
    A class to test move cards of tasks without project board in current interval
    of Personal Board.
    """

    def setUp(self):
        super(TestMoveCard, self).setUp()
        self.board_adapter = self.personal_board.getAdapter()

    def test_move_between_columns(self):
        with util.SkipAccessCheck():
            # create tasks
            self.task_test = self.create_task(status=10,
                                              target_date=datetime.datetime.today())

            # calling board URL to update board and create cards
            self.request_board(self.personal_board)

        # move card between columns from
        card = self.get_card(self.personal_board, self.task_test)
        self.assertIsNotNone(card, "Card has not been found")

        # move card between columns from READY to DOING
        self._move_between_columns(card, COLUMN_DOING, 100)

        # move card between columns from DOING to DONE
        self._move_between_columns(card, COLUMN_DONE, 200)

        # move card between columns from DONE to DOING
        self._move_between_columns(card, COLUMN_DOING, 100)

        # move card between columns from DOING to READY
        self._move_between_columns(card, COLUMN_READY, 10)

    def _move_between_columns(self, card, column_type, status):
        column = self.board_adapter.get_column_by_type(column_type)
        self.move_to_column(self.board_adapter, card, column_type)
        self.task_test.Reload()
        card = self.get_card(self.personal_board, self.task_test)

        self.assertIsNotNone(card, "Card has not been found")
        self.assertEqual(card.column_object_id, column.cdb_object_id,
                         "Task should be in column '%s'" % column_type)
        self.assertEqual(self.task_test.status, status,
                         "Task status should be set to %s (column '%s')"
                         % (status, column_type))


@unittest.SkipTest
class TestPersonalCardsRanking(SetupPersonalBoardTest):
    """FIXME"""
    pass


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
