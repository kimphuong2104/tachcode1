# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module create_from_template_app

This is the documentation for the create_from_template_app module.
"""

import logging

from cdb import util, constants, auth
from cdb.objects import ByID, Forward, ClassRegistry
from cdb.platform.mom import operations
from cs.platform.web.rest.support import rest_object
from cs.platform.web.root.main import _get_dummy_request, get_v1
from cs.platform.web.uisupport import get_uisupport
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel
from cs.web.components.ui_support.forms import FormInfoBase

from cs.workflow.web.main import APP
from cs.workflow.web.main import VERSION
from cs.workflow.web.main import WebApp

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

MOUNT_FROM_TEMPLATE = "create_from_template"
CLASSNAME = "cdbwf_process"
TEMPLATE_CATALOG = "cdbwf_process_templ"
SELECT_TEMPLATE_LABEL = "select_workflow_template"
DATA_SHEET_LABEL = "data_sheet"

fProcess = Forward("cs.workflow.processes.Process")


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


class WFTemplateCreateApp(BaseApp):
    def update_app_setup(self, app_setup, model, request):
        super(WFTemplateCreateApp, self).update_app_setup(
            app_setup,
            model,
            request
        )
        catalog_config = FormInfoBase.get_catalog_config(
            request,
            TEMPLATE_CATALOG,
            is_combobox=False,
            as_objs=True
        )
        app_setup["template_catalog_config"] = catalog_config
        app_setup["create_link"] = request.link(WFTemplateCreateModel())
        app_setup["wizard_labels"] = [
            util.get_label(SELECT_TEMPLATE_LABEL),
            util.get_label(DATA_SHEET_LABEL)
        ]


class WFTemplateCreateModel(object):
    def createFromTemplate(self, request):
        opData = {}

        template_id = request.json.get("template_id", None)
        ahwf_content = request.json.get("ahwf_content", None)
        classname = request.json.get("classname", None)
        rest_key = request.json.get("rest_key", None)
        cls = ClassRegistry().findByClassname(classname)
        rest_obj = rest_object(cls, rest_key)
        prj_id = None
        if hasattr(rest_obj, 'cdb_project_id'):
            prj_id = rest_obj.cdb_project_id

        try:
            objects = [ByID(uuid) for uuid in ahwf_content]
            objects = [o for o in objects if o.CheckAccess("read")]

        except (ValueError, AttributeError, ImportError):
            logging.exception("unknown object_id '%s'", ahwf_content)
            raise  # frontend will see http 500 (internal server error)

        objects_classes = set([o.__class__ for o in objects])
        if len(objects_classes) > 1:
            logging.error("objects classes are %s (ids: %s)", objects_classes, ahwf_content)
            raise TypeError("objects have to be of uniform type")

        planned_operation = constants.kOperationCopy
        oi = operations.OperationInfo(CLASSNAME, planned_operation)
        if not (oi and oi.offer_in_webui()):
            oi = None  # To be able to use the error handling in the same way
        if oi:
            # Prefill parameters for CDB_COPY mask like
            # in on_copy_pre_mask in the win-client
            opData["parameters"] = {
                "is_template": 0,
                "cdb_project_id": prj_id,
                "subject_id": auth.persno,
                "cdb::argument.ahwf_content": ','.join(ahwf_content),
                "cdb::argument.context_object_id": rest_obj.cdb_object_id if rest_obj else "",
                "cdb::argument.uses_create_from_template": True
            }
            # get template checklist object by id ...
            template = fProcess.ByKeys(template_id)
            # ... and turn it into a rest obj
            template_rest = _getRestObject(template, request)
            # this is used as parameter for the copy operation
            # called by the wizard
            opData["template"] = template_rest
            # get info about copy operation
            ui_app = get_uisupport(request)
            # this operation obj is later called via
            # runOperation by the wizard
            # -> triggers CDB Copy with template info as prefilled info
            opData["opInfo"] = request.view(oi, app=ui_app)
            # used to determine if the error notification should be shown in the frontend
            from cs.workflow.process_template import content_in_whitelist
            opData["content_in_whitelist"] = content_in_whitelist(ahwf_content[0], False) if ahwf_content else True
        else:
            # error handling
            m = util.CDBMsg(util.CDBMsg.kFatal, "csweb_err_op_not_available")
            m.addReplacement(planned_operation)
            m.addReplacement(CLASSNAME)
            opData["error"] = unicode(m)
            opData["error_caption"] = util.get_label("pccl_cap_err")
        # return all data needed for the copy operation to the wizard as json
        return opData


@WebApp.mount(app=WFTemplateCreateApp, path=MOUNT_FROM_TEMPLATE)
def _mount_app():
    return WFTemplateCreateApp()


@WFTemplateCreateApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label(SELECT_TEMPLATE_LABEL)


@WFTemplateCreateApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(APP, VERSION)
    return "{}-WFTemplateCreateApp".format(APP)


@WFTemplateCreateApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@WFTemplateCreateApp.path(path="create", model=WFTemplateCreateModel)
def _get_model():
    return WFTemplateCreateModel()


@WFTemplateCreateApp.json(model=WFTemplateCreateModel, request_method="POST")
def create_from_template(model, request):
    return model.createFromTemplate(request)
