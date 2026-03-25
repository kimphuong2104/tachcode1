#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import ElementsError
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal
from webob.exc import HTTPBadRequest, HTTPInternalServerError, HTTPNotFound

from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects.common.webdata import util
from cs.pcs.projects.project_structure.views import ObjectNotFound
from cs.pcs.projects.web.rest_app.project_structure.helpers import (
    parse_persist_drop_payload,
    parse_revert_drop_payload,
)
from cs.pcs.projects.web.rest_app.project_structure.models import (
    StructureModel,
    StructureURLModel,
)

APP = "structure_tree"


def get_app_url_patterns(request):
    app = StructureApp.get_app(request)
    models = [
        (APP, StructureModel, ["view", "root_rest_key"]),
    ]
    return get_url_patterns(request, app, models)


class StructureApp(JsonAPI):
    @staticmethod
    def get_app(request):
        return get_internal(request).child(APP)


@Internal.mount(app=StructureApp, path=APP)
def _mount_app():
    return StructureApp()


@StructureApp.path(path="URL/{rest_key}", model=StructureURLModel)
def get_structure_URL_model(request, rest_key):
    return StructureURLModel(request, rest_key)


@StructureApp.json(model=StructureURLModel)
def get_generated_URL(model, request):
    return model.generate_URL(request)


@StructureApp.path(path="{view}/{root_rest_key}", model=StructureModel)
def get_structure_model(request, view, root_rest_key):
    return StructureModel(request, view, root_rest_key)


@StructureApp.json(model=StructureModel)
def resolve_structure(model, request):
    return model.resolve(request)


@StructureApp.json(model=StructureModel, name="full", request_method="POST")
def get_full_data(model, request):
    object_ids = util.get_oids_from_json(request)
    return model.get_full_data(object_ids, request)


@StructureApp.json(model=StructureModel, name="save_dropped", request_method="POST")
def save_dropped_node(model, request):
    # may raise HTTPBadRequest
    target, parent, children, predecessor, is_move = parse_persist_drop_payload(
        request.json
    )

    def log_parsing_error():
        parsed_payload = {
            "target": target,
            "parent": parent,
            "children": children,
            "predecessor": predecessor,
            "is_move": is_move,
        }
        logging.exception("parsed payload: %s", parsed_payload)

    try:
        return model.persist_drop(target, parent, children, predecessor, is_move)
    except ObjectNotFound as exc:
        log_parsing_error()
        raise HTTPNotFound from exc
    except ValueError as exc:
        log_parsing_error()
        raise HTTPBadRequest from exc
    except ElementsError as error:
        log_parsing_error()
        raise HTTPInternalServerError(str(error)) from error


@StructureApp.json(model=StructureModel, name="delete_copy", request_method="POST")
def delete_copied_node(model, request):
    # may raise HTTPBadRequest
    copy_id = parse_revert_drop_payload(request.json)

    def log_parsing_error():
        parsed_payload = {"copy_id": copy_id}
        logging.exception("parsed payload: %s", parsed_payload)

    try:
        model.delete_copy(copy_id)
    except ObjectNotFound as exc:
        log_parsing_error()
        raise HTTPNotFound from exc
    except ElementsError as error:
        log_parsing_error()
        raise HTTPInternalServerError(str(error)) from error
