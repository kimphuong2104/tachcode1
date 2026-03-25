#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cs.taskboard.column_mappers import TeamOLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.issues import Issue
from cs.pcs.taskboards.issues.display_attributes import IssueDisplayAttributes
from cs.pcs.taskboards.team_board import util


class TeamBoardIssueColumnMapper(TeamOLCColumnMapper):

    STATUS_TO_COLUMN = {
        0: [COLUMN_READY],
        30: [COLUMN_READY],
        50: [COLUMN_DOING],
        60: [COLUMN_READY],
        70: [COLUMN_DOING],
        100: [COLUMN_DOING],
        180: [COLUMN_DONE],
        200: [COLUMN_DONE],
    }

    COLUMN_TO_STATUS = {
        COLUMN_READY: [30, 0, 60],
        COLUMN_DOING: [50, 70, 100],
        COLUMN_DONE: [200, 180],
    }


class TeamBoardIssueAdapter(CardAdapter):
    COLUMN_MAPPER = TeamBoardIssueColumnMapper
    DISPLAY_ATTRIBUTES = IssueDisplayAttributes
    DUE_DATE_ATTRIBUTE = "target_date"
    COMPLETION_DATE_ATTRIBUTE = "completion_date"
    STATUS_NEW = set([0])
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
        # all issues that are assigned to the team within the given time frame
        subjects = cls.get_available_subjects_sql_condition(board_adapter)
        if not subjects:
            return set()

        # all issues that are assigned to an active board or no board at all
        valid_boards = cls.get_valid_boards_sql_condition()

        start, end = board.get_total_timeframe()
        if not start or not end:
            return set()
        start = sqlapi.SQLdbms_date(start)
        end = sqlapi.SQLdbms_date(end)

        status_1 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_READY])
        status_2 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DOING])
        status_3 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DONE])
        status_4 = (status_1 | status_2) - cls.STATUS_NEW

        stmt = """SELECT DISTINCT t.*
            FROM cdbpcs_issue t
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
            AND ((t.status IN ({status_3})
                  AND t.completion_date >= {start}
                  AND t.completion_date <= {end}
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.target_date IS NULL
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.target_date <= {end}
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
        )
        return sqlapi.RecordSet2(sql=stmt)

    @classmethod
    def set_due_date(cls, task, due_date, overwrite=False):
        super(TeamBoardIssueAdapter, cls).set_due_date(task, due_date, overwrite=True)

    @classmethod
    def get_create_operation(cls, board_adapter):
        return {"class": Issue}
