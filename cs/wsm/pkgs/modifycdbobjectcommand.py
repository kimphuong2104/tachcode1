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
import six

from cdb import transaction
from cs.workspaces import WsDocuments
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext


class ModifyObjectsProcessor(CmdProcessorBase):
    """
    Modify an object in PDM.

    WARNING: This processor works for teamspace objects only at the moment.
    """

    name = "modifyobjects"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def _parseInput(self):
        idToAttrs = dict()
        ctxObjs = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        for ctxObj in ctxObjs:
            cdbObjId = ctxObj.attributes.get("cdb_object_id")
            newAttrs = dict()
            attrs = ctxObj.getChildrenByName("ATTRIBUTES")
            for attr in attrs:
                for k, v in six.iteritems(attr.attributes):
                    newAttrs[k] = v
            if cdbObjId:
                idToAttrs[cdbObjId] = newAttrs
        return idToAttrs

    def _execute(self, parsedInput):
        # ws_documents only
        with transaction.Transaction():
            cdbObjIdsQuoted = []
            for cdbObjId in six.iterkeys(parsedInput):
                cdbObjIdQuoted = "'%s'" % cdbObjId
                cdbObjIdsQuoted.append(cdbObjIdQuoted)
            cdbObjIdsStr = ", ".join(cdbObjIdsQuoted)
            condition = "cdb_object_id IN (%s)" % cdbObjIdsStr
            wsdocs = WsDocuments.Query(condition).Execute()
            for wsdoc in wsdocs:
                attrs = parsedInput.get(wsdoc.cdb_object_id)
                wsdoc.Update(**attrs)

    @timingWrapper
    @timingContext("MODIFYOBJECTS")
    def call(self, resultStream, request):
        parsedInput = self._parseInput()
        self._execute(parsedInput)
        return WsmCmdErrCodes.messageOk
