# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import logging
import os

from cdb import constants
from cdb import rte
from cdb import sig
from cdb import tools
from cdb import util
from cdb.platform.mom import entities
from cdb.platform.mom import operations
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.platform.web.uisupport.main import get_uisupport
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.web.components.plugin_config import Csweb_plugin
from cs.web.components.ui_support.forms import FormInfoBase

_Logger = logging.getLogger(__name__)


class WorkplanTemplateCreateApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(WorkplanTemplateCreateApp, self).update_app_setup(
            app_setup, model, request
        )
        catalog_config = FormInfoBase.get_catalog_config(
            request, "cswp_workplan_template", is_combobox=False, as_objs=True
        )
        app_setup["template_catalog_config"] = catalog_config
        app_setup["wizard_labels"] = [
            util.get_label("template_create_app_step_1"),
            util.get_label("template_create_app_step_2"),
        ]
        app_setup["op_para_link"] = request.link(GetCopyOpPara({}))
        oi = operations.OperationInfo("cswp_workplan", "cswp_create_new_from_template")
        cdef = entities.CDBClassDef("cswp_workplan")
        if oi:
            app_setup["header_icon"] = "/" + oi.get_icon_urls()[0]
            app_setup["header_title"] = "%s: %s" % (
                cdef.getDesignation(),
                oi.get_label(),
            )
        app_setup["appSettings"]["navigation_app_url"] = "/info/cswp_workplan"
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


@Root.mount(app=WorkplanTemplateCreateApp, path="/cs-workplan-web-template_create_app")
def _mount_app():
    return WorkplanTemplateCreateApp()


@WorkplanTemplateCreateApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("template_create_app_label")


@WorkplanTemplateCreateApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-workplan-web-template_create_app", "0.0.1")
    return "cs-workplan-web-template_create_app-WorkplanTemplateCreateApp"


@WorkplanTemplateCreateApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


class GetCopyOpPara(object):
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
        oi = operations.OperationInfo(classname, constants.kOperationCopy)
        if oi and oi.offer_in_webui():
            if rs_name:
                try:
                    from cs.web.components.ui_support.operations import (
                        RSReferenceOperationInfo,
                    )
                except ImportError:
                    opData["error"] = (
                        "A new cs.web version is required to create from "
                        "a template in a relationship context."
                    )
                    opData["error_caption"] = util.get_label("pccl_cap_err")
                    return opData

                oi = RSReferenceOperationInfo(
                    self.extra_parameters["classname"],
                    self.extra_parameters["keys"],
                    rs_name,
                    constants.kOperationCopy,
                )
        else:
            oi = None  # To be able to use the error handling in the same way
        if oi:
            opData["args"] = {
                constants.kArgumentTemplateUUID: uuid,
                'is_template': 0
            }
            ui_app = get_uisupport(request)
            opData["opInfo"] = request.view(oi, app=ui_app)
        else:
            m = util.CDBMsg(util.CDBMsg.kFatal, "csweb_err_op_not_available")
            m.addReplacement(constants.kOperationCopy)
            m.addReplacement(classname)
            opData["error"] = str(m)
            opData["error_caption"] = util.get_label("pccl_cap_err")
        return opData


@WorkplanTemplateCreateApp.path(path="copy_para", model=GetCopyOpPara)
def get_op_para(extra_parameters):
    return GetCopyOpPara(extra_parameters)


@WorkplanTemplateCreateApp.json(model=GetCopyOpPara)
def get_op_para_json(self, request):
    return self.get_op_para(request)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-workplan-web-template_create_app",
        "0.0.1",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-workplan-web-template_create_app.js")
    lib.add_file("cs-workplan-web-template_create_app.js.map")
    static.Registry().add(lib)
