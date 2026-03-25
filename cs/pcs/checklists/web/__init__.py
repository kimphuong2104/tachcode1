#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import os

from cdb import rte, sig
from cs.platform.web import JsonAPI, static
from cs.platform.web.root import Internal, get_internal
from cs.web.components.storybook.main import add_stories
from webob.exc import HTTPBadRequest

from cs.pcs.checklists.web.models import (
    ChecklistItemsModel,
    ChecklistsProgressModel,
    RatingsModel,
    WorkObjectsModel,
)
from cs.pcs.checklists.web.related.models import (
    RelatedChecklistsContentModel,
    RelatedChecklistsRefreshModel,
    RelatedChecklistsStructureModel,
)
from cs.pcs.projects.common.cards import add_card
from cs.pcs.projects.common.web import get_url_patterns

APP = "cs-pcs-checklists-web"
STORIES = f"{APP}-stories"
VERSION = "15.1.0"
PATH = "checklists"
ONE_DAY_IN_SECONDS = 24 * 60 * 60  # 1 day


def ensure_payload(request):
    if not request.json:
        logging.error("Request Missing payload.")
        raise HTTPBadRequest


def get_app_url_patterns(request):
    """
    :param request: The request sent from the frontend.
    :type request: morepath.Request

    :returns: Link patterns (URLs with placeholders) indexed by names to be
        referenced by the frontend.
    :rtype: dict

    :raises morepath.error.LinkError: if any model class cannot be linked to.
    """
    checklist_keys = ["cdb_project_id", "checklist_id"]
    no_keys = []
    models = [
        ("checklist_items", ChecklistItemsModel, checklist_keys),
        ("progress", ChecklistsProgressModel, no_keys),
        ("ratings", RatingsModel, no_keys),
        ("work_objects", WorkObjectsModel, no_keys),
        ("related_structure", RelatedChecklistsStructureModel, ["cdb_object_id"]),
        ("related_content", RelatedChecklistsContentModel, no_keys),
        ("related_refresh", RelatedChecklistsRefreshModel, ["cdb_object_id"]),
    ]
    return get_url_patterns(request, ChecklistApp.get_app(request), models)


class ChecklistApp(JsonAPI):
    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(PATH)


@Internal.mount(app=ChecklistApp, path=PATH)
def _mount_app():
    return ChecklistApp()


@ChecklistApp.path(path="ratings", model=RatingsModel)
def get_ratings_model(request):
    return RatingsModel()


@ChecklistApp.json(model=RatingsModel)
def get_checklist_ratings(model, request):
    return model.get_rating_values()


@ChecklistApp.path(
    path="items/{cdb_project_id}/{checklist_id}", model=ChecklistItemsModel
)
def get_checklist_items_model(request, cdb_project_id, checklist_id):
    return ChecklistItemsModel(cdb_project_id, checklist_id)


@ChecklistApp.json(model=ChecklistItemsModel)
def get_checklist_items(model, request):
    return model.get_checklist_items(request)


@ChecklistApp.json(model=ChecklistItemsModel, request_method="POST")
def set_checklist_item_positions(model, request):
    ensure_payload(request)
    return model.set_checklist_item_positions(request)


@ChecklistApp.path(path="progress", model=ChecklistsProgressModel)
def get_checklists_progress_model(request):
    return ChecklistsProgressModel()


@ChecklistApp.json(model=ChecklistsProgressModel, request_method="POST")
def get_checklists_progress(model, request):
    ensure_payload(request)
    return model.get_checklists_progress(request)


@ChecklistApp.path(path="work_objects", model=WorkObjectsModel)
def check_work_objects_model(request):
    return WorkObjectsModel()


@ChecklistApp.json(model=WorkObjectsModel, name="status", request_method="POST")
def check_work_objects(model, request):
    ensure_payload(request)
    return model.check_work_objects(request)


@ChecklistApp.json(model=WorkObjectsModel, name="documents", request_method="POST")
def get_work_objects_documents(model, request):
    ensure_payload(request)
    return model.get_work_objects_documents(request)


@ChecklistApp.path(
    path="related_structure/{cdb_object_id}", model=RelatedChecklistsStructureModel
)
def get_structure_model(request, cdb_object_id):
    return RelatedChecklistsStructureModel(cdb_object_id)


@ChecklistApp.json(model=RelatedChecklistsStructureModel)
def resolve_structure(model, request):
    return model.resolve_structure(request)


@ChecklistApp.path(
    path="related_refresh/{cdb_object_id}", model=RelatedChecklistsRefreshModel
)
def get_structure_model(request, cdb_object_id):
    return RelatedChecklistsRefreshModel(cdb_object_id)


@ChecklistApp.json(model=RelatedChecklistsRefreshModel, request_method="POST")
def resolve_refresh_structure(model, request):
    ensure_payload(request)
    return model.resolve(
        request, expanded_checklists=request.json.get("expanded_checklists")
    )


@ChecklistApp.path(path="related_content", model=RelatedChecklistsContentModel)
def get_content_model(request):
    return RelatedChecklistsContentModel()


@ChecklistApp.json(model=RelatedChecklistsContentModel, request_method="POST")
def resolve_content(model, request):
    return model.resolve(request, rest_keys=request.json.get("rest_keys"))


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    for app in [APP, STORIES]:
        lib = static.Library(
            app, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
        )
        lib.add_file(f"{app}.js")
        lib.add_file(f"{app}.js.map")
        static.Registry().add(lib)

    add_stories((APP, VERSION), (STORIES, VERSION))


def setup_cards(model, request, app_setup):
    """
    Adds the serialized mask configuration for class "cdbpcs_cl_item" and
    ``DisplayConfiguration`` "table_card" to ``app_setup``.

    :param model: The application's main model (unused).
    :type model:

    :param request: The request sent from the frontend (unused).
    :type request: morepath.Request

    :param app_setup: The application setup object.
    :type app_setup: cs.web.components.base.main.SettingDict

    .. note ::

        Every page, outlet or application intending to use "cards" has to load
        the appropriate configuration somehow.
        Putting them into ``app_setup`` is the recommended pattern.

    """
    add_card(app_setup, "cdbpcs_cl_item", "table_card")
    add_card(app_setup, "cdb_pyrule", "table_card")
