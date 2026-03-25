#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
REST API to render the Dashboard navigation.
"""

from __future__ import absolute_import

__revision__ = "$Id$"

from cs.web.components.ui_support.navigation_modules import NavigationModules, NavigationAppViewModule
from . import Dashboard
from .internal import InternalDashboardApp


class DashboardNavigationModel(object):
    BOARDS_PATH = 'boards'

    @classmethod
    def boards_module(cls, request):
        return NavigationAppViewModule(
            "web.cs_web_dashboard.my_dashboards",
            "%s/%s" % (request.class_link(cls), cls.BOARDS_PATH)
        )

    @classmethod
    def nav_modules(cls, request):
        app_view = cls.boards_module(request)
        nav_modules = NavigationModules()
        nav_modules.addModule(0, app_view)
        return nav_modules.frontEndModuleList()

    @classmethod
    def boards_content(cls, request):
        app_view = cls.boards_module(request)
        for d in Dashboard.get_dashboard_collection():
            app_view.appendAppEntry(
                d.name,
                "/dashboard?dbid=%s" % d.cdb_object_id,
                "csweb_dashboard"
            ) if not d.is_template else None
        return app_view.moduleContent()


@InternalDashboardApp.path(model=DashboardNavigationModel, path='dashboard_navigation')
def _dashboard_navigation_path():
    return DashboardNavigationModel()


@InternalDashboardApp.json(model=DashboardNavigationModel)
def _get_dashboard_menu(model, request):
    return model.nav_modules(request)


@InternalDashboardApp.json(model=DashboardNavigationModel,
                           name=DashboardNavigationModel.BOARDS_PATH)
def _get_dashboard_boards(model, request):
    return model.boards_content(request)
