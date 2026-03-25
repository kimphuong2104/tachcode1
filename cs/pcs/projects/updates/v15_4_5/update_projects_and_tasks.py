#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


"""
Module update_projects_and_tasks

Re-set projects and task timeframes, so that the difference between
start_time_fcast and end_time_fcast in days corresponds to days.
"""

import getopt
import sys

import mock
from cdb import progress, sig

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

USAGE = """USAGE: update_projects_and_tasks.py -r <ATTR>

This script recalculates either start_time_fcast, end_time_fcast or
days_fcast based on the other two for all tasks and projects.

-r, --recalculate <ATTR>:
    The value of ATTR is recalculated for all non-baseline projects and tasks
    based on the other two possible values.

    Valid values for ATTR:
    - start_time_fcast
    - end_time_fcast
    - days_fcast

    Usually, choosing end_time_fcast is the right choice.
"""
KEYMAP = {
    # keyword arg of setTimeframe: field name of task or project
    "start": "start_time_fcast",
    "end": "end_time_fcast",
    "days": "days_fcast",
}
QUERY = {
    "ce_baseline_id": "",
}


def setTimeframe(obj, parameter, is_task=False):
    values = {
        key: obj[field] if field != parameter else None for key, field in KEYMAP.items()
    }
    new_start, new_end, new_days = obj.calculateTimeFrame(**values)
    if is_task:
        # pylint: disable=protected-access
        obj._ensureResourceConstraints(new_start, new_end)
    obj.Update(
        start_time_fcast=new_start,
        end_time_fcast=new_end,
        days_fcast=new_days,
    )
    if is_task:
        sig.emit(Task, "adjust_dates")(obj)


def update_projects(parameter):
    projects = Project.KeywordQuery(**QUERY)
    pbar = progress.ProgressBar(
        maxval=len(projects),
        prefix="(1/3) Updating projects",
    )
    pbar.show()

    for project in projects:
        setTimeframe(project, parameter)
        pbar += 1
        pbar.show()


def update_tasks(parameter):
    tasks = Task.KeywordQuery(**QUERY)
    pbar = progress.ProgressBar(
        maxval=len(tasks),
        prefix="(2/3) Updating tasks",
    )
    pbar.show()

    for task in tasks:
        setTimeframe(task, parameter, True)
        pbar += 1
        pbar.show()


def reschedule():
    projects = Project.KeywordQuery(**QUERY)
    pbar = progress.ProgressBar(
        maxval=len(projects),
        prefix="(3/3) Re-scheduling",
    )
    pbar.show()

    for project in projects:
        project.recalculate()
        pbar += 1
        pbar.show()


def recalculate(parameter):
    with mock.patch.object(Project, "recalculate"):
        update_projects(parameter)
        update_tasks(parameter)

    reschedule()
    print("\nDone")


def main(argv):
    parameter = ""

    try:
        opts, _ = getopt.getopt(argv, "hr:", ["recalculate="])
    except getopt.GetoptError:
        print(USAGE)
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print(USAGE)
            sys.exit()
        elif opt in ("-r", "--recalculate"):
            if arg in KEYMAP.values():
                parameter = arg
            else:
                print(USAGE)
                sys.exit(2)

    if parameter:
        recalculate(parameter)
    else:
        print(USAGE)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
