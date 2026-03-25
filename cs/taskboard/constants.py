#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Definition of constants for cs.taskboard
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig


COLUMN_BACKLOG = "BACKLOG"
"""Type of backlog column, which contains not planned tasks"""

COLUMN_READY = "READY"
"""Type of column, which contains tasks ready to be done"""

COLUMN_DOING = "DOING"
"""Type of column, which contains tasks in processing"""

COLUMN_DONE = "DONE"
"""Type of column, which contains completed tasks"""

GROUP_RESPONSIBLE = "Responsible"
"""Group ID for grouping by responsible"""

GROUP_CATEGORY = "Category"
"""Group ID for grouping by category"""

GROUP_PRIORITY = "Priority"
"""Group ID for grouping by priority"""

SETTING_ID = "cs-taskboard-board_settings"

BOARD_DIALOG_ITEM_CHANGE_SIGNAL = sig.signal()
BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL = sig.signal()

BLANK_ICON = "BLANK_ICON"
"""Indicate that use a blank icon to hold the place to be displayed on a card"""

UI_VIEWS = {
    "BACKLOG": "0",
    "BOARD": "1",
    "TEAM": "2",
    "EVALUATION": "3",
    "PREVIEW": "4"
}
