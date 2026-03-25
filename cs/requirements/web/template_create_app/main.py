# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$
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
from cs.requirements import RQMSpecObject, RQMSpecification

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


Logger = logging.getLogger(__name__)


class TemplateCreateApp(BaseApp):

    MOUNT_PATH = "/cs-requirements-web-TemplateCreateApp"
    JS_NAMESPACE = "cs-requirements-web-template_create_app"

    def update_app_setup(self, app_setup, model, request):
        super(TemplateCreateApp, self).update_app_setup(
            app_setup, model, request)
        app_dict = {}
        if not hasattr(model, 'catalogs'):
            return
        catalog_configs = [FormInfoBase.get_catalog_config(
            request,
            catalog,
            is_combobox=False,
            as_objs=True
        ) for catalog in model.catalogs]
        app_dict["template_catalog_configs"] = catalog_configs
        app_dict["wizard_labels"] = [
            util.get_label("template_create_app_step_1") for _ in model.catalogs
        ]
        app_dict["wizard_labels"].append(util.get_label("template_create_app_step_2"))
        app_dict["op_para_link"] = request.link(GetCopyOpPara({}))
        oi = operations.OperationInfo(model.classname,
                                      model.operation)
        cdef = entities.CDBClassDef(model.classname)
        if oi:
            app_dict["header_icon"] = "/" + oi.get_icon_urls()[0]
            app_dict["header_title"] = "%s: %s" % (cdef.getDesignation(),
                                                   oi.get_label())
        app_setup[self.JS_NAMESPACE] = app_dict
        app_setup["appSettings"]["navigation_app_url"] = model.navigation_app_url
        plg_config = {}
        plg_libs = []
        plg_setup = []
        cfg_entries = []
        for entry in Csweb_plugin.get_plugin_config('content-view'):
            cfg_entries.append({'discriminator': entry.get('discriminator'),
                                'component': entry.get('component')})
            for name, version in entry.get("libraries", []):
                plg_libs.append((name, version))
            fqpyname = entry.get("setup")
            if fqpyname is not None:
                try:
                    plg_setup.append(tools.getObjectByName(fqpyname))
                except ImportError as e:
                    Logger.error(
                        "ConfigurableUIModel: Could not import setup"
                        " function '%s': %s",
                        fqpyname, e)
        plg_config['content-view'] = cfg_entries
        app_setup.update(pluginConfiguration=plg_config)
        for fct in plg_setup:
            fct(model, request, app_setup)
        for name, version in plg_libs:
            request.app.include(name, version)


class SpecObjectBaseModel(BaseModel):
    catalogs = [
        "cdbrqm_specification_template",
        "cdbrqm_spec_obj_template"
    ]
    operation = "cdbrqm_create_from_template"
    classname = RQMSpecObject.__classname__
    navigation_app_url = '/info/spec_object'


class SpecificationBaseModel(BaseModel):
    catalogs = ["cdbrqm_specification_template"]
    operation = "cdbrqm_create_from_template"
    classname = RQMSpecification.__classname__
    navigation_app_url = '/info/specification'


@Root.mount(app=TemplateCreateApp, path=TemplateCreateApp.MOUNT_PATH)
def _mount_app():
    return TemplateCreateApp()


@TemplateCreateApp.path(path="/spec_object", model=SpecObjectBaseModel)
def get_spec_object_model():
    return SpecObjectBaseModel()


@TemplateCreateApp.path(path="/specification", model=SpecificationBaseModel)
def get_specification_model():
    return SpecificationBaseModel()


@TemplateCreateApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("template_create_app_label")


@TemplateCreateApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-requirements-web-template_create_app", "0.0.1")
    request.app.include("cs-requirements-web-richtext", "0.0.1")
    request.app.include("cs-requirements-web-weblib", "0.0.1")
    request.app.include("cs-classification-web-component", "15.1.0")
    return "cs-requirements-web-template_create_app-TemplateCreate"


@TemplateCreateApp.view(model=BaseModel, name="base_path", internal=True)
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
                from cs.web.components.ui_support.operations import RSReferenceOperationInfo
                oi = RSReferenceOperationInfo(self.extra_parameters["classname"],
                                              self.extra_parameters["keys"],
                                              rs_name,
                                              constants.kOperationCopy)
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
            m.addReplacement(constants.kOperationNew)
            m.addReplacement(classname)
            opData["error"] = str(m)
            opData["error_caption"] = util.get_label("pccl_cap_err")
        return opData


@TemplateCreateApp.path(path="op_para",
                             model=GetCopyOpPara)
def get_op_para(extra_parameters):
    return GetCopyOpPara(extra_parameters)


@TemplateCreateApp.json(model=GetCopyOpPara)
def get_op_para_json(self, request):
    return self.get_op_para(request)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-requirements-web-template_create_app", "0.0.1",
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-requirements-web-template_create_app.js")
    lib.add_file("cs-requirements-web-template_create_app.js.map")
    static.Registry().add(lib)
