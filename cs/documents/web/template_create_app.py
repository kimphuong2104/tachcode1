# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module template_create_app

This is the documentation for the template_create_app module.
"""

__docformat__ = "restructuredtext en"


import logging
import os

from cdb import constants, rte, sig, tools, util
from cdb.platform.mom import entities, operations
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.platform.web.uisupport.main import get_uisupport
from cs.web.components.base.main import BaseApp, BaseModel
from cs.web.components.plugin_config import Csweb_plugin
from cs.web.components.ui_support.forms import FormInfoBase

_Logger = logging.getLogger(__name__)


class DocTemplateCreateApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(DocTemplateCreateApp, self).update_app_setup(app_setup, model, request)
        catalog_config = FormInfoBase.get_catalog_config(
            request, "cdb_doc_template", is_combobox=False, as_objs=True
        )
        app_setup["template_catalog_config"] = catalog_config
        app_setup["wizard_labels"] = [
            util.get_label("template_create_app_step_1"),
            util.get_label("template_create_app_step_2"),
        ]
        app_setup["op_para_link"] = request.link(GetCreateOpPara({}))
        oi = operations.OperationInfo("document", "cdb_create_doc_from_template")
        cdef = entities.CDBClassDef("document")
        if oi:
            app_setup["header_icon"] = "/" + oi.get_icon_urls()[0]
            app_setup["header_title"] = "%s: %s" % (
                cdef.getDesignation(),
                oi.get_label(),
            )
        app_setup["appSettings"]["navigation_app_url"] = "/info/document"
        plg_config = {}
        plg_libs = []
        plg_setup = []
        cfg_entries = []
        for entry in Csweb_plugin.get_plugin_config("content-view"):
            cfg_entries.append(
                {
                    "discriminator": entry.get("discriminator"),
                    "component": entry.get("component"),
                }
            )
            for name, version in entry.get("libraries", []):
                plg_libs.append((name, version))
            fqpyname = entry.get("setup")
            if fqpyname is not None:
                try:
                    plg_setup.append(tools.getObjectByName(fqpyname))
                except ImportError as e:
                    _Logger.error(
                        "ConfigurableUIModel: Could not import setup"
                        " function '%s': %s",
                        fqpyname,
                        e,
                    )
        plg_config["content-view"] = cfg_entries
        app_setup.update(pluginConfiguration=plg_config)
        for fct in plg_setup:
            fct(model, request, app_setup)
        for name, version in plg_libs:
            request.app.include(name, version)


@Root.mount(app=DocTemplateCreateApp, path="/cs-documents/template_creation")
def _mount_app():
    return DocTemplateCreateApp()


@DocTemplateCreateApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("template_create_app_label")


@DocTemplateCreateApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-web-dashboard", "15.1.0")
    request.app.include("cs-documents-web", "15.3.0")
    return "cs-documents-web-DocTemplateCreateApp"


@DocTemplateCreateApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


class GetCreateOpPara(object):
    """
    Class that is used to generate the information the
    frontend needs to call the create operation after
    a template has been chosen.
    """

    def __init__(self, extra_parameters):
        self.extra_parameters = extra_parameters

    def get_op_para(self, request):
        opData = {}
        uuid = self.extra_parameters["template_uuid"]
        classname = util.ObjectDictionary().get_classname(uuid)
        rs_name = self.extra_parameters.get("rs_name")
        oi = operations.OperationInfo(classname, constants.kOperationNew)
        opInfo = None
        if oi and oi.offer_in_webui():
            if rs_name:
                try:
                    from cs.web.components.ui_support.operations import (
                        OperationInfoRelship,
                        _op_info_data,
                    )
                except ImportError:
                    opData["error"] = (
                        "A new cs.web version is required to create a document "
                        "from a template in a relationship context."
                    )
                    opData["error_caption"] = util.get_label("pccl_cap_err")
                    return opData
                oir = OperationInfoRelship(
                    self.extra_parameters["classname"],
                    self.extra_parameters["keys"],
                    rs_name,
                )
                opInfo = _op_info_data(
                    oi,
                    request,
                    oir.run_operation_model(oi),
                    oir.form_settings_model(oi),
                )
        else:
            oi = None  # To be able to use the error handling in the same way
        if oi:
            opData["args"] = {constants.kArgumentTemplateUUID: uuid}
            ui_app = get_uisupport(request)
            if opInfo:
                opData["opInfo"] = opInfo
            else:
                opData["opInfo"] = request.view(oi, app=ui_app)
        else:
            m = util.CDBMsg(util.CDBMsg.kFatal, "csweb_err_op_not_available")
            m.addReplacement(constants.kOperationNew)
            m.addReplacement(classname)
            opData["error"] = str(m)
            opData["error_caption"] = util.get_label("pccl_cap_err")
        return opData


@DocTemplateCreateApp.path(path="create_para", model=GetCreateOpPara)
def get_op_para(extra_parameters):
    return GetCreateOpPara(extra_parameters)


@DocTemplateCreateApp.json(model=GetCreateOpPara)
def get_op_para_json(self, request):
    return self.get_op_para(request)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-documents-web",
        "15.3.0",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-documents-web.js")
    lib.add_file("cs-documents-web.js.map")
    static.Registry().add(lib)
