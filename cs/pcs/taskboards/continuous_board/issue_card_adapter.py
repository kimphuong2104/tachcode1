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
from cs.taskboard.constants import (
    COLUMN_BACKLOG,
    COLUMN_DOING,
    COLUMN_DONE,
    COLUMN_READY,
)
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.taskboards.issues.display_attributes import IssueDisplayAttributes


class ContinuousBoardIssueColumnMapper(OLCColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_BACKLOG],
        30: [COLUMN_BACKLOG, COLUMN_READY],
        50: [COLUMN_DOING],
        60: [COLUMN_BACKLOG],
        70: [COLUMN_DOING],
        100: [COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_BACKLOG: 60,
        COLUMN_READY: 30,
        COLUMN_DOING: 50,
        COLUMN_DONE: 200,
    }


class ContinuousBoardIssueAdapter(CardAdapter):
    COLUMN_MAPPER = ContinuousBoardIssueColumnMapper
    DISPLAY_ATTRIBUTES = IssueDisplayAttributes

    @classmethod
    def get_available_object_ids(cls, board_adapter):
        board = board_adapter.get_board()
        if board.ContextObject:
            return set(
                r.cdb_object_id for r in board.ContextObject.get_issues_for_board()
            )
        return set()

    def get_responsible(self):
        return self.task.Subject
