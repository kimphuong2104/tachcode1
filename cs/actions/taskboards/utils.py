# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Provides a method to manage the state of actions if an iteration starts.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

from cs.taskboard.constants import COLUMN_READY
from cs.taskboard.utils import auto_change_card_task_status


def on_iteration_start_post(board_adapter, iteration, card_adapter):
    # Set every Action into ready, if iteration starts.
    # In this case status 0 is aquivalent to status NEW
    from_status = [0]
    to = card_adapter.COLUMN_MAPPER.COLUMN_TO_STATUS.get(COLUMN_READY, [])
    if not to:
        return
    to_status = to[0]
    cards = card_adapter.get_cards_for_iteration(board_adapter, iteration)
    auto_change_card_task_status(board_adapter, cards, from_status, to_status)
