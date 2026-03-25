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


from cdb import typeconversion, util
from cs.taskboard.objects import Board, Iteration

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


def calculate_project_task_taskboard_header(hook):
    values = hook.get_new_values()
    oid = values.get("cs_taskboard_board.cdb_object_id")
    d_label = util.get_label("cs_taskboard_label_project_and_task_interval_format")
    board = Board.ByKeys(cdb_object_id=oid)
    if not board:
        return
    cto_tmp = board.ContextObject
    if isinstance(cto_tmp, Task):
        task_duration = ""
        task = cto_tmp
        if task.start_time_fcast and task.end_time_fcast:
            task_duration = d_label.format(
                start=typeconversion.to_user_repr_date_format(task.start_time_fcast),
                end=typeconversion.to_user_repr_date_format(task.end_time_fcast),
            )
        hook.set("task_duration", task_duration)
        hook.set("task_name", task.task_name)
        hook.set("project_tag", task.Project.project_tag)
    elif isinstance(cto_tmp, Project):
        prj = cto_tmp
        hook.set("project_tag", prj.project_tag)
    else:
        return
    curr_iter = ""
    for sp in board.Iterations:
        if sp.status == Iteration.EXECUTION.status:
            start = (
                typeconversion.to_user_repr_date_format(sp.start_date)
                if sp.start_date
                else ""
            )
            end = (
                typeconversion.to_user_repr_date_format(sp.end_date)
                if sp.end_date
                else ""
            )
            curr_iter = sp.title + " (" + d_label.format(start=start, end=end) + ")"
            break
    hook.set("current_iteration", curr_iter)
