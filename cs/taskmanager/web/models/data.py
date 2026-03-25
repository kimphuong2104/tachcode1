#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from webob.exc import (
    HTTPBadRequest,
    HTTPForbidden,
    HTTPInternalServerError,
    HTTPNotFound,
)

from cdb.objects import ByID
from cdb.objects.org import User
from cdb.util import ErrorMessage, PersonalSettings, get_label
from cs.platform.web.rest.support import get_restlink
from cs.taskmanager.conditions import get_conditions
from cs.taskmanager.conf import TaskClass
from cs.taskmanager.mapping import get_tasks
from cs.taskmanager.userdata import ReadStatus, Tags
from cs.taskmanager.web.models.views import get_backend_condition
from cs.taskmanager.web.util import get_collection_app, get_rest_object

DEFAULT_TASKS_LIMIT = 5000


def get_max_tasks():
    try:
        limit = PersonalSettings().getValue("cs.taskmanager", "max_tasks")
        return int(limit)
    except (KeyError, TypeError, ValueError):
        logging.exception("cannot retrieve max_tasks settings")
        return DEFAULT_TASKS_LIMIT


def check_show_tasks(users):
    denied_persnos = []

    for persno in users:
        user = User.ByKeys(persno)

        if not (user and user.CheckAccess("show_tasks")):
            denied_persnos.append(persno)

    if denied_persnos:
        message = ErrorMessage(
            "cs_tasks_show_denied",
            ", ".join(denied_persnos),
        ).errp[0]
        raise HTTPForbidden(message)


def _get_tasks_condition(condition):
    """
    Conditions for getting (new) tasks. See documentation of
    :py:func:`cs.taskmanager.conditions.get_conditions` for request
    parameters.
    """
    deadline = condition["deadline"]
    responsible = condition["responsible"]
    users = condition.get("users", [])

    def get_bool(kwargs, key, default=None):
        return kwargs.get(key, default) is True

    deadline_active = deadline["active"]
    deadline_filter = {}

    if deadline_active == "days":
        deadline_filter["days"] = deadline["days"]
    if deadline_active == "range":
        deadline_filter["start"] = deadline["range"]["start"]
        deadline_filter["end"] = deadline["range"]["end"]

    # pylint: disable=use-dict-literal
    backend_condition = get_backend_condition(
        dict(
            users=set(users),
            my_personal=get_bool(responsible, "my_personal"),
            my_roles=get_bool(responsible, "my_roles"),
            substitutes=get_bool(responsible, "substitutes"),
            absence=get_bool(responsible, "absence"),
            user_personal=get_bool(responsible, "user_personal"),
            user_roles=get_bool(responsible, "user_roles"),
            types=set(condition.get("types", [])),
            contexts=set(condition.get("contexts", [])).difference([None]),
            **deadline_filter
        )
    )

    return get_conditions(**backend_condition)


class Data(object):
    def get_tasks_condition(self, condition):
        try:
            return _get_tasks_condition(condition)
        except KeyError:
            logging.exception("invalid condition: %s", condition)
            raise HTTPBadRequest

    def _get_rest_tasks(self, tasks, request):
        task_object_ids = [t.cdb_object_id for t in tasks]
        collection_app = get_collection_app(request)
        return {
            "objects": [
                get_rest_object(task, collection_app, request) for task in tasks
            ],
            "readStatus": ReadStatus.GetReadStatus(task_object_ids),
            "tags": Tags.GetIndexedTags(task_object_ids),
            "allTags": Tags.GetUserTags(),
            # frontend will clear "updates"
        }

    def get_tasks(self, frontend_condition, request):
        """
        Return task REST objects for given `frontend_condition`
        along with tasks-specific data ("tags" and "readStatus")

        :param frontend_condition: filter conditions in frontend format
        :type frontend_condition: dict

        :param request: The request sent from the frontend
            (used for link generation)
        :type request: morepath.Request

        :raises HTTPBadRequest: if `frontend_condition` is invalid
        :raises HTTPForbidden: if access right "show_tasks"
            is not granted for all users in `frontend_condition`
        """
        condition = self.get_tasks_condition(frontend_condition)
        check_show_tasks(condition.users)

        max_tasks = get_max_tasks()
        tasks = get_tasks(condition, max_tasks + 1)

        if len(tasks) > max_tasks:
            tasks = tasks[:-1]
            title = get_label("pccl_hits_restricted") % max_tasks
        else:
            title = ""

        result = self._get_rest_tasks(tasks, request)
        result["title"] = title
        return result

    def _is_task_object(self, obj):
        object_classname = obj.GetClassname()
        task_classnames = TaskClass.Query().classname
        return object_classname in task_classnames

    def get_updates(self, frontend_condition, request):
        """
        Return task updates for given `frontend_condition`
        (REST IDs only)

        :param frontend_condition: filter conditions in frontend format
        :type frontend_condition: dict

        :param request: The request sent from the frontend
            (used for link generation)
        :type request: morepath.Request

        :raises HTTPBadRequest: if `frontend_condition` is invalid
        :raises HTTPForbidden: if access right "show_tasks"
            is not granted for all users in `frontend_condition`
        """
        condition = self.get_tasks_condition(frontend_condition)
        check_show_tasks(condition.users)

        result = {
            "updates": [get_restlink(task, request) for task in get_tasks(condition)],
        }
        return result

    def get_target_statuses(self, cdb_object_id):
        task = ByID(cdb_object_id)

        if not (task and task.CheckAccess("read")):
            logging.error("Task not found: '%s'", cdb_object_id)
            raise HTTPNotFound

        try:
            targets = task.getCsTasksNextStatuses()
        except:  # noqa: E722
            logging.exception("Could not get target statuses for '%s'", cdb_object_id)
            raise HTTPInternalServerError

        if isinstance(targets, list):
            result = {
                "targets": targets,
            }
            return result
        else:
            raise HTTPInternalServerError
