#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.taskboard.column_mappers import TeamDateColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY

from cs.pcs.taskboards.team_board.issue_card_adapter import TeamBoardIssueAdapter


class TeamIntervalBoardIssueColumnMapper(TeamDateColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_READY, COLUMN_DOING],
        30: [COLUMN_READY, COLUMN_DOING],
        50: [COLUMN_READY, COLUMN_DOING],
        70: [COLUMN_READY, COLUMN_DOING],
        100: [COLUMN_READY, COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [30, 50, 70, 100, 0],
        COLUMN_DOING: [30, 50, 70, 100, 0],
        COLUMN_DONE: [200, 180],
    }


class TeamIntervalBoardIssueAdapter(TeamBoardIssueAdapter):
    COLUMN_MAPPER = TeamIntervalBoardIssueColumnMapper

    @classmethod
    def on_change_position_post(cls, board_adapter, card):
        task = card.TaskObject
        board = card.Board
        _, end = board.get_present_timeframe()
        if task and board:
            if board_adapter.get_column_by_type(COLUMN_DOING) == card.Column:
                cls.set_due_date(task, end)
            elif board_adapter.get_column_by_type(COLUMN_READY) == card.Column:
                cls.set_due_date(task, "")
