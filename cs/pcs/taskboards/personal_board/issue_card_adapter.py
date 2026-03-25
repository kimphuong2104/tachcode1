#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime

import cdbwrapc
from cdb import auth, sqlapi
from cdb import util as cdbutil
from cs.taskboard.column_mappers import OLCColumnMapper
from cs.taskboard.constants import COLUMN_DOING, COLUMN_DONE, COLUMN_READY
from cs.taskboard.interfaces.card_adapter import CardAdapter

from cs.pcs.issues import Issue
from cs.pcs.substitute.util import is_substitute_licensed
from cs.pcs.taskboards.issues.display_attributes import IssueDisplayAttributes
from cs.pcs.taskboards.team_board import util


class PersonalBoardIssueColumnMapper(OLCColumnMapper):

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


class PersonalBoardIssueAdapter(CardAdapter):
    COLUMN_MAPPER = PersonalBoardIssueColumnMapper
    DISPLAY_ATTRIBUTES = IssueDisplayAttributes
    DUE_DATE_ATTRIBUTE = "target_date"
    COMPLETION_DATE_ATTRIBUTE = "completion_date"
    TIME_DIFF = 7
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
        # all issues that are assigned to the team within the given time frame
        subjects = cls.get_available_subjects_sql_condition(board_adapter)

        # all issues that are assigned to an active board or no board at all
        valid_boards = cls.get_valid_boards_sql_condition()

        status_1 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_READY])
        status_2 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DOING])
        status_3 = set(cls.COLUMN_MAPPER.COLUMN_TO_STATUS[COLUMN_DONE])
        status_4 = (status_1 | status_2) - cls.STATUS_NEW
        ref_date = datetime.datetime.today()
        ref_date -= datetime.timedelta(days=cls.TIME_DIFF)
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
            AND ((c.board_object_id IS NULL
                  AND t.status IN ({status_3})
                  AND t.completion_date >= {ref_date}
                 )
                  OR
                 (c.board_object_id IS NULL
                  AND t.status IN ({status_4})
                 )
                  OR
                 (c.sprint_object_id IS NOT NULL
                  AND s.status = 50
                  AND (
                      t.status NOT IN ({status_3})
                      OR
                      (t.status IN ({status_3})
                      AND t.completion_date >= {ref_date})
                  )
                 )
                )
            """.format(
            ref_date=sqlapi.SQLdbms_date(ref_date),
            status_3=",".join([str(x) for x in status_3]),
            status_4=",".join([str(x) for x in status_4]),
            valid_boards=valid_boards,
            subjects=subjects,
        )
        return sqlapi.RecordSet2(sql=stmt)

    @classmethod
    def get_create_operation(cls, board_adapter):
        board = board_adapter.get_board()
        me = board.ContextObject
        return {
            "class": Issue,
            "arguments": {
                "subject_id": me.personalnummer,
                "subject_type": me.SubjectType(),
            },
        }

    @classmethod
    def get_filters(cls, board_adapter, card, task):
        f = {}
        if is_substitute_licensed():
            label = "cs_taskboard_substitute_own"
            value = "own"
            order = 1
            additional_label = ""
            additional_value = ""
            if task.subject_id != auth.persno:
                label = "cs_taskboard_substitute_absent_all"
                value = "all"
                additional_label = "cs_taskboard_substitute_absent_day"
                order = 2
                if cdbwrapc.user_substitute_is_absent(task.subject_id):
                    additional_value = "day"
            f["substitute_filter"] = {
                "label": cdbutil.get_label(label),
                "value": value,
                # Special implementation for substitute_filter do not use otherwise
                "order": order,
                "additional_label": cdbutil.get_label(additional_label)
                if additional_label
                else "",
                "additional_value": additional_value,
            }
        return f
