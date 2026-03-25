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
from cs.taskboard.objects import Board
from cs.taskboard.continuous_board import CONTINUOUS_BOARD_TYPE
from cs.taskboard.constants import BOARD_DIALOG_ITEM_CHANGE_SIGNAL
from cs.taskboard.constants import BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL


@sig.connect(BOARD_DIALOG_ITEM_CHANGE_SIGNAL)
def taskboard_dialog_item_change(ctx, tmpl_board):
    """
    Legacy event handler for mask in Desktop Client.
    """
    if ctx.changed_item != "template_object_id":
        return
    if tmpl_board.board_type == CONTINUOUS_BOARD_TYPE:
        fields = ["interval_length", "interval_name",
                  "start_date", "auto_create_iteration"]
        for field in fields:
            ctx.set_optional(field)
            ctx.set(field, "")
        ctx.set_fields_readonly(fields)
        ctx.set("interval_type", "")


@sig.connect(BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL)
def change_board_type(hook, tmpl):
    changed_fields = hook.get_changed_fields()
    if ".template_object_id" not in changed_fields or not tmpl:
        return
    if tmpl.board_type == CONTINUOUS_BOARD_TYPE:
        for field in [".interval_length", ".interval_name",
                      ".start_date", ".auto_create_iteration"]:
            hook.set_optional(field)
            hook.set_readonly(field)
            hook.set(field, "")
        hook.set(".interval_type", "")
