# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from collections import OrderedDict, defaultdict
from json import JSONDecodeError

from cdb import sqlapi

from cs.pcs.projects.common import format_in_condition
from cs.pcs.projects.project_structure import util

PROJECT_SQL = """
    SELECT p.cdb_object_id FROM cdbpcs_project p
    JOIN cdbpcs_task t ON p.cdb_project_id = t.cdb_project_id
    AND p.ce_baseline_id = t.ce_baseline_id
    WHERE t.cdb_object_id = '{}'
"""

BASELINED_TASK_SQL = """
    SELECT bt.cdb_object_id, bt.task_id, bt.cdb_project_id
    FROM cdbpcs_task bt
    JOIN cdbpcs_task t ON t.task_id = bt.task_id
    WHERE t.cdb_object_id = '{}'
    AND bt.ce_baseline_id = '{}'
"""


def get_project(task_oid):
    sql = PROJECT_SQL.format(task_oid)

    result = sqlapi.RecordSet2(sql=sql)
    if result:
        return result[0]
    return None


def get_baselined_task(task_oid, baseline_id):
    sql = BASELINED_TASK_SQL.format(task_oid, baseline_id)

    result = sqlapi.RecordSet2(sql=sql)
    if result:
        return result[0]
    return None


def get_requested_baseline(project_oid, request):
    try:
        if hasattr(request, "json"):
            baselines = request.json.get("selectedBaselines")
            if baselines:
                return baselines.get(project_oid)
        else:
            return None
    except JSONDecodeError:
        return None


def format_key(pid, tid):
    return f"{pid}@{tid}"


def get_tasks_data(pcs_levels):
    oids = [
        level.cdb_object_id for level in pcs_levels if level.table_name == "cdbpcs_task"
    ]

    condition = format_in_condition("cdb_object_id", oids)
    query = f"""
        SELECT cdb_object_id, cdb_project_id, task_id, parent_task, position
        FROM cdbpcs_task WHERE {condition}
    """

    rset = sqlapi.RecordSet2(sql=query)
    records_by_oid = {r.cdb_object_id: r for r in rset}
    tasks_by_oid = OrderedDict()
    oids_by_tasks = OrderedDict()
    for oid in oids:
        record = records_by_oid[oid]

        tasks_by_oid[record.cdb_object_id] = (
            record.cdb_project_id,
            record.parent_task,
            record.task_id,
            record.position,
        )
        oids_by_tasks[
            format_key(record.cdb_project_id, record.task_id)
        ] = record.cdb_object_id

    return tasks_by_oid, oids_by_tasks


def flatten(structure, levels):
    flattened_structure = []
    root = structure["#"][0]
    _, root_key = root

    def dfs(root):
        flattened_structure.append(levels[root])
        for _, child in structure[root]:
            dfs(child)

    dfs(root_key)

    return flattened_structure


def merge_with_baseline_task(pcs_levels, baseline_pcs_levels, task):
    return merge_with_baseline(
        pcs_levels, baseline_pcs_levels, format_key(task.cdb_project_id, task.task_id)
    )


def merge_with_baseline_proj(pcs_levels, baseline_pcs_levels, baseline_project):
    merged_structure = merge_with_baseline(
        pcs_levels, baseline_pcs_levels, format_key(baseline_project.cdb_project_id, "")
    )
    if merged_structure:
        merged_structure[0] = merged_structure[0]._replace(
            additional_data=baseline_project.cdb_object_id
        )
    return merged_structure


def merge_with_baseline(pcs_levels, baseline_pcs_levels, root_key):
    """
    Merges the baseline data (of complete project or individual tasks)
    with the data of current project head.
    For a given project P1 with a baseline B1, there can be three cases
    for merging strategy:
        1. The task T from B1 is still part of P1. In this case the data of
            both versions of T is kept.
        2. The task T from B1 is no more a part of B1. Which means T was
            deleted after the baseline B1 was created. We merge T into the
            structure at it's appropriate place (where it existed before the
            creation of B1)
        3. The task T is a new task in P1 and not part of B1. In this case the
            data of only this task is kept.

    :param baseline_pcs_levels: PCS_LEVEL objects representing the resolved structure
        of the requested baseline.
    :type baseline_pcs_levels: List of named tuples `PCS_LEVEL`.

    :param root_key: Rest key of the root object. The root object can be a project or a task.
    :type root_key: str

    :returns: merged structure in the form of a list.
    :rtype: list of named tuples `PCS_LEVEL`.

    """
    proj_tasks_by_oid, _ = get_tasks_data(pcs_levels)
    bl_tasks_by_oid, bl_oids_by_task = get_tasks_data(baseline_pcs_levels)

    all_baseline_tasks = bl_oids_by_task.keys()

    merged_structure = defaultdict(list)
    levels = defaultdict()

    common_tasks = set()

    merged_structure["#"].append((0, root_key))
    if pcs_levels:  # root level
        levels[root_key] = pcs_levels[0]

    for level in pcs_levels:
        obj_id = level.cdb_object_id
        if level.table_name != "cdbpcs_task":
            continue

        task_data = proj_tasks_by_oid[obj_id]
        task_key = format_key(task_data[0], task_data[2])
        parent_key = format_key(task_data[0], task_data[1])

        merged_structure[parent_key].append((task_data[3], task_key))

        lvl = level

        if task_key in bl_oids_by_task:  # task was also part of baseline
            common_tasks.add(task_key)
            lvl = level._replace(additional_data=bl_oids_by_task[task_key])

        levels[task_key] = lvl

    deleted_tasks = [x for x in all_baseline_tasks if x not in common_tasks]

    for task in deleted_tasks:
        # place each deleted task to it's right parent at the right position
        task_oid = bl_oids_by_task[task]
        task_data = bl_tasks_by_oid[task_oid]
        task_key = format_key(task_data[0], task_data[2])
        parent_key = format_key(task_data[0], task_data[1])
        parent_level = levels[parent_key]
        merged_structure[parent_key].append((task_data[3], task_key))
        levels[task_key] = util.PCS_LEVEL(
            task_oid, "cdbpcs_task", parent_level.level + 1
        )
        if parent_key in merged_structure:  # parent task exists in current project?
            # fix the order according to the position of the tasks
            merged_structure[parent_key] = sorted(
                merged_structure[parent_key], key=lambda x: x[0]
            )

    # recompute the structure from adjacency lists
    return flatten(merged_structure, levels)
