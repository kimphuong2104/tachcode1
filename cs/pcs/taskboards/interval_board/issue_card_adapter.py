#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cs.taskboard.column_mappers import DateColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.issues import Issue
from cs.pcs.taskboards.issues.display_attributes import IssueDisplayAttributes
from cs.pcs.taskboards.utils import on_iteration_start_post


class IntervalBoardIssueColumnMapper(DateColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_READY, COLUMN_DOING],
        30: [COLUMN_READY, COLUMN_DOING],
        50: [COLUMN_READY, COLUMN_DOING],
        60: [COLUMN_READY, COLUMN_DOING],
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


class IntervalBoardIssueAdapter(CardAdapter):
    COLUMN_MAPPER = IntervalBoardIssueColumnMapper
    DISPLAY_ATTRIBUTES = IssueDisplayAttributes
    DUE_DATE_ATTRIBUTE = "target_date"
    COMPLETION_DATE_ATTRIBUTE = "completion_date"
    PROTOCOL_TABLE = "cdbpcs_iss_prot"
    USE_CDB_MDATE = True

    @classmethod
    def get_available_records(cls, board_adapter):
        board = board_adapter.get_board()
        return board.ContextObject.get_issues_for_board()

    @classmethod
    def set_due_date(cls, task, due_date, overwrite=False):
        super(IntervalBoardIssueAdapter, cls).set_due_date(
            task, due_date, overwrite=True
        )

    @classmethod
    def on_change_position_post(cls, board_adapter, card):
        task = card.TaskObject
        sprint = card.Iteration
        if task and sprint:
            if board_adapter.get_column_by_type(COLUMN_DOING) == card.Column:
                cls.set_due_date(task, sprint.end_date)
            elif board_adapter.get_column_by_type(COLUMN_READY) == card.Column:
                cls.set_due_date(task, "")

    @classmethod
    def get_create_operation(cls, board_adapter):
        ctx = board_adapter.get_board().ContextObject
        return {
            "class": Issue,
            "arguments": {
                "cdb_project_id": ctx.cdb_project_id,
                "task_id": getattr(ctx, "task_id", ""),
            },
        }

    @classmethod
    def on_iteration_start_post(cls, board_adapter, iteration):
        on_iteration_start_post(board_adapter, iteration, cls)
