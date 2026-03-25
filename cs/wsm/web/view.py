#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

import json
import six

from .main import WorkspacesApp
from .model import WorkspacesModel
from cs.platform.web.rest import get_collection_app
from cs.platform.web import uisupport
from cs.documents import Document
from cdb import ElementsError


@WorkspacesApp.json(
    name="cdbClient_call_component", request_method="POST", model=WorkspacesModel
)
def _cdbClient_call_component(model, request):
    """Forwards a request from WS client via the REST API
    to the WsmCommandProcessor.

    Example:

    >>> dict(request.json)
    {'inputLines': 'd29ya3NwYWNlcw==', 'wsVersion': '3.15'}

    :param model: The model which takes care of the further processing.
    :type model: WorkspacesModel
    :param request: Contains the input with the key 'inputLines'.
    :type request: webob.Request
    :return: A JSON response with the error code and the base64 encoded response.
    :rtype: dict
    """
    wsVersion = request.json.get("wsVersion", None)
    inputLines = request.json.get("inputLines", "[]")
    inputLines = json.loads(inputLines)
    returnCode, resultLines = model.cdbClient_call_component(
        inputLines, wsVersion, request
    )
    replyBase64Lines = []
    if returnCode is not None:
        replyBase64Lines.append(six.text_type(returnCode))
    replyBase64Lines.extend(resultLines)
    return {"replyBase64Lines": replyBase64Lines}


@WorkspacesApp.json(
    name="cdbObject_bind_n", request_method="POST", model=WorkspacesModel
)
def _cdbObject_bind_n(model, request):
    """Return all attributes for a list of document types and
    its primary keys.

    Example:

    >>> dict(request.json)
    {'attrs': '[["document", "000001@"]]'}

    :param model: The model which takes care of the further processing.
    :type model: WorkspacesModel
    :param request: Contains the input with the key 'attrs'.
    :type request: webob.Request
    :return: A JSON response as a list of attributes for the objects in 'objs'.
    :rtype: dict
    """
    attrs = request.json.get("attrs", None)
    objs = []
    if attrs is not None:
        attrList = json.loads(attrs)
        objs = model.cdbObject_bind_n(attrList)
    main_app = get_collection_app(request)
    r_objs = []
    for o in objs:
        r_v = request.view(o, app=main_app)
        r_o = dict()
        for k, v in r_v.items():
            if k == "@id":
                k = "_rest_id_"
            elif k.find("@") >= 0 or k.find(":") >= 0:
                k = None
            if k is not None:
                r_o[k] = v
        r_o["_system_ui_link_"] = uisupport.get_webui_link(request, o)
        r_objs.append(r_o)
    return {"objs": r_objs}


@WorkspacesApp.json(name="run_op_copy", request_method="POST", model=WorkspacesModel)
def _run_ws_op(model, request):
    json_data = request.json
    main_app = get_collection_app(request)
    presetAttrs = json_data.get("presetattrs")
    srcobj_dict = json_data.get("srcobj")
    reply_data = {"error": 102, "error_msg": "Source object not specified"}
    if srcobj_dict:
        srcobj = Document.ByKeys(**srcobj_dict)
        if srcobj is not None:
            new_object = None
            err_msg = ""
            try:
                new_object = model.run_op("CDB_Copy", srcobj, presetAttrs)
            except ElementsError as e:
                err_msg = str(e)
            r_o = dict()
            if new_object:
                reply_data["error"] = 0
                r_v = request.view(new_object, app=main_app)
                r_o = dict()
                for k, v in r_v.items():
                    if k == "@id":
                        k = "_rest_id_"
                    elif k.find("@") >= 0 or k.find(":") >= 0:
                        k = None
                    if k is not None:
                        r_o[k] = v
                r_o["_system_ui_link_"] = uisupport.get_webui_link(request, new_object)
                reply_data["obj"] = r_o
            else:
                reply_data["error"] = 103
                reply_data["error_msg"] = err_msg
        else:
            reply_data["error"] = 104
            reply_data["error_msg"] = "Source object does not exist"
    return reply_data
