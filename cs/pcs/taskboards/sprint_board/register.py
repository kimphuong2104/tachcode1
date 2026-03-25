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
from cs.taskboard.sprint_board.board_adapter import SprintBoardAdapter

from cs.pcs.issues import Issue
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.sprint_board import (
    context_adapters,
    issue_card_adapter,
    task_card_adapter,
)


@sig.connect(REGISTER_BOARD_ADAPTER, SprintBoardAdapter)
def register_sprint_board():
    # pylint: disable=protected-access
    return {
        "card_adapters": {
            Issue._getClassname(): {
                "adapter": issue_card_adapter.SprintBoardIssueAdapter
            },
            Task._getClassname(): {"adapter": task_card_adapter.SprintBoardTaskAdapter},
        },
        "context_adapters": {
            Project._getClassname(): context_adapters.SprintBoardProjectContextAdapter,
            Task._getClassname(): context_adapters.SprintBoardTaskContextAdapter,
        },
    }
