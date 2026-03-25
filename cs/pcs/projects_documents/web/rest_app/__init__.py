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

from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects_documents.web.rest_app.models.doc_templates_model import (
    DocTemplatesModel,
)

APP = "cs-pcs-doctemplates"


def get_app_url_patterns(request):
    internal_app = InternalDocTemplatesApp.get_app(request)
    models = [
        ("doc_templates", DocTemplatesModel, ["object_id"]),
    ]
    return get_url_patterns(request, internal_app, models)


class InternalDocTemplatesApp(JsonAPI):
    @staticmethod
    def get_app(request):
        "Try to look up /internal/doctemplates"
        return get_internal(request).child(APP)


@Internal.mount(app=InternalDocTemplatesApp, path=APP)
def _mount_app():
    return InternalDocTemplatesApp()


@InternalDocTemplatesApp.path(path="doctemplates/{object_id}", model=DocTemplatesModel)
def get_doc_templates_model(request, object_id):
    return DocTemplatesModel(object_id)


@InternalDocTemplatesApp.json(model=DocTemplatesModel, request_method="GET")
def _get_doc_templates(model, request):
    """
    Request URL:    {SERVER_URL}/{APP_URL}/doctemplates
    Method:         GET

    With a GET request it is possible to get all doc templates which
    are relevant for specific project.

    If the request contains a correct JSON payload, then the backend
    will return all doc templates that belongs to that project.

    """
    return model.get_doc_templates_data(request)
