#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

__docformat__ = ""
__revision__ = "$Id: "


from cdb import rte, sig
from cs.actions import Action
from cs.taskboard.groups import add_group_mapping

from cs.pcs.projects.tasks import Task

GROUP_TASK = "Task"


def get_action_task(action):
    if action.cdb_project_id:
        return Task.ByKeys(cdb_project_id=action.cdb_project_id, task_id=action.task_id)
    return None


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    # Global group mappings
    add_group_mapping(
        Action._getClassname(),  # pylint: disable=protected-access
        {
            GROUP_TASK: get_action_task,
        },
    )
