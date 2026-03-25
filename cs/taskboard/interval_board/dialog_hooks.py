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
from cs.taskboard.constants import BOARD_DIALOG_ITEM_CHANGE_SIGNAL
from cs.taskboard.constants import BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL
from cs.taskboard.interval_board import INTERVAL_BOARD_TYPE


@sig.connect(BOARD_DIALOG_ITEM_CHANGE_SIGNAL)
def taskboard_dialog_item_change(ctx, tmpl_board):
    """
    Legacy event handler for mask in Desktop Client
    """
    if ctx.changed_item != "template_object_id":
        return
    if tmpl_board.board_type == INTERVAL_BOARD_TYPE:
        fields = ["interval_length", "interval_name", "interval_type"]
        for field in fields:
            ctx.set_mandatory(field)
            ctx.set(field, tmpl_board[field])
        ctx.set_mandatory("start_date")
        ctx.set_fields_writeable(fields + ["start_date"])
        ctx.set_readonly("auto_create_iteration")
        ctx.set("auto_create_iteration", "")


@sig.connect(BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL)
def change_board_type(hook, tmpl):
    """
    Specific dialog hook for WebUI usage
    """
    changed_fields = hook.get_changed_fields()
    if ".template_object_id" not in changed_fields or not tmpl:
        return
    if tmpl.board_type == INTERVAL_BOARD_TYPE:
        fields = [".interval_length", ".interval_name", ".interval_type"]
        for field in fields:
            hook.set_mandatory(field)
            hook.set_writeable(field)
            hook.set(field, tmpl[field[1:]])
        hook.set_mandatory(".start_date")
        hook.set_writeable(".start_date")
        hook.set_readonly(".auto_create_iteration")
        hook.set(".auto_create_iteration", "")
