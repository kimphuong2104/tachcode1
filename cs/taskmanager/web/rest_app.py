#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for cs.taskmanager.web, mounted @ /internal/tasks
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import logging

from webob.exc import HTTPBadRequest, HTTPInternalServerError

from cdb.util import ErrorMessage
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal
from cs.taskmanager.web.main import MOUNTEDPATH
from cs.taskmanager.web.models.context import TaskContextModel
from cs.taskmanager.web.models.data import Data
from cs.taskmanager.web.models.settings import Settings
from cs.taskmanager.web.models.views import ChangeViews, NewView, View
from cs.taskmanager.web.models.webdata import Webdata
from cs.taskmanager.web.models.write_data import WriteReadStatus, WriteTags


def require_payload(prefix, request, *keys):
    payload = request.json
    try:
        if len(keys) == 1:
            return payload[keys[0]]
        return [payload[key] for key in keys]
    except KeyError as error:
        logging.error(
            "%s: invalid payload '%s' (%s)",
            prefix,
            payload,
            error,
        )
        raise HTTPBadRequest


class App(JsonAPI):
    pass


@Internal.mount(app=App, path=MOUNTEDPATH)
def _mount_app():
    return App()


@App.path(path="settings", model=Settings)
def _get_settings_model():
    return Settings()


@App.json(model=Settings)
def get_tasks_settings(model, request):
    try:
        result = model.get_tasks_settings(request)
    except ErrorMessage as e:
        raise HTTPInternalServerError(e.errp[0])
    return result


@App.path(path="data", model=Data)
def _get_data_model():
    return Data()


@App.json(model=Data, request_method="POST")
def get_data(model, request):
    conditions = require_payload("data", request, "conditions")
    results = []
    for condition in conditions:
        result = model.get_tasks(condition, request)
        result["widgetID"] = condition["widgetID"]
        results.append(result)
    return results


@App.json(model=Data, name="updates", request_method="POST")
def get_updates(model, request):
    conditions = require_payload("updates", request, "conditions")
    results = []
    for condition in conditions:
        result = model.get_updates(condition, request)
        result["widgetID"] = condition["widgetID"]
        results.append(result)
    return results


@App.json(model=Data, name="target_statuses", request_method="POST")
def get_target_statuses(model, request):
    cdb_object_id = require_payload("data_target_statuses", request, "cdb_object_id")
    return model.get_target_statuses(cdb_object_id)


@App.path(path="context/{task_classname}/{task_oid}", model=TaskContextModel)
def _get_context_model(task_classname, task_oid):
    return TaskContextModel(task_classname, task_oid)


@App.json(model=TaskContextModel)
def get_task_context(model, request):
    return model.resolve_context(request)


@App.path(path="data/read_status", model=WriteReadStatus)
def _get_read_status_model():
    return WriteReadStatus()


@App.json(model=WriteReadStatus, request_method="POST")
def set_read_status(model, request):
    read, unread = require_payload("set_read_status", request, "read", "unread")
    model.set_read_status(read, unread)


@App.path(path="data/tags", model=WriteTags)
def _get_tag_model():
    return WriteTags()


@App.json(model=WriteTags, request_method="POST")
def set_tags(model, request):
    return model.set_tags(request.json)


@App.path(path="new_view", model=NewView)
def get_new_view_model(_):
    return NewView()


@App.json(model=NewView, request_method="POST")
def new_view(model, request):
    name, condition = require_payload("new_view", request, "name", "condition")
    model.new(name, condition)
    return model.get_all_views(request)


@App.path(path="views/{view_object_id}/{widget_object_id}", model=View)
def get_view_model(request, view_object_id, widget_object_id):
    return View(view_object_id, widget_object_id)


@App.json(model=View, name="select", request_method="POST")
def select_view(model, request):
    model.select()
    return model.get_all_views(request)


@App.json(model=View, name="save", request_method="POST")
def save_view(model, request):
    condition = require_payload("save_view", request, "condition")
    model.save(condition)
    return model.get_all_views(request)


@App.json(model=View, name="edit", request_method="POST")
def edit_view(model, request):
    condition = require_payload("edit_view", request, "condition")
    model.edit(condition)
    return model.get_all_views(request)


@App.json(model=View, name="revert", request_method="POST")
def revert_view(model, request):
    model.revert()
    return model.get_all_views(request)


@App.path(path="change_views", model=ChangeViews)
def get_change_views_model(request):
    return ChangeViews()


@App.json(model=ChangeViews, request_method="POST")
def change_views(model, request):
    delete, changesById = require_payload("change_views", request, "delete", "byID")
    errors = model.apply_all_changes(delete, changesById)

    if errors:
        raise HTTPInternalServerError("\n".join(errors))

    result = model.get_all_views(request)
    return result


@App.path(path="webdata", model=Webdata)
def _get_webdata_model(request):
    return Webdata()


@App.json(model=Webdata, request_method="POST")
def get_webdata(model, request):
    return model.get_async_data(request)
