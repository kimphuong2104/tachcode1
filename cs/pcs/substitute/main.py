#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.pcs.substitute.main
======================

"Manage Substitutes" web application. This just registers libraries and role
contexts and provides functionality for the configured outlet to render the
application as a tab of the project details page.

.. autofunction :: addLinkPatterns

.. autoclass :: SubstitutesOutletCallback
    :members: adapt_initial_config

"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os
from copy import deepcopy
from datetime import date, timedelta

import webob
from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components import outlet_config
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects import Project
from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.substitute import rest_app_model, util

APP = "cs-pcs-substitute"
VERSION = "15.4.0"
MOUNT = "/project_substitutes"


def get_app_url_patterns(request):
    from cs.pcs.substitute.rest_app import App

    app = App.get_app(request)
    pid = "cdb_project_id"
    models = [
        ("team", rest_app_model.ProjectTeamModel, ["rest_key"]),
        ("substitutes", rest_app_model.UserSubstitutesModel, ["persno"]),
        ("substitution_info", rest_app_model.SubstitutionInfoModel, [pid]),
        ("roles", rest_app_model.RoleComparisonModel, ["substitute_oid", pid]),
        (
            "role_assignment",
            rest_app_model.SubjectModel,
            ["classname", "role_id", "persno"],
        ),
    ]
    return get_url_patterns(request, app, models)


def _getInitialState(project):
    """
    :param project: The project to derive initial application state from.
    :type project: `cs.pcs.projects.Project`

    :returns: The initial application state (org. context information and
        observation period defaults) to be included in ``app_setup``.
    :rtype: dict
    """
    today = date.today()
    next_month = today + timedelta(weeks=4)

    if project.end_time_fcast:
        to_date = max(
            util.datetimeToDate(project.end_time_fcast),
            next_month,
        )
    else:
        to_date = next_month

    return {
        "orgContextName": "ProjectContext",
        "orgContextID": project.cdb_project_id,
        "fromDate": util.datetimeToISOString(today),
        "toDate": util.datetimeToISOString(to_date),
    }


class SubstitutesOutletCallback(outlet_config.OutletPositionCallbackBase):
    """
    A callback setting properties for the Main component if the app was
    started via an outlet in a detail view of a project. The application is
    not guaranteed run otherwise.

    If the substitutes feature is not licensed in the system, this callback
    will not show the tab (e.g. return an empty list).
    """

    @classmethod
    def adapt_initial_config(cls, pos_config, cldef, obj):
        if not util.is_substitute_licensed():
            # do not show tab if substitutes are not licensed
            return []

        new_config = deepcopy(pos_config)
        new_config["properties"] = _getInitialState(obj)
        return [new_config]


#################################################################################
# Substitute App for Hybrid Client                                              #
#################################################################################


class HCModel(SinglePageModel):
    """
    SinglePageModel of the Substitute App,
    used for integrating the Application via eLink
    into the hybrid client
    """

    page_name = "cs-pcs-substitute-hybrid-client"

    def __init__(self, cdb_project_id):
        super().__init__()
        kwargs = {"cdb_project_id": cdb_project_id, "ce_baseline_id": ""}
        project = get_and_check_object(Project, "read", **kwargs)

        if not project:
            raise webob.exc.HTTPNotFound()
        self.cdb_project_id = cdb_project_id
        self.project = project


class HCApp(ConfigurableUIApp):
    def __init__(self):
        super().__init__()

    def update_app_setup(self, app_setup, model, request):
        """
        Extends app_setup with the initial state of the HCModel project,
        if the model has a project.

        :param app_setup: the global app setup
        :type app_setup: cs.web.components.base.main.SettingDict

        :param model: the single page model for Hybrid Client
        :param request: the morepath request (unused)
        """
        super().update_app_setup(app_setup, model, request)
        if hasattr(model, "project"):
            app_setup.merge_in(
                [APP],
                {
                    "initialState": _getInitialState(model.project),
                },
            )


@Root.mount(app=HCApp, path=MOUNT)
def _mount_app():
    return HCApp()


@HCApp.path(path="", model=HCModel, absorb=True)
def _get_model(absorb):
    # absorb contains cdb_project_id from URL
    return HCModel(absorb)


@HCApp.view(model=HCModel, name="base_path", internal=True)
def get_base_path(model, request):
    return request.path


#########################################################################################


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_role_contexts():
    util.register_role_context("cdb_global_role", "cdb_global_subject", None)
    util.register_role_context(
        "cdbpcs_prj_role", "cdbpcs_subject_per", "cdb_project_id"
    )
