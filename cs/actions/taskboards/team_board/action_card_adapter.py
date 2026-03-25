# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
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


from cdb import sqlapi
from cs.taskboard.column_mappers import TeamOLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.actions import Action
from cs.actions.taskboards.display_attributes import ActionDisplayAttributes
from cs.actions.taskboards.team_board import util


class TeamBoardActionColumnMapper(TeamOLCColumnMapper):

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


class TeamBoardActionCardAdapter(CardAdapter):
    COLUMN_MAPPER = TeamBoardActionColumnMapper
    DISPLAY_ATTRIBUTES = ActionDisplayAttributes
    DUE_DATE_ATTRIBUTE = "end_time_plan"
    COMPLETION_DATE_ATTRIBUTE = "end_time_act"
    STATUS_NEW = set([Action.EDITING.status])

    @classmethod
    def get_available_subjects_sql_condition(cls, board):
        return util.get_available_subjects_sql_condition(board)

    @classmethod
    def get_valid_boards_sql_condition(cls):
        return util.get_valid_boards_sql_condition()

    @classmethod
    def get_available_records(cls, board_adapter):
        # Disable linting warning 'line too long' in this function
        # pylint: disable=line-too-long

        board = board_adapter.get_board()
        # all actions that are assigned to the team within the given time frame
        subjects = cls.get_available_subjects_sql_condition(board_adapter)
        if not subjects:
            return set()

        # all actions that are assigned to an active board or no board at all
        valid_boards = cls.get_valid_boards_sql_condition()

        start, end = board.get_total_timeframe()
        if not start or not end:
            return set()
        start = sqlapi.SQLdbms_date(start)
        end = sqlapi.SQLdbms_date(end)

        status_1 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_READY])
        status_2 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DOING])
        status_3 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DONE])
        status_4 = status_1.union(status_2)

        stmt = """SELECT DISTINCT t.*
            FROM cdb_action t
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
            AND ((c.board_object_id IS NULL
                  AND t.status IN ({status_3})
                  AND t.end_time_act >= {start}
                  AND t.end_time_act <= {end}
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.end_time_plan IS NULL
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                  AND t.end_time_plan <= {end}
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
    def get_create_operation(cls, board_adapter):
        return {"class": Action}
