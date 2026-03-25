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
from cs.taskboard.team_board import TEAM_BOARD_TYPE
from cdb import util
from cs.taskboard.objects import Board
from cdb import typeconversion


@sig.connect(BOARD_DIALOG_ITEM_CHANGE_SIGNAL)
def taskboard_dialog_item_change(ctx, tmpl_board):
    """
    Legacy event handler for mask in Desktop Client
    """
    if ctx.changed_item != "template_object_id":
        return
    if tmpl_board.board_type == TEAM_BOARD_TYPE:
        fields = ["interval_length", "interval_name",
                  "start_date", "auto_create_iteration"]
        for field in fields:
            ctx.set_mandatory(field)
        ctx.set_fields_writeable(fields)


@sig.connect(BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL)
def change_board_type(hook, tmpl):
    """
    Specific dialog hook for WebUI usage
    """
    changed_fields = hook.get_changed_fields()
    if ".template_object_id" not in changed_fields or not tmpl:
        return
    if tmpl.board_type == TEAM_BOARD_TYPE:
        for field in [".interval_length", ".interval_name",
                      ".start_date", ".auto_create_iteration"]:
            hook.set_mandatory(field)
            hook.set_writeable(field)


def calculate_team_board_header(hook):
    values = hook.get_new_values()
    oid = values.get("cs_taskboard_board.cdb_object_id")
    board = Board.ByKeys(oid)
    if not board:
        return
    d_label = util.get_label(
        "cs_taskboard_label_project_and_task_interval_format")
    start_date = end_date = None
    current = board.getAdapter().get_active_iteration()
    if current:
        start_date = typeconversion.to_user_repr_date_format(current.start_date)
        end_date = typeconversion.to_user_repr_date_format(current.end_date)
    hook.set("current_interval", d_label.format(
        start=start_date, end=end_date))
