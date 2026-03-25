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


from cs.taskboard.column_mappers import OLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.issues import Issue
from cs.pcs.taskboards.issues.display_attributes import IssueDisplayAttributes
from cs.pcs.taskboards.utils import on_iteration_start_post


class SprintBoardIssueColumnMapper(OLCColumnMapper):

    STATUS_TO_COLUMN = {
        Issue.NEW.status: [COLUMN_READY],
        Issue.EVALUATION.status: [COLUMN_READY],
        Issue.DEFERRED.status: [COLUMN_READY],
        Issue.EXECUTION.status: [COLUMN_DOING],
        Issue.WAITINGFOR.status: [COLUMN_DOING],
        Issue.REVIEW.status: [COLUMN_DOING],
        Issue.DISCARDED.status: [COLUMN_DONE],
        Issue.COMPLETED.status: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [
            Issue.EVALUATION.status,
            Issue.NEW.status,
            Issue.DEFERRED.status,
        ],
        COLUMN_DOING: [
            Issue.EXECUTION.status,
            Issue.WAITINGFOR.status,
            Issue.REVIEW.status,
        ],
        COLUMN_DONE: [Issue.COMPLETED.status, Issue.DISCARDED.status],
    }


class SprintBoardIssueAdapter(CardAdapter):
    COLUMN_MAPPER = SprintBoardIssueColumnMapper
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
