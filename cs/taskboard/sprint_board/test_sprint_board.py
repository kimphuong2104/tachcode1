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
from cs.taskboard.sprint_board import SPRINT_BOARD_TYPE
from cs.taskboardtest.tests.common import get_board_template
from cs.taskboardtest.tests.common import create_board_for_context
from cs.taskboardtest.tests.common import SetupSprintBoardTest

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
        self.board_template = get_board_template(SPRINT_BOARD_TYPE)

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


class TestCreateSprintBoard(testcase.RollbackTestCase):
    """
    A class to test creating Sprint Task Board.
    """
    def setUp(self):
        super(TestCreateSprintBoard, self).setUp()
        self.board_template = get_board_template(SPRINT_BOARD_TYPE)
        self.board_context = BoardContext.Create(title="Test Board Context")
        self.content_types = Foo._getClassname()

    def test_create_sprint_board(self):
        board = create_board_for_context(
            self.board_context, self.board_template, content_types=self.content_types)
        self.assertIsNotNone(board)
        self.assertEqual(len(board.Iterations), 1,
                         "New Sprint Board should have 1 Sprint.")


class TestBoardBacklogNewCards(SetupSprintBoardTest):
    """
    A class to test manage existing Sprint Task Board containing new cards
    without sprint assignments.
    """

    def setUp(self):
        super(TestBoardBacklogNewCards, self).setUp()
        self.create_sprint_tasks()

    def test_no_active_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration:
                self.sprint_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.sprint_board.ActiveIteration,
                              "There should not be an active sprint")
            # calling board URL to update board
            self.request_board(self.sprint_board)

        should_cards = 4  # new, ready, doing, done
        self.assertEqual(len(self.sprint_board.Cards), should_cards,
                         "Opening Board and it should be updated and contains %i cards" %
                         should_cards)
        visible_cards = 3  # new, ready, doing
        self.assertEqual(len(self.sprint_board.VisibleCards), visible_cards,
                         "Opening Board and it should be updated and shows %i cards" %
                         visible_cards)
        card = self.get_card(self.sprint_board, self.sprint_task_new)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_doing)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_done)
        self.assertEqual(card.is_hidden, 1, "Done task should be hidden in board backlog")

    def test_with_active_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration is None:
                self.sprint_board.Iterations[0].ChangeState(50)
            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            # calling board URL to update board
            self.request_board(self.sprint_board)

        should_cards = 4  # new, ready, doing, done
        self.assertEqual(len(self.sprint_board.Cards), should_cards,
                         "Opening Board and it should be updated and contains %i cards" %
                         should_cards)
        visible_cards = 3  # new, ready, doing
        self.assertEqual(len(self.sprint_board.VisibleCards), visible_cards,
                         "Opening Board and it should be updated and shows %i cards" %
                         visible_cards)
        card = self.get_card(self.sprint_board, self.sprint_task_new)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_doing)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        card = self.get_card(self.sprint_board, self.sprint_task_done)
        self.assertEqual(card.is_hidden, 1, "Done task should be hidden in board backlog")


class TestBoardBacklogExistingCards(SetupSprintBoardTest):
    """
    A class to test manage existing Sprint Task Board containing existing cards
    without sprint assignments.
    """

    def setUp(self):
        super(TestBoardBacklogExistingCards, self).setUp()

    def test_no_active_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration:
                self.sprint_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.sprint_board.ActiveIteration,
                              "There should not be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=0)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        # Then this card should be disappeared
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertIsNotNone(card, "Done task should be found on board")
        self.assertEqual(card.is_hidden, 1, "But done task should be hidden")

    def test_with_active_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration is None:
                self.sprint_board.Iterations[0].ChangeState(50)
            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=0)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "Ready task should be in board backlog")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "Doing task should be in board backlog")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        # Then this card should be disappeared
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertIsNotNone(card, "Done task should be found on board")
        self.assertEqual(card.is_hidden, 1, "But done task should be hidden")


class TestSprintAssignment(SetupSprintBoardTest):
    """
    A class to test manage existing Sprint Task Board containing cards with sprint
    assignments.
    """

    def setUp(self):
        super(TestSprintAssignment, self).setUp()
        self.board_adapter = self.sprint_board.getAdapter()

    def test_no_active_sprint(self):
        with util.SkipAccessCheck():
            self.sprint = self.sprint_board.Iterations[0]
            if self.sprint_board.ActiveIteration:
                self.sprint_board.ActiveIteration.ChangeState(0)
            self.assertIsNone(self.sprint_board.ActiveIteration,
                              "There should not be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=0)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        self.assign_iteration(card, self.sprint)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card should be assigned to specified sprint")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to specified sprint")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of doing task should keep assigned to specified sprint")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to specified sprint")

    def test_with_active_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration is None:
                self.sprint = self.sprint_board.Iterations[0]
                self.sprint.ChangeState(50)
            else:
                self.sprint = self.sprint_board.ActiveIteration

            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=0)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id, "", "New task should be in board backlog")

        self.assign_iteration(card, self.sprint)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card should be assigned to specified sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "New task should be in Ready column")

        # Change the task of new card to "Done" outside board
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to specified sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "Ready task should be in Ready column")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(100)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of doing task should keep assigned to specified sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Doing task should be in Doing column")

        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to specified sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DONE).cdb_object_id,
                         "Done task should be in Done column")


class TestCompletedSprintAssignment(SetupSprintBoardTest):
    """
    A class to test manage existing Sprint Task Board containing cards with sprint
    assignments.
    """

    def setUp(self):
        super(TestCompletedSprintAssignment, self).setUp()
        self.board_adapter = self.sprint_board.getAdapter()

    def test_completed_sprint(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration is None:
                self.sprint = self.sprint_board.Iterations[0]
                self.sprint.ChangeState(50)
            else:
                self.sprint = self.sprint_board.ActiveIteration

            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=100)
            # not completed task
            self.sprint_task_ready = self.create_sprint_task(status=10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assign_iteration(card, self.sprint)
        # Card with ready task
        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assign_iteration(card_ready, self.sprint)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card should be assigned to specified sprint")

        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card with ready task should be assigned to specified sprint")

        # Change the task of new card to "Done"
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to specified sprint")

        # complete iteration
        with util.SkipAccessCheck():
            self.sprint.ChangeState(200)
            self.request_board(self.sprint_board)

        self.assertTrue(self.sprint.is_completed(),
                        "Sprint should be set to completed")
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to completed sprint")

        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         "",
                         "Card with ready task should be moved back to backlog")


class TestCompletedSprintAssignmentWithOpenIteration(SetupSprintBoardTest):
    """
    A class to test sprint assignments of cards on sprint board with both completed
    and open iterations.
    """

    def setUp(self):
        super(TestCompletedSprintAssignmentWithOpenIteration, self).setUp()
        self.board_adapter = self.sprint_board.getAdapter()

    def test_assignments(self):
        with util.SkipAccessCheck():
            self.create_sprint(self.sprint_board)
            self.sprint = self.sprint_board.Iterations[0]
            self.sprint_open = self.sprint_board.Iterations[1]
            self.sprint.ChangeState(50)

            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=100)
            # not completed task
            self.sprint_task_ready = self.create_sprint_task(status=10)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assign_iteration(card, self.sprint)
        # Card with ready task
        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assign_iteration(card_ready, self.sprint)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card should be assigned to specified sprint")

        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card with ready task should be assigned to specified sprint")

        # Change the task of new card to "Done"
        with util.SkipAccessCheck():
            self.sprint_task_test.ChangeState(200)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to specified sprint")

        # complete iteration
        with util.SkipAccessCheck():
            self.sprint.ChangeState(200)
            self.request_board(self.sprint_board)

        self.assertTrue(self.sprint.is_completed(),
                        "Sprint should be set to completed")
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of done task should keep assigned to completed sprint")

        card_ready = self.get_card(self.sprint_board, self.sprint_task_ready)
        self.assertEqual(card_ready.sprint_object_id,
                         self.sprint_open.cdb_object_id,
                         "Card with ready task should be moved to next open iteration")


class TestMoveCard(SetupSprintBoardTest):
    """
    A class to test move cards in current sprint.
    """

    def setUp(self):
        super(TestMoveCard, self).setUp()
        self.board_adapter = self.sprint_board.getAdapter()

    def test_move_between_columns(self):
        with util.SkipAccessCheck():
            if self.sprint_board.ActiveIteration is None:
                self.sprint = self.sprint_board.Iterations[0]
                self.sprint.ChangeState(50)
            else:
                self.sprint = self.sprint_board.ActiveIteration

            self.assertIsNotNone(self.sprint_board.ActiveIteration,
                                 "There should be an active sprint")
            self.sprint_task_test = self.create_sprint_task(status=0)
            # calling board URL to update board
            self.request_board(self.sprint_board)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assign_iteration(card, self.sprint)

        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card should be assigned to current sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "New task should be in Ready column")

        # move card between columns

        self.move_to_column(self.board_adapter, card, COLUMN_DOING)
        self.sprint_task_test.Reload()
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to current sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Task should be in Doing column")
        self.assertEqual(self.sprint_task_test.status,
                         100,
                         "Task status should be set to Doing")

        self.move_to_column(self.board_adapter, card, COLUMN_DONE)
        self.sprint_task_test.Reload()
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to current sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DONE).cdb_object_id,
                         "Task should be in Done column")
        self.assertEqual(self.sprint_task_test.status,
                         200,
                         "Task status should be set to Done")

        self.move_to_column(self.board_adapter, card, COLUMN_DOING)
        self.sprint_task_test.Reload()
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to current sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_DOING).cdb_object_id,
                         "Task should be in Doing column")
        self.assertEqual(self.sprint_task_test.status,
                         100,
                         "Task status should be set to Doing")

        self.move_to_column(self.board_adapter, card, COLUMN_READY)
        self.sprint_task_test.Reload()
        card = self.get_card(self.sprint_board, self.sprint_task_test)
        self.assertEqual(card.sprint_object_id,
                         self.sprint.cdb_object_id,
                         "Card of ready task should keep assigned to current sprint")
        self.assertEqual(card.column_object_id,
                         self.board_adapter.get_column_by_type(COLUMN_READY).cdb_object_id,
                         "Task should be in Ready column")
        self.assertEqual(self.sprint_task_test.status,
                         10,
                         "Task status should be set to Ready")


@unittest.SkipTest
class TestSprintStartStop(SetupSprintBoardTest):
    """FIXME"""
    pass


@unittest.SkipTest
class TestSprintCardsRanking(SetupSprintBoardTest):
    """FIXME"""
    pass


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
