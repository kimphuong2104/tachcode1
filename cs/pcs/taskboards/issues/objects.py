#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
"""
This module extends the Project, Task and Issue class by
additional methods to manage Open Issues on task boards.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig
from cdb.classbody import classbody

from cs.pcs.issues import Issue
from cs.pcs.projects import Project  # pylint: disable=unused-import
from cs.pcs.projects.tasks import Task  # pylint: disable=unused-import
from cs.pcs.taskboards import utils
from cs.pcs.taskboards.objects import refresh_taskboards


@classbody
class Project:
    def get_issues_for_board(self, task_id=None):
        """
        Returns all open issues of the given task that may need to be displayed on the task board.

        :param task_id:
            The task to which the task board is assigned.

            The system only searches for open issues that are assigned
            to the task structure of the given task.

            If no task is given, all open issues of the project are determined independently
            of a possible task assignment
        :return:
            all open issues that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        task_id = "" if not task_id else task_id
        search_objects, ignore_objects, _ = self.getTaskSets(task_id=task_id)
        return utils.get_objects(
            "cdbpcs_issue", self.cdb_project_id, task_id, search_objects, ignore_objects
        )


@classbody
class Task:
    def get_issues_for_board(self):
        """
        Returns all open issues of the task that may need to be displayed on the task board

        The system only searches for open issues that are assigned
        to the task structure of the current task.

        :return:
            all open issues that may need to be displayed
        :rtype:
            cdb.sqlapi.RecordSet2
        """
        return self.Project.get_issues_for_board(task_id=self.task_id)


@classbody
class Issue:

    # noinspection PyPep8Naming
    def getParent(self):
        """
        Returns either the project for project stages or the parent task if task_id is not empty.
        """
        if self.task_id:
            return self.Task
        return self.Project

    @sig.connect(Issue, "state_change", "post")
    def _refresh_taskboards_post(self, ctx):
        if self.status in [Issue.DISCARDED.status, Issue.COMPLETED.status]:
            # reset iteration object id if status is finalized
            sig.emit(Issue, "changed_to_finial_status")(self)
        refresh_taskboards(self)

    @sig.connect(Issue, "adjust_dates_on_taskboard")
    @sig.connect(Issue, "create", "post")
    @sig.connect(Issue, "copy", "post")
    @sig.connect(Issue, "delete", "post")
    def refresh_taskboards(self, ctx=None):
        refresh_taskboards(self)
