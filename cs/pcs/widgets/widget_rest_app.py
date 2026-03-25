# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST backend for `cs.pcs.widgets`, mounted at
``/internal/cs-pcs--widgets``.
"""

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK

from cs.objectdashboard.widgets import register_widget_url
from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.widgets import widget_rest_models

APP = "cs-pcs-widgets"
VERSION = "15.1.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)


def get_app_url_patterns(request):
    internal_app = widget_rest_models.InternalWidgetApp.get_app(request)
    rest_key = "rest_key"
    oid = "cdb_object_id"
    models = [
        ("in_budget", widget_rest_models.InBudgetModel, [rest_key]),
        ("project_notes", widget_rest_models.ProjectNotesModel, [rest_key, oid]),
        ("rating", widget_rest_models.RatingModel, [rest_key]),
        ("remaining_time", widget_rest_models.RemainingTimeModel, [rest_key]),
        ("in_time", widget_rest_models.InTimeModel, [rest_key]),
        ("unassigned_roles", widget_rest_models.UnassignedRolesModel, [rest_key]),
        ("list_widget", widget_rest_models.ListModel, [rest_key, "list_config_name"]),
    ]
    return get_url_patterns(request, internal_app, models)


@sig.connect(GLOBAL_APPSETUP_HOOK)
def extend_app_setup(app_setup, request):
    """
    Make widget endpoints available at
    ``/internal/cs-pcs-widgets/${widget_code}/${rest_key}/${add.Param}``.
    """
    links = get_app_url_patterns(request)

    for label in links:
        register_widget_url(app_setup, label, links[label])
