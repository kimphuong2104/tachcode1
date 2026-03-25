#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


def set_task_writeable_readonly(hook):
    """
    Hook to set task values writeable if project values are filled and
    readonly else.
    """
    task_name = hook.get_new_value("cdb_action.task_id")

    if task_name is None:
        prj_id = hook.get_new_value("cdb_action.cdb_project_id")
        prj_name = hook.get_new_value(".project_name")
        if prj_id and prj_name:
            hook.set_writeable("cdb_action.task_id")
            hook.set_writeable(".task_name")
        else:
            hook.set_readonly("cdb_action.task_id")
            hook.set_readonly(".task_name")
