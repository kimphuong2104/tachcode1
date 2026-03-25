#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Morepath app for the dashboard page
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import os
import six

from cdb import rte
from cdb import sig
from cdb import auth
from cdb.util import get_roles

from cs.platform.web import static
from cs.platform.web.root.main import Root

from cs.web.components.configurable_ui import (ConfigurableUIApp,
                                               ConfigurableUIModel,
                                               SinglePageModel)

from . import DashboardWidget, DASHBOARD_LAYOUTS
from .internal import InternalDashboardApp, Dashboard, DashboardCollection
from cs.web.components.library_config import get_dependencies


class DashboardApp(ConfigurableUIApp):
    def __init__(self):
        super(DashboardApp, self).__init__()


@Root.mount(app=DashboardApp, path="dashboard")
def _mount_app():
    return DashboardApp()


class DashboardModel(SinglePageModel):
    page_name = "cs-web-dashboard"


@DashboardApp.path(path="", model=DashboardModel)
def _get_model():
    return DashboardModel()


@DashboardApp.view(model=DashboardModel, name="document_title", internal=True)
def _document_title(_model, _request):
    return "Dashboard"


@sig.connect(DashboardModel, ConfigurableUIModel, "application_setup")
def _app_setup(model, request, app_setup):
    # Setup for the widget catalog
    widgets = DashboardWidget.Query().Execute()
    for w in widgets:
        for lib in w.Libraries:
            for _lib in get_dependencies(lib):
                model.add_library(_lib.library_name, _lib.library_version)
        # The attributes library_name and library_version are deprecated and
        # will be removed in a future version
        if w.library_name:
            model.add_library(w.library_name, w.library_version)
    widget_catalog = [w.app_setup() for w in widgets]
    # Setup to access the user's dashboard
    internal_app = InternalDashboardApp.get_app(request)
    request.app.include("d3", "3.5.17")
    my_roles = get_roles('GlobalContext', '', auth.persno)
    app_setup.merge_in(["cs-web-dashboard"],
                       {"widgets": widget_catalog,
                        "layouts": DASHBOARD_LAYOUTS,
                        "dashboards": request.view(DashboardCollection(), app=internal_app),
                        "manageDashboards": "Administration: Dashboards" in my_roles
                        })
    dashboard_collection_link = request.class_link(
        DashboardCollection,
        app=InternalDashboardApp.get_app(request)
    )
    dashboard_collection_manage_view_link = request.class_link(
        DashboardCollection,
        name='manage_view',
        app=InternalDashboardApp.get_app(request)
    )
    dashboard_collection_create_link = request.class_link(
        DashboardCollection,
        name='create',
        app=InternalDashboardApp.get_app(request)
    )
    dashboard_collection_copy_link = request.class_link(
        DashboardCollection,
        name='copy',
        app=InternalDashboardApp.get_app(request)
    )
    dashboard_collection_update_link = request.class_link(
        DashboardCollection,
        name='update',
        app=InternalDashboardApp.get_app(request)
    )
    app_setup.merge_in(["links", "cs-web-dashboard"], {
        "dashboardCollectionTemplate": six.moves.urllib.parse.unquote(dashboard_collection_link),
        "dashboardCollectionManageViewTemplate": six.moves.urllib.parse.unquote(
            dashboard_collection_manage_view_link),
        "dashboardCollectionCreateTemplate": six.moves.urllib.parse.unquote(
            dashboard_collection_create_link),
        "dashboardCollectionCopyTemplate": six.moves.urllib.parse.unquote(
            dashboard_collection_copy_link),
        "dashboardCollectionUpdateTemplate": six.moves.urllib.parse.unquote(
            dashboard_collection_update_link),
    })


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-web-dashboard", "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file("cs-web-dashboard.js")
    lib.add_file("cs-web-dashboard.js.map")
    static.Registry().add(lib)
