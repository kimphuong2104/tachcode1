#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"


from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects.common.webdata.models.generic_async_data import (
    GenericAsyncDataModel,
)
from cs.pcs.projects.common.webdata.models.subject_thumbnails import (
    SubjectThumbnailModel,
)

APP = "cs-pcs-webdata"


def get_app_url_patterns(request):
    models = [
        ("object_data", GenericAsyncDataModel, []),
        ("subject_thumbnails", SubjectThumbnailModel, []),
    ]
    return get_url_patterns(request, WebData.get_app(request), models)


class WebData(JsonAPI):
    @staticmethod
    def get_app(request):
        "Try to look up /internal/cs-pcs-webdata"
        return get_internal(request).child(APP)


@Internal.mount(app=WebData, path=APP)
def _mount_app():
    return WebData()


@WebData.path(path="object_data", model=GenericAsyncDataModel)
def get_model(request):
    return GenericAsyncDataModel()


@WebData.json(model=GenericAsyncDataModel, request_method="POST")
def get_data_via_post(model, request):
    return model.get_data(request)


@WebData.path(path="subject_thumbnails", model=SubjectThumbnailModel)
def get_thumbnail_model(request):
    return SubjectThumbnailModel()


@WebData.json(model=SubjectThumbnailModel, request_method="POST")
def get_thumbnail_via_post(model, request):
    return model.get_data(request)
