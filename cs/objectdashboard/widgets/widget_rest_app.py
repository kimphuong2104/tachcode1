# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for `cs.objectdashboard.widgets`, mounted at
``/internal/cs-objdashboard-widgets``.
"""

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK

from cs.objectdashboard.widgets import register_widget_url, widget_rest_models
from cs.pcs.projects.common.web import get_url_patterns

APP = "cs-objectdashboard-widgets"
VERSION = "15.1.0"
WIDGETS = [
    # Widget rest models can be added here like the following:
    # ("widget_name", widget_rest_models.Model),
]


def get_app_url_patterns(request):
    internal_app = widget_rest_models.InternalWidgetApp.get_app(request)
    pid = ["cdb_project_id"]
    models = [(label, model_class, pid) for label, model_class in WIDGETS]
    return get_url_patterns(request, internal_app, models)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def extend_app_setup(app_setup, request):
    """
    Make widget endpoint URLs
    ``/internal/cs-objdashboard-widgets/${widget_code}/${cdb_project_id}``
    available in app setup.
    """
    links = get_app_url_patterns(request)

    for label in links:
        register_widget_url(app_setup, label, links[label])
