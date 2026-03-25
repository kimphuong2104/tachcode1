#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


from collections import OrderedDict, defaultdict
from datetime import date

from cdb import sig, sqlapi

from cs.pcs.projects.tasks_efforts.helpers import is_discarded


def SQLdate(x, j, i):
    str_date = sqlapi.SQLdate(x, j, i)
    if str_date:
        day, month, year = map(int, str_date.split("."))
        return date(year, month, day)
    return None


def custom_converter(required_type, x, j, i):
    str_val = sqlapi.SQLstring(x, j, i)
    if str_val:
        return required_type(str_val)
    return None


def SQLinteger(*args):
    return custom_converter(int, *args)


def SQLnumber(*args):
    return custom_converter(float, *args)


TASK_ATTR_TYPES = OrderedDict(
    {
        "parent_task": sqlapi.SQLstring,
        "task_id": sqlapi.SQLstring,
        "auto_update_time": SQLinteger,
        "auto_update_effort": SQLinteger,
        "is_group": SQLinteger,
        "start_time_plan": SQLdate,
        "end_time_plan": SQLdate,
        "start_time_act": SQLdate,
        "end_time_act": SQLdate,
        "effort_plan": SQLnumber,
        "effort_fcast": SQLnumber,
        "effort_act": SQLnumber,
        "effort_fcast_d": SQLnumber,
        "effort_fcast_a": SQLnumber,
        "start_time_fcast": SQLdate,
        "end_time_fcast": SQLdate,
        "status": SQLinteger,
        "percent_complet": SQLinteger,
        "status_time_fcast": SQLinteger,
        "status_effort_fcast": SQLinteger,
        "days": SQLinteger,
        "days_act": SQLinteger,
        "start_is_early": SQLinteger,
        "end_is_early": SQLinteger,
    }
)

TASK_ATTR = TASK_ATTR_TYPES.keys()


def get_tasks(cdb_project_id):
    tasks = sqlapi.SQLselect(
        f"{','.join(TASK_ATTR)} FROM cdbpcs_task "
        f"WHERE cdb_project_id='{cdb_project_id}' AND ce_baseline_id=''"
    )
    rows = sqlapi.SQLrows(tasks)
    subs_by_parent_id = defaultdict(list)
    tasks_by_id = {}
    for i in range(rows):
        task = {
            col: TASK_ATTR_TYPES[col](tasks, j, i) for j, col in enumerate(TASK_ATTR)
        }
        subs_by_parent_id[task["parent_task"]].append(task)
        tasks_by_id[task["task_id"]] = task
    subs_by_parent_id[cdb_project_id] = subs_by_parent_id[""]
    return subs_by_parent_id, tasks_by_id


def get_efforts(cdb_project_id):
    changes = defaultdict(float)
    efforts = sqlapi.SQLselect(
        f"task_id, SUM(hours) AS hours FROM cdbpcs_time_sheet "
        f"WHERE cdb_project_id='{cdb_project_id}' GROUP BY task_id"
    )
    for i in range(sqlapi.SQLrows(efforts)):
        task_id = sqlapi.SQLstring(efforts, 0, i)
        hours = sqlapi.SQLnumber(efforts, 1, i)
        changes[task_id] = hours
    return changes


def get_demands(cdb_project_id):
    result = sig.emit("project_get_demands")(cdb_project_id)
    if result:
        return result[0]
    return defaultdict(float)


def get_assignments(cdb_project_id):
    result = sig.emit("project_get_assignments")(cdb_project_id)
    if result:
        return result[0]
    return defaultdict(float)


def load_project_data(project):
    cdb_project_id = project["cdb_project_id"]
    task_tree, tasks_by_id = get_tasks(cdb_project_id)
    efforts = get_efforts(cdb_project_id)
    demands = get_demands(cdb_project_id)
    assignments = get_assignments(cdb_project_id)

    return task_tree, tasks_by_id, efforts, demands, assignments


def count_leaftasks(cdb_project_id, subs_by_parent_id):
    leaftasks = defaultdict(int)

    def _dfs(parent_id):
        subs = subs_by_parent_id[parent_id]
        if subs:
            for sub in subs:
                if not is_discarded(sub):
                    sub_task_id = sub["task_id"]
                    _dfs(sub_task_id)
                    leaftasks[parent_id] += leaftasks[sub_task_id]
        else:  # leaf task of project structure tree
            leaftasks[parent_id] += 1

    _dfs(cdb_project_id)
    return leaftasks
