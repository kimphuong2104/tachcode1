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

from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.tasks.display_attributes import TaskDisplayAttributes
from cs.pcs.taskboards.utils import on_iteration_start_post


class SprintBoardTaskColumnMapper(OLCColumnMapper):

    STATUS_TO_COLUMN = {
        Task.NEW.status: [COLUMN_READY],
        Task.READY.status: [COLUMN_READY],
        Task.EXECUTION.status: [COLUMN_DOING],
        Task.DISCARDED.status: [COLUMN_DONE],
        Task.FINISHED.status: [COLUMN_DONE],
        Task.COMPLETED.status: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [Task.READY.status, Task.NEW.status],
        COLUMN_DOING: [Task.EXECUTION.status],
        COLUMN_DONE: [
            Task.FINISHED.status,
            Task.DISCARDED.status,
            Task.COMPLETED.status,
        ],
    }


class SprintBoardTaskAdapter(CardAdapter):
    COLUMN_MAPPER = SprintBoardTaskColumnMapper
    DISPLAY_ATTRIBUTES = TaskDisplayAttributes
    DUE_DATE_ATTRIBUTE = "end_time_fcast"
    COMPLETION_DATE_ATTRIBUTE = "end_time_act"
    PROTOCOL_TABLE = "cdbpcs_tsk_prot"
    USE_CDB_MDATE = True

    @classmethod
    def get_available_records(cls, board_adapter):
        board = board_adapter.get_board()
        return board.ContextObject.get_project_tasks_for_board()

    @classmethod
    def get_create_operation(cls, board_adapter):
        ctx = board_adapter.get_board().ContextObject
        return {
            "class": Task,
            "arguments": {
                "cdb_project_id": ctx.cdb_project_id,
                "parent_task": getattr(ctx, "task_id", ""),
                "ce_baseline_id": "",
            },
        }

    @classmethod
    def on_iteration_start_post(cls, board_adapter, iteration):
        on_iteration_start_post(board_adapter, iteration, cls)
