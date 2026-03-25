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


from cdb import sqlapi


class AdjustCardsDisplayOrder(object):
    def run(self):
        for r in sqlapi.RecordSet2(sql="SELECT * FROM cs_taskboard_board"):
            self.update_positions(r.cdb_object_id)

    def update_positions(self, board_oid):
        stmt = """
        SELECT backlog, start_date, display_order, cdb_object_id FROM
            (SELECT c.board_object_id, i.start_date, display_order,
                    c.cdb_object_id, 0 AS backlog
             FROM cs_taskboard_card c JOIN cs_taskboard_iteration i
             ON c.sprint_object_id = i.cdb_object_id
             UNION
             SELECT c.board_object_id, NULL AS start_date, display_order,
                    c.cdb_object_id, 1 AS backlog
             FROM cs_taskboard_card c
             WHERE c.sprint_object_id IS NULL OR c.sprint_object_id = '') a
        WHERE board_object_id = '{board_oid}'
        ORDER BY backlog, start_date, display_order
        """.format(board_oid=board_oid)
        result = sqlapi.RecordSet2(sql=stmt)
        i = 0
        new_order = {}
        for r in result:
            i += 10
            new_order[r.cdb_object_id] = i
        stmt = """
        SELECT * FROM cs_taskboard_card WHERE board_object_id = '{board_oid}'
        """.format(board_oid=board_oid)
        for r in sqlapi.RecordSet2(sql=stmt):
            pos = new_order.get(r.cdb_object_id, None)
            if r.display_order != pos:
                upd_stmt = """
                UPDATE cs_taskboard_card
                SET display_order = {display_order}
                WHERE cdb_object_id = '{cdb_object_id}'
                """.format(cdb_object_id=r.cdb_object_id,
                           display_order=pos)
                sqlapi.RecordSet2(sql=upd_stmt)


class AdjustTeamIntervalBoards(object):
    def run(self):
        # adjust board_type and board_api
        sqlapi.SQLupdate(
            "cs_taskboard_board SET board_type = 'team_board', "
            "board_api = 'cs.taskboard.team_board.board_adapter.TeamBoardAdapter' "
            "WHERE board_api = 'cs.taskboard.team_interval_board.board_adapter.TeamIntervalBoardAdapter'"
        )

        # adjust column titles
        sqlapi.SQLupdate(
            "cs_taskboard_column SET title_de = 'Backlog', title_en = 'Backlog' "
            "WHERE column_name = 'READY' AND board_object_id IN "
            "(SELECT cdb_object_id FROM cs_taskboard_board WHERE board_type = 'team_board') "
        )
        sqlapi.SQLupdate(
            "cs_taskboard_column SET title_de = 'Bearbeitung', title_en = 'Doing' "
            "WHERE column_name = 'DOING' AND board_object_id IN "
            "(SELECT cdb_object_id FROM cs_taskboard_board WHERE board_type = 'team_board') "
        )


class InitializeCardsHiddenProperty(object):
    """
    Cards may exist invisibly on the board.
    The new field of the class card needs an initial value for the code to do the right thing at runtime.
    """

    def run(self):
        """
        The update statement will be executed
        """
        sqlapi.SQLupdate("cs_taskboard_card set is_hidden = 0 where is_hidden is NULL")


pre = []
post = [AdjustCardsDisplayOrder,
        AdjustTeamIntervalBoards,
        InitializeCardsHiddenProperty]
