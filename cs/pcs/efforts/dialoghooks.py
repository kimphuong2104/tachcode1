#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb.util import CDBMsg

from cs.pcs.efforts import BOOKABLE_PROJECT_RULE, BOOKABLE_TASK_RULE
from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

from . import TimeSheet

TASK_NAME = "cdbpcs_task.task_name"


def get_proj_keys_from_dialog(hook):
    prj_id = hook.get_new_value("cdbpcs_time_sheet.cdb_project_id")
    return prj_id


def set_task_values(hook):
    task_name = hook.get_new_value(TASK_NAME)
    if not task_name:
        prj_id = get_proj_keys_from_dialog(hook)
        if prj_id:
            hook.set_writeable(TASK_NAME)
        else:
            hook.set_readonly(TASK_NAME)


def get_message(label):
    msg = CDBMsg(CDBMsg.kFatal, label)
    return str(msg)


def validate_project_selection(hook):
    prj_id = get_proj_keys_from_dialog(hook)
    kwargs = {"cdb_project_id": prj_id, "ce_baseline_id": ""}
    selected_proj = get_and_check_object(Project, "read", **kwargs)

    if selected_proj and not selected_proj.MatchRule(BOOKABLE_PROJECT_RULE):
        hook.set_error("", get_message("pcs_efforts_invalid_proj_selection"))


def validate_task_selection(hook):
    prj_id = get_proj_keys_from_dialog(hook)
    task_id = hook.get_new_value("cdbpcs_time_sheet.task_id")
    kwargs = {"cdb_project_id": prj_id, "task_id": task_id, "ce_baseline_id": ""}
    selected_task = get_and_check_object(Task, "read", **kwargs)

    if selected_task and not selected_task.MatchRule(BOOKABLE_TASK_RULE):
        hook.set_error("", get_message("pcs_efforts_invalid_task_selection"))


def setEffortDefaultValues(hook):
    """
    This function is used for dialog hook and sets the values of default
    attributes (see TimeSheet getValsForDefaultAttr func)
    based on selected Project and Task.
    """

    def get_mapped_attr_name(name):
        return TimeSheet.__maps_to__ + "." + name

    cdb_project_id = hook.get_new_value(get_mapped_attr_name("cdb_project_id"))
    task_id = hook.get_new_value(get_mapped_attr_name("task_id"))

    # fetch default values based on selected project and task
    values = TimeSheet.getValsForDefaultAttr(cdb_project_id, task_id)

    for attr, val in values.items():
        # if value is not already set the set it
        mapped_attr_name = get_mapped_attr_name(attr)
        if not hook.get_new_value(mapped_attr_name):
            hook.set(mapped_attr_name, val)
