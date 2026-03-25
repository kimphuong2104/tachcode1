#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from cdb import util
from cdb.classbody import classbody
from cdb.constants import kOperationModify
from cdb.platform.gui import Message
from cdbwrapc import getOpNameFromMenuLabel
from cs.pcs.resources import RessourceAssignment, RessourceDemand
from cs.pcs.resources.helpers import date_from_legacy_str
from cs.pcs.resources.pools.assignments import ResourcePoolAssignment
from cs.web.components.ui_support.frontend_dialog import FrontendDialog


def _filter_hook_vals(vals, class_prefix):
    """
    :param vals: values of dialog hook
    :type vals: dictionary

    :returns: all vals entries, which keys started with class_prefix,
        but now without this prefix.
        class_prefix is e.g. for projects 'cdbpcs_project.'
    :rtype: dict
    """
    processed_vals = {}
    for val in vals:
        if val.startswith(class_prefix):
            new_val = val.split(".")[1]
            processed_vals.update({new_val: vals[val]})
    return processed_vals


def _get_object_from_hook(cls, hook):
    # filter values for all entries starting with table name and remove it
    processed_values = _filter_hook_vals(
        hook.get_new_values(), "{}.".format(cls.__maps_to__)
    )
    return cls(**processed_values)


def get_prefixed_field(cls, name):
    return "{}.{}".format(cls.__maps_to__, name)


def set_hook_values(cls, changes, hook):
    for k, v in changes.items():
        hook.set(get_prefixed_field(cls, k), v)


def _get_button_label(label):
    """
    Strips & and other things the client uses for buttons.
    """
    return getOpNameFromMenuLabel(util.get_label(label), False)


@classbody
class ResourcePoolAssignment(object):
    @staticmethod
    def dialogitem_change_web(hook):
        """
        Sets the start and/or end date of the resource assignment
        based on the resource selection.
        """
        obj = _get_object_from_hook(ResourcePoolAssignment, hook)
        obj.start_date = ""
        obj.end_date = ""
        start_date = obj.getStart()
        end_date = obj.getEnd()
        changes = {
            "start_date": start_date if start_date else "",
            "end_date": end_date if end_date else "",
        }
        set_hook_values(ResourcePoolAssignment, changes, hook)

    @staticmethod
    def check_dates_overlap_web(hook):
        """
        This is a post_mask dialog hook that verifies if the newly selected
        dates for a resource overlap with another entry using the same resource.
        (A resource cannot have multiple assignments for the same period).

        Executed only for CDB_Modify operation.
        """
        if not hook.get_operation_name() == kOperationModify:
            return
        state_info = hook.get_operation_state_info()
        objects = state_info.get_objects()
        if objects:
            op_obj = objects[0]  # CDB_Modify will have only one object
            hook_obj = _get_object_from_hook(ResourcePoolAssignment, hook)

            orig_start_date = date_from_legacy_str(op_obj.start_date)
            orig_end_date = date_from_legacy_str(op_obj.end_date)
            new_start_date = hook_obj.start_date
            new_end_date = hook_obj.end_date
            try:
                hook_obj.check_dates_overlap(
                    orig_start_date, orig_end_date, new_start_date, new_end_date
                )
            except Exception:  # pylint: disable=W0703
                hook.set_error("", Message.GetMessage("cdbpcs_pool_ass_overlap", hook_obj.ResourcePool.name))


@classbody
class RessourceDemand(object):
    @staticmethod
    def dialog_item_change_web(hook):
        obj = _get_object_from_hook(RessourceDemand, hook)
        vals = _filter_hook_vals(hook.get_changed_fields(), RessourceDemand.__maps_to__)
        for val in vals:
            hook.changed_item = val
            obj.dialog_item_change(hook)

    @staticmethod
    def check_task_web(hook):
        obj = _get_object_from_hook(RessourceDemand, hook)
        obj.check_task(hook=hook)

    @staticmethod
    def check_subject_web(hook):
        obj = _get_object_from_hook(RessourceDemand, hook)
        obj.check_subject(hook=hook)

    @staticmethod
    def set_demand_type_web(hook):
        obj = _get_object_from_hook(RessourceDemand, hook)
        obj.set_demand_type()


@classbody
class RessourceAssignment(object):
    @staticmethod
    def dialog_item_change_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        vals = _filter_hook_vals(
            hook.get_changed_fields(), RessourceAssignment.__maps_to__
        )
        for val in vals:
            hook.changed_item = val
            obj.dialog_item_change(hook)

    @staticmethod
    def check_task_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        obj.check_task(hook=hook)

    @staticmethod
    def check_subject_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        obj.check_subject(hook=hook)

    @staticmethod
    def check_demand_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        obj.check_demand()

    @staticmethod
    def set_alloc_type_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        obj.set_alloc_type()

    @staticmethod
    def check_team_web(hook):
        obj = _get_object_from_hook(RessourceAssignment, hook)
        obj.check_team(hook)

    def ask_user_web(self, hook, txt, alloc_pool_name, demand_pool_name):
        # Create a message box
        title = "Question"
        fe = FrontendDialog(
            title, Message.GetMessage(txt, alloc_pool_name, demand_pool_name), "assign"
        )
        fe.add_button(
            _get_button_label("web.base.dialog_yes"),
            "ASSIGN_YES",
            FrontendDialog.ActionSubmit,
        )
        fe.add_button(
            _get_button_label("web.base.dialog_no"),
            "ASSIGN_NO",
            FrontendDialog.ActionBackToDialog,
            is_cancel=True,
        )
        hook.set_dialog(fe)
