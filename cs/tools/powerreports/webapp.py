# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import CADDOK, rte, sig
from cdb.objects import ByID
from cdb.platform.mom import entities
from cs.platform.web import static
from cs.platform.web.rest import get_collection_app
from cs.platform.web.root import Root, get_v1
from cs.tools.powerreports import XMLReport, get_fqpynames, get_report_by_name
from cs.tools.powerreports.utils import _get_error_msg
from cs.web.components.base.main import BaseApp, BaseModel


def build_args(model):
    params = {}
    if hasattr(model, "extra_parameters") and model.extra_parameters:
        params = model.extra_parameters

    skip_dialog = False
    if (
        "cdb::argument.cdbxml_report_skip_dlg" in params
        and params["cdb::argument.cdbxml_report_skip_dlg"] == "1"
    ):
        skip_dialog = True

    # if dialog are not skipped, args are pre-filled by pre-mask
    # thus, return empty dict
    if not skip_dialog:
        return {}

    context_fqpynames = []
    if hasattr(model, "obj") and model.obj:
        context_fqpynames = get_fqpynames(model.obj.__class__)

    # supReport is mandatory, so we do not have to check if key exists
    report_name = params["cdb::argument.cdbxml_report_subreport"]

    # use isolang if not specified by user
    sub_lang = (
        params["cdb::argument.cdbxml_report_lang"]
        if "cdb::argument.cdbxml_report_lang" in params
        else CADDOK.get("ISOLANG", "de")
    )

    report_info = get_report_by_name(
        context_fqpynames, "", report_name=report_name, iso_code=sub_lang
    )

    if not report_info:
        raise Exception(  # pylint: disable=W0719
            _get_error_msg("powerreports_tmpl_name_not_found", report_name)
        )

    # use report action and format if not specified by user
    set_action = (
        params["cdbxml_report_action"]
        if "cdbxml_report_action" in params
        else report_info["cdbxml_report_action"]
    )
    set_format = (
        params["cdbxml_report_format"]
        if "cdbxml_report_format" in params
        else report_info["cdbxml_report_format"]
    )

    tmpl_cdb_object_id = report_info["tmpl_cdb_object_id"]
    cdb_file_cdb_object_id = report_info["file_cdb_object_id"]

    args = {
        # dialog name to skip to
        "dialog": report_info["dialog"],
        # preset action and format
        "cdbxml_report_action": set_action,
        "cdbxml_report_format": set_format,
        # required by on_cdbxml_excel_report_now
        "cdb::argument.cdbxml_report_tmpl_cdb_object_id": tmpl_cdb_object_id,
        "cdb::argument.cdbxml_report_cdb_file_cdb_object_id": cdb_file_cdb_object_id,
        # required for the standard save filter button to work
        "cdbxml_report_id": report_info["cdbxml_report_id"],
    }

    # Set defaults for report specific dialog
    report = XMLReport.ByKeys(cdb_object_id=report_info["cdbxml_report_id"])
    if report:
        for k, v in report.getParameters().items():
            if k not in params:
                args[k] = v
    return args


class PowerreportsApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(PowerreportsApp, self).update_app_setup(app_setup, model, request)
        classdef = entities.CDBClassDef("cdbxml_source")
        app_config = {
            "metaClassLink": request.link(classdef, app=get_v1(request).child("class")),
            "args": build_args(model),
        }
        if hasattr(model, "obj") and model.obj is not None:
            app_config["contextObject"] = request.view(
                model.obj, app=get_collection_app(request)
            )

        app_setup.update(app_config)


class PowerreportsAppContextFree(PowerreportsApp):
    pass


@Root.mount(app=PowerreportsApp, path="/cs-tools-powerreports")
def _mount_app():
    return PowerreportsApp()


@Root.mount(app=PowerreportsAppContextFree, path="/cs-tools-powerreports-context-free")
def _mount_app():
    return PowerreportsAppContextFree()


@PowerreportsApp.path(path="{oid}")
class PowerReportsModel(BaseModel):
    def __init__(self, oid, extra_parameters):
        super(PowerReportsModel, self).__init__()
        self.obj = ByID(oid)
        self.extra_parameters = extra_parameters


@PowerreportsAppContextFree.path(path="")
class PowerReportsContextFreeModel(BaseModel):
    def __init__(self, extra_parameters):
        super(PowerReportsContextFreeModel, self).__init__()
        self.obj = None
        self.extra_parameters = extra_parameters


@PowerreportsApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Powerreports"


@PowerreportsApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-tools-powerreports", "15.3.0")
    return "cs-tools-powerreports-MainComponent"


@PowerreportsApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@PowerreportsApp.view(model=BaseModel, name="application_title", internal=True)
def get_application_title(self, request):
    return "Powerreports"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-tools-powerreports",
        "15.3.0",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-tools-powerreports.js")
    lib.add_file("cs-tools-powerreports.js.map")
    static.Registry().add(lib)
