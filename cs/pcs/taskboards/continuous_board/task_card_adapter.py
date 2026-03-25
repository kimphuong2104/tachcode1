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

from cs.pcs.taskboards.tasks.display_attributes import TaskDisplayAttributes


class ContinuousBoardTaskColumnMapper(OLCColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_BACKLOG],
        20: [COLUMN_READY],
        50: [COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
        250: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_BACKLOG: 0,
        COLUMN_READY: 20,
        COLUMN_DOING: 50,
        COLUMN_DONE: 200,
    }


class ContinuousBoardTaskAdapter(CardAdapter):
    COLUMN_MAPPER = ContinuousBoardTaskColumnMapper
    DISPLAY_ATTRIBUTES = TaskDisplayAttributes

    @classmethod
    def get_available_object_ids(cls, board_adapter):
        board = board_adapter.get_board()
        if board.ContextObject:
            return set(
                r.cdb_object_id
                for r in board.ContextObject.get_project_tasks_for_board()
            )
        return set()

    def get_responsible(self):
        return self.task.Subject
