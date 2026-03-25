#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable-msg=E0213,E1103,E0102,E0203,W0212,W0621,W0201
# pylint: disable=too-many-lines

import datetime

from cdb import typeconversion, ue, util
from cdb.classbody import classbody
from cdb.objects import ByID
from cdb.platform.gui import Message
from cdb.platform.olc import StateDefinition
from cdbwrapc import getOpNameFromMenuLabel
from cs.web.components.ui_support.frontend_dialog import FrontendDialog

from cs.pcs.projects import Project
from cs.pcs.projects import calendar as Calendar
from cs.pcs.projects.helpers import _filter_hook_vals, _get_act_dates
from cs.pcs.projects.tasks import (
    DAYTIME_EVENING,
    DAYTIME_NOT_APPLICABLE,
    Task,
    TaskRelation,
)

DAYTIME = ".daytime"


def _get_button_label(label):
    """
    Strips & and other things the client uses for buttons.
    """
    return getOpNameFromMenuLabel(util.get_label(label), False)


def ask_user_msp(ctx, txt):
    box = ctx.MessageBox(
        "cdbpcs_ask_user_msp", [txt], "question_msp", ctx.MessageBox.kMsgBoxIconAlert
    )
    box.addButton(ctx.MessageBoxButton("cdbpcs_activate", "AUTOMATIC"))
    box.addButton(ctx.MessageBoxButton("cdbpcs_manual", "MANUAL"))
    box.addCancelButton(1)
    ctx.show_message(box)


def ask_user_msp_inactive(ctx):
    msgbox = ctx.MessageBox(
        "cdbpcs_ask_user_msp_inactive",
        "[]",
        "question_msp_inactive",
        ctx.MessageBox.kMsgBoxIconAlert,
    )
    msgbox.addButton(ctx.MessageBoxButton("ok", "OK"))
    msgbox.addCancelButton(1)
    ctx.show_message(msgbox)


def ask_active(hook, txt):
    title = util.get_label("cdbpcs_use_msp_for_scheduling")
    msg = Message.GetMessage("cdbpcs_ask_user_msp")
    fe = FrontendDialog(title, msg % txt, "cdb::argument.question_msp")
    fe.add_button(
        _get_button_label("cdbpcs_activate"),
        "AUTOMATIC",
        FrontendDialog.ActionCallServer,
    )
    fe.add_button(
        _get_button_label("cdbpcs_manual"), "MANUAL", FrontendDialog.ActionCallServer
    )
    fe.add_button(
        _get_button_label("button_cancel"),
        "",
        FrontendDialog.ActionBackToDialog,
        is_cancel=True,
    )
    hook.set_dialog(fe)


def ask_inactive(hook):
    title = util.get_label("cdbpcs_use_msp_for_scheduling")
    msg = Message.GetMessage("cdbpcs_ask_user_msp_inactive")
    fe = FrontendDialog(title, msg, "cdb::argument.question_msp_inactive")
    fe.add_button(_get_button_label("ok"), "OK", FrontendDialog.ActionCallServer)
    fe.add_button(
        _get_button_label("button_cancel"),
        "",
        FrontendDialog.ActionBackToDialog,
        is_cancel=True,
    )
    hook.set_dialog(fe)


def dialogitem_change(ctx, attr_whitelist):
    """
    :param ctx: Context adapter

    :param attr_whitelist: Whitelist of attributes a ``dialogitem_change``
        handler is defined for (``ctx.changed_item`` has to be part of this)
    :type attr_whitelist: iterable

    :returns: Whether ``ctx`` warrants running a ``dialogitem_change`` user
        exit or not.
    :rtype: bool
    """
    attr = ctx.changed_item
    is_relevant = (
        # "create" only lists non-empty attributes, while "copy" lists all
        ctx.action == "create"
        or attr in ctx.dialog.get_attribute_names()
    )
    return attr in attr_whitelist and is_relevant


def dialog_item_change(obj, ctx):
    for attr, method in obj.dialog_item_change_methods.items():
        if dialogitem_change(ctx, [attr]):
            method(obj, ctx)


def _get_object_from_hook(cls, hook):
    # filter values for all entries starting with table name and remove it
    processed_values = _filter_hook_vals(hook.get_new_values(), f"{cls.__maps_to__}.")
    return cls(**processed_values)


def _change_days_fcast(obj):
    if obj.days_fcast in [None, ""]:
        return {
            "start_time_fcast": None,
            "end_time_fcast": None,
            "days_fcast": None,
        }
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(
        start=obj.start_time_fcast, days=max(0, obj.days_fcast)
    )
    return {
        "start_time_fcast": start,
        "end_time_fcast": end,
        "days_fcast": days,
    }


def changeDuration(obj, ctx=None):
    obj.Update(**_change_days_fcast(obj))


def _change_days(obj):
    if obj.days in [None, ""]:
        return {
            "start_time_plan": None,
            "end_time_plan": None,
            "days": None,
        }
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(
        start=obj.start_time_plan, days=max(0, obj.days)
    )
    return {
        "start_time_plan": start,
        "end_time_plan": end,
        "days": days,
    }


def change_days(obj, ctx=None):
    obj.Update(**_change_days(obj))


def _change_start_time_plan(obj, new_start):
    days = 0
    if obj.days:
        days = obj.days
    elif obj.days_fcast:
        days = obj.days_fcast
    if new_start and not days:
        days = 1
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(start=new_start, days=days)
    return {
        "start_time_plan": start,
        "end_time_plan": end,
        "days": days,
    }


def change_start_time_plan(obj, ctx=None):
    new_start = obj.start_time_plan
    obj.Update(**_change_start_time_plan(obj, new_start))


def _change_end_time_plan(obj, new_end):
    start = None
    days = None
    today = datetime.date.today()
    if new_end:
        if obj.start_time_plan:
            start = obj.start_time_plan
        elif obj.start_time_act:
            start = obj.start_time_act
        elif obj.start_time_fcast:
            start = max(obj.start_time_fcast, today)
        else:
            start = today
        start = min(start, new_end)
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(start=start, end=new_end, days=days)
    return {
        "start_time_plan": start,
        "end_time_plan": end,
        "days": days,
    }


def change_end_time_plan(obj, ctx=None):
    new_end = obj.end_time_plan
    obj.Update(**_change_end_time_plan(obj, new_end))


def _change_start_time_fcast(obj, new_start):
    constraints = obj._determineConstraints(start=new_start)
    changes = {"start": new_start}
    if hasattr(obj, "constraint_type") and int(obj.constraint_type) in [3, 6, 7]:
        changes.update(end=obj.end_time_fcast)
    else:
        days = obj.days_fcast
        changes.update(days=1 if new_start and not days else days)
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(**changes)
    if hasattr(obj, "_ensureResourceConstraints"):
        obj._ensureResourceConstraints(start=start, end=end)
    return {
        "start_time_fcast": start,
        "end_time_fcast": end,
        "days_fcast": days,
        **constraints,
    }


def changeStartTime(obj, ctx=None):
    new_start = obj.start_time_fcast
    obj.Update(**_change_start_time_fcast(obj, new_start))


def _change_end_time_fcast(obj, new_end):
    constraints = {}
    changes = {"end": new_end}
    if obj.isMilestone():
        constraints = obj._determineConstraints(constraint_date=new_end)
        changes.update(start=new_end, days=0)
    else:
        start = obj.start_time_fcast
        if not start or not new_end:
            start = new_end
        if new_end:
            constraints = obj._determineConstraints(end=new_end)
            changes.update(start=start)
        else:
            constraints = obj._determineConstraints(constraint_date=new_end)
            changes.update(days=obj.days_fcast)
    # determine all values in context of each other
    start, end, days = obj.calculateTimeFrame(**changes)
    return {
        "start_time_fcast": start,
        "end_time_fcast": end,
        "days_fcast": days,
        **constraints,
    }


def changeEndTime(obj, ctx=None):
    new_end = obj.end_time_fcast
    obj.Update(**_change_end_time_fcast(obj, new_end))


def _change_start_time_act(obj, new_start):
    changes = {"start_time_act": new_start, "days_act": None}
    if new_start:
        days_act = None
        if obj.end_time_act:
            if obj.GetClassname() == "cdbpcs_task" and obj.milestone:
                # In case of a milestone, we need to use Calendar.calculateTimeFrame
                # directly in order to calculate days_act as difference between
                # start_time_act and end_time_act
                calendar_profile_id = None
                if obj.Project:
                    calendar_profile_id = obj.Project.calendar_profile_id
                _, _, days_act = Calendar.calculateTimeFrame(
                    calendar_profile_id, start=new_start, end=obj.end_time_act
                )
            else:
                _, _, days_act = obj.calculateTimeFrame(
                    start=new_start, end=obj.end_time_act
                )
            changes.update(days_act=days_act)
    return changes


def changeStartTimeAct(obj, ctx):
    change_start_time_act(obj, ctx)


def change_start_time_act(obj, ctx=None):
    new_start = obj.start_time_act
    obj.Update(**_change_start_time_act(obj, new_start))


def _change_end_time_act(obj, new_end):
    changes = {"end_time_act": new_end, "days_act": None}
    if new_end and obj.start_time_act:
        days_act = None
        if obj.GetClassname() == "cdbpcs_task" and obj.milestone:
            # In case of a milestone, we need to use Calendar.calculateTimeFrame
            # directly in order to calculate days_act as difference between
            # start_time_act and end_time_act
            calendar_profile_id = None
            if obj.Project:
                calendar_profile_id = obj.Project.calendar_profile_id
            _, _, days_act = Calendar.calculateTimeFrame(
                calendar_profile_id, start=obj.start_time_act, end=new_end
            )
        else:
            _, _, days_act = obj.calculateTimeFrame(
                start=obj.start_time_act, end=new_end
            )
        changes.update(days_act=days_act)
    return changes


def changeEndTimeAct(obj, ctx):
    change_end_time_act(obj, ctx)


def change_end_time_act(obj, ctx=None):
    new_end = obj.end_time_act
    obj.Update(**_change_end_time_act(obj, new_end))


def _change_efforts(obj):
    changes = {}
    if obj.effort_fcast and obj.effort_fcast < 0:
        changes.update(effort_fcast=0.0)
        if not obj.is_group:
            changes.update(effort_plan=0.0)
    elif not obj.is_group:
        changes.update(effort_plan=obj.effort_fcast)
    return changes


def changeEffort(obj, ctx=None):
    changes = _change_efforts(obj)
    if changes:
        obj.Update(**changes)


def _change_autoUpdateEffort(obj):
    changes = {}
    if not obj.auto_update_effort and obj.is_group:
        changes.update(effort_fcast=0.0)
    if obj.auto_update_effort and obj.is_group:
        changes.update(effort_fcast=obj.effort_plan)
    return changes


def changeAutoUpdateEffort(obj, ctx=None):
    changes = _change_autoUpdateEffort(obj)
    if changes:
        obj.Update(**changes)


def changeTemplate(obj, ctx):
    if obj.template:
        # fields for project manager: optional and empty
        ctx.set_fields_readonly(["mapped_project_manager"])
        ctx.set_optional("mapped_project_manager")
        ctx.set("mapped_project_manager", "")
        ctx.set("project_manager", "")
    else:
        # fields for project manager: mandatory
        ctx.set_fields_writeable(["mapped_project_manager"])
        ctx.set_mandatory("mapped_project_manager")


def change_constraint_date(obj, ctx):
    new_value = obj.constraint_date
    obj.Update(constraint_date=new_value)


def get_lang_fields(obj, field):
    multilang_field = obj.GetFieldByName(field)
    lang_fields = multilang_field.getLanguageFields()
    return list(lang_fields.values())


def _set_mapped_daytime_value(obj, ctx, daytime):
    changes = {}
    for field in get_lang_fields(obj, "mapped_daytime_value"):
        value = field.ma.getValue(daytime)
        ctx.set(f".{field.name}", value)
    return changes


def _reset_daytime(obj, ctx, readonly):
    for field in get_lang_fields(obj, "mapped_daytime_value"):
        fieldname = f".{field.name}"
        if readonly:
            ctx.set_readonly(fieldname)
            ctx.set_optional(fieldname)
        ctx.set(fieldname, DAYTIME_NOT_APPLICABLE)
    ctx.set(DAYTIME, DAYTIME_NOT_APPLICABLE)


def _enable_daytime(obj, ctx):
    if obj.Project.msp_active:
        return {}

    changes = {}
    for field in get_lang_fields(obj, "mapped_daytime_value"):
        fieldname = f".{field.name}"
        ctx.set_writeable(fieldname)
        ctx.set_mandatory(fieldname)
    changes.update(_set_mapped_daytime_value(obj, ctx, str(DAYTIME_EVENING)))
    changes["daytime"] = str(DAYTIME_EVENING)
    return changes


def _change_milestone(obj, ctx_or_hook, uses_webui=False):
    def _set_fields_writeable(fields):
        if uses_webui:
            for field in fields:
                ctx_or_hook.set_writeable(field)
        else:
            ctx_or_hook.set_fields_writeable(fields)

    def _set_fields_readonly(fields):
        if uses_webui:
            for field in fields:
                ctx_or_hook.set_readonly(field)
        else:
            ctx_or_hook.set_fields_readonly(fields)

    # milestone flag has been changed:
    # - this can only be done on leaf tasks
    # - adjust start and end dates and days
    start, end, days = obj.calculateTimeFrame(
        start=obj.start_time_fcast, end=obj.end_time_fcast
    )
    # set target values
    changes = {
        "start_time_fcast": start,
        "days_fcast": days,
    }
    # set forecast values
    if obj.auto_update_time == 0:
        changes.update(
            start_time_plan=start,
            end_time_plan=end,
            days=days,
        )

    milestone_readonly = [
        "cdbpcs_task.effort_fcast",
        "cdbpcs_task.days_fcast",
        "cdbpcs_task.start_time_fcast",
    ]
    if obj.milestone:
        _set_fields_readonly(milestone_readonly)
        changes.update(
            is_group=0,
            effort_fcast=0.0,
        )
        if uses_webui:
            if obj.automatic:
                _reset_daytime(obj, ctx_or_hook, readonly=True)
            else:
                changes.update(_enable_daytime(obj, ctx_or_hook))
        elif not obj.automatic:
            changes[DAYTIME] = str(DAYTIME_EVENING)
    else:
        _set_fields_writeable(milestone_readonly)
        _reset_daytime(obj, ctx_or_hook, readonly=uses_webui)
        changes.update(
            effort_fcast=obj.getEffortMax(),
        )
    return changes


def changeMilestone(obj, ctx, uses_webui=False):
    changes = _change_milestone(obj, ctx, uses_webui)
    if changes:
        obj.Update(**changes)


def change_constraint_type(obj, ctx):
    """
    This method is only called by the Desktop Client if the value of the field has really been changed.
    NOTE the different behavior in the Web Client as described in
    E048567: The User Exit maskaction is always running,
             even if the value of the field has not been changed.
    In the user exit code, it is not possible to compare the old value of the field against the
    current value because the old value is not available.
    Comparisons against the value of `ctx.object` do not compare the values of the mask field,
    but the value of the mask field against the value in the database (not applicable for new creation).
    Comparisons against the value of `ctx.object` do raise an AttributeError, when creating a new task.
    """
    changes = {}

    # reset constraint type if necessary
    reset = not obj.constraint_type
    if reset:
        changes.update(constraint_type="0")

    # set constraint date
    ct = int(changes.get("constraint_type", obj.constraint_type))
    if ct in [0, 1]:
        ctx.set_optional("constraint_date")
    else:
        ctx.set_mandatory("constraint_date")
        if ct in [2, 4, 5]:
            changes.update(constraint_date=obj.start_time_fcast)
        elif ct in [3, 6, 7]:
            changes.update(constraint_date=obj.end_time_fcast)

    # apply changes
    if changes:
        obj.Update(**changes)
        if reset:
            inform_user(ctx, "cdbpcs_constraint_type_needed")


def inform_user(ctx, msg, *args):
    # Create a message box
    message_box = ctx.MessageBox(
        msg, args, "inform", ctx.MessageBox.kMsgBoxIconInformation
    )
    message_box.addButton(ctx.MessageBoxButton("ok", "OK"))
    ctx.show_message(message_box)


def changeDaytime(obj, ctx):
    if (not obj.milestone or obj.automatic) and ctx.dialog[
        "daytime"
    ] != DAYTIME_NOT_APPLICABLE:
        inform_user(ctx, "cdbpcs_daytime_only_manual_milestone")
        ctx.set("daytime", DAYTIME_NOT_APPLICABLE)


def _change_automatic(obj, ctx_or_hook, uses_webui=False):
    changes = {}
    if uses_webui:
        if not obj.automatic and obj.milestone:
            changes.update(_enable_daytime(obj, ctx_or_hook))
        else:
            _reset_daytime(obj, ctx_or_hook, readonly=True)
    else:
        if not obj.automatic and obj.milestone:
            ctx_or_hook.set(DAYTIME, str(DAYTIME_EVENING))
        elif obj.automatic and obj.milestone:
            ctx_or_hook.set(DAYTIME, DAYTIME_NOT_APPLICABLE)

    if obj.automatic == 0 and obj.auto_update_time == 1:
        changes.update({"auto_update_time": 2})
    return changes


def changeAutomatic(obj, ctx_or_hook, uses_webui=False):
    changes = _change_automatic(obj, ctx_or_hook, uses_webui)
    if changes:
        obj.Update(**changes)


def checkAutomatic(obj, ctx=None):
    if obj.auto_update_time == 1 and not obj.automatic:
        if obj.Project and obj.Project.msp_active:
            obj.auto_update_time = 2
        else:
            obj.automatic = 1


def percentage_is_invalid(percent_complet):
    """
    :param percent_complet: Dialog value of ``cdbpcs_task.percent_complet``.
        Should be a string representing any whole number between 0 and 100.
    :type percent_complet: str

    :returns: Whether ``percent_complet`` is invalid.
        ``None`` and empty strings are considered valid for backwards compatibility.
        All values not castable to int and not between 1 and 99 (including them)
        are considered invalid.
    :rtype: bool
    """
    try:
        completion = int(percent_complet or 1)
    except (TypeError, ValueError):
        return True
    return completion < 1 or completion > 99


def check_percentage(obj, ctx=None):
    if percentage_is_invalid(obj.percent_complet):
        raise ue.Exception("cdbpcs_task_percentage_validation")


start_time_field = "cdbpcs_task.start_time_act"
end_time_field = "cdbpcs_task.end_time_act"


def disable_and_fill(ctx, field, val=None):
    ctx.set_readonly(field)
    ctx.set(field, val)


def enable_and_fill(ctx, field, val):
    ctx.set_writeable(field)
    ctx.set(field, val)


def state_dialog_set_act_date_summary(obj, ctx, target_status):
    start, end = _get_act_dates(obj)
    if target_status in [
        Task.NEW.status,
        Task.READY.status,
        Task.DISCARDED.status,
        Task.EXECUTION.status,
    ]:
        disable_and_fill(ctx, start_time_field)
        disable_and_fill(ctx, end_time_field)
    elif target_status == Task.FINISHED.status:
        disable_and_fill(ctx, start_time_field, start)
        disable_and_fill(ctx, end_time_field)
    elif target_status == Task.COMPLETED.status:
        disable_and_fill(ctx, start_time_field, start)
        disable_and_fill(ctx, end_time_field, end)


def state_dialog_set_act_date_single(use_today, obj, ctx, target_status):
    today = datetime.date.today()
    default_date = today if use_today else None
    start, end = _get_act_dates(obj)
    if isinstance(start, str):
        try:
            start = typeconversion.from_legacy_date_format(start).date()
        except ValueError:
            return
    if isinstance(end, str):
        try:
            end = typeconversion.from_legacy_date_format(end).date()
        except ValueError:
            return
    if target_status in [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]:
        disable_and_fill(ctx, start_time_field)
        disable_and_fill(ctx, end_time_field)
    elif target_status == Task.EXECUTION.status:
        enable_and_fill(ctx, start_time_field, default_date)
        disable_and_fill(ctx, end_time_field)
    elif target_status == Task.FINISHED.status:
        enable_and_fill(ctx, start_time_field, start if start else default_date)
        enable_and_fill(ctx, end_time_field, default_date)
    elif target_status == Task.COMPLETED.status:
        enable_and_fill(ctx, start_time_field, start)
        enable_and_fill(ctx, end_time_field, end)


def state_dialog_set_act_date(use_today, obj, ctx, target_status):
    try:
        # in case obj is object handle is_group is '1' and '0'
        is_group = obj.is_group and int(obj.is_group)
    except ValueError:  # empty value of is_group
        is_group = False

    if is_group:
        state_dialog_set_act_date_summary(obj, ctx, target_status)
    else:
        state_dialog_set_act_date_single(use_today, obj, ctx, target_status)


def state_dialog_item_change(obj, ctx=None):
    attr = "zielstatus_int"
    attr_name = "zielstatus"

    if ctx.changed_item != attr_name:
        return

    if hasattr(ctx.dialog, attr):
        try:
            selected_status = int(ctx.dialog[attr])
        except ValueError:
            return  # do nothing if target status int can't be parsed
    else:
        return  # cannot determine the integer status

    state_dialog_set_act_date(
        obj.Project.act_vals_status_chng, obj, ctx, selected_status
    )


def hook_set_task_selection(hook):
    if not (
        len(Project.KeywordQuery(ce_baseline_id=""))
        > TaskRelation.NUMBER_OF_PROJECTS_FOR_SETTING_TASK_SELECTION_READONLY
    ):
        return

    taskrel = "cdbpcs_taskrel."

    for prj_id, task_id in TaskRelation._ATTRIBUTES_FOR_TASK_SELECTION_READONLY.items():
        if taskrel + prj_id in hook.get_changed_fields():
            if hook.get_new_value(taskrel + prj_id) != "":
                hook.set_writeable(taskrel + task_id)
            else:
                hook.set_readonly(taskrel + task_id)


class WithDateHooks:
    def change_start_time_plan(self):
        change_start_time_plan(self)

    def change_end_time_plan(self):
        change_end_time_plan(self)

    def change_start_time_act(self):
        change_start_time_act(self)

    def change_end_time_act(self):
        change_end_time_act(self)

    def change_days(self):
        change_days(self)


@classbody
class Project(WithDateHooks):

    dialog_item_change_methods = {
        "days_fcast": changeDuration,
        "days": change_days,
        "start_time_fcast": changeStartTime,
        "end_time_fcast": changeEndTime,
        "start_time_plan": change_start_time_plan,
        "end_time_plan": change_end_time_plan,
        "start_time_act": changeStartTimeAct,
        "end_time_act": changeEndTimeAct,
        "effort_fcast": changeEffort,
        "template": changeTemplate,
    }

    def dialog_item_change(self, ctx):
        dialog_item_change(self, ctx)

    @staticmethod
    def changeDurationWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        obj.update_object_web(hook, **_change_days_fcast(obj))

    @staticmethod
    def change_days_web(hook):
        obj = _get_object_from_hook(Project, hook)
        obj.update_object_web(hook, **_change_days(obj))

    @staticmethod
    def changeStartTimeWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.start_time_fcast
        obj.update_object_web(hook, **_change_start_time_fcast(obj, new_value))

    @staticmethod
    def changeEndTimeWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.end_time_fcast
        obj.update_object_web(hook, **_change_end_time_fcast(obj, new_value))

    @staticmethod
    def change_start_time_plan_web(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.start_time_plan
        obj.update_object_web(hook, **_change_start_time_plan(obj, new_value))

    @staticmethod
    def change_end_time_plan_web(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.end_time_plan
        obj.update_object_web(hook, **_change_end_time_plan(obj, new_value))

    @staticmethod
    def changeStartTimeActWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.start_time_act
        obj.update_object_web(hook, **_change_start_time_act(obj, new_value))

    @staticmethod
    def changeEndTimeActWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        new_value = obj.end_time_act
        obj.update_object_web(hook, **_change_end_time_act(obj, new_value))

    @staticmethod
    def changeEffortWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        project_id = obj.cdb_project_id
        if hook.get_operation_name() == "CDB_Copy":
            # determine project_id of copied template
            # retrieve copy_template object from operation info
            op_info = hook.get_operation_state_info()
            if op_info.get_objects():
                object_id = op_info.get_objects()[0].cdb_object_id
                # find project by retrieved object_id
                project = ByID(object_id)
                # get project_id
                project_id = project.cdb_project_id

        obj.is_group = 0
        if project_id:
            obj.is_group = (
                1
                if len(Task.KeywordQuery(cdb_project_id=project_id, ce_baseline_id=""))
                else 0
            )
        obj.update_object_web(hook, **_change_efforts(obj))

    @staticmethod
    def changeTemplateWeb(hook):
        # Backend Dialog Hook for the web
        template = hook.get_new_values()["cdbpcs_project.template"]
        # if the the checkbox template is deselected
        if template == 1:
            hook.set_readonly(".mapped_project_manager")
            hook.set_optional(".mapped_project_manager")
            hook.set(".mapped_project_manager", "")
            hook.set("cdbpcs_project.project_manager", "")
        # if checkbox template is selected
        else:
            hook.set_writeable(".mapped_project_manager")
            hook.set_mandatory(".mapped_project_manager")

    def changeMSP(self, ctx):
        if ctx.uses_webui:
            return
        if not ctx.object:
            return
        if self.msp_active and ctx.object.msp_active in ("", "0"):
            tasks = self.Tasks.Query("auto_update_time != automatic")
            if tasks and "question_msp" not in ctx.dialog.get_attribute_names():
                messages = []
                for t in tasks:
                    messages.append(t.task_name)
                ask_user_msp(ctx, "\n".join(messages))
            elif tasks:
                cca = self.MakeChangeControlAttributes()
                result = ctx.dialog["question_msp"]
                if result == "MANUAL":
                    tasks.Update(auto_update_time=0, **cca)
                elif result == "AUTOMATIC":
                    tasks.Update(auto_update_time=1, automatic=1, **cca)
        elif not self.msp_active and ctx.object.msp_active in ("1", "2"):
            if (
                ctx.interactive
                and "question_msp_inactive" not in ctx.dialog.get_attribute_names()
            ):
                ask_user_msp_inactive(ctx)
            else:
                ctx.keep("do_recalculation", 1)

    @staticmethod
    def changeMSPWeb(hook):
        obj = _get_object_from_hook(Project, hook)
        old_obj = Project.ByKeys(cdb_project_id=obj.cdb_project_id)
        if not old_obj:
            return
        if obj.msp_active and not old_obj.msp_active:
            tasks = old_obj.Tasks.Query("auto_update_time != automatic")
            confirm = hook.get_new_values().get("cdb::argument.question_msp")
            if tasks and not confirm:
                messages = []
                for t in tasks:
                    messages.append(t.task_name)
                ask_active(hook, "\n".join(messages))
            elif tasks:
                cca = obj.MakeChangeControlAttributes()
                if confirm == "MANUAL":
                    tasks.Update(auto_update_time=0, **cca)
                elif confirm == "AUTOMATIC":
                    tasks.Update(auto_update_time=1, automatic=1, **cca)
        elif not obj.msp_active and old_obj.msp_active:
            confirm = hook.get_new_values().get("cdb::argument.question_msp_inactive")
            if not confirm:
                ask_inactive(hook)
            elif confirm == "OK":
                hook.set("cdb::argument.do_recalculation", 1)


@classbody
class Task(WithDateHooks):

    dialog_item_change_methods = {
        "days_fcast": changeDuration,
        "days": change_days,
        "start_time_fcast": changeStartTime,
        "end_time_fcast": changeEndTime,
        "start_time_plan": change_start_time_plan,
        "end_time_plan": change_end_time_plan,
        "start_time_act": change_start_time_act,
        "end_time_act": change_end_time_act,
        "effort_fcast": changeEffort,
        "constraint_date": change_constraint_date,
        "milestone": changeMilestone,
        "constraint_type": change_constraint_type,
        "automatic": changeAutomatic,
        "auto_update_time": checkAutomatic,
        "percent_complet": check_percentage,
        "daytime": changeDaytime,
        "auto_update_effort": changeAutoUpdateEffort,
    }

    def dialog_item_change(self, ctx):
        dialog_item_change(self, ctx)

    def state_dialog_item_change(self, ctx):
        state_dialog_item_change(self, ctx)

    def state_dialog_pre_mask(self, ctx):
        if hasattr(ctx, "targetstatelist") and ctx.targetstatelist:
            # by default the first status in the target state list will be selected
            state_dialog_set_act_date(
                self.Project.act_vals_status_chng, self, ctx, ctx.targetstatelist[0]
            )

    def state_dialog_pre(self, ctx):
        # check if given actual start and end dates are within calendar time frame
        prof_start = self.Project.CalendarProfile.valid_from
        prof_end = self.Project.CalendarProfile.valid_until

        # evaluate given start date
        sd = self.get_dialog_attr(ctx, "start_time_act")
        if sd:
            sd = typeconversion.from_legacy_date_format(sd).date()
        # evaluate given end date
        ed = self.get_dialog_attr(ctx, "end_time_act")
        if ed:
            ed = typeconversion.from_legacy_date_format(ed).date()

        # compare start and end date
        if sd and (sd < prof_start or prof_end < sd):
            raise ue.Exception("cdb_cal_outside_range")
        if ed and (ed < prof_start or prof_end < ed):
            raise ue.Exception("cdb_cal_outside_range")

    @staticmethod
    def get_dialog_attr(ctx, attr):
        if hasattr(ctx, "dialog"):
            if hasattr(ctx.dialog, attr):
                return ctx.dialog[attr] if ctx.dialog[attr] else None
        return None

    @staticmethod
    def changeTargetStatus(hook):
        status_text = hook.get_new_values()[".zielstatus"]
        objs = hook.get_operation_state_info().get_objects()
        if objs:
            obj = objs[0]

            # first get the status number using the status text
            # TODO: fix after E056769
            sds = StateDefinition.KeywordQuery(objektart=obj.cdb_objektart)
            sd_iterator = filter(lambda sd: sd.StateText[""] == status_text, sds)
            sd = list(sd_iterator)
            if sd:
                selected_status = sd[0].statusnummer

                # get project setting for using today as actual date
                useToday = Project.ByKeys(
                    cdb_project_id=obj.cdb_project_id, ce_baseline_id=""
                ).act_vals_status_chng

                state_dialog_set_act_date(useToday, obj, hook, selected_status)

    @staticmethod
    def changeAutomaticWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        obj.update_object_web(hook, **_change_automatic(obj, hook, True))

    @staticmethod
    def changeMilestoneWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        obj.update_object_web(hook, **_change_milestone(obj, hook, True))

    @staticmethod
    def changeAutoUpdateEffortWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        obj.update_object_web(hook, **_change_autoUpdateEffort(obj))

    @staticmethod
    def changeDurationWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        obj.update_object_web(hook, **_change_days_fcast(obj))

    def change_constraint_type(self, ctx):
        change_constraint_type(self, ctx)

    @staticmethod
    def change_days_web(hook):
        obj = _get_object_from_hook(Task, hook)
        obj.update_object_web(hook, **_change_days(obj))

    @staticmethod
    def change_start_time_plan_web(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.start_time_plan
        obj.update_object_web(hook, **_change_start_time_plan(obj, new_value))

    @staticmethod
    def change_end_time_plan_web(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.end_time_plan
        obj.update_object_web(hook, **_change_end_time_plan(obj, new_value))

    @staticmethod
    def changeStartTimeWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.start_time_fcast
        obj.update_object_web(hook, **_change_start_time_fcast(obj, new_value))

    @staticmethod
    def changeEndTimeWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.end_time_fcast
        obj.update_object_web(hook, **_change_end_time_fcast(obj, new_value))

    @staticmethod
    def hook_move_dates(hook):
        uuid = hook.get_new_object_value("cdb_object_id")
        obj = ByID(uuid)
        changed_fields = hook.get_changed_fields()
        start_time_new = changed_fields.get(".start_time_new", None)
        end_time_new = changed_fields.get(".end_time_new", None)
        result = obj.move_dates(start_time_new, end_time_new)
        if result:
            start, end = result
            hook.set(".start_time_new", start)
            hook.set(".end_time_new", end)

    @staticmethod
    def changeStartTimeActWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.start_time_act
        obj.update_object_web(hook, **_change_start_time_act(obj, new_value))

    @staticmethod
    def changeEndTimeActWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.end_time_act
        obj.update_object_web(hook, **_change_end_time_act(obj, new_value))

    @staticmethod
    def changeConstraintDateWeb(hook):
        obj = _get_object_from_hook(Task, hook)
        new_value = obj.constraint_date
        obj.update_object_web(hook, constraint_date=new_value)

    @staticmethod
    def check_percentage_web(hook):
        obj = _get_object_from_hook(Task, hook)
        if percentage_is_invalid(obj.percent_complet):
            hook.set_error(
                Message.GetMessage("cs_installer_error_label"),
                Message.GetMessage("cdbpcs_task_percentage_validation"),
            )
