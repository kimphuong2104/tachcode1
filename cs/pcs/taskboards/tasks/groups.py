#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import rte, sig
from cs.taskboard.constants import GROUP_CATEGORY, GROUP_RESPONSIBLE
from cs.taskboard.groups import add_group_mapping, get_subject_group_context

from cs.pcs.projects.tasks import Task

GROUP_TASK = "Task"


def get_parent_task(task):
    if task.parent_task:
        return Task.ByKeys(cdb_project_id=task.cdb_project_id, task_id=task.parent_task)
    return None


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    # Global group mappings
    add_group_mapping(
        Task._getClassname(),
        {
            GROUP_RESPONSIBLE: get_subject_group_context,
            GROUP_CATEGORY: "mapped_category",
            GROUP_TASK: get_parent_task,
        },
    )
