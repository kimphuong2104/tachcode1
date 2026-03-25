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

from cdb import testcase
from cdb import util

from cs.taskboard.constants import COLUMN_READY, COLUMN_DOING, COLUMN_DONE
from cs.taskboard.interval_board import INTERVAL_BOARD_TYPE
from cs.taskboardtest.tests.common import get_board_template
from cs.taskboardtest.tests.common import create_board_for_context
from cs.taskboardtest.tests.common import SetupIntervalBoardTest

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
        self.board_template = get_board_template(INTERVAL_BOARD_TYPE)

    def test_template_exists(self):
        self.assertTrue(self.board_template, " Template not found.")

    def test_number_of_columns(self):
        self.assertEqual(len(self.board_template.Columns), 3, "The template does not have three columns")

    def test_number_of_rows(self):
        self.assertEqual(len(self.board_template.Rows), 1, "The template does not have one row")

    def test_number_of_iterations(self):
        self.assertEqual(len(self.board_template.Iterations), 0, "The template has iterations")

    def test_number_of_members(self):
        self.assertEqual(len(self.board_template.TeamMembers), 0, "The template has members")

    def test_number_of_cards(self):
        self.assertEqual(len(self.board_template.Cards), 0, "The template has cards")

    def test_context(self):
        self.assertFalse(self.board_template.context_object_id, "The template has a context object")

    def test_duration(self):
        self.assertTrue(self.board_template.interval_length, "The template does not have a duration")

    def test_time_unit(self):
        self.assertTrue(self.board_template.interval_name, "The template does not have a time unit")

    def test_import_board_adapter(self):
        module_name = ".".join(self.board_template.board_api.split(".")[:-1])
        cls_name = self.board_template.board_api.split(".")[-1]
        try:
            loaded_module = __import__(module_name, globals(), locals(), [cls_name])
            cls = getattr(loaded_module, cls_name)
        except ImportError:
            self.assertTrue(False, "Cannot import board adpater")


class TestCreateIntervalBoard(testcase.RollbackTestCase):
    """
    A class to test creating Interval Task Board.
    """
    def setUp(self):
        super(TestCreateIntervalBoard, self).setUp()
        self.board_template = get_board_template(INTERVAL_BOARD_TYPE)
        self.board_context = BoardContext.Create(title="Test Board Context")
        self.content_types = Foo._getClassname()

    def test_create_interval_board(self):
        board = create_board_for_context(
            self.board_context, self.board_template, content_types=self.content_types)
        self.assertIsNotNone(board)
        self.assertEqual(len(board.Iterations), 1,
                         "New Interval Board should have 1 Interval.")


class TestBoardBacklogNewCards(SetupIntervalBoardTest):
    """
    A class to test manage existing Interval Task Board containing new cards
    without interval assignments.
    """

    def setUp(self):
        super(TestBoardBacklogNewCards, self).setUp()
        self.create_interval_tasks()

    def test_no_active_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration:
                self.interval_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.interval_board.ActiveIteration,
                              "There should not be an active interval")
            # calling board URL to update board
            self.request_board(self.interval_board)

        should_cards = 4  # new, ready, doing, done
        actual_cards = len(self.interval_board.Cards)
        self.assertEqual(actual_cards, should_cards,
                         "Board should contains %i cards instead of %i" %
                         (should_cards, actual_cards))
        visible_cards = 3  # new, ready, doing
        self.assertEqual(len(self.interval_board.VisibleCards), visible_cards,
                         "Board should shows %i cards instead of %i" %
                         (visible_cards, actual_cards))
        card = self.get_card(self.interval_board, self.interval_task_new)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_doing)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_done)
        self.assertEqual(card.is_hidden, 1, "Done task should be hidden in board backlog")

    def test_with_active_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration is None:
                self.interval_board.Iterations[0].ChangeState(50)
            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            # calling board URL to update board
            self.request_board(self.interval_board)

        should_cards = 4  # new, ready, doing, done
        self.assertEqual(len(self.interval_board.Cards), should_cards,
                         "Opening Board and it should be updated and contains %i cards" %
                         should_cards)
        visible_cards = 3  # new, ready, doing
        self.assertEqual(len(self.interval_board.VisibleCards), visible_cards,
                         "Opening Board and it should be updated and shows %i cards" %
                         visible_cards)
        card = self.get_card(self.interval_board, self.interval_task_new)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_doing)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        card = self.get_card(self.interval_board, self.interval_task_done)
        self.assertEqual(card.is_hidden, 1, "Done task should be hidden in board backlog")


class TestBoardBacklogExistingCards(SetupIntervalBoardTest):
    """
    A class to test manage existing Interval Task Board containing existing cards
    without interval assignments.
    """

    def setUp(self):
        super(TestBoardBacklogExistingCards, self).setUp()

    def test_no_active_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration:
                self.interval_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.interval_board.ActiveIteration,
                              "There should not be an active interval")
            self.interval_task_test = self.create_interval_task(status=0)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "New task should be visible.")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "Ready task should be visible.")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "Doing task should be visible.")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        # Then this card should be disappeared
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertIsNotNone(card, "Done task should be found on board")
        self.assertEqual(card.sprint_object_id, "", "Done task should be in board backlog")
        self.assertEqual(card.is_hidden, 1, "Done task should not be visible.")

    def test_with_active_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration is None:
                self.interval_board.Iterations[0].ChangeState(50)
            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            self.interval_task_test = self.create_interval_task(status=0)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "New task should be visible.")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "Ready task should be visible.")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")
        self.assertEqual(card.is_hidden, 0, "Doing task should be visible.")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        # Then this card should be disappeared
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertIsNotNone(card, "Done task should be found on board")
        self.assertEqual(card.sprint_object_id, "", "Done task should be in board backlog")
        self.assertEqual(card.is_hidden, 1, "Done task should not be visible.")


class TestIntervalAssignment(SetupIntervalBoardTest):
    """
    A class to test manage existing Interval Task Board containing cards with interval
    assignments.
    """

    def setUp(self):
        super(TestIntervalAssignment, self).setUp()
        self.board_adapter = self.interval_board.getAdapter()

    def test_no_active_interval(self):
        with util.SkipAccessCheck():
            self.interval = self.interval_board.Iterations[0]
            if self.interval_board.ActiveIteration:
                self.interval_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.interval_board.ActiveIteration,
                              "There should not be an active interval")
            self.interval_task_test = self.create_interval_task(status=0)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        self.assign_iteration(card, self.interval)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card should be assigned to specified interval")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to specified interval")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of doing task should keep assigned to specified interval")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to specified interval")

    def test_with_active_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration is None:
                self.interval = self.interval_board.Iterations[0]
                self.interval.ChangeState(50)
            else:
                self.interval = self.interval_board.ActiveIteration

            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            self.interval_task_test = self.create_interval_task(status=0)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        self.assign_iteration(card, self.interval)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card should be assigned to specified interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "New task should be in Ready column")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to specified interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "Ready task should be in Ready column")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of doing task should keep assigned to specified interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Doing task should be in Doing column")

        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to specified interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DONE).cdb_object_id,
                         "Done task should be in Done column")


class TestCompletedIntervalAssignment(SetupIntervalBoardTest):
    """
    A class to test manage existing Interval Task Board containing cards with interval
    assignments.
    """

    def setUp(self):
        super(TestCompletedIntervalAssignment, self).setUp()
        self.board_adapter = self.interval_board.getAdapter()

    def test_completed_interval(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration is None:
                self.interval = self.interval_board.Iterations[0]
                self.interval.ChangeState(50)
            else:
                self.interval = self.interval_board.ActiveIteration

            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            self.interval_task_test = self.create_interval_task(status=100)
            # not completed task
            self.interval_task_ready = self.create_interval_task(status=10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assign_iteration(card, self.interval)
        # Card with ready task
        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assign_iteration(card_ready, self.interval)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card should be assigned to specified interval")

        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card with ready task should be assigned to specified interval")

        # Change the task of new card to "Done"
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to specified interval")

        # complete iteration
        with util.SkipAccessCheck():
            self.interval.ChangeState(200)
            self.request_board(self.interval_board)

        self.assertTrue(self.interval.is_completed(),
                        "Interval should be set to completed")
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to completed interval")

        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         "",
                         "Card with ready task should be moved back to backlog")


class TestCompletedIntervalAssignmentWithOpenIteration(SetupIntervalBoardTest):
    """
    A class to test interval assignments of cards on interval board with both completed
    and open iterations.
    """

    def setUp(self):
        super(TestCompletedIntervalAssignmentWithOpenIteration, self).setUp()
        self.board_adapter = self.interval_board.getAdapter()

    def test_assignments(self):
        with util.SkipAccessCheck():
            self.create_interval(self.interval_board)
            self.interval = self.interval_board.Iterations[0]
            self.interval_open = self.interval_board.Iterations[1]
            self.interval.ChangeState(50)

            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            self.interval_task_test = self.create_interval_task(status=100)
            # not completed task
            self.interval_task_ready = self.create_interval_task(status=10)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assign_iteration(card, self.interval)
        # Card with ready task
        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assign_iteration(card_ready, self.interval)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card should be assigned to specified interval")

        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card with ready task should be assigned to specified interval")

        # Change the task of new card to "Done"
        with util.SkipAccessCheck():
            self.interval_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to specified interval")

        # complete iteration
        with util.SkipAccessCheck():
            self.interval.ChangeState(200)
            self.request_board(self.interval_board)

        self.assertTrue(self.interval.is_completed(),
                        "Interval should be set to completed")
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of done task should keep assigned to completed interval")

        card_ready = self.get_card(self.interval_board, self.interval_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.interval_open.cdb_object_id,
                         "Card with ready task should be moved to next open iteration")


class TestMoveCard(SetupIntervalBoardTest):
    """
    A class to test move cards in current interval.
    """

    def setUp(self):
        super(TestMoveCard, self).setUp()
        self.board_adapter = self.interval_board.getAdapter()

    def test_move_between_columns(self):
        with util.SkipAccessCheck():
            if self.interval_board.ActiveIteration is None:
                self.interval = self.interval_board.Iterations[0]
                self.interval.ChangeState(50)
            else:
                self.interval = self.interval_board.ActiveIteration

            self.assertIsNotNone(self.interval_board.ActiveIteration,
                                 "There should be an active interval")
            self.interval_task_test = self.create_interval_task(status=0)
            # calling board URL to update board
            self.request_board(self.interval_board)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assign_iteration(card, self.interval)

        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card should be assigned to current interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "New task should be in Ready column")

        # move card between columns

        self.move_to_column(self.board_adapter, card, COLUMN_DOING)
        self.interval_task_test.Reload()
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to current interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Task should be in Doing column")
        self.assertEqual(self.interval_task_test.status,
                         100,
                         "Task status should be set to Doing")

        self.move_to_column(self.board_adapter, card, COLUMN_DONE)
        self.interval_task_test.Reload()
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to current interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DONE).cdb_object_id,
                         "Task should be in Done column")
        self.assertEqual(self.interval_task_test.status,
                         200,
                         "Task status should be set to Done")

        self.move_to_column(self.board_adapter, card, COLUMN_DOING)
        self.interval_task_test.Reload()
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to current interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Task should be in Doing column")
        self.assertEqual(self.interval_task_test.status,
                         100,
                         "Task status should be set to Doing")

        self.move_to_column(self.board_adapter, card, COLUMN_READY)
        self.interval_task_test.Reload()
        card = self.get_card(self.interval_board, self.interval_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.interval.cdb_object_id,
                         "Card of ready task should keep assigned to current interval")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "Task should be in Ready column")
        self.assertEqual(self.interval_task_test.status,
                         10,
                         "Task status should be set to Ready")


@unittest.SkipTest
class TestIntervalStartStop(SetupIntervalBoardTest):
    """FIXME"""
    pass


@unittest.SkipTest
class TestIntervalCardsRanking(SetupIntervalBoardTest):
    """FIXME"""
    pass


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
