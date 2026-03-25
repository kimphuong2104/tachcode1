# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
The ActionCardAdapter maps columns to the respective status values
and provides methods that determine the actions to be displayed
on the board.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"


from cs.taskboard.column_mappers import OLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.actions import Action
from cs.actions.taskboards.display_attributes import ActionDisplayAttributes
from cs.actions.taskboards.utils import on_iteration_start_post


class SprintBoardActionColumnMapper(OLCColumnMapper):
    STATUS_TO_COLUMN = {
        Action.EDITING.status: [COLUMN_READY],
        Action.IN_WORK.status: [COLUMN_DOING],
        Action.DISCARDED.status: [COLUMN_DONE],
        Action.FINISHED.status: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [Action.EDITING.status],
        COLUMN_DOING: [Action.IN_WORK.status],
        COLUMN_DONE: [Action.FINISHED.status, Action.DISCARDED.status],
    }


class SprintBoardActionCardAdapter(CardAdapter):
    COLUMN_MAPPER = SprintBoardActionColumnMapper
    DISPLAY_ATTRIBUTES = ActionDisplayAttributes
    DUE_DATE_ATTRIBUTE = "end_time_plan"
    COMPLETION_DATE_ATTRIBUTE = "end_time_act"

    @classmethod
    def get_available_records(cls, board_adapter):
        board = board_adapter.get_board()
        if hasattr(board.ContextObject, "get_actions_for_board"):
            # API support for cs.pcs 15.4.5 and later
            return board.ContextObject.get_actions_for_board()
        # Support of API up to cs.pcs 15.4.4
        # Can be removed if all versions of cs.pcs up to and including 15.4.4
        # are no longer supported.
        return board.ContextObject.getBoardActions()

    @classmethod
    def get_create_operation(cls, board_adapter):
        ctx = board_adapter.get_board().ContextObject
        return {
            "class": Action,
            "arguments": {
                "cdb_project_id": getattr(ctx, "cdb_project_id", ""),
                "task_id": getattr(ctx, "task_id", ""),
            },
        }

    @classmethod
    def on_iteration_start_post(cls, board_adapter, iteration):
        on_iteration_start_post(board_adapter, iteration, cls)
