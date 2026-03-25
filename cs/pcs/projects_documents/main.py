#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components import outlet_config
from cs.web.components.base.main import BaseApp, BaseModel

from cs.pcs.helpers import is_feature_licensed


class Projects_documentsApp(BaseApp):
    pass


@Root.mount(app=Projects_documentsApp, path="/cs-pcs-projects_documents")
def _mount_app():
    return Projects_documentsApp()


@Projects_documentsApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Projects_documents"


@Projects_documentsApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-pcs-projects_documents", "0.0.1")
    return "cs-pcs-projects_documents-MainComponent"


@Projects_documentsApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-pcs-projects_documents",
        "0.0.1",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-pcs-projects_documents.js")
    lib.add_file("cs-pcs-projects_documents.js.map")
    static.Registry().add(lib)


class ProjectDocumentsOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    If the project documents feature is not licensed in the system, this callback
    will not show the tab (e.g. return an empty list).
    """

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        if not is_feature_licensed(["DOCUMENTS_001", "TASK_DOCS_001"]):
            # do not show tab if project documents are not licensed
            return []
        return [pos_config]
