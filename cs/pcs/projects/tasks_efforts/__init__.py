#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.projects import tasks_changes
from cs.pcs.projects.tasks_efforts.adjust_days import adjust_project_and_task_days
from cs.pcs.projects.tasks_efforts.aggregation import (
    AGGREGATION_ATTRIBUTES,
    aggregate_project_structure,
)
from cs.pcs.projects.tasks_efforts.status_signals import update_status_signals


def add_task_changes(tasks_by_id, value_dict):
    def add_change(changes, task, new_values, attr, default_value):
        new_val = new_values.get(attr, default_value)
        if task[attr] != new_val:
            changes[attr] = new_val

    for task_id, new_values in value_dict.items():
        task = tasks_by_id[task_id]
        changes = {}

        # check for changes on listed attributes
        for attr, _, _, default_value, _, _, _, _ in AGGREGATION_ATTRIBUTES:
            if attr in new_values:
                add_change(changes, task, new_values, attr, default_value)

        if task["is_group"]:
            # check changes for percent completion
            add_change(changes, task, new_values, "percent_complet", 0)

        if changes:
            tasks_changes.add_indirect_changes(task_id, **changes)


def apply_task_changes_to_db(tasks_by_id, value_dict, cdb_project_id):
    tasks_changes.set_project_id(cdb_project_id)
    del value_dict[cdb_project_id]

    add_task_changes(tasks_by_id, value_dict)
    tasks_changes.apply_changes_to_db()


def save_project_changes(value_dict, project):
    project_changes = value_dict[project.cdb_project_id]
    if project_changes:
        cca = project.MakeChangeControlAttributes()
        project_changes.update(
            cdb_adate=cca["cdb_mdate"],
            cdb_apersno=cca["cdb_mpersno"],
        )
        project.Update(**project_changes)


def aggregate_changes(project):
    """
    Performs the following steps:

    1. Aggregate the project and its tasks (bottom up)
    2. Updates the status signals of task and project
    3. Adjust task and project days
    4. Save aggregation/status signal changes to the db (if any)

    :param project: Project to update
    :type project: cs.pcs.projects.Project
    """
    project_dict = {**project}

    value_dict, tasks_by_id = aggregate_project_structure(project_dict)
    update_status_signals(project_dict, value_dict, tasks_by_id)

    adjust_project_and_task_days(project, project_dict, tasks_by_id, value_dict)

    save_project_changes(value_dict, project)
    apply_task_changes_to_db(tasks_by_id, value_dict, project.cdb_project_id)
