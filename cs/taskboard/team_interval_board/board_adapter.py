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


from cs.platform.web.rest.generic import convert
from cs.taskboard.constants import COLUMN_DOING
from cs.taskboard.team_board.board_adapter import TeamBoardAdapter


class TeamIntervalBoardAdapter(TeamBoardAdapter):

    def get_change_position_followup(self, card, row, column):
        if self.get_column_type(column) == COLUMN_DOING:
            start, end = card.Board.get_present_timeframe()
            args = {
                "cdb::argument.valid_start": convert.dump_datetime(start),
                "cdb::argument.valid_end": convert.dump_datetime(end)
            }
            return dict(name="cs_taskboard_move_card",
                        arguments=args)
        return None
