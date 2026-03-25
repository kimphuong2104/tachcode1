#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cs.pcs.efforts import EFFORTS_TASK_CATALOG
from cs.pcs.projects import Project
from cs.pcs.projects.catalogs import CatalogProjectTaskProposals
from cs.pcs.projects.tasks import Task


class RecentlyUsedTasks:
    """
    Provides the recently used tasks by a specific user.
    """

    def __init__(self, user_id):
        self.user_id = user_id

    def combine(self, id1, id2):
        return f"{id1}@{id2}"

    def retrieve_task_proposals(self):
        task_proposals = CatalogProjectTaskProposals.Query(
            f"catalog_personalnummer='{self.user_id}' AND catalog_name='{EFFORTS_TASK_CATALOG}'",
            order_by="catalog_sel_time desc",
        )

        tasks = Task.KeywordQuery(
            task_id=task_proposals.task_id,
            cdb_project_id=task_proposals.cdb_project_id,
            ce_baseline_id="",
        )

        projects = Project.KeywordQuery(
            cdb_project_id=task_proposals.cdb_project_id, ce_baseline_id=""
        )

        return task_proposals, tasks, projects

    def indexing_by_id(self, tasks, projects):
        task_by_id = {
            self.combine(task.cdb_project_id, task.task_id): task for task in tasks
        }

        project_by_id = {project.cdb_project_id: project for project in projects}

        return task_by_id, project_by_id

    def separating_tasks_by_pin_status(self, task_proposals):
        pinned_tasks = []
        unpinned_tasks = []

        for proposal in task_proposals:
            if proposal.pinned:
                pinned_tasks.append(proposal)
            else:
                unpinned_tasks.append(proposal)

        sorted_pinned_tasks = sorted(pinned_tasks, key=lambda d: d.pinned_sel_time)

        return sorted_pinned_tasks, unpinned_tasks

    def mutate_rec_used_tasks_result(
        self, task_proposals, task_by_id, project_by_id, seen, result
    ):
        for proposal in task_proposals:
            task_key = self.combine(proposal.cdb_project_id, proposal.task_id)
            if task_key not in task_by_id or task_key in seen:
                # task no longer exists or task already counted
                continue

            seen.add(task_key)
            task = task_by_id[task_key]
            if not task.CheckAccess("read"):
                continue

            project = project_by_id[task.cdb_project_id]
            result.append(
                {
                    "task_desc": task.GetDescription(),
                    "task_id": task.task_id,
                    "task_name": task.task_name,
                    "project_desc": project.GetDescription(),
                    "cdb_project_id": task.cdb_project_id,
                    "project_name": project.project_name,
                    "pinned": proposal.pinned,
                }
            )

    def get_recently_use_tasks(self):
        """
        Returns the recently used tasks from `pcs_task_proposals`
        for the user specified by `self.user_id`. Tasks are ordered by
        ascending selection datetime for pinned tasks and descending
        selection datetime for unpinned tasks. Only tasks with `read`
        access are returned as a result.

        :returns: List of all the tasks ordered by (descending)
            the selection time of the task.
        :rtype: list
        """

        task_proposals, tasks, projects = self.retrieve_task_proposals()

        task_by_id, project_by_id = self.indexing_by_id(tasks, projects)

        sorted_pinned_tasks, unpinned_tasks = self.separating_tasks_by_pin_status(
            task_proposals
        )

        result = []
        seen = set()

        self.mutate_rec_used_tasks_result(
            sorted_pinned_tasks, task_by_id, project_by_id, seen, result
        )
        self.mutate_rec_used_tasks_result(
            unpinned_tasks, task_by_id, project_by_id, seen, result
        )

        return result

    def update_task_pin_status(self, request):
        task_id = request.json["task_id"]
        pin_status = request.json["pin_status"]
        cdb_project_id = request.json["cdb_project_id"]

        task_proposal = CatalogProjectTaskProposals.KeywordQuery(
            catalog_personalnummer=self.user_id,
            catalog_name=EFFORTS_TASK_CATALOG,
            task_id=task_id,
            cdb_project_id=cdb_project_id,
            ce_baseline_id="",
        )
        task_proposal = task_proposal[0]

        kwargs = {
            "pinned": pin_status,
            "pinned_sel_time": datetime.datetime.utcnow()
            if pin_status
            else task_proposal.pinned_sel_time,
        }
        task_proposal.Update(**kwargs)
