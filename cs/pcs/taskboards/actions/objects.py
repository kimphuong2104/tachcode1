#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
"""
This class extends the Project, Task and Action class by
additional methods to manage the objects on a taskboard.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sig
from cdb.classbody import classbody
from cs.actions import Action

from cs.pcs.projects import Project  # pylint: disable=unused-import
from cs.pcs.projects.tasks import Task  # pylint: disable=unused-import
from cs.pcs.taskboards import utils
from cs.pcs.taskboards.objects import refresh_taskboards


@classbody
class Project:
    def get_actions_for_board(self, task_id=None):
        """
        Returns all actions of the given task that may need to be displayed on the task board.

        :param task_id:
            The task to which the task board is assigned.

            The system only searches for actions that are assigned
            to the task structure of the given task.

            If no task is given, all actions of the project are determined independently
            of a possible task assignment
        :return:
            all actions that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        task_id = "" if not task_id else task_id
        search_objects, ignore_objects, _ = self.getTaskSets(task_id=task_id)
        return utils.get_objects(
            "cdb_action", self.cdb_project_id, task_id, search_objects, ignore_objects
        )


@classbody
class Task:
    def get_actions_for_board(self):
        """
        Returns all actions of the task that may need to be displayed on the task board

        The system only searches for actions that are assigned
        to the task structure of the current task.

        :return:
            all actions that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        return self.Project.get_actions_for_board(task_id=self.task_id)


@classbody
class Action:

    # noinspection PyPep8Naming
    def getParent(self):
        """
        Returns either the project for project stages or the parent task if task_id is not empty.
        """
        if self.task_id:
            return self.Task
        return self.Project

    @sig.connect(Action, "state_change", "post")
    def _refresh_taskboards_post(self, ctx):
        if self.status in [Action.DISCARDED.status, Action.FINISHED.status]:
            # reset iteration object id if status is finalized
            sig.emit(Action, "changed_to_finial_status")(self)
        refresh_taskboards(self)

    @sig.connect(Action, "adjust_dates_on_taskboard")
    @sig.connect(Action, "create", "post")
    @sig.connect(Action, "copy", "post")
    @sig.connect(Action, "delete", "post")
    def refresh_taskboards(self, ctx=None):
        refresh_taskboards(self)
