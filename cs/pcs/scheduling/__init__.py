#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-locals

import logging

from cs.pcs.scheduling import load_project, load_relships, load_tasks
from cs.pcs.scheduling.load_sorted_tasks import get_sorted_task_uuids
from cs.pcs.scheduling.persist import persist_changes
from cs.pcs.scheduling.pretty_print import pretty_log
from cs.pcs.scheduling.scheduling import calculate_network


def schedule(project_id):
    """
    Schedule (= calculate new target dates for)
    the single project identified by ``project_id``.

    Changed dates and network values will be written to database.
    """

    # 1. load and transform (index, normalize) data
    project, calendar = load_project.load_project(project_id)
    latest_finish = project["end_time_fcast"] if project["fixed"] else None
    task_data = load_tasks.load_tasks(project_id, calendar)

    discarded = task_data[1]
    original_dates = task_data[2]
    all_children = task_data[5]
    relships = load_relships.load_relships(all_children, project_id, discarded)

    by_uuid = task_data[0]
    persistent_relships = relships[2]
    pred_uuids_forward, pred_uuids_backward = relships[3], relships[4]
    uuids_forward, uuids_backward = get_sorted_task_uuids(
        by_uuid, pred_uuids_forward, pred_uuids_backward
    )

    tasks_forward = [by_uuid[uuid] for uuid in uuids_forward]
    tasks_backward = [by_uuid[uuid] for uuid in uuids_backward]

    # 2. calculate network
    try:
        network = calculate_network(
            task_data, tasks_forward, tasks_backward, relships, latest_finish
        )
    except RuntimeError as exc:
        raise RuntimeError(f"failed to calculate network for '{project_id}'") from exc

    # 3. write back changes (only) to database
    changed_task_ids, changed_res_task_ids = persist_changes(
        tasks_forward,
        discarded,
        original_dates,
        network,
        project,
        calendar,
        persistent_relships,
    )

    logging.info("schedule CALENDAR: %s", calendar)
    logging.info("schedule NETWORK: %s", network)
    pretty_log(f"scheduled '{project_id}':", calendar, network)

    return changed_task_ids, changed_res_task_ids, calendar, network
