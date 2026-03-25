#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This module extends the Project and Task class by
additional methods to manage Project Tasks on a task boards.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig
from cdb.classbody import classbody
from cs.taskboard.utils import add_to_change_stack, remove_from_change_stack

# noinspection PyUnresolvedReferences
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.taskboards.objects import refresh_taskboards


@classbody
class Project:
    def get_project_tasks_for_board(self, task_id=None):
        """
        Returns all project tasks of the given task that may need to be displayed on the task board.

        :param task_id:
            The task to which the task board is assigned.

            The system only searches for project tasks that are assigned
            to the task structure of the given task.

            If no task is given, all project tasks of the project are determined

        :return:
            all project tasks that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        task_id = "" if not task_id else task_id
        search_ids, _, groups = self.getTaskSets(task_id=task_id)
        return search_ids - groups

    @sig.connect(Project, "delete", "pre")
    @sig.connect(Project, "state_change", "pre")
    def _refresh_taskboards_pre(self, ctx):
        add_to_change_stack(self, ctx)

    @sig.connect(Project, "delete", "post")
    @sig.connect(Project, "state_change", "post")
    def _refresh_taskboards_post(self, ctx):
        remove_from_change_stack(self, ctx)


@classbody
class Task:
    def get_project_tasks_for_board(self):
        """
        Returns all project tasks of the task that may need to be displayed on the task board

        The system only searches for project tasks that are assigned
        to the task structure of the current task.

        :return:
            all project tasks that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        return self.Project.get_project_tasks_for_board(task_id=self.task_id)

    def on_cs_taskboard_move_card_now(self, ctx):
        end = ctx.dialog["end_time_fcast"]
        self.setTimeframe(days=self.days_fcast, end=end)

    @sig.connect(Task, "state_change", "pre")
    def _refresh_taskboards_pre(self, ctx):
        add_to_change_stack(self, ctx)

    @sig.connect(Task, "state_change", "post")
    def _refresh_taskboards_post(self, ctx):
        if self.status in [Task.DISCARDED.status, Task.FINISHED.status]:
            # reset iteration object id if status is finalized
            sig.emit(Task, "changed_to_finial_status")(self)
        remove_from_change_stack(self, ctx)

    @sig.connect(Task, "adjust_dates_on_taskboard")
    @sig.connect(Task, "adjust_dates")
    @sig.connect(Task, "create", "post")
    @sig.connect(Task, "copy_task_structure")
    def refresh_taskboards(self, ctx=None):
        refresh_taskboards(self)
