#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging

from cdb import auth, util
from cs.platform.web import JsonAPI
from cs.platform.web.rest.support import rest_key, values_from_rest_key
from cs.platform.web.root import Internal, get_internal
from cs.web.components.ui_support import navigation_modules as nav
from webob.exc import HTTPBadRequest

from cs.objectdashboard.config import DefaultKPIsThreshold
from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects import Project
from cs.pcs.projects.common.lists.list import ListDataProvider
from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects.common.webdata.util import get_sql_condition
from cs.pcs.projects.web.navigation import get_nav_entries, get_restname

APP = "cs.pcs.projects"

PROJECTS_CLASS = "cdbpcs_project"


def get_app_url_patterns(request):
    app = ProjectsApp.get_app(request)
    no_keys = []
    models = [
        ("kpis", ProjectKPIsModel, no_keys),
        ("relshiplists", RelshipListsModel, no_keys),
    ]
    return get_url_patterns(request, app, models)


def _get_key_values(rest_keys):
    """
    :param rest_keys: REST keys in the form
        `["value1@value2", "value3"]`
    :type rest_keys: list

    :returns: Decoded and separated key values in the form
        `[["value1", "value2"], ["value3"]]`
    :rtype: list

    :raises HTTPBadRequest: if `rest_keys` is not iterable
        or any element is not a string.
    """
    try:
        return [values_from_rest_key(rest_key) for rest_key in rest_keys]
    except (TypeError, AttributeError) as exc:
        logging.exception("malformed rest keys: '%s'", rest_keys)
        raise HTTPBadRequest() from exc


def get_objects_from_rest_keys(rest_keys, objects_cls):
    """
    :param rest_keys: REST keys in the form
        `["value1@value2", "value3"]`
    :type rest_keys: list

    :param objects_cls: Objects Powerscript class
    :type objects_cls: class derived from cdb.objects.Object

    :returns: Readable objects of `objects_cls` matching `rest_keys`
    :rtype: cdb.objects.ObjectCollection

    :raises HTTPBadRequest: if `rest_keys` is not iterable
        or any element is not a string.
    """
    key_values = _get_key_values(rest_keys)
    condition = get_sql_condition(
        objects_cls.GetTableName(),
        [key.name for key in objects_cls.GetTablePKeys()],
        key_values,
    )
    result = objects_cls.Query(condition, access="read")
    return result


class ProjectsApp(JsonAPI):
    @staticmethod
    def get_app(request):
        "Try to look up /internal/cs.pcs.projects"
        return get_internal(request).child(APP)


@Internal.mount(app=ProjectsApp, path=APP)
def _mount_app():
    return ProjectsApp()


class ProjectKPIsModel:
    def get_kpis(self, request):
        # pylint: disable=too-many-locals
        try:
            rest_keys = request.json["projects"]
        except KeyError as exc:
            logging.exception("get_kpis, request: %s", request)
            raise HTTPBadRequest() from exc

        projects = get_objects_from_rest_keys(rest_keys, Project)
        CPI_Kwargs = {"kpi_name": "CPI"}
        SPI_Kwargs = {"kpi_name": "SPI"}
        cpi_threshold = get_and_check_object(DefaultKPIsThreshold, "read", **CPI_Kwargs)
        spi_threshold = get_and_check_object(DefaultKPIsThreshold, "read", **SPI_Kwargs)
        result = {}

        for project in projects:
            (ev, pv) = project.get_ev_pv_for_project()
            cst = project.get_cost_state(ev)
            sst = project.get_schedule_state(ev, pv)
            timeSchedules = {}
            validAndNewTimeSchedules = project.PrimaryTimeSchedule.KeywordQuery(
                status=[0, 100]
            )
            project_rest_key = rest_key(project)
            for ts in validAndNewTimeSchedules:
                timeScheduleURL = ts.getProjectPlanURL()
                timeScheduleName = ts.name
                timeScheduleStatus = ts.cdb_status_txt
                timeSchedules.update({timeScheduleURL: {}})
                timeSchedules[timeScheduleURL].update(
                    {"name": timeScheduleName, "status": timeScheduleStatus}
                )

            result[project_rest_key] = {
                "cpi": cst[3],
                "cpi_variance": cst[2],
                "spi": sst[3],
                "spi_variance": sst[2],
                "timeschedules": timeSchedules,
            }
            if cpi_threshold:
                result[project_rest_key]["cpi_threshold"] = [
                    cpi_threshold.success_threshold,
                    cpi_threshold.danger_threshold,
                ]
            if spi_threshold:
                result[project_rest_key]["spi_threshold"] = [
                    spi_threshold.success_threshold,
                    spi_threshold.danger_threshold,
                ]
        return result


@ProjectsApp.path(path="kpis", model=ProjectKPIsModel)
def get_project_kpis():
    return ProjectKPIsModel()


@ProjectsApp.json(model=ProjectKPIsModel, request_method="POST")
def get_kpis_for_projects(model, request):
    return model.get_kpis(request)


class Navigation:
    def get_navigation(self, request):
        root = nav.NavigationModules()
        project_rest_name = get_restname(PROJECTS_CLASS)
        main_module = nav.NavigationHomepageModule(project_rest_name)
        root.addModule(10, main_module)

        # add favourites module
        fav_module = nav.NavigationFavoritesModule(project_rest_name)
        root.addModule(20, fav_module)

        more_apps_module = nav.NavigationSubMenuModule(
            "web.pcs.more_applications", f"/internal/{APP}/navigation/submenu"
        )
        root.addModule(30, more_apps_module)
        return root.frontEndModuleList()

    def get_submenu(self, request):
        more_apps_module = nav.NavigationSubMenuModule("web.pcs.more_applications", "")

        entries = get_nav_entries()
        try:
            for label, icon, link in entries:
                more_apps_module.appendAppEntry(label, label, icon, link)
        except ValueError:
            # pylint: disable=no-value-for-parameter
            logging.log("Navigation entries do not contain the desired information.")

        return more_apps_module.moduleContent()


@ProjectsApp.path(path="navigation", model=Navigation)
def get_navigation_model():
    return Navigation()


@ProjectsApp.json(model=Navigation)
def _(model, request):
    return model.get_navigation(request)


@ProjectsApp.json(model=Navigation, name="submenu")
def _(model, request):
    return model.get_submenu(request)


class RelshipListsModel:
    def get_relship_list(self, request):
        try:
            relship = request.json["relshipName"]
            restKey = request.json["restKey"]
            classname = request.json["classname"]

            if not relship:
                raise ValueError
            if not restKey:
                raise ValueError
            if not classname:
                raise ValueError
        except (KeyError, ValueError) as exc:
            logging.exception("get_relship_list, request: %s", request)
            raise HTTPBadRequest() from exc

        data_providers = [
            ldp
            for ldp in ListDataProvider.KeywordQuery(
                rolename=relship, referer=classname
            )
            if ldp.CheckAccess("read")
        ]
        if not data_providers:
            logging.exception(
                """
                RelshipListsModel: '%s' has no read access on ListDataProvider
                with rolename '%s' and referer '%s' or ListDataProvider does
                not exist.
                """,
                auth.persno,
                relship,
                classname,
            )
            # return empty result
            return {
                "title": util.get_label("web.cs-pcs-projects.relship_list_error_title"),
                "items": [],
                "displayConfigs": {},
                "configError": util.get_label(
                    "cs.pcs.projects.common.lists.provider_access_error"
                ).format(relship, classname),
            }
        else:
            data_provider = data_providers[0]
            return data_provider.generateListJSON(request, restKey)


@ProjectsApp.path(path="relshiplists", model=RelshipListsModel)
def get_relship_lists_model():
    return RelshipListsModel()


@ProjectsApp.json(model=RelshipListsModel, request_method="POST")
def _(model, request):
    return model.get_relship_list(request)
