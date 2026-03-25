#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sqlapi, ue
from cs.taskboard.column_mappers import TeamOLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.tasks.display_attributes import TaskDisplayAttributes
from cs.pcs.taskboards.team_board import util


class TeamBoardTaskColumnMapper(TeamOLCColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_READY],
        20: [COLUMN_READY],
        50: [COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
        250: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [20, 0],
        COLUMN_DOING: [50],
        COLUMN_DONE: [200, 180, 250],
    }


class TeamBoardTaskAdapter(CardAdapter):
    COLUMN_MAPPER = TeamBoardTaskColumnMapper
    DISPLAY_ATTRIBUTES = TaskDisplayAttributes
    DUE_DATE_ATTRIBUTE = "end_time_fcast"
    COMPLETION_DATE_ATTRIBUTE = "end_time_act"
    STATUS_NEW = set([0])
    STATUS_CLOSED = set([250])
    USE_CDB_MDATE = True

    @classmethod
    def get_available_subjects_sql_condition(cls, board):
        return util.get_available_subjects_sql_condition(board)

    @classmethod
    def get_valid_boards_sql_condition(cls):
        return util.get_valid_boards_sql_condition()

    @classmethod
    def get_available_records(cls, board_adapter):
        board = board_adapter.get_board()
        # all tasks that are assigned to the team within the given time frame
        subjects = cls.get_available_subjects_sql_condition(board_adapter)
        if not subjects:
            return set()

        # all tasks that are assigned to an active board or no board at all
        valid_boards = cls.get_valid_boards_sql_condition()

        start, end = board.get_total_timeframe()
        if not start or not end:
            return set()
        start = sqlapi.SQLdbms_date(start)
        end = sqlapi.SQLdbms_date(end)
        # FIXME: also check whether the target column available on board
        # available_columns = board.Adapter.get_column_types()
        status_1 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_READY])
        status_2 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DOING])
        status_3 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DONE])
        status_4 = (status_1 | status_2) - cls.STATUS_NEW
        status_5 = status_3 - cls.STATUS_CLOSED

        stmt = """SELECT DISTINCT t.*
            FROM cdbpcs_task t
            LEFT JOIN (SELECT cs_taskboard_card.context_object_id,
                              cs_taskboard_card.sprint_object_id,
                              cs_taskboard_card.board_object_id
                       FROM cs_taskboard_card, cs_taskboard_board
                       WHERE cs_taskboard_card.board_object_id = cs_taskboard_board.cdb_object_id
                       AND (cs_taskboard_board.is_aggregation = 0
                            OR cs_taskboard_board.is_aggregation IS NULL)
                       ) c
            ON c.context_object_id = t.cdb_object_id
            LEFT JOIN cs_taskboard_iteration s
            ON c.sprint_object_id = s.cdb_object_id
            WHERE ({subjects})
            AND ({valid_boards})
            AND t.ce_baseline_id = ''
            AND t.is_group != 1
            AND ((t.status IN ({status_5})
                  AND t.end_time_act >= {start}
                  AND t.end_time_act <= {end}
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.end_time_fcast IS NULL
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.end_time_fcast <= {end}
                 )
                  OR
                 (c.sprint_object_id IS NOT NULL
                  AND t.status IN ({status_3})
                  AND s.start_date <= {end}
                  AND s.status IN (0, 50)
                 )
                  OR
                 (c.sprint_object_id IS NOT NULL
                  AND t.status IN ({status_3})
                  AND s.start_date <= {end}
                  AND s.end_date >= {start}
                 )
                  OR
                 (c.sprint_object_id IS NOT NULL
                  AND t.status IN ({status_2})
                  AND s.start_date <= {end}
                 )
                  OR
                 (c.sprint_object_id IS NOT NULL
                  AND t.status IN ({status_1})
                  AND s.start_date <= {end}
                 )
                )
            """.format(
            subjects=subjects,
            start=start,
            end=end,
            valid_boards=valid_boards,
            status_1=",".join([str(x) for x in status_1]),
            status_2=",".join([str(x) for x in status_2]),
            status_3=",".join([str(x) for x in status_3]),
            status_4=",".join([str(x) for x in status_4]),
            status_5=",".join([str(x) for x in status_5]),
        )
        return sqlapi.RecordSet2(sql=stmt)

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
        super(TeamBoardTaskAdapter, cls).on_change_position_pre(
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
    def get_create_operation(cls, board_adapter):
        return {"class": Task}
