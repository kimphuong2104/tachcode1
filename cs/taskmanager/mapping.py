#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from contextlib import contextmanager

from cdb import version
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cs.taskmanager import TaskHeaders
from cs.taskmanager.conditions import apply_post_select_conditions
from cs.taskmanager.conf import get_cache

if version.verstring(0) < "16.0":
    from cdb.platform.mom import increase_eviction_queue_limit
else:
    # CE 16 has no max cache size per request
    @contextmanager
    def increase_eviction_queue_limit(_):
        yield


EVICTION_QUEUE_BUFFER = 500


def _get_task_object(task_handle, task_classname, contexts):
    cache = get_cache()
    task_class = cache.classes.get(task_classname, None)

    if not task_class:
        logging.error("unknown task class: '%s'", task_classname)
        return None

    objects_cls = task_class.ObjectsClass

    if not objects_cls:
        logging.error("unknown objects class: '%s'", task_class.classname)
        return None

    # pylint: disable=protected-access
    task = objects_cls._FromObjectHandle(task_handle)
    setattr(task, "@cs_tasks_class", task_classname)

    if task and apply_post_select_conditions(task, contexts):
        return task

    return None


def get_tasks(condition, max_tasks=None):
    """
    Public API for cs.taskmanager.web.rest_app

    :type condition: :py:const:`cs.taskmanager.conditions.CONDITION`
    :type max_tasks: int

    :returns: Task objects matching `condition` readable by logged-in user
    :rtype: list of `cdb.objects.Object`
    """
    result = []

    classnames_by_uuid = TaskHeaders.GetHeaders(
        condition.users + condition.substituted,
        condition.condition,
    )
    # apply limit not to headers, but unique UUIDs
    # (headers include duplicates)
    task_uuids = list(classnames_by_uuid)[:max_tasks]

    with increase_eviction_queue_limit(len(task_uuids) + EVICTION_QUEUE_BUFFER):
        tasks_by_uuid = getObjectHandlesFromObjectIDs(
            list(task_uuids),
            True,  # refresh
            True,  # check_read_access
        )

        for task_uuid, task_handle in tasks_by_uuid.items():
            task = _get_task_object(
                task_handle,
                classnames_by_uuid[task_uuid],
                condition.contexts,
            )
            if task:
                result.append(task)

    return result


def matches_filters(condition, cdb_object_id):
    """
    Public API for cs.taskmanager.web.rest_app

    :returns: If `cdb_object_id` matches given `condition`
    :rtype: bool
    """
    classnames_by_uuid = TaskHeaders.GetHeaders(
        set(condition.users).union(condition.substituted),
        condition.condition,
    )
    task_uuids = classnames_by_uuid.keys()
    return cdb_object_id in task_uuids
