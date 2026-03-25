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

import logging

from cdb import constants
from cdb import rte
from cs.documents import Document
from cs.workspaces import Workspace
from cs.wsm.cdbwsmcommands import processCommand
from cdb.objects import ClassRegistry
from cdb.objects.operations import operation, form_input

sdm_modules_installed = False
try:
    from cs.sdm.variant import Variant

    sdm_modules_installed = True
except ImportError:
    pass


class WorkspacesModel(object):
    @staticmethod
    def cdbClient_call_component(inputLines, wsVersion, request):
        """Forwards the base64 encoded input 'inputLines'
        to the WsmCommandProcessor.

        :param inputLines: The lines contain the command to be executed.
        :type inputLines: list(str)
        :param wsVersion: The version of the client that made this request.
        :type wsVersion: str|None
        :param request: The request from the web call.
        :type request: webob.Request
        :return: The error code and the base64 encoded response.
        :rtype: tuple(str, str)
        """
        logging.info("WorkspacesModel.cdbClient_call_component: start")
        rte.environ["WS_VERSION"] = wsVersion
        returnCode, resultLines = processCommand(inputLines, wsVersion, request)
        logging.info("WorkspacesModel.cdbClient_call_component: end")
        return returnCode, resultLines

    @staticmethod
    def _getTransferableCdbObjectDict(cdbObj):
        # This is required for properly recreating the dictionary
        # on the client side:
        # -exclude private attributes (the ones starting with '_')
        ret = {}
        for key in cdbObj.GetFieldNames():
            if not key.startswith("_"):
                val = getattr(cdbObj, key, None)
                ret[key] = "%s" % val
        return ret

    @classmethod
    def cdbObject_bind_n(cls, attrList):
        """Return all attributes for a list of document types and
        its primary keys.

        :param attrList: List of document types and primary keys.
        :type attrList: list(list(str, str))
        :return: A list of attributes for each object.
        :rtype: list(dict)
        """
        logging.info("WorkspacesModel.cdbObject_bind_n: start")
        cdbObjs = []
        clsReg = ClassRegistry()
        for attrs in attrList:
            # attrs: ["document", "000001@"]
            cdbClassname = attrs[0]
            primaryKeys = attrs[1]
            if cdbClassname is not None:
                documentClasses = {"document", "kCdbDoc", "model"}
                keys = primaryKeys.split("@")
                cdbObj = None
                if cdbClassname in documentClasses:
                    cdbObj = Document.ByKeys(*keys)
                elif cdbClassname == "cdb_wsp":
                    cdbObj = Workspace.ByKeys(*keys)
                elif cdbClassname == "cs_sdm_variant":
                    if sdm_modules_installed:
                        cdbObj = Variant.ByKeys(*keys)
                else:
                    foundCls = clsReg.findByClassname(cdbClassname)
                    if foundCls is not None:
                        cdbObj = foundCls.ByKeys(*keys)
                if cdbObj is not None:
                    if cdbObj.CheckAccess("read"):
                        cdbObjs.append(cdbObj)
        logging.info("WorkspacesModel.cdbObject_bind_n: stop")
        return cdbObjs

    @classmethod
    def run_op(cls, opName, obj, presetAttrs):
        """
        runs the copy operation
        """
        presetAttrs.update(
            {
                constants.kArgumentActiveIntegration: "wspmanager",
                constants.kArgumentActiveCAD: "wspmanager",
            }
        )

        obj = operation(opName, obj, form_input(obj.GetClassDef(), **presetAttrs))
        return obj
