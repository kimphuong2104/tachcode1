#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import rte, sig
from cs.taskboard.constants import GROUP_CATEGORY, GROUP_PRIORITY, GROUP_RESPONSIBLE
from cs.taskboard.groups import add_group_mapping, get_subject_group_context

from cs.pcs.issues import Issue
from cs.pcs.projects.tasks import Task

GROUP_TASK = "Task"


def get_issue_task(issue):
    if issue.task_id:
        return Task.ByKeys(cdb_project_id=issue.cdb_project_id, task_id=issue.task_id)
    return None


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    # Global group mappings
    add_group_mapping(
        Issue._getClassname(),
        {
            GROUP_RESPONSIBLE: get_subject_group_context,
            GROUP_CATEGORY: "mapped_category_name",
            GROUP_TASK: get_issue_task,
            GROUP_PRIORITY: "mapped_priority_name",
        },
    )
