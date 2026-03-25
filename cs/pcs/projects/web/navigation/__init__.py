#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import cdbwrapc
from cdb import sig
from cdb.lru_cache import lru_cache

from cs.pcs.efforts import APP_MOUNT_PATH as EffortsAppPath
from cs.pcs.projects.common import get_restname

GET_NAV_ENTRIES = sig.signal()


SEARCH_EFFORTS_LABEL = "cdbpcs_search_efforts"
MY_EFFORTS_APP_LABEL = "web.efforts.my_efforts"
TIME_SCHEDULE_LABEL = "cdbpcs_time_schedules"
PROJECTS_CLASS = "cdbpcs_project"
TIME_SCHEDULE_CLASS = "cdbpcs_time_schedule"
EFFORTS_CLASS = "cdbpcs_effort"
TASK_CLASS = "cdbpcs_task"
ISSUE_CLASS = "cdbpcs_issue"
CHECKLIST_CLASS = "cdbpcs_checklist"
ACTION_CLASS = "cdb_action"
SEARCH_TASKS = "web.projects.tasks_search"
SEARCH_OPEN_ISSUES = "web.projects.open_issues_search"
SEARCH_CHECKLIST = "web.projects.checklist_search"
SEARCH_ACTIONS = "web.projects.actions_search"


@lru_cache(maxsize=1)
def get_nav_entries_default():
    def get_label(id):
        return cdbwrapc.get_label(id)

    def get_class_link(classname):
        return f"/info/{get_restname(classname)}"

    timeScheduleLabel = get_label(TIME_SCHEDULE_LABEL)
    searchEffortsLabel = get_label(SEARCH_EFFORTS_LABEL)
    myEffortsLabel = get_label(MY_EFFORTS_APP_LABEL)
    searchTasksLabel = get_label(SEARCH_TASKS)
    searchOpenIssuesLabel = get_label(SEARCH_OPEN_ISSUES)
    searchChecklistLabel = get_label(SEARCH_CHECKLIST)
    searchActionsLablel = get_label(SEARCH_ACTIONS)

    return [
        (timeScheduleLabel, "cdbpcs_gantt_chart", get_class_link(TIME_SCHEDULE_CLASS)),
        (searchTasksLabel, "cdbpcs_task", get_class_link(TASK_CLASS)),
        (searchOpenIssuesLabel, "cdbpcs_issue", get_class_link(ISSUE_CLASS)),
        (searchChecklistLabel, "cdbpcs_checklist", get_class_link(CHECKLIST_CLASS)),
        (searchActionsLablel, "cdb_action", get_class_link(ACTION_CLASS)),
        (searchEffortsLabel, "cdbpcs_effort_entry", get_class_link(EFFORTS_CLASS)),
        (myEffortsLabel, "cdbpcs_efforts_person_time", f"/{EffortsAppPath}"),
    ]


def get_nav_entries():
    """
    Returns a list of navigation entries. Each entry is represented
    in the form of a tuple. Each tuple contains label, icon and link of the nav entry.
    The label is also used as a tooltip text.
    """

    nav_entries = sig.emit(GET_NAV_ENTRIES)()
    if nav_entries:
        # result is a list of return values all functions connected with the signal
        return [entry for entries in nav_entries for entry in entries]
    else:
        # if no signal result, return the default nav values
        return get_nav_entries_default()
