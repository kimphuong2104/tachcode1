#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import ue
from cs.taskboard.column_mappers import DateColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.tasks.display_attributes import TaskDisplayAttributes
from cs.pcs.taskboards.utils import on_iteration_start_post


class IntervalBoardTaskColumnMapper(DateColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_READY, COLUMN_DOING],
        20: [COLUMN_READY, COLUMN_DOING],
        50: [COLUMN_READY, COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
        250: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [20, 50, 0],
        COLUMN_DOING: [20, 50, 0],
        COLUMN_DONE: [200, 180, 250],
    }


class IntervalBoardTaskAdapter(CardAdapter):
    COLUMN_MAPPER = IntervalBoardTaskColumnMapper
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
    def set_due_date(cls, task, due_date, overwrite=False):
        if due_date:
            constraints = task._determineConstraints(end=due_date)
            if not task.end_time_fcast or overwrite:
                if task.days_fcast:
                    task.setTimeframe(days=task.days_fcast, end=due_date, **constraints)
                else:
                    task.setTimeframe(start=due_date, end=due_date, **constraints)
        elif task.end_time_fcast:
            task.setTimeframe(end="", days=task.days_fcast)

    @classmethod
    def on_change_position_pre(cls, board_adapter, card, row, column):
        super(IntervalBoardTaskAdapter, cls).on_change_position_pre(
            board_adapter, card, row, column
        )
        task = board_adapter.get_card_task(card)
        if (
            COLUMN_READY == board_adapter.get_column_type(column)
            and task
            and task.automatic
        ):
            raise ue.Exception("cs_taskboard_automatic_calculated")

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
