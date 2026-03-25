#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import unittest

import pytest
from cs.taskboard import internal
from cs.taskboard.internal import TaskLongTextModel
from webob.exc import HTTPForbidden


@pytest.mark.unit
class TestInternal(unittest.TestCase):

    # CHANGE_CARDS

    @mock.patch.object(internal.sig, "emit")
    @mock.patch.object(internal, "auth", persno="bass")
    @mock.patch.object(internal.Board, "refresh_boards_by_context_object_ids")
    @mock.patch.object(internal.Board, "adjust_display_order")
    @mock.patch.object(internal, "_get_board", return_value="foo")
    def _change_cards(self, get_board, adjust, refresh, auth, emit,
                      access=True, **kwargs):
        # mock board and adapter
        board = mock.Mock()
        board_adapter = mock.Mock()
        board.getAdapter.return_value = board_adapter

        # mock request
        request = mock.Mock()
        request.json = kwargs.copy()

        # mock context object
        task = mock.MagicMock()

        with mock.patch.object(task, "CheckAccess",
                               return_value=access):
            with mock.patch.object(internal.Card, "TaskObject",
                                   new_callable=mock.PropertyMock,
                                   return_value=task):
                # mock card
                card = internal.Card()
                card.board_object_id = "board_foo"
                card.context_object_id = "context_foo"
                card.sprint_object_id = ""

                with mock.patch.object(internal.Card, "ByKeys",
                                       return_value=card):
                    # call method
                    result = internal._change_cards(board, request)
                    internal.Card.ByKeys.assert_called_once_with("card_foo")
                    task.CheckAccess.assert_called_once_with("save", "bass")
                    self.assertEqual(result, dict(
                        runOp=None,
                        board="foo"
                    ))
        return locals()

    def test_changes_cards_01(self):
        "TestInternal 001: change cards with access rights given"
        # values of request
        request = dict(
            cards=["card_foo"],
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        test = self._change_cards(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]
        emit = test["emit"]

        # check called methods
        board_adapter.change_card_position_to.assert_called_once_with(
            card, 'row_foo', 'column_foo'
        )
        board_adapter.change_card_iteration.assert_not_called()
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with(["context_foo"], board)
        get_board.assert_called_once_with(board, request, "group_foo")
        emit.assert_has_calls([
            mock.call("changing_cards"),
            mock.call()(board, ['context_foo']),
            mock.call("cards_changed"),
            mock.call()(board, ['context_foo'])
        ])
        self.assertEqual(emit.call_count, 2)
        self.assertEqual(emit.return_value.call_count, 2)

    def test_changes_cards_02(self):
        "TestInternal 002: change cards with access rights given "\
            "(sprint given but no row or column)"
        # values of request
        request = dict(
            cards=["card_foo"],
            row_object_id="",
            column_object_id="",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        test = self._change_cards(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]

        # check called methods
        board_adapter.change_card_position_to.assert_not_called()
        board_adapter.change_card_iteration.assert_called_with(
            card, "sprint_foo")
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with(["context_foo"], board)
        get_board.assert_called_once_with(board, request, "group_foo")

    def test_changes_cards_03(self):
        "TestInternal 003: change cards with access rights given "\
            "(no sprint, row or column given)"
        # values of request
        request = dict(
            cards=["card_foo"],
            row_object_id="",
            column_object_id="",
            next_card_object_id="next_foo",
            sprint_object_id="",
            group_by="group_foo",
        )
        test = self._change_cards(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]

        # check called methods
        board_adapter.change_card_position_to.assert_not_called()
        board_adapter.change_card_iteration.assert_not_called()
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with(["context_foo"], board)
        get_board.assert_called_once_with(board, request, "group_foo")

    def test_changes_cards_04(self):
        "TestInternal 004: change cards without access rights"
        # values of request
        request = dict(
            cards=["card_foo"],
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        with self.assertRaises(HTTPForbidden):
            self._change_cards(access=False, **request)

    @mock.patch.object(internal.Board, "refresh_boards_by_context_object_ids")
    @mock.patch.object(internal.Board, "adjust_display_order")
    @mock.patch.object(internal, "_get_board", return_value="foo")
    def test_change_cards_05(self, get_board, adjust, refresh):
        "TestInternal 005: change cards with no cards given"
        # mock board and adapter
        board = mock.Mock()
        board_adapter = mock.Mock()
        board.getAdapter.return_value = board_adapter

        # mock request
        json = dict(
            cards=[],
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        request = mock.Mock()
        request.json = json

        # mock context object
        task = mock.MagicMock()

        with mock.patch.object(task, "CheckAccess",
                               return_value=True):
            with mock.patch.object(internal.Card, "TaskObject",
                                   new_callable=mock.PropertyMock,
                                   return_value=task):
                # mock card
                card = internal.Card()
                card.board_object_id = "board_foo"
                card.context_object_id = "context_foo"
                card.sprint_object_id = "sprint_foo"

                with mock.patch.object(internal.Card, "ByKeys",
                                       return_value=card):
                    # call method
                    result = internal._change_cards(board, request)
                    internal.Card.ByKeys.assert_not_called()
                    task.CheckAccess.assert_not_called()
                    self.assertEqual(result, dict(
                        runOp=None,
                        board="foo"
                    ))

        # check called methods
        board_adapter.change_card_position_to.assert_not_called()
        board_adapter.change_card_iteration.assert_not_called()
        adjust.assert_not_called()
        refresh.assert_not_called()
        get_board.assert_called_once_with(board, request, "group_foo")

    # CHANGE_CARD

    @mock.patch.object(internal, "opdata_view", return_value="follow")
    @mock.patch.object(internal, "auth", persno="bass")
    @mock.patch.object(internal.Board, "refresh_boards_by_context_object_ids")
    @mock.patch.object(internal.Board, "adjust_display_order")
    @mock.patch.object(internal, "_get_board", return_value="foo")
    def _change_card(self, get_board, adjust, refresh, auth, opdata_view,
                     access=True, **kwargs):
        # mock board and adapter
        board = mock.Mock()
        board_adapter = mock.Mock()
        board.getAdapter.return_value = board_adapter
        board_adapter.change_card_position_to.return_value = dict(foo="bar")

        # mock request
        request = mock.Mock()
        request.json = kwargs.copy()

        # mock context object
        task = mock.MagicMock()
        task.GetClassname.return_value = "foo_bar"

        with mock.patch.object(task, "CheckAccess",
                               return_value=access):
            with mock.patch.object(internal.Card, "TaskObject",
                                   new_callable=mock.PropertyMock,
                                   return_value=task):
                with mock.patch.object(internal.Card, "Board",
                                       new_callable=mock.PropertyMock,
                                       return_value=board):
                    # mock card
                    card = internal.Card()
                    card.board_object_id = "board_foo"
                    card.context_object_id = "context_foo"
                    card.sprint_object_id = ""

                    # call method
                    result = internal._change_card(card, request)
                    task.CheckAccess.assert_called_once_with("save", "bass")
        return locals()

    def test_changes_card_06(self):
        "TestInternal 006: change card with access rights given"
        # values of request
        request = dict(
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        test = self._change_card(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]
        opdata_view = test["opdata_view"]
        result = test["result"]

        # check called methods
        board_adapter.change_card_position_to.assert_called_once_with(
            card, 'row_foo', 'column_foo', 'group_foo'
        )
        board_adapter.change_card_iteration.assert_not_called()
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with("context_foo", board)
        get_board.assert_called_once_with(board, request, "group_foo")
        opdata_view.assert_called_once_with(
            dict(classname='foo_bar', foo='bar'), request)
        self.assertEqual(result, dict(
            runOp="follow",
            board="foo"
        ))

    def test_changes_card_07(self):
        "TestInternal 007: change cards with access rights given "\
            "(sprint given but no row or column)"
        # values of request
        request = dict(
            row_object_id="",
            column_object_id="",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        test = self._change_card(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]
        opdata_view = test["opdata_view"]
        result = test["result"]

        # check called methods
        board_adapter.change_card_position_to.assert_not_called()
        board_adapter.change_card_iteration.assert_called_with(
            card, "sprint_foo")
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with("context_foo", board)
        get_board.assert_called_once_with(board, request, "group_foo")
        opdata_view.assert_not_called()
        self.assertEqual(result, dict(
            runOp=None,
            board="foo"
        ))

    def test_changes_card_08(self):
        "TestInternal 008: change card with access rights given "\
            "(no sprint, row or column given)"
        # values of request
        request = dict(
            row_object_id="",
            column_object_id="",
            next_card_object_id="next_foo",
            sprint_object_id="",
            group_by="group_foo",
        )
        test = self._change_card(access=True, **request)

        # mocked objects and methods
        board = test["board"]
        request = test["request"]
        card = test["card"]
        adjust = test["adjust"]
        refresh = test["refresh"]
        get_board = test["get_board"]
        board_adapter = test["board_adapter"]
        opdata_view = test["opdata_view"]
        result = test["result"]

        # check called methods
        board_adapter.change_card_position_to.assert_not_called()
        board_adapter.change_card_iteration.assert_not_called()
        adjust.assert_called_once_with("board_foo", [card], "next_foo")
        refresh.assert_called_once_with("context_foo", board)
        get_board.assert_called_once_with(board, request, "group_foo")
        opdata_view.assert_not_called()
        self.assertEqual(result, dict(
            runOp=None,
            board="foo"
        ))

    def test_changes_card_09(self):
        "TestInternal 009: change card without access rights"
        # values of request
        request = dict(
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        with self.assertRaises(HTTPForbidden):
            self._change_card(access=False, **request)

    def test_change_card_010(self):
        "TestInternal 010: change card with no card given"
        # mock request
        json = dict(
            row_object_id="row_foo",
            column_object_id="column_foo",
            next_card_object_id="next_foo",
            sprint_object_id="sprint_foo",
            group_by="group_foo",
        )
        request = mock.Mock()
        request.json = json

        # call method
        with self.assertRaises(AttributeError):
            internal._change_card(None, request)

    @mock.patch.object(internal.Board, "TeamMembers",
                       new_callable=mock.PropertyMock,
                       return_value=["one team member"])
    @mock.patch.object(internal.Board, "NextIteration",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "Iterations",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "CompletedIterations",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "OpenIterations",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "VisibleCards",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "Columns",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal.Board, "Rows",
                       new_callable=mock.PropertyMock)
    @mock.patch.object(internal, "Workflow")
    @mock.patch.object(internal, "group_view", return_value="foo group view")
    @mock.patch.object(internal, "get_collection_app", return_value="foo app")
    @mock.patch.object(internal, "opdata_view", return_value="foo op view")
    @mock.patch.object(internal, "_display_config", return_value="foo_d_config")
    @mock.patch.object(internal, "_get_card", return_value="foo_card_data")
    @mock.patch.object(internal, "board_base_view", return_value=dict())
    def _get_board_view(self, board_base_view, _get_card, _display_config,
                        opdata_view, get_collection_app, group_view, Workflow,
                        Rows, Columns, VisibleCards, OpenIterations,
                        CompletedIterations, Iterations, NextIteration,
                        TeamMembers, hasBacklog=True, hasEvaluation=True,
                        hasPreview=True, hasTeam=True, **kwargs):
        # mocked iteration class (no variables)
        foo_iter_class = mock.Mock()
        foo_iter_class._getClassname.return_value = "foo_iter_class_name"

        # mocked row (no variables)
        row = mock.Mock()
        row.cdb_object_id = "row_cdb_object_id"
        row.title = "row_title"
        row.context_object_id = "row_context_object_id"
        row.display_order = "row_display_order"
        internal.Board.Rows = [row]

        # mocked column (no variables)
        column = mock.Mock()
        column.cdb_object_id = "column_cdb_object_id"
        column.title = "column_title"
        column.column_name = "column_column_name"
        column.display_order = "column_display_order"
        internal.Board.Columns = [column]

        internal.Board.TeamMember = ""

        # mocked card (no variables)
        visible_card = mock.Mock()

        # mocked interations (no variables)
        active_sprint = mock.Mock()
        active_sprint.cdb_object_id = "foo_active_sprint_id"
        next_sprint = mock.Mock()
        next_sprint.cdb_object_id = "foo_next_sprint_id"
        open_sprint = mock.Mock()
        open_sprint.cdb_object_id = "foo_open_sprint_id"
        closed_sprint = mock.Mock()
        closed_sprint.cdb_object_id = "foo_closed_sprint_id"

        # mock properties
        internal.Board.VisibleCards = [visible_card]
        internal.Board.NextIteration = next_sprint
        internal.Board.OpenIterations = [open_sprint]
        internal.Board.CompletedIterations = [closed_sprint]
        internal.Board.Iterations = [closed_sprint, active_sprint,
                                     next_sprint, open_sprint]

        # mock board adapter (not variable)
        board_adapter = mock.Mock()
        board_adapter.get_group_attributes.return_value = "foo_group_types"
        board_adapter.get_filter_names.return_value = "foo_filters"
        board_adapter.get_working_view_title.return_value = "foo_view_title"
        board_adapter.get_create_operations.return_value = ["foo_operation"]
        board_adapter.get_extra_operations.return_value = ["foo_extra_operation"]
        board_adapter.enable_moving_cards_in_groups.return_value = "foo_moving"
        board_adapter.get_display_configs.return_value = ["foo_config"]
        board_adapter.get_iteration_class.return_value = foo_iter_class
        board_adapter.has_preview_add_button.return_value = "foo_button"
        board_adapter.enable_moving_cards_in_preview.return_value = "foo_move"

        # mock board adapter (variables)
        board_adapter.group_by.return_value = dict(
            foo_group_A=["foo1", "foo2"], foo_group_B=["foo3", "foo4"]
        )
        board_adapter.has_backlog.return_value = hasBacklog
        board_adapter.has_evaluation.return_value = hasEvaluation
        board_adapter.has_preview.return_value = hasPreview
        board_adapter.get_active_iteration.return_value = active_sprint
        board_adapter.has_team.return_value = hasTeam

        # mock Workflow (no variables)
        wf = mock.Mock()
        wf.current_status = "foo_current_status"
        Workflow.return_value = wf

        # mock Workflow (not variable)
        request = mock.Mock()
        request.link.return_value = "foo_link"
        request.view.return_value = "foo_view"

        # mock Workflow (variables)
        request.params = dict(group_by="test_grouping_other")

        result = None
        board = internal.Board()
        with mock.patch.object(board, "getAdapter",
                               return_value=board_adapter):
            # call method
            result = internal._get_board_view(board, request, "test_grouping")
            board.getAdapter.assert_called_once_with()

        # check mocked methods
        board_adapter.update_board.assert_called_once_with()
        board_base_view.assert_called_once_with(board, request)
        board_adapter.get_group_attributes.assert_called_once_with()
        board_adapter.get_filter_names.assert_called_once_with()
        board_adapter.get_working_view_title.assert_called_once_with()
        _get_card.assert_called_once_with(visible_card, request)
        board_adapter.get_create_operations.assert_called_once_with()
        opdata_view.assert_has_calls([
            mock.call("foo_operation", request),
            mock.call("foo_extra_operation", request)
        ])
        board_adapter.get_extra_operations.assert_called_once_with()
        board_adapter.enable_moving_cards_in_groups.assert_called_once_with()
        request.link.assert_has_calls([
            mock.call(board, name="+adjust_new_card"),
            mock.call(board, name="+move_cards")
        ])
        board_adapter.group_by.assert_called_once_with("test_grouping_other")
        group_view.assert_has_calls([
            mock.call(board, ["foo3", "foo4"], request),
            mock.call(board, ["foo1", "foo2"], request),
        ], any_order=True)
        get_collection_app.assert_called_once_with(request)
        board_adapter.get_iteration_class.assert_called_once_with()
        board_adapter.has_backlog.assert_called_once_with()
        board_adapter.has_evaluation.assert_called_once_with()
        board_adapter.has_preview.assert_called_once_with()
        board_adapter.has_preview_add_button.assert_called_once_with()
        board_adapter.enable_moving_cards_in_preview.assert_called_once_with()
        foo_iter_class._getClassname.assert_called_once_with()
        board_adapter.has_team.assert_has_calls([mock.call()])
        board_adapter.get_display_configs.assert_called_once_with()
        _display_config.assert_called_once_with("foo_config")
        return locals()

    @staticmethod
    def get_basic_result():
        return dict(
            active_sprint_id="foo_active_sprint_id",
            adjustNewCardURL="foo_link",
            cards=["foo_card_data"],
            columns=[dict(
                cdb_object_id="column_cdb_object_id",
                column_name="column_column_name",
                display_order="column_display_order",
                title="column_title"
            )],
            completed_sprints=["foo_view"],
            createOperations=['foo op view'],
            display_configs=dict(foo_config="foo_d_config"),
            enableGroupMoving="foo_moving",
            enableMoving="foo_move",
            extraOperations=['foo op view'],
            filters="foo_filters",
            group_types="foo_group_types",
            groups=["foo group view", "foo group view"],
            hasBacklog=True,
            hasEvaluation=True,
            hasPreview=True,
            hasPreviewAddButton="foo_button",
            hasTeam=True,
            headerDataFields=["context_object_id"],
            moveCardsURL="foo_link",
            next_sprint_id=None,
            rows=[dict(
                cdb_object_id="row_cdb_object_id",
                context_object_id="row_context_object_id",
                display_order="row_display_order",
                title="row_title"
            )],
            sprint_context_type="foo_iter_class_name",
            sprint_status=dict(
                foo_active_sprint_id="foo_current_status",
                foo_closed_sprint_id="foo_current_status",
                foo_next_sprint_id="foo_current_status",
                foo_open_sprint_id="foo_current_status"
            ),
            sprints=["foo_view"],
            teamAssigned=True,
            workingViewTitle="foo_view_title"
        )

    def check_get_board_view_with_backlog_eval_or_preview(self, **kwargs):
        test = self._get_board_view(**kwargs)
        expected_result = self.get_basic_result().copy()
        expected_result.update(**kwargs)
        self.maxDiff = None

        # mocked objects and methods
        result = test["result"]
        request = test["request"]
        active_sprint = test["active_sprint"]
        next_sprint = test["next_sprint"]
        open_sprint = test["open_sprint"]
        closed_sprint = test["closed_sprint"]
        workflow = test["Workflow"]
        board_adapter = test["board_adapter"]

        # additional checks
        request.view.assert_has_calls([
            mock.call(open_sprint, app='foo app'),
            mock.call(closed_sprint, app='foo app')
        ])
        workflow.assert_has_calls([
            mock.call(closed_sprint),
            mock.call(active_sprint),
            mock.call(next_sprint),
            mock.call(open_sprint),
        ])
        board_adapter.get_active_iteration.assert_called_once_with()
        self.assertEqual(result, expected_result)

    def test_get_board_view_01(self):
        "TestInternal 011: get_board_view: " \
            "(backlog, evaluation, preview, team)"
        test_args = dict(
            hasBacklog=True, hasEvaluation=True,
            hasPreview=True, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_02(self):
        "TestInternal 012: get_board_view: " \
            "(evaluation, preview, team)"
        test_args = dict(
            hasBacklog=False, hasEvaluation=True,
            hasPreview=True, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_03(self):
        "TestInternal 013: get_board_view: " \
            "(backlog, preview, team)"
        test_args = dict(
            hasBacklog=True, hasEvaluation=False,
            hasPreview=True, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_04(self):
        "TestInternal 014: get_board_view: " \
            "(backlog, evaluation, team)"
        test_args = dict(
            hasBacklog=True, hasEvaluation=True,
            hasPreview=False, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_05(self):
        "TestInternal 015: get_board_view: " \
            "(backlog, team)"
        test_args = dict(
            hasBacklog=True, hasEvaluation=False,
            hasPreview=False, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_06(self):
        "TestInternal 016: get_board_view: " \
            "(evaluation, team)"
        test_args = dict(
            hasBacklog=False, hasEvaluation=True,
            hasPreview=False, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_07(self):
        "TestInternal 017: get_board_view: " \
            "(preview, team)"
        test_args = dict(
            hasBacklog=False, hasEvaluation=False,
            hasPreview=True, hasTeam=True
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    def test_get_board_view_08(self):
        "TestInternal 018: get_board_view: " \
            "(team)"
        test_args = dict(
            hasBacklog=False, hasEvaluation=False,
            hasPreview=False, hasTeam=True
        )
        test = self._get_board_view(**test_args)
        expected_result = self.get_basic_result().copy()
        expected_result.update(
            active_sprint_id=None,
            sprints=[],
            sprint_status={},
            **test_args)
        self.maxDiff = None

        # mocked objects and methods
        result = test["result"]
        request = test["request"]
        workflow = test["Workflow"]
        board_adapter = test["board_adapter"]

        # additional checks
        request.view.assert_not_called()
        workflow.assert_not_called()
        board_adapter.get_active_iteration.assert_not_called()
        self.assertEqual(result, expected_result)

    def test_get_board_view_09(self):
        "TestInternal 019: get_board_view: " \
            "(backlog, evaluation, preview)"
        test_args = dict(
            hasBacklog=True, hasEvaluation=True,
            hasPreview=True, hasTeam=False, teamAssigned=False
        )
        self.check_get_board_view_with_backlog_eval_or_preview(
            **test_args)

    @mock.patch.object(internal.DDTextField, "ByKeys")
    def test_get_label_base_class(self, ByKeys):
        "long text field defined in base class 2"
        task_long_text = mock.MagicMock(spec=TaskLongTextModel)
        task_long_text.text_name = 'bar'
        task = mock.MagicMock()
        base_class_1 = mock.MagicMock()  # does not have field
        base_class_2 = mock.MagicMock()  # has field
        task.GetClassDef.return_value.getBaseClasses.return_value = [
            base_class_1, base_class_2,
        ]
        task_long_text.task = task


        def get_field(classname, _):
            if classname == base_class_2.getClassname.return_value:
                field = mock.MagicMock()
                field.getLabel.return_value = "foo"
                return field
            return None

        ByKeys.side_effect = get_field
        self.assertEqual(
            TaskLongTextModel.get_label(task_long_text),
            "foo",
        )
        self.assertEqual(ByKeys.call_count, 3)
        ByKeys.assert_has_calls([
            mock.call(task.GetClassDef.return_value.getClassname.return_value, task_long_text.text_name),
            mock.call(base_class_1.getClassname.return_value, task_long_text.text_name),
            mock.call(base_class_2.getClassname.return_value, task_long_text.text_name),
        ])

    @mock.patch.object(internal.DDTextField, "ByKeys", return_value=None)
    def test_get_label_no_field(self, ByKeys):
        "long text field can not be found"
        task_long_text = mock.MagicMock(spec=TaskLongTextModel)
        task_long_text.text_name = 'bar'
        task = mock.MagicMock()
        base_class = mock.MagicMock()
        task.GetClassDef.return_value.getBaseClasses.return_value = [
            base_class]
        task_long_text.task = task

        self.assertEqual(
            TaskLongTextModel.get_label(task_long_text),
            'bar',
        )
        self.assertEqual(ByKeys.call_count, 2)
        ByKeys.assert_has_calls([
            mock.call(task.GetClassDef.return_value.getClassname.return_value, task_long_text.text_name),
            mock.call(base_class.getClassname.return_value, task_long_text.text_name),
        ])


if __name__ == "__main__":
    unittest.main()
