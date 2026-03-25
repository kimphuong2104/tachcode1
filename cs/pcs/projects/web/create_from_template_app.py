#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module create_from_template_app

This is the documentation for the create_from_template_app module.
"""

from cdb import util
from cdb.objects import Forward
from cdb.platform.mom import entities, operations
from cs.platform.web.root import Root, get_v1
from cs.platform.web.root.main import _get_dummy_request
from cs.web.components.base.main import BaseApp, BaseModel
from cs.web.components.library_config import Libraries, get_dependencies
from cs.web.components.ui_support.forms import FormInfoBase

fProject = Forward("cs.pcs.projects.Project")

APP_PATH = "project_template"
MOUNT_FROM_TEMPLATE = "/create_project_from_template"
DEPENDS_ON = [
    ("cs-pcs-projects-web", True),
    # load UC optionally for search dialog tab
    ("cs-classification-web-component", False),
]
CLASSNAME = "cdbpcs_project"
TEMPLATE_CATALOG = "pcs_project_templates"
WIZARD_LABEL_1 = "project_template_create_app_step_1"
WIZARD_LABEL_2 = "project_template_create_app_step_2"


def add_libs_and_deps(request, leaf_libs):
    """
    extends ``request`` to include
    all libraries in ``leaf_libs`` and their dependencies
    in bottom-up order

    :param leaf_libs: Tuples of library name and mandatory flag.
    :type leaf_libs: list

    :raises RuntimeError: if an entry of ``leaf_libs`` is flagged mandatory and missing.
    """
    for lib_name, mandatory in leaf_libs:
        leaf_lib = Libraries.ByKeys(lib_name)
        if leaf_lib:
            for lib in get_dependencies(leaf_lib):
                request.app.include(lib.library_name, lib.library_version)
        elif mandatory:
            raise RuntimeError(f"library not available: '{lib_name}'")


class ProjectTemplateCreateApp(BaseApp):
    """
    Class for setting up the wizard, that executes
    the process of creating a project from template
    """

    def update_app_setup(self, app_setup, model, request):
        super().update_app_setup(app_setup, model, request)

        # NOTE: custom app has to load JS libraries and dependencies explicitly
        add_libs_and_deps(request, DEPENDS_ON)

        # setup catalog for frontend
        catalog_config = FormInfoBase.get_catalog_config(
            request, TEMPLATE_CATALOG, is_combobox=False, as_objs=True
        )
        app_setup["template_catalog_config"] = catalog_config

        # labels for the two steps of the wizard
        app_setup["wizard_labels"] = [
            util.get_label(WIZARD_LABEL_1),
            util.get_label(WIZARD_LABEL_2),
        ]

        # operation information,
        # used to retrieve labels and icons for wizard gui
        # here the operation cdbpcs_create_project (== New from template)
        # is used, even though internally CDB_Copy is triggered
        oi = operations.OperationInfo(CLASSNAME, "cdbpcs_create_project")
        # class definition
        cdef = entities.CDBClassDef(CLASSNAME)
        if oi:
            # setup title and icons for the wizard
            app_setup["header_icon"] = "/" + oi.get_icon_urls()[0]
            app_setup["header_title"] = f"{cdef.getDesignation()}: {oi.get_label()}"

        if "parent_project" in request.params:
            project_id = request.params["parent_project"]
            # note: both catalog and operation should not permit non-empty
            # baseline IDs, but at this point, we're keeping refs intact
            baseline_id = request.params["ce_baseline_id"]
            project = fProject.ByKeys(
                cdb_project_id=project_id, ce_baseline_id=baseline_id
            )

            if project:
                app_setup["parent_project"] = _getRestObject(project, request)

        if "relationship_name" in request.params:
            app_setup["relationship_name"] = request.params["relationship_name"]


@Root.mount(app=ProjectTemplateCreateApp, path=MOUNT_FROM_TEMPLATE)
def _mount_app():
    return ProjectTemplateCreateApp()


@ProjectTemplateCreateApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label(WIZARD_LABEL_1)


@ProjectTemplateCreateApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    return "cs-pcs-projects-web-ProjectTemplateCreateApp"


@ProjectTemplateCreateApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


def _getCollectionApp(request):
    """identify the collection app to calculate links with"""
    if request is None:
        request = _get_dummy_request()
    return get_v1(request).child("collection")


def _getRestObject(obj, request):
    """
    return the full REST API representation of obj
    """
    if not obj:
        return None

    if request is None:
        request = _get_dummy_request()

    collection_app = _getCollectionApp(request=request)

    return request.view(
        obj,
        app=collection_app,
        # use relship-target over default view, because
        # resolving relships is _expensive_
        # this also resolves long texts
        name="relship-target",
    )
