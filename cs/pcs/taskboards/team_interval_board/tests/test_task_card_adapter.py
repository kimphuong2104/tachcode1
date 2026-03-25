#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase
from cs.taskboard.objects import Board, Card, Column

from cs.pcs.taskboards.team_interval_board.task_card_adapter import (
    TeamIntervalBoardTaskAdapter,
)


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TestTeamIntervalBoardTaskAdapter(unittest.TestCase):
    @mock.patch.object(TeamIntervalBoardTaskAdapter, "set_due_date")
    def test_on_change_position_post_COLUMN_READY(self, set_due_date):
        "Team Interval Board: Change position from Task card to column 'READY'"
        # create board
        board = mock.MagicMock(autospec=Board)
        board.get_present_timeframe.return_value = ("start", "end")

        # create column
        column = mock.MagicMock(autospec=Column)
        column.return_value = "right column"

        # create board adapter instance
        board_adapter = mock.MagicMock(autospec=TeamIntervalBoardTaskAdapter)
        board_adapter.get_column_by_type.side_effect = ["wrong column", column]

        # create card
        card = mock.MagicMock(autospec=Card)
        card.Board = board
        card.TaskObject = "reference"
        card.Column = column

        # call of actual method to test
        TeamIntervalBoardTaskAdapter.on_change_position_post(board_adapter, card)

        # checks: have the calls been made correctly?
        board.get_present_timeframe.assert_called_once()
        calls = [mock.call("DOING"), mock.call("READY")]
        board_adapter.get_column_by_type.assert_has_calls(calls, any_order=False)
        set_due_date.assert_called_with("reference", "")

    @mock.patch.object(TeamIntervalBoardTaskAdapter, "set_due_date")
    def test_on_change_position_post_COLUMN_DOING(self, set_due_date):
        "Team Interval Board: Change position from Task card to column 'DOING'"
        # create board
        board = mock.MagicMock(autospec=Board)
        board.get_present_timeframe.return_value = ("start", "end")

        # create column
        column = mock.MagicMock(autospec=Column)
        column.return_value = "right column"

        # create board adapter instance
        board_adapter = mock.MagicMock(autospec=TeamIntervalBoardTaskAdapter)
        board_adapter.get_column_by_type.side_effect = [column, "wrong column"]

        # create card
        card = mock.MagicMock(autospec=Card)
        card.Board = board
        card.TaskObject = "reference"
        card.Column = column

        # call of actual method to test
        TeamIntervalBoardTaskAdapter.on_change_position_post(board_adapter, card)

        # checks: have the calls been made correctly?
        board.get_present_timeframe.assert_called_once()
        calls = [mock.call("DOING")]
        board_adapter.get_column_by_type.assert_has_calls(calls, any_order=False)
        set_due_date.assert_called_with("reference", "end")
