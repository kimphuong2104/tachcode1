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

from lxml import etree as ElementTree
from lxml.etree import Element

from cdb import constants, sqlapi
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cdbwrapc import SimpleArgument
from cdbwrapc import SimpleArgumentList
from cdbwrapc import Operation
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.xmlmapper import LOCK_ITEM

from cs.workspaces.sqlutils import partionedSqlQuery

import six


class LockCmdProcessor(CmdProcessorBase):

    """
    Process the lock command from the client.

    This class locks or unlocks objects by its cdb_object_id.
    """

    name = u"lock"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self._doLockAttr = rootElement.lock_mode == u"lock"
        self._wspLockId = rootElement.wsp_lock_id
        self._workspaceId = rootElement.ws_id
        self._lockPdmObjectsForTeamspace = (
            rootElement.lock_pdm_objects_for_teamspace == u"1"
        )
        self._id2handle = {}  # cdb_object_id -> objecthandle

    def _parseInput(self):
        cdbObjectIds = []
        for child in self._rootElement.getChildrenByName("LOCK_ITEM"):
            cdbObjectId = child.etreeElem.attrib.get("cdb_object_id")
            cdbObjectIds.append(cdbObjectId)
        return cdbObjectIds

    def _doLock(self, cdbObjectIds, wsDocFileIdToPdmDocFileId):
        logging.info("LockCommandProcessor._doLock: start")
        objErrors = []
        for objId in cdbObjectIds:
            objIdToQuery = objId
            if self._lockPdmObjectsForTeamspace:
                objIdToQuery = wsDocFileIdToPdmDocFileId.get(objId, objId)
            try:
                obj = self._id2handle[objIdToQuery]
                try:
                    arglist = SimpleArgumentList()
                    arglist.append(
                        SimpleArgument(
                            constants.kArgumentWorkspaceInstance, self._wspLockId
                        )
                    )
                    op = Operation(constants.kOperationLock, obj, arglist)
                    op.run()
                    objErrors.append(0)  # 0 for ok
                except Exception:
                    objErrors.append(1)  # 1 for not ok
                    logging.exception(
                        "LockCmdProcessor: lock '%s' failed", objIdToQuery
                    )
            except IndexError:
                logging.info("Could not get an object with cdb_object_id=%s", objId)
                objErrors.append(1)  # 1 for not ok
        logging.info("LockCommandProcessor._doLock: stop")
        return objErrors

    def _doUnlock(self, cdbObjectIds, wsDocFileIdToPdmDocFileId):
        logging.info("LockCommandProcessor._doUnlock: start")
        objErrors = []
        for objId in cdbObjectIds:
            objIdToQuery = objId
            if self._lockPdmObjectsForTeamspace:
                objIdToQuery = wsDocFileIdToPdmDocFileId.get(objId, objId)
            try:
                obj = self._id2handle[objIdToQuery]
                try:
                    op = Operation(
                        constants.kOperationUnlock, obj, SimpleArgumentList()
                    )
                    op.run()
                    objErrors.append(0)  # 0 for ok
                except Exception:
                    objErrors.append(1)  # 1 for not ok
                    logging.exception(
                        "LockCmdProcessor: unlock '%s' failed", objIdToQuery
                    )
            except IndexError:
                logging.info("Could not get an object with cdb_object_id=%s", objId)
                objErrors.append(1)  # 1 for not ok
        logging.info("LockCommandProcessor._doUnlock: stop")
        return objErrors

    def _writeReply(self, resultStream, objErrors, cdbObjectIds):
        cmdResultElem = Element("WSCOMMANDRESULT")
        for objErr in objErrors:
            lockItem = LOCK_ITEM(error=objErr)
            cmdResultElem.append(lockItem.toXmlTree())
        xmlStr = ElementTree.tostring(cmdResultElem, encoding="utf-8")
        resultStream.write(xmlStr)

    def getPdmFileObjectIdsForTeamspaceFileObjectIds(self, cdbObjectIds):
        # cdb_object_id TS file -> cdb_file TS -> cdbf_object_id TS -> cdb_object_id PDM -> wspitem_id -> cdb_object_id PDM
        wsDocFileIdToPdmDocFileId = {}
        if self._workspaceId:
            sql = """
            SELECT
                    wsdoc_file.cdb_object_id AS cdb_object_id,
                    pdm_file.cdb_object_id AS pdm_cdb_object_id
            FROM
                    cdb_file wsdoc_file

                    LEFT JOIN
                            ws_documents ws_docs
                    ON
                            ws_docs.ws_object_id = '%s' AND
                            ws_docs.cdb_object_id = wsdoc_file.cdbf_object_id

                    LEFT JOIN
                            cdb_file pdm_file
                    ON
                            pdm_file.cdbf_object_id = ws_docs.doc_object_id AND
                            pdm_file.cdb_wspitem_id = wsdoc_file.cdb_wspitem_id AND
                            pdm_file.cdb_classname = 'cdb_file' AND
                            (pdm_file.cdb_belongsto='' OR pdm_file.cdb_belongsto IS NULL)

            WHERE
                wsdoc_file.cdb_classname='cdb_file' AND
                (wsdoc_file.cdb_belongsto='' OR wsdoc_file.cdb_belongsto IS NULL)
            """ % sqlapi.quote(
                self._workspaceId or ""
            )
            records = partionedSqlQuery(sql, "wsdoc_file.cdb_object_id", cdbObjectIds)
            for r in records:
                # if pdm file exists, the current file is a teamspace file and
                # we store this mapping
                if r.pdm_cdb_object_id:
                    wsDocFileIdToPdmDocFileId[r.cdb_object_id] = r.pdm_cdb_object_id
        return wsDocFileIdToPdmDocFileId

    def call(self, resultStream, request=None):
        cdbObjectIds = self._parseInput()
        wsDocFileIdToPdmDocFileId = self.getPdmFileObjectIdsForTeamspaceFileObjectIds(
            cdbObjectIds
        )
        allFileIds = list(
            set(cdbObjectIds + list(six.itervalues(wsDocFileIdToPdmDocFileId)))
        )
        self._id2handle = getObjectHandlesFromObjectIDs(allFileIds, True, False)

        if self._doLockAttr:
            objErrors = self._doLock(cdbObjectIds, wsDocFileIdToPdmDocFileId)
        else:
            objErrors = self._doUnlock(cdbObjectIds, wsDocFileIdToPdmDocFileId)

        self._writeReply(resultStream, objErrors, cdbObjectIds)
        return WsmCmdErrCodes.messageOk
