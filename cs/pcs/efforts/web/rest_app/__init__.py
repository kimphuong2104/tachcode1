#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

from cs.pcs.efforts import APP_MOUNT_PATH
from cs.pcs.efforts.web import APP  # noqa, for collect_links
from cs.pcs.efforts.web.rest_app.models.efforts_model import EffortsModel
from cs.pcs.efforts.web.rest_app.models.recently_used_tasks import RecentlyUsedTasks
from cs.pcs.projects.common.web import get_url_patterns


def get_app_url_patterns(request):
    internal_app = InternalMyEffortsApp.get_app(request)
    models = [
        ("efforts", EffortsModel, []),
        ("recUsedTasks", RecentlyUsedTasks, ["user_id"]),
    ]
    return get_url_patterns(request, internal_app, models)


class InternalMyEffortsApp(JsonAPI):
    @staticmethod
    def get_app(request):
        "Try to look up /internal/myefforts"
        return get_internal(request).child(APP_MOUNT_PATH)


@Internal.mount(app=InternalMyEffortsApp, path=APP_MOUNT_PATH)
def _mount_app():
    return InternalMyEffortsApp()


@InternalMyEffortsApp.path("efforts", model=EffortsModel)
def get_efforts_model():
    return EffortsModel()


@InternalMyEffortsApp.json(model=EffortsModel, request_method="GET")
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts
    Method:         GET

    With a GET request it is possible to get all the efforts which
    are relevant for the current user and the current week or a specific
    time interval. You can pass nothing or a JSON payload formatted as
    follows to the backend:

    {
        "fromDate": "2020-01-20T00:00:00.000000",
        "toDate": "2020-01-26T00:00:00.000000"
    }


    If the request contains a correct JSON payload, then the backend
    will return all efforts that belongs to the given date interval and
    the currently logged in user.
    If no JSON payload is passed to the backend, it will return all
    efforts of the current week and the currently logged in user.
    """
    return model.get_efforts(request)


@InternalMyEffortsApp.json(
    model=EffortsModel, request_method="PUT", name="start-stopwatch"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/start-stopwatch
    Method:         PUT

    This method creates a new stopwatch with a given time and returns
    the json parsed object.

    Raises: HTTPConflict (409) if the server stopwatch state does not
    match the client state.

    """
    return model.start_stopwatch(request)


@InternalMyEffortsApp.json(
    model=EffortsModel, request_method="PUT", name="stop-stopwatch"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/stop-stopwatch
    Method:         PUT

    Stops the stopwatch referenced by stopwatch id in the request.

    Raises: HTTPConflict if the stopwatch is already stopped.
    """
    return model.stop_stopwatch(request)


@InternalMyEffortsApp.json(
    model=EffortsModel, request_method="PUT", name="record-stopwatches"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/record-stopwatches
    Method:         PUT

    Records the given stopwatches for a given effort.

    Raises: HTTPConflict (409) if the server stopwatch state does not
    match the client state.
    """
    return model.record_stopwatches(request)


@InternalMyEffortsApp.json(
    model=EffortsModel, request_method="PUT", name="reset-stopwatches"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/reset-stopwatches
    Method:         PUT

    Marks all the stopwatches as booked. The front-end is responsible
    for clearing all the stopwatches it hosts after this api call.

    Raises: HTTPConflict (409) if the server stopwatch state does not
    match the client state.
    """
    return model.reset_stopwaches(request)


@InternalMyEffortsApp.json(
    model=EffortsModel, request_method="GET", name="valid-stopwatches"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/valid-stopwatches
    Method:         PUT

    Checks if the front-end stopwatch state is coherent with back-end state.

    Raises: HTTPConflict (409) if the server stopwatch state does not
    match the client state.
    """
    return model.valid_stopwatches(request)


@InternalMyEffortsApp.path("rec-used-tasks/{user_id}", model=RecentlyUsedTasks)
def get_recently_used_task_model(user_id):
    return RecentlyUsedTasks(user_id)


@InternalMyEffortsApp.json(model=RecentlyUsedTasks, request_method="GET")
def get_recently_used_tasks(model, request):
    return model.get_recently_use_tasks()


@InternalMyEffortsApp.json(
    model=RecentlyUsedTasks, request_method="PUT", name="update-task-pin-status"
)
def _(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/efforts/update-task-pin-status
    Method:         PUT

    Updates the pinned status of a task depending on the request payload.
    """
    return model.update_task_pin_status(request)
