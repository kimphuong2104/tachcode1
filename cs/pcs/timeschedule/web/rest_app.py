#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for `cs.pcs.substitute`, mounted at
``/internal/project_substitutes``
"""

from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

from cs.pcs.projects.common.webdata.util import get_oids_from_json
from cs.pcs.timeschedule.web.models.app_model import AppModel
from cs.pcs.timeschedule.web.models.baseline_model import (
    BaselineDataModel,
    BaselineModel,
)
from cs.pcs.timeschedule.web.models.data_model import DataModel
from cs.pcs.timeschedule.web.models.elements_model import ElementsModel
from cs.pcs.timeschedule.web.models.read_only_model import ReadOnlyModel
from cs.pcs.timeschedule.web.models.set_attribute_model import SetAttributeModel
from cs.pcs.timeschedule.web.models.set_dates_model import SetDatesModel
from cs.pcs.timeschedule.web.models.set_relships_model import SetRelshipsModel
from cs.pcs.timeschedule.web.models.update_model import UpdateModel

MOUNT = "/timeschedule"


class RestApp(JsonAPI):
    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(MOUNT)


@Internal.mount(app=RestApp, path=MOUNT)
def _mount_rest_app():
    return RestApp()


@RestApp.path(path="{context_object_id}/app", model=AppModel)
def get_app_data_model(request, context_object_id):
    return AppModel(context_object_id)


@RestApp.json(model=AppModel)
def get_app_data(model, request):
    return model.get_app_data(request)


@RestApp.json(model=AppModel, request_method="POST")
def update_app_data(model, request):
    return model.update_app_data(request)


@RestApp.path(path="{context_object_id}/data", model=DataModel)
def get_table_data_model(request, context_object_id):
    return DataModel(context_object_id)


@RestApp.json(model=DataModel, request_method="POST")
def get_data(model, request):
    return model.get_data(request)


@RestApp.json(model=DataModel, name="full", request_method="POST")
def get_full_data(model, request):
    object_ids = get_oids_from_json(request)
    return model.get_full_data(object_ids, None, None, [], request)


@RestApp.json(model=DataModel, name="related_names", request_method="POST")
def get_related_names(model, request):
    # time schedule-specific; will raise an AttributeError in other contexts
    return model.schedule_get_related_names(request)


@RestApp.path(path="{context_object_id}/update", model=UpdateModel)
def get_update_model(request, context_object_id):
    return UpdateModel(context_object_id)


@RestApp.json(model=UpdateModel, request_method="POST")
def get_changed_data(model, request):
    return model.get_changed_data(request)


@RestApp.path(
    path="{context_object_id}/set_dates/{content_object_id}", model=SetDatesModel
)
def get_set_dates_model(request, context_object_id, content_object_id):
    return SetDatesModel(context_object_id, content_object_id)


@RestApp.json(model=SetDatesModel, name="start", request_method="POST")
def set_start(model, request):
    return model.set_start(request)


@RestApp.json(model=SetDatesModel, name="end", request_method="POST")
def set_end(model, request):
    return model.set_end(request)


@RestApp.json(model=SetDatesModel, name="start_and_end", request_method="POST")
def set_start_and_end(model, request):
    return model.set_start_and_end(request)


@RestApp.path(
    "{context_object_id}/set_relships/{task_object_id}/{relship_name}",
    model=SetRelshipsModel,
)
def get_set_relships_model(request, context_object_id, task_object_id, relship_name):
    return SetRelshipsModel(context_object_id, task_object_id, relship_name)


@RestApp.json(model=SetRelshipsModel, request_method="POST")
def set_relships(model, request):
    return model.set_relships(request)


@RestApp.path(
    "{context_object_id}/set_attribute/{cdb_object_id}", model=SetAttributeModel
)
def get_set_attribute_model(request, context_object_id, cdb_object_id):
    return SetAttributeModel(context_object_id, cdb_object_id)


@RestApp.json(model=SetAttributeModel, request_method="POST")
def set_attribute(model, request):
    return model.set_attribute(request)


@RestApp.path("{context_object_id}/elements", model=ElementsModel)
def get_elements_model(request, context_object_id):
    return ElementsModel(context_object_id)


@RestApp.json(model=ElementsModel)
def get_elements(model, request):
    return model.get_manage_elements_data(request)


@RestApp.json(model=ElementsModel, request_method="POST")
def persist_elements(model, request):
    model.persist_elements(request)
    if hasattr(request, "json"):
        run_outside_ts_app = request.json.get("runOutsideTSApp")
        if not run_outside_ts_app:
            # return updates like a refresh would
            response_model = UpdateModel(model.context_object_id)
            return response_model.get_changed_data(request)


@RestApp.path("{context_object_id}/read_only", model=ReadOnlyModel)
def get_read_only_model(request, context_object_id):
    return ReadOnlyModel(context_object_id)


@RestApp.json(model=ReadOnlyModel, request_method="POST")
def get_read_only(model, request):
    return model.get_read_only(request)


@RestApp.path("baselines", model=BaselineModel)
def get_baseline_model(request):
    return BaselineModel()


@RestApp.json(model=BaselineModel, request_method="POST")
def get_baselines(model, request):
    return model.get_baselines(request)


@RestApp.path(path="{context_object_id}/baseline_data", model=BaselineDataModel)
def get_baseline_model(request, context_object_id):
    return BaselineDataModel(context_object_id)


@RestApp.json(model=BaselineDataModel, request_method="POST")
def get_baseline_data(model, request):
    return model.get_data_with_baseline(request)
