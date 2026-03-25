#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from cs.pcs.projects.tasks import Task


def task_create_from_template(hook):
    keynames = [key.name for key in Task.GetTablePKeys()]
    # Only try to access fields, that are on the mask and belong to Task
    task_hook_fields = [
        f.split(".")[1] for f in hook.get_new_values() if Task.__classname__ in f
    ]
    kwargs = {
        key: hook.get_new_value(key) for key in keynames if key in task_hook_fields
    }
    task = Task.ByKeys(**kwargs)

    if task:
        if task.start_time_fcast:
            hook.set(".start_time_old", task.start_time_fcast.isoformat())
            hook.set_writeable(".start_time_new")
            hook.set_mandatory(".start_time_new")
        else:
            hook.set_readonly(".start_time_new")
            hook.set_optional(".start_time_new")
