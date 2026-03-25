#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import logging
import os

from cdb import rte, sig
from cdb.util import get_label
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp, BaseModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


IMPORT_RESULT_APP_NAME = "cs-pcs-msp-imports-result"
IMPORT_APP_NAMESPACE = "cs-pcs-msp-web-imports"
IMPORT_APP_VERSION = "15.4.0"


class ImportResultApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        from cs.pcs.msp.web.imports import rest

        super().update_app_setup(app_setup, model, request)
        if not getattr(model, "extra_parameters"):
            logging.error("ImportResultApp: Cannot generate link patterns")
        else:
            rest_model = rest.ImportResultModel(model.extra_parameters)
            app_setup.merge_in(
                ["links", IMPORT_APP_NAMESPACE],
                {
                    "dataLink": request.link(
                        rest_model, app=rest.get_import_result(request)
                    )
                },
            )


class ImportResultModel(BaseModel):
    def __init__(self, extra_parameters):
        super().__init__()
        self.extra_parameters = extra_parameters


@ImportResultApp.path(path="/", model=ImportResultModel)
def get_model(extra_parameters):
    return ImportResultModel(extra_parameters)


@Root.mount(app=ImportResultApp, path=f"/{IMPORT_RESULT_APP_NAME}")
def _mount_app():
    return ImportResultApp()


@ImportResultApp.view(model=ImportResultModel, name="document_title", internal=True)
def default_document_title(self, request):
    return (
        get_label("cdbpcs_msp_import")
        + f'({self.extra_parameters.get("cdb_project_id")})'
    )


@ImportResultApp.view(model=ImportResultModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(IMPORT_APP_NAMESPACE, IMPORT_APP_VERSION)
    return "cs-pcs-msp-web-imports-MainComponent"


@ImportResultApp.view(model=ImportResultModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@ImportResultApp.view(model=ImportResultModel, name="application_title", internal=True)
def get_application_title(self, request):
    # " - Preview (%s)" % self.extra_parameters.get("cdb_project_id")
    return get_label("cdbpcs_msp_import")


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        IMPORT_APP_NAMESPACE,
        IMPORT_APP_VERSION,
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file(f"{IMPORT_APP_NAMESPACE}.js")
    lib.add_file(f"{IMPORT_APP_NAMESPACE}.js.map")
    static.Registry().add(lib)
