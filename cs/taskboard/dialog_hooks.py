#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from cdb import ue
from cdb import util
from cdb import sig
from cs.platform.web.rest.generic import convert
from cs.web.components.ui_support.frontend_dialog import FrontendDialog
from cs.taskboard.objects import Board
from cs.taskboard.constants import BOARD_DIALOG_ITEM_CHANGE_SIGNAL
from cs.taskboard.constants import BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL
from cs.taskboard.utils import ensure_date


def dialog_item_change(ctx):
    dlg_attrs = ctx.dialog.get_attribute_names()
    tmpl = None
    if "template_object_id" in dlg_attrs:
        tmpl = Board.ByKeys(ctx.dialog.template_object_id)
    if not tmpl:
        return
    if ctx.changed_item == "template_object_id":
        contents = tmpl.getBoardContentTypesAndNames()
        ctx.set("content_types", contents["content_types"])
        ctx.set("content_types_names", contents["content_types_names"])
        ctx.set("description", tmpl.description)
    elif "content_types_names" in dlg_attrs:
        if ctx.dialog.content_types_names:
            content_types_names = ctx.dialog.content_types_names.split(',')
            content_types = tmpl._convert_to_content_types(content_types_names)
            ctx.set("content_types", ','.join(content_types))
        else:
            contents = tmpl.getBoardContentTypesAndNames()
            ctx.set("content_types", contents["content_types"])
            ctx.set("content_types_names", contents["content_types_names"])
    if "interval_type" in dlg_attrs and not ctx.dialog.interval_type:
        ctx.set("interval_type", tmpl.interval_type)
        if tmpl.TimeUnit:
            ctx.set("interval_name", tmpl.interval_name)
    if "interval_length" in dlg_attrs and not ctx.dialog.interval_length:
        ctx.set("interval_length", tmpl.interval_length)
    # To separate the logic for different board types, calling
    # type specific handlers
    sig.emit(BOARD_DIALOG_ITEM_CHANGE_SIGNAL)(ctx, tmpl)


if __name__ == "__main__":
    ue.run(dialog_item_change, 'cdbmaskaction')


def confirm_date(hook):
    """
    Check whether a change of the due date field on a dialog is valid, show
    a warning if not.
    """
    values = hook.get_new_values()
    date_field = values.get("cdb::argument.task_due_date_field", None)
    if date_field:
        changed = values.get(date_field, None)
        valid_start = values.get("cdb::argument.valid_start", None)
        valid_end = values.get("cdb::argument.valid_end", None)
        if valid_end and valid_start and changed:
            end_date = ensure_date(convert.load_datetime(valid_end))
            changed_date = ensure_date(changed)
            if changed_date > end_date:
                fe = FrontendDialog(util.get_label("cs_taskboard_confirm_due_date_title"),
                                    util.get_label("cs_taskboard_confirm_due_date"))
                fe.add_button(util.get_label("web.cs-taskboard.yes"), 0,
                              FrontendDialog.ActionSubmit, is_default=True)
                fe.add_button(util.get_label("web.cs-taskboard.no"), 0,
                              FrontendDialog.ActionBackToDialog, is_default=False)
                hook.set_dialog(fe)


def change_board_content_types(hook):
    changed_fields = hook.get_changed_fields()
    values = hook.get_new_values()
    if "cs_taskboard_board.cdb_object_id" not in values:
        return
    board = Board.ByKeys(values["cs_taskboard_board.cdb_object_id"])
    old_types = board.content_types.split(',')
    new_types = changed_fields["cs_taskboard_board.content_types"].split(',')
    if set(old_types) - set(new_types):
        hook.set("cs_taskboard_board.content_types", ','.join(new_types))


def change_board_fields(hook):
    changed_fields = hook.get_changed_fields()
    values = hook.get_new_values()
    if ".template_object_id" not in values:
        return
    tmpl = Board.ByKeys(values[".template_object_id"])
    if not tmpl:
        return
    if ".template_object_id" in changed_fields:
        contents = tmpl.getBoardContentTypesAndNames()
        hook.set(".content_types", contents["content_types"])
        hook.set(".content_types_names", contents["content_types_names"])
        hook.set("description", tmpl.description)
    elif ".content_types_names" in changed_fields:
        if changed_fields[".content_types_names"]:
            content_types_names = changed_fields[".content_types_names"].split(',')
            content_types = tmpl._convert_to_content_types(content_types_names)
            hook.set(".content_types", ','.join(content_types))
        else:
            contents = tmpl.getBoardContentTypesAndNames()
            hook.set(".content_types", contents["content_types"])
            hook.set(".content_types_names", contents["content_types_names"])
    if ".interval_type" in values and not values[".interval_type"]:
        hook.set(".interval_type", tmpl.interval_type)
        if tmpl.TimeUnit:
            hook.set(".interval_name", tmpl.interval_name)
    if ".interval_length" in values and not values[".interval_length"]:
        hook.set(".interval_length", tmpl.interval_length)
    # To separate the logic for different board types, calling
    # type specific handlers
    sig.emit(BOARD_DIALOG_HOOK_FIELD_CHANGE_SIGNAL)(hook, tmpl)
