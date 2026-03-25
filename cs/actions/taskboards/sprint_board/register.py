# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This method is responsible for registering the ActionCardAdapter
for each board.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cdb import sig
from cs.taskboard.interfaces.register import REGISTER_BOARD_ADAPTER
from cs.taskboard.sprint_board.board_adapter import SprintBoardAdapter

from cs.actions import Action
from cs.actions.taskboards.sprint_board import action_card_adapter


@sig.connect(REGISTER_BOARD_ADAPTER, SprintBoardAdapter)
def register_sprint_board():
    return {
        "card_adapters": {
            Action._getClassname(): {  # pylint: disable=protected-access
                "adapter": action_card_adapter.SprintBoardActionCardAdapter
            },
        },
        "context_adapters": {},
    }
