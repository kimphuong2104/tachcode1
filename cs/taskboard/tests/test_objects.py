#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import unittest

import pytest
from cdb import ue
from cs.taskboard import objects


@pytest.mark.unit
class TestObjects(unittest.TestCase):

    def test_remove_cards_0(self):
        "TestObjects 000: remove cards, without context"
        cards = mock.MagicMock()
        with mock.patch.object(objects.Board, "Cards",
                               new_callable=mock.PropertyMock,
                               return_value=cards):
            board = objects.Board()
            objects.Board.remove_cards(board, None)
            cards.Delete.assert_called_once_with()

    def test_remove_cards_1(self):
        "TestObjects 001: remove cards, with any context object"
        ctx = "foo"
        cards = mock.MagicMock()
        with mock.patch.object(objects.Board, "Cards",
                               new_callable=mock.PropertyMock,
                               return_value=cards):
            board = objects.Board()
            objects.Board.remove_cards(board, ctx)
            cards.Delete.assert_called_once_with()

    def test_refresh_boards_by_context_object_ids_0(self):
        "TestObjects 002: Refresh boards by context oid: " \
            "Two board are given, a different active board is given"
        board_active = objects.Board()
        board_active.cdb_object_id = "bel"
        board_1 = objects.Board()
        board_1.cdb_object_id = "foo"
        board_2 = objects.Board()
        board_2.cdb_object_id = "bass"
        boards = [board_1, board_2]
        # Two boards are given. Active board is given.
        # The object id of the active board differs from object id of the given boards.
        with mock.patch.object(objects.Board, "get_boards_by_context_object_ids",
                               return_value=boards):
            with mock.patch.object(board_1, "updateBoard"):
                with mock.patch.object(board_2, "updateBoard"):
                    # call method for test run
                    objects.Board.refresh_boards_by_context_object_ids("bar", board_active)

                    # active board not in list, both boards should be called
                    objects.Board.get_boards_by_context_object_ids.assert_called_once_with("bar")
                    board_1.updateBoard.assert_called_once()
                    board_2.updateBoard.assert_called_once()

    def test_refresh_boards_by_context_object_ids_1(self):
        "TestObjects 003: Refresh boards by context oid: " \
            "Two board are given, one of them is same as active board"
        board_active = objects.Board()
        board_active.cdb_object_id = "foo"
        board_1 = objects.Board()
        board_1.cdb_object_id = "foo"
        board_2 = objects.Board()
        board_2.cdb_object_id = "bass"
        boards = [board_1, board_2]
        # Two boards are given. Active board is given.
        # The active board has the same object id as one of the boards.
        with mock.patch.object(objects.Board, "get_boards_by_context_object_ids",
                               return_value=boards):
            with mock.patch.object(board_1, "updateBoard"):
                with mock.patch.object(board_2, "updateBoard"):
                    # call method for test run
                    objects.Board.refresh_boards_by_context_object_ids("bar", board_active)

                    # active board in list, only different board should be called
                    objects.Board.get_boards_by_context_object_ids.assert_called_once_with("bar")
                    board_1.updateBoard.assert_not_called()
                    board_2.updateBoard.assert_called_once()

    def test_refresh_boards_by_context_object_ids_2(self):
        "TestObjects 004: Refresh boards by context oid: " \
            "Two board are given, no active board is given"
        board_1 = objects.Board()
        board_1.cdb_object_id = "foo"
        board_2 = objects.Board()
        board_2.cdb_object_id = "bass"
        boards = [board_1, board_2]
        # Two boards are given. Active board is given.
        # The active board has the same object id as one of the boards.
        with mock.patch.object(objects.Board, "get_boards_by_context_object_ids",
                               return_value=boards):
            with mock.patch.object(board_1, "updateBoard"):
                with mock.patch.object(board_2, "updateBoard"):
                    # call method for test run
                    objects.Board.refresh_boards_by_context_object_ids("bar", None)

                    # active board is None, both boards should be called
                    objects.Board.get_boards_by_context_object_ids.assert_called_once_with("bar")
                    board_1.updateBoard.assert_called_once()
                    board_2.updateBoard.assert_called_once()

    @mock.patch.object(objects.sig, "emit")
    @mock.patch.object(objects.utils, "clear_update_stack", return_value=True)
    @mock.patch.object(objects.utils, "is_board_update_activated", return_value=True)
    def test_updateBoard_0(self, update_activated, clear_stack, emit):
        "TestObjects 005: updateBoard for regular board called "\
            "while board update activated"
        board = objects.Board()
        board.is_template = False
        adapter = mock.MagicMock()
        with mock.patch.object(board, "Reload", return_value=None):
            with mock.patch.object(board, "getAdapter", return_value=adapter):
                objects.Board.updateBoard(board)
                board.Reload.assert_called_once()
        adapter.update_board.assert_called_once()
        update_activated.assert_called_once()
        clear_stack.assert_called_once()
        emit.assert_called_once()

    @mock.patch.object(objects.sig, "emit")
    @mock.patch.object(objects.utils, "clear_update_stack", return_value=True)
    @mock.patch.object(objects.utils, "is_board_update_activated", return_value=True)
    def test_updateBoard_1(self, update_activated, clear_stack, emit):
        "TestObjects 006: updateBoard for template board called "\
            "while board update activated"
        board = objects.Board()
        board.is_template = True
        adapter = mock.MagicMock()
        with mock.patch.object(board, "Reload", return_value=None):
            with mock.patch.object(board, "getAdapter", return_value=adapter):
                objects.Board.updateBoard(board)
                board.Reload.assert_called_once()
        update_activated.assert_called_once()
        clear_stack.assert_called_once()
        emit.assert_called_once()

    @mock.patch.object(objects.utils, "is_board_update_activated", return_value=False)
    def test_updateBoard_2(self, update_activated):
        "TestObjects 007: updateBoard called while board update deactivated"
        board = objects.Board()
        objects.Board.updateBoard(board)
        update_activated.assert_called_once()

    @mock.patch.object(objects, "auth", persno="foo")
    def test_on_taskboard_start_sprint_now_0(self, auth):
        "TestObjects 008: Start Iteration without Access Right 'save': "\
            "Exception is thrown."
        iteration = objects.Iteration()
        with mock.patch.object(iteration, "CheckAccess", return_value=False):
            with self.assertRaises(ue.Exception):
                objects.Iteration.on_taskboard_start_sprint_now(iteration, None)
                iteration.CheckAccess.assert_called_once_with("save", "foo")

    @mock.patch.object(objects.sig, "emit")
    @mock.patch.object(objects.utils, "NoBoardUpdate")
    @mock.patch.object(objects, "auth", persno="foo")
    def test_on_taskboard_start_sprint_now_1(self, auth, NoBoardUpdate, emit):
        "TestObjects 009: Start Iteration with Access Right 'save': "\
            "Iteration gets started."
        board = mock.MagicMock()
        adapter = mock.MagicMock()
        board.getAdapter.return_value = adapter
        with mock.patch.object(objects.Iteration, "Board",
                               new_callable=mock.PropertyMock,
                               return_value=board):
            status_ref = mock.MagicMock()
            status_ref.status.return_value = 50
            with mock.patch.object(objects.Iteration, "EXECUTION",
                                   new_callable=mock.PropertyMock,
                                   return_value=status_ref):
                iteration = objects.Iteration()
                with mock.patch.object(iteration, "CheckAccess", return_value=True):
                    with mock.patch.object(iteration, "ChangeState", return_value=50):
                        objects.Iteration.on_taskboard_start_sprint_now(iteration, None)
                        iteration.CheckAccess.assert_called_once_with("save", "foo")
                        iteration.ChangeState.assert_called_once()
                emit.assert_has_calls([
                    mock.call("starting_iteration"),
                    mock.call()(iteration),
                    mock.call("iteration_started"),
                    mock.call()(iteration)
                ])
                self.assertEqual(emit.call_count, 2)
                self.assertEqual(emit.return_value.call_count, 2)
        NoBoardUpdate.assert_called_once_with()
        adapter.on_iteration_start_pre.assert_called_once()
        adapter.on_iteration_start_post.assert_called_once()
        board.updateBoard.assert_called_once()

    @mock.patch.object(objects.Iteration, "COMPLETED")
    @mock.patch.object(objects, "auth", persno="foo")
    def test_on_taskboard_stop_sprint_now(self, auth, completed):
        completed.status = 200
        board = mock.MagicMock()
        adapter = mock.MagicMock()
        adapter.is_done = mock.MagicMock(return_value=False)

        card_adapter = mock.MagicMock()

        board.getAdapter.return_value = adapter
        board.getCardAdapter.return_value = card_adapter
        cards = [mock.MagicMock(sprint_object_id="123", context_object_id="co_id")]
        ctx = mock.MagicMock(dialog={})

        iteration = objects.Iteration()
        with mock.patch.object(iteration, "CheckAccess", return_value=True),\
            mock.patch.object(iteration, "ChangeState"),\
            mock.patch.object(objects.Iteration, "Board", board),\
            mock.patch.object(objects.Iteration, "Cards", cards):

            iteration.on_taskboard_stop_sprint_now(ctx)

            iteration.CheckAccess.assert_called_once_with("save", auth.persno)

        adapter.on_iteration_stop_pre.assert_called_once_with(iteration)
        adapter.on_iteration_stop_post.assert_called_once_with(iteration)
        adapter.is_done.assert_called_once_with(card_adapter, "co_id")
        cards[0].Update.assert_called_once_with(sprint_object_id="")


    @mock.patch.object(objects, "kOperationNew")
    @mock.patch.object(objects, "operation")
    @mock.patch.object(objects.Iteration, "COMPLETED")
    @mock.patch.object(objects, "auth", persno="foo")
    def test_on_taskboard_stop_sprint_now_new_iteration(self, auth, completed, operation, kOperationNew):
        completed.status = 200
        board = mock.MagicMock()
        adapter = mock.MagicMock()
        board.getAdapter.return_value = adapter
        board.NextIteration = None
        board.cdb_object_id = "board-123"
        ctx = mock.MagicMock(dialog=mock.MagicMock())

        iteration = objects.Iteration()
        with mock.patch.object(iteration, "CheckAccess", return_value=True),\
            mock.patch.object(iteration, "ChangeState"),\
            mock.patch.object(objects.Iteration, "Board", board):

            iteration.on_taskboard_stop_sprint_now(ctx)

            iteration.CheckAccess.assert_called_once_with("save", auth.persno)

        adapter.on_iteration_stop_pre.assert_called_once_with(iteration)
        adapter.on_iteration_stop_post.assert_called_once_with(iteration)
        operation.assert_called_once_with(kOperationNew, iteration, board_object_id="board-123")

    @mock.patch.object(objects.Board, "MakeChangeControlAttributes")
    @mock.patch.object(objects.Board, "ByKeys")
    def test__create_board_1(self, ByKeys, MakeCCA):
        "TestObjects 010: create board: Template exists"
        board = objects.Board()
        with mock.patch.object(board, "setupBoard"):
            template = mock.Mock(spec=["copyBoard"])
            template.copyBoard.return_value = board
            objects.Board.ByKeys.return_value = template
            objects.Board.MakeChangeControlAttributes.return_value = dict(
                change_control_attrs="cca foo"
            )

            ctx = mock.Mock(spec=["dialog"])
            dialog = mock.MagicMock()
            real_dict = dict(template_object_id="template foo")
            dialog.get_attribute_names.return_value = real_dict.keys()
            dialog.__getitem__.side_effect = real_dict.__getitem__
            ctx.dialog = dialog

            # call method
            result = objects._create_board(ctx, "bar",
                                           additional_kwargs="my bar")

            # check calls
            self.assertEqual(result, board)
            ByKeys.assert_called_once_with("template foo")
            ctx.dialog.get_attribute_names.assert_called_once_with()
            MakeCCA.assert_called_once_with()
            template.copyBoard.assert_called_once_with(
                change_control_attrs='cca foo', check_access='bar',
                is_template=0, additional_kwargs='my bar',
                template_object_id='template foo'
            )
            board.setupBoard.assert_called_once_with()

    @mock.patch.object(objects.Board, "MakeChangeControlAttributes")
    @mock.patch.object(objects.Board, "ByKeys")
    def test__create_board_2(self, ByKeys, MakeCCA):
        "TestObjects 011: create board: Template does not exist"
        board = objects.Board()
        with mock.patch.object(board, "setupBoard"):
            objects.Board.ByKeys.return_value = None
            objects.Board.MakeChangeControlAttributes.return_value = dict(
                change_control_attrs="cca foo"
            )

            ctx = mock.Mock(spec=["dialog"])
            dialog = mock.MagicMock()
            real_dict = dict(template_object_id="template foo")
            dialog.get_attribute_names.return_value = real_dict.keys()
            dialog.__getitem__.side_effect = real_dict.__getitem__
            ctx.dialog = dialog

            # call method
            result = objects._create_board(ctx, "bar",
                                           additional_kwargs="my bar")

            # check calls
            self.assertEqual(result, None)
            ByKeys.assert_called_once_with("template foo")
            ctx.dialog.get_attribute_names.assert_not_called()
            MakeCCA.assert_not_called()
