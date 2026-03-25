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


from cdb import sig
from cs.taskboard.interfaces.register import REGISTER_BOARD_ADAPTER
from cs.taskboard.personal_board.board_adapter import PersonalBoardAdapter

from cs.pcs.issues import Issue
from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.personal_board import issue_card_adapter, task_card_adapter


@sig.connect(REGISTER_BOARD_ADAPTER, PersonalBoardAdapter)
def register_interval_board():
    # pylint: disable=protected-access
    return {
        "card_adapters": {
            Issue._getClassname(): {
                "adapter": issue_card_adapter.PersonalBoardIssueAdapter
            },
            Task._getClassname(): {
                "adapter": task_card_adapter.PersonalBoardTaskAdapter
            },
        },
        "context_adapters": {},
    }
