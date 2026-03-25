#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sig
from cs.taskboard.interfaces.register import REGISTER_BOARD_ADAPTER
from cs.taskboard.team_board.board_adapter import TeamBoardAdapter

from cs.pcs.issues import Issue
from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.team_board import issue_card_adapter, task_card_adapter


@sig.connect(REGISTER_BOARD_ADAPTER, TeamBoardAdapter)
def register_team_board():
    return {
        "card_adapters": {
            Issue._getClassname(): {
                "adapter": issue_card_adapter.TeamBoardIssueAdapter
            },
            Task._getClassname(): {"adapter": task_card_adapter.TeamBoardTaskAdapter},
        },
        "context_adapters": {},
    }
