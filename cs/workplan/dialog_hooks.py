#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.workplan import Workplan


def set_reference_sequence_read_only(hook):
    """
    Checks if task list type field is 'alternative',
    set reference task list field to standard sequence of work plan and
    set reference task list field read only.

    If task list type field is 'parallel', lot size is set to read only
    """
    workplan_id = hook.get_new_object_value("workplan_id")
    workplan_index = hook.get_new_object_value("workplan_index")
    workplan = Workplan.ByKeys(workplan_id, workplan_index)
    hook.set_writeable("cswp_task_list.reference_task_list")
    hook.set_writeable("cswp_task_list.lot_size_from")
    hook.set_writeable("cswp_task_list.lot_size_to")
    if hook.get_new_value("task_list_type") == "alternative":
        hook.set_readonly("cswp_task_list.reference_task_list")
        hook.set(
            "cswp_task_list.reference_task_list", workplan.RootTaskList.task_list_id
        )
    if hook.get_new_value("task_list_type") == "parallel":
        hook.set("cswp_task_list.lot_size_from", "")
        hook.set("cswp_task_list.lot_size_to", "")
        hook.set_readonly("cswp_task_list.lot_size_from")
        hook.set_readonly("cswp_task_list.lot_size_to")
