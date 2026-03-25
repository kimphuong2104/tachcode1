# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module checkincommand

Implements checkin command
"""
from __future__ import absolute_import

import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import os
from collections import defaultdict, OrderedDict
import logging
import datetime
import json
import base64

from cdb import sqlapi
from cdb import transaction
from cdb import kernel
from cdb import auth
from cdb import cdbuuid
from cdb import fls
from cdb import sig

from cdbwrapc import SimpleArgument
from cdbwrapc import Operation

from cs.documents import Document
from cdb.objects import ByID
from cdb.objects.cdb_file import (
    cdb_folder_item,
    cdb_link_item,
    cdb_file_record,
    CDB_File,
)
from cs.platform.cad import Frame
from cdb.objects.operations import operation, system_args
from cdb import constants
from cdb.util import DBInserter, SkipAccessCheck

from cs.wsm.pkgs.cdbobj2xml import FrameBuilder
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor
from cs.wsm.pkgs.checkincommand_utils import copyFileObjectsToTeamspace
from cs.wsm.pkgs.cmdprocessorbase import WsmCmdErrCodes
from cs.wsm.pkgs.wscommand import WsCommand
from cs.wsm.pkgs.servertimingwrapper import measuringPoint, timingContext, timingWrapper
from cs.wsm.pkgs.pkgsutils import tr
from cs.wsm.pkgs.xmlmapper import (
    COMMANDSTATUSLIST,
    COMMANDSTATUS,
    ERROR,
    TRANSLATIONARGLIST,
    TRANSLATIONARG,
)

from cs.wsm.wsobjectcache import WsObjectCache, grouper, MAX_IN_ELEMENTS
from cs.wsm.partnerexport import PartnerFilename
from cs.wsm.pkgs.checkincommand_publisher import CheckinCommandPublisher
from cs.workspaces import WsDocuments, Workspace

try:
    from cdb.objects.cdb_file import BLACKLISTED_FILENAMES_EVENT

    logging.debug("wsm:CheckinCommand is using blacklist mode")
except ImportError:
    BLACKLISTED_FILENAMES_EVENT = None

KW_MANUALLY_ASSIGNED = "wsm_manual_assigned"
KW_MANUALLY_REPLACED = "manually_replaced"
KW_EXTERNAL_LINK = "is_external_link"


class CheckinCommand(WsCommand):
    NAME = "checkin"

    def __init__(self, request):
        WsCommand.__init__(self, request)
        # only used for checkin:
        # nested dict cdbf_object_id -> cdb_wspitem_id -> cdb_file_base-derived object
        # if there is a entry, the complete document content was cached in the beginning
        self.checkinFilesByWspItemId = defaultdict(dict)
        # nested dict cdbf_object_id -> (cdb_classname, cdb_folder, cdbf_name.upper()) -> cdb_file_base-derived object
        self.checkinFilesByName = defaultdict(dict)
        # cache for checkin only
        self._checkinCache = WsObjectCache(
            simplifiedRightsCheck=True,
            doRightsCheck=False,
            fileCaching=True,
            extendedCaching=False,
            workspaceId=self._request.ws_id,
        )
        self._checkinCache.setFileAttributesCaching(True)
        self._checkinCache.setLinkStatusCaching(True)

        # caches cdb_classname for new objects
        self._createCdbClassnames = {}
        # cdbf_hidden is new in 15.2
        self.cdbf_hidden_exists = hasattr(cdb_file_record, "cdbf_hidden")
        self._use_direct_blob = GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
        self._lock_on_create_by_filetype = set()
        self._init_lock_on_create()
        # collected ids of files to add or modify
        # includes tuple of cdb_object_id of the real pdm doc and
        # the wsp_item_id of the file (which can be in TS too)
        # FIXME: think about teamspace objects, without corresponding pdm objects
        #  -> create_object_id?
        self._addModifyObjIds = set()
        self._docIdToWsDocId = dict()
        self._pdmFileIdToWsFileId = dict()
        # collecting ids of documents from deleted links
        # to delete standalone ts only documents
        self.potential_del_in_ts_obj_ids = set()
        self._existingFiles = None
        # existingFiles is a set of lowername basenames of all
        # files in workspace that are not new and part of this commit
        existingFilesObj = self._request.getFirstChildByName("EXISTINGFILES")
        if existingFilesObj:
            content = existingFilesObj.etreeElem.text
            if content:
                contentAsList = json.loads(content)
                if type(contentAsList) == list:
                    self._existingFiles = set(contentAsList)
                    logging.debug(
                        "CheckinCommand: Existing files in workspace: %s", contentAsList
                    )
                else:
                    logging.error(
                        "CheckinCommand: unexpected content for EXSTINGFILES '%s'",
                        content,
                    )
        self._webrequest = None
        self._wspId = self._request.ws_id
        self._publisher = None
        # used for cache to distinguish between pdm and teamspace docs
        self._wsDocIds = set()
        self.objects_with_modified_reference = (
            set()
        )  # set of tuples (src_ob, dst_obj, action_name)

    def _getPublisher(self):
        if self._publisher is None:
            wsObj = Workspace.ByKeys(cdb_object_id=self._wspId)
            self._publisher = CheckinCommandPublisher(self, self._checkinCache, wsObj)
        return self._publisher

    def _init_lock_on_create(self):
        """
        inits the set _lock_on_create_by_filetype
        """
        for ft in kernel.getFileTypes():
            if ft.doAutoLock(constants.kOperationNew):
                self._lock_on_create_by_filetype.add(ft.getName())

    def _existingFileCallBack(self, _cdbf_object_id, _filename, names):
        """
        Callback for filename generation in CIM DATABASE
        """
        if self._existingFiles:
            names.update(self._existingFiles)
        logging.debug(
            "CheckinCommand_existingFilessCallBack: complete list of files: %s", names
        )

    def verifyFastBlob(self):
        """
        :return WsmErrorCode
        """
        ret = WsmCmdErrCodes.messageOk
        if self._use_direct_blob:
            if not fls.get_license("WSM_004"):
                ret = WsmCmdErrCodes.fastBlobLicense
            elif not hasattr(CDB_File, "presigned_blob_write_url"):
                ret = WsmCmdErrCodes.fastBlobOldServer
        return ret

    def setupCaching(self, webrequest):
        self._webrequest = webrequest
        WsCommand._setupCaching(self)
        if self._use_direct_blob:
            # this feature needs a cdb object
            self._cache.limitedFileAttrs = None
        self._performCaching()

    def _setupXmlGenerator(self):
        WsCommand._setupXmlGenerator(self)
        self._xmlGenerator.attrCollector.checkInMode = True
        if self._use_direct_blob:
            self._xmlGenerator.attrCollector.setPresignedBlobsEnabled(True)
            self._xmlGenerator.attrCollector.setCheckinObjIds(self._addModifyObjIds)

    def executeCommand(self):
        cdbObjId2CtxObj, pdmDocId2TsDocId, tsDocIds = self._parseIdsFromContextObjects()
        with measuringPoint("CACHING CHECKIN %s" % self.NAME):
            self._cacheCheckinObjects(list(pdmDocId2TsDocId))
        self._createTeamspaceObjects(cdbObjId2CtxObj, pdmDocId2TsDocId, tsDocIds)

        for contextObj in self._contextObjs:
            cntxCdbObjectId = contextObj.cdb_object_id
            cMethod = None
            try:
                if BLACKLISTED_FILENAMES_EVENT is not None:
                    cMethod = sig.connect(BLACKLISTED_FILENAMES_EVENT)(
                        self._existingFileCallBack
                    )
                status, localStatusList, globalErr = self._executeCheckin(contextObj)
            finally:
                if cMethod is not None:
                    sig.disconnect(cMethod)
            self._contextStatusDict[cntxCdbObjectId] = localStatusList
            if status:
                value = "ok"
            else:
                value = "error"
                if globalErr:
                    self._globalCmdStatusList.addChild(globalErr)
            self._addCtxObjectCmdStatus(cntxCdbObjectId, value)
        # handle deletion of alone ts documents
        self._deleteTSDocuments()

    def _parseIdsFromContextObjects(self):
        # Parse the ids of PDM documents and Teamspace documents here.
        cdbObjId2CtxObj = dict()
        pdmDocId2TsDocId = (
            dict()
        )  # cdb_object_id of Document -> cdb_object_id of WsDocuments
        tsDocIds = set()  # cdb_object_id of WsDocuments
        if self._wspId:
            for contextObj in self._contextObjs:
                cdbObjectId = contextObj.cdb_object_id
                cdbObjId2CtxObj[cdbObjectId] = contextObj
                if cdbObjectId != self._wspId:  # never for the workspace object itself
                    teamspaceObj = contextObj.teamspace_obj
                    if cdbObjectId == teamspaceObj:
                        self._wsDocIds.add(teamspaceObj)
                        if contextObj.commit_mode == u"teamspace":
                            tsDocIds.add(teamspaceObj)
                    elif teamspaceObj:
                        self._wsDocIds.add(teamspaceObj)
                        self._docIdToWsDocId[cdbObjectId] = teamspaceObj
                        pdmDocId2TsDocId[cdbObjectId] = teamspaceObj
        return cdbObjId2CtxObj, pdmDocId2TsDocId, tsDocIds

    def _createTeamspaceObjects(self, cdbObjId2CtxObj, pdmDocId2TsDocId, tsDocIds):
        # Create TS documents for PDM documents or Teamspace only documents
        if self._wspId:
            pdmDocIds = set(pdmDocId2TsDocId.keys())
            # for teamspace docs with corresponding pdm doc:
            if pdmDocIds:
                wsDocs = self._checkinCache.getCachedWsDocumentsByDocId(pdmDocIds)
                docToWsDoc = {
                    d.doc_object_id: d.cdb_object_id for d in wsDocs if d.doc_object_id
                }
                self._docIdToWsDocId.update(docToWsDoc)
                objectsWithoutTeamspaceObject = pdmDocIds - set(docToWsDoc)
                if objectsWithoutTeamspaceObject:
                    newTsDocIds = list()
                    # atomically create WsDocuments and copy file objects
                    with transaction.Transaction():
                        for objId in objectsWithoutTeamspaceObject:
                            tsDocId = pdmDocId2TsDocId.get(objId)
                            newTsDocIds.append(tsDocId)
                            WsDocuments._Create(
                                cdb_object_id=tsDocId,
                                ws_object_id=self._wspId,
                                doc_object_id=objId,
                                create_object_id="",
                                cdb_lock=auth.persno,
                            )
                            self._docIdToWsDocId[objId] = tsDocId
                            self._pdmFileIdToWsFileId = copyFileObjectsToTeamspace(
                                objId,
                                tsDocId,
                                cache=self._checkinCache,
                                newCdbLock=auth.persno,
                            )
                    self._checkinCache.prefetchTeamspaceObjects(newTsDocIds)

            # for teamspace only docs:
            if tsDocIds:
                wsDocs = self._checkinCache.getCachedWsDocumentsById(tsDocIds)
                existingTsDocIds = {
                    d.create_object_id for d in wsDocs if d.create_object_id
                }
                objectsWithoutTeamspaceObject = tsDocIds - existingTsDocIds
                if objectsWithoutTeamspaceObject:
                    # atomically create WsDocuments;
                    # file objects are copied from teamspace object to
                    # pdm object, when commit_mode=="publish"
                    with transaction.Transaction():
                        for objId in objectsWithoutTeamspaceObject:
                            ctxObj = cdbObjId2CtxObj.get(objId)
                            if ctxObj:
                                jsonObjAttrs = ctxObj.json_object_attrs
                            WsDocuments._Create(
                                cdb_object_id=objId,
                                ws_object_id=self._wspId,
                                doc_object_id="",
                                create_object_id=objId,
                                json_object_attrs=jsonObjAttrs,
                                cdb_lock=auth.persno,
                            )
                    self._checkinCache.prefetchTeamspaceObjects(
                        objectsWithoutTeamspaceObject
                    )

    def _cacheCheckinObjects(self, pdmDocIds):
        """
        Retrieve documents, files and directories of all checkin documents
        efficiently. The teamspace documents will be cached here also.
        """
        logging.info(u"cdbwsmcmdprocessor._cacheCheckinObjects: start")
        self.checkinFilesByWspItemId.clear()
        self.checkinFilesByName.clear()

        allDocIds = []
        checkinDocIds = []
        for wsCmdContextObj in self._contextObjs:
            # cache all non teamspace objects
            if wsCmdContextObj.teamspace_obj != wsCmdContextObj.cdb_object_id:
                objId = wsCmdContextObj.cdb_object_id
                allDocIds.append(objId)
                # only cache the files of documents with a large ratio of new files
                # (starting with 15.5.1, new_docs_ratio is the ratio of new OR CHANGED files)
                if wsCmdContextObj.new_docs_ratio:
                    newDocsRatio = float(wsCmdContextObj.new_docs_ratio)
                    if newDocsRatio > 0.5:
                        checkinDocIds.append(objId)

        if self._wsDocIds:
            # cache teamspace objects
            self._checkinCache.prefetchTeamspaceObjects(self._wsDocIds)
            self._checkinCache.prefetchTeamspaceObjectsByDocId(pdmDocIds)

        if allDocIds:
            if not checkinDocIds:
                self._checkinCache.setLinkStatusCaching(False)
                self._checkinCache.setFileAttributesCaching(False)

            self._checkinCache.prefetchObjects(allDocIds, alsoFetchLinkedObjects=False)

        if checkinDocIds:
            for cdbf_object_id in checkinDocIds:
                workspaceItems = self._checkinCache.workspaceItemsOf(cdbf_object_id)
                checkinFilesByWspItemId = self.checkinFilesByWspItemId[cdbf_object_id]
                checkinFilesByName = self.checkinFilesByName[cdbf_object_id]
                for workspaceItem in workspaceItems:
                    # remember by wspitem_id
                    checkinFilesByWspItemId[
                        workspaceItem.cdb_wspitem_id
                    ] = workspaceItem
                    # remember by class/folder/filename
                    className = workspaceItem.cdb_classname
                    logging.debug(
                        "WorkspaceItem: %s %s %s %s",
                        workspaceItem.cdb_object_id,
                        workspaceItem.cdbf_object_id,
                        workspaceItem.cdb_classname,
                        workspaceItem,
                    )
                    if className != "cdb_link_item":
                        if className == "cdb_file_record":
                            className = "cdb_file"
                        folder = workspaceItem.cdb_folder or ""
                        name = workspaceItem.cdbf_name.upper()
                        nameKey = (className, folder, name)
                        checkinFilesByName[nameKey] = workspaceItem
        logging.info(u"cdbwsmcmdprocessor._cacheCheckinObjects: end")

    def _executeCheckin(self, wsCmdContextObj):
        cmdStatusList = COMMANDSTATUSLIST()
        globalErr = None
        with transaction.Transaction():
            # if False checkin of context object failed
            cntxCmdStatus = True
            ctxObjectId = wsCmdContextObj.cdb_object_id
            logging.info(u"cdbwsmcmdprocessor: checkin %s", ctxObjectId)

            # theDoc may also be a WsDocuments objects
            theDoc = self._checkinCache.getObjectById(ctxObjectId)
            if theDoc is None:
                framesFromDatabase = Frame.KeywordQuery(cdb_object_id=ctxObjectId)
                try:
                    theDoc = framesFromDatabase[0]
                except IndexError:
                    pass

            if theDoc:
                teamspaceId = ""
                cdbObjId = theDoc.cdb_object_id
                if self._wspId and cdbObjId != self._wspId:
                    if isinstance(theDoc, WsDocuments):
                        teamspaceId = cdbObjId
                    if not teamspaceId:
                        teamspaceId = self._docIdToWsDocId.get(cdbObjId, "")
                requestTeamspaceId = wsCmdContextObj.teamspace_obj
                commit_mode = wsCmdContextObj.commit_mode
                initialPublish = wsCmdContextObj.initial_publish == "1"
                commitAction = wsCmdContextObj.commit_action
                if not commitAction:
                    commitAction = ""
                    if initialPublish:
                        commitAction = "NEW"

                if teamspaceId and not requestTeamspaceId and commit_mode == "pdm":
                    # the client does not know about the teamspace object
                    # the checkin request must fail because
                    # we don't want to allow writing to PDM when there is still a TS object
                    cntxCmdStatus = False
                    globalErr = ERROR(
                        msg=tr(
                            "There is teamspace content for"
                            " at least one of the documents to save."
                            " Please fetch the change status from the PDM system and try again."
                        )
                    )

                if (
                    requestTeamspaceId
                    and teamspaceId
                    and requestTeamspaceId != teamspaceId
                ):
                    # the client has a different teamspace object
                    # this should not happen (should be avoided by transaction mechanism and locks)
                    cntxCmdStatus = False
                    globalErr = ERROR(
                        msg=tr(
                            "An error occured when saving to the PDM system"
                            " (multiple teamspace objects for one document)."
                            " Try to update the workspace first."
                        )
                    )

                if cntxCmdStatus:
                    objects = wsCmdContextObj.getChildrenByName("WSCOMMANDS_OBJECT")
                    # process objects collectively to perform some optimizations
                    addObjs = []
                    # deletions must be done sorted, e.g. folders last
                    wspItemId2delObjs = OrderedDict()
                    replaceObjs = []

                    for obj in objects:
                        cmdStatus = True
                        command = obj.getFirstChildByName("COMMAND")
                        if command.action == "add":
                            addObjs.append((obj, command))

                        elif command.action == "modify":
                            cmdStatus = self.__handleModify(
                                theDoc,
                                teamspaceId,
                                obj,
                                cmdStatusList,
                                command,
                                commit_mode,
                                commitAction,
                            )

                        elif command.action == "delete":
                            wspItemId2delObjs[obj.local_id] = (obj, command)

                        elif command.action == "replace":
                            replaceObjs.append((obj, command))

                        else:
                            cmdStatusList.addChild(
                                COMMANDSTATUS(
                                    cdb_object_id=self._pdmFileIdToWsFileId.get(
                                        ctxObjectId, ctxObjectId
                                    ),
                                    local_id=obj.local_id,
                                    action=command.action,
                                    value="error",
                                )
                            )
                        if not cmdStatus:
                            cntxCmdStatus = False

                    # replaces may filter delete operations
                    replaceCmdStatus, delObjs = self._replaceObjects(
                        theDoc,
                        teamspaceId,
                        cmdStatusList,
                        replaceObjs,
                        commit_mode,
                        commitAction,
                        wspItemId2delObjs,
                    )
                    cntxCmdStatus &= replaceCmdStatus

                    cntxCmdStatus &= self._addObjects(
                        theDoc,
                        teamspaceId,
                        cmdStatusList,
                        addObjs,
                        commit_mode,
                        commitAction,
                    )
                    cntxCmdStatus &= self._deleteObjects(
                        theDoc, teamspaceId, cmdStatusList, delObjs
                    )

                    # update context object with meta data
                    commandStatusError = self._updateMetaData(
                        wsCmdContextObj, theDoc, teamspaceId
                    )
                    if commandStatusError is not None:
                        cntxCmdStatus = False
                        cmdStatusList.addChild(commandStatusError)

                    if cntxCmdStatus:
                        if teamspaceId:
                            if commit_mode == "prepare_publish":
                                # in the "first save" we only update the document attributes
                                # so that the WSM has a chance to use these new attributes for frames etc.
                                commandStatusError = self._updateMetaData(
                                    wsCmdContextObj, theDoc, teamspaceId=None
                                )
                                if commandStatusError is not None:
                                    cmdStatusList.addChild(commandStatusError)
                            elif commit_mode == "publish":
                                p = self._getPublisher()
                                cntxCmdStatus = p.publishTeamspaceObject(
                                    wsCmdContextObj,
                                    theDoc,
                                    teamspaceId,
                                    cmdStatusList,
                                    commitAction,
                                )

            else:
                cntxCmdStatus = False
                globalErr = ERROR(
                    msg=tr(
                        "A document has been deleted in the meantime."
                        " Please update the workspace and try again."
                    )
                )
        if self.objects_with_modified_reference:
            self.inform_other_modules_link_action_performed()
        return cntxCmdStatus, cmdStatusList, globalErr

    def _replaceObjects(
        self,
        theDoc,
        teamspaceId,
        cmdStatusList,
        replaceObjs,
        commit_mode,
        commitAction,
        wspItemId2delObjs,
    ):
        """
        Replace files with same cdb_wspitem_id. Performs deletions first.

        Returns filtered delete commands/objects
        """
        cntxCmdStatus = True
        for replaceObj, command in replaceObjs:
            localId = replaceObj.local_id
            logging.debug("CheckinCommand._replaceObjects: file with ID '%s'", localId)
            # add flag for cdb_file_wsm
            objAttrs = replaceObj.getObjectAttributes()
            objAttrs[KW_MANUALLY_REPLACED] = "1"
            # each replace should match a delete command
            delStatus = False
            delEntry = wspItemId2delObjs.pop(localId, None)
            if delEntry is None:
                # missing delete command
                delObj = self._getObjectByWspId(
                    replaceObj.cdb_classname, theDoc.cdb_object_id, localId
                )
                # if object ID equals, the new file was already added, e.g. on second save for non primary files
                if delObj is None or delObj.cdb_object_id == replaceObj.cdb_object_id:
                    logging.info(
                        "CheckinCommand._replaceObjects: previous file already deleted"
                    )
                    delStatus = True
            else:
                delObj, command = delEntry
                delStatus = self.__handleDelete(
                    theDoc, teamspaceId, delObj, cmdStatusList, command
                )
            if not delStatus:
                cntxCmdStatus = False
                cmdStatus = COMMANDSTATUS(
                    cdb_object_id=theDoc.cdb_object_id,
                    local_id=localId,
                    action=command.action,
                    value="error",
                )
                objectDesc = theDoc.cdb_object_id
                try:
                    objectDesc = "%s-%s" % (theDoc.z_nummer, theDoc.z_index)
                except AttributeError:
                    pass
                statusError = ERROR(
                    msg=tr(
                        "A file replacement failed due to a missing or failed delete operation of the previous file. File cdb_wspitem_id: '%1'; document: '%2'."
                    )
                )
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=localId))
                argList.addChild(TRANSLATIONARG(trArg=objectDesc))
                statusError.addChild(argList)
                cmdStatus.addChild(statusError)
                cmdStatusList.addChild(cmdStatus)

        if replaceObjs and cntxCmdStatus:
            cntxCmdStatus &= self._addObjects(
                theDoc,
                teamspaceId,
                cmdStatusList,
                replaceObjs,
                commit_mode,
                commitAction,
            )

        return cntxCmdStatus, wspItemId2delObjs.values()

    def _addObjects(
        self, theDoc, teamspaceId, cmdStatusList, addObjs, commitMode, commitAction
    ):
        cntxCmdStatus = True
        if addObjs:
            # add first file with full access checks, skip them for all following files
            # primary files are added first, then belongsto files
            obj, command = addObjs[0]
            cmdStatus = self.__handleAdd(
                theDoc,
                teamspaceId,
                obj,
                cmdStatusList,
                command,
                commitMode,
                commitAction,
            )
            if not cmdStatus:
                cntxCmdStatus = False
                if obj.cdb_classname == "cdb_folder_item":
                    return cntxCmdStatus

            if len(addObjs) > 1:
                with SkipAccessCheck():
                    for obj, command in addObjs[1:]:
                        cmdStatus = self.__handleAdd(
                            theDoc,
                            teamspaceId,
                            obj,
                            cmdStatusList,
                            command,
                            commitMode,
                            commitAction,
                        )
                        if not cmdStatus:
                            cntxCmdStatus = False
                            if obj.cdb_classname == "cdb_folder_item":
                                return cntxCmdStatus
        return cntxCmdStatus

    def __handleAdd(
        self, theDoc, teamspaceId, obj, cmdStatusList, command, commitMode, commitAction
    ):
        attrs = obj.getObjectAttributes()
        cntxCmdStatus = True
        statusError = None
        cdbObjId = None
        className = obj.cdb_classname
        # ---------------------------------------------------------------------------- #
        #                                FOLDER_ITEMS                                  #
        # ---------------------------------------------------------------------------- #
        if className == "cdb_folder_item":
            with measuringPoint("CHECKIN ADDFOLDERS"):
                cdbObjId, statusError = self._handleAddFolder(
                    theDoc, teamspaceId, obj, attrs, commitAction
                )

        # ---------------------------------------------------------------------------- #
        #                               FILE_ITEMS                                     #
        # ---------------------------------------------------------------------------- #
        elif className == "cdb_file":
            with measuringPoint("CHECKIN ADDFILES"):
                cmdAttrs = command.getObjectAttributes()
                keepFilename = cmdAttrs.get("keep_filename") == "yes"
                cdbObjId, statusError = self._handleAddFile(
                    theDoc,
                    teamspaceId,
                    obj,
                    attrs,
                    command,
                    keepFilename,
                    commitMode,
                    commitAction,
                )

        # ---------------------------------------------------------------------------- #
        #                              LINK_ITEMS                                      #
        # ---------------------------------------------------------------------------- #
        elif className == "cdb_link_item":
            with measuringPoint("CHECKIN ADDLINKS"):
                cdbObjId, statusError = self._addOrModifyLinkItem(
                    theDoc, teamspaceId, obj, attrs, commitMode, commitAction
                )

        if cdbObjId is not None:
            cmdStatus = COMMANDSTATUS(
                cdb_object_id=self._pdmFileIdToWsFileId.get(cdbObjId, cdbObjId),
                local_id=obj.local_id,
                action=command.action,
                value="ok",
            )
            cmdStatusList.addChild(cmdStatus)

        else:
            cntxCmdStatus = False
            cmdStatus = COMMANDSTATUS(
                cdb_object_id="",
                local_id=obj.local_id,
                action=command.action,
                value="error",
            )
            if statusError:
                cmdStatus.addChild(statusError)
            else:
                statusError = ERROR(msg=tr("failed to create new %1 "))
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=obj.cdb_classname))
                statusError.addChild(argList)
                cmdStatus.addChild(statusError)
            cmdStatusList.addChild(cmdStatus)

        return cntxCmdStatus

    def _handleAddFile(
        self,
        theDoc,
        teamspaceId,
        obj,
        attrs,
        command,
        keepFilename,
        commitMode,
        commitAction,
    ):
        cdbObjId = None
        statusError = None
        cdbfHiddenFlag = attrs.get("cdbf_hidden", "")
        belongsto = attrs.get("cdb_belongsto", "")
        fileName = attrs.get("cdbf_name", "")
        fileParentId = attrs.get("cdb_folder", "")
        fileType = attrs.get("cdbf_type", "")
        primary = attrs.get("cdbf_primary", "")
        docId = theDoc.cdb_object_id
        wspItemId = obj.local_id
        if commitAction in ("COPY", "NEWINDEX"):
            docIdForSave = docId
            existingFile = self._queryCdbFileByWspId(
                "cdb_file", theDoc.cdb_object_id, obj.local_id
            )
        else:
            docIdForSave = teamspaceId or docId
            existingFile = self._getObjectByWspId(
                "cdb_file", theDoc.cdb_object_id, obj.local_id
            )

        if not existingFile:
            # check name is not used in case of keep_filename
            if keepFilename:
                existingItem = self._getExistingItemByName(
                    theDoc, fileParentId, "cdb_file", fileName
                )
            else:
                existingItem = None

            if existingItem is None:
                # build arguments for new file record
                argDict = dict(
                    cdbf_type=fileType,
                    cdbf_object_id=docIdForSave,
                    cdb_folder=fileParentId,
                    cdb_wspitem_id=wspItemId,
                    cdb_belongsto=belongsto,
                    cdbf_primary=primary,
                )

                if belongsto:
                    keepFilename = True

                    if self.cdbf_hidden_exists:
                        # The "cdbf_hidden" flag is usually not sent from the client.
                        # It is only sent for state change secondary files as "0", if
                        # the automatically created files should be visible, e.g. ".pdf".
                        # By default, all other belongsto files are not visible.
                        # The client never sends "1" for "cdbf_hidden".
                        if not cdbfHiddenFlag:
                            argDict["cdbf_hidden"] = 1
                        else:
                            argDict["cdbf_hidden"] = int(cdbfHiddenFlag == "1")

                else:
                    original_name = os.path.splitext(fileName)[0]
                    argDict["cdbf_original_name"] = original_name
                    force = commitMode == "teamspace"
                    self._add_lock_attributes(fileType, argDict, force=force)

                try:
                    with measuringPoint("DETAIL CREATEFILERECORD"):

                        cdbObjId = cdbuuid.create_uuid()
                        argDict["cdb_object_id"] = cdbObjId
                        argDict["cdb_classname"] = self._getClassnameForCreate(
                            cdb_file_record
                        )
                        if self._use_direct_blob:
                            fType = argDict.get("cdbf_type")
                            belongsTo = argDict.get("cdb_belongsto")
                            if (
                                fType
                                and fType in self._lock_on_create_by_filetype
                                and not belongsTo
                            ):
                                argDict["cdb_lock_date"] = datetime.datetime.now()
                                argDict["cdb_lock"] = auth.persno
                        if keepFilename:
                            argDict["cdbf_name"] = fileName
                            cdb_file_record._Create(**argDict)
                        else:
                            cdb_obj = cdb_file_record.Create(**argDict)
                            updateDict = {}
                            if not teamspaceId:
                                updateDict["cdbf_name"] = cdb_obj.generate_name(
                                    fileName
                                )
                            else:
                                updateDict[
                                    "cdbf_name"
                                ] = WsDocuments.generate_name_for_document(
                                    cdb_obj, docId
                                )
                            cdb_obj.Update(**updateDict)

                except Exception as ex:
                    identifier = attrs.get("cdbf_name", "")
                    statusError = ERROR(
                        msg=tr("requested creation failed on file %1: %2")
                    )
                    argList = TRANSLATIONARGLIST()
                    argList.addChild(TRANSLATIONARG(trArg=identifier))
                    argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                    statusError.addChild(argList)
            else:
                forceCommit = command.force == "yes"
                if not forceCommit:
                    # do force commit for belongsto files
                    # (e.g. appinfo and preview)
                    forceCommit = (
                        belongsto
                        and "cdb_belongsto" in existingItem
                        and existingItem["cdb_belongsto"] == belongsto
                    )

                className = existingItem.cdb_classname
                if className == "cdb_file" and not forceCommit:
                    statusError = ERROR(
                        msg=tr(
                            "creation of file failed: "
                            "file with name %1 is already existing."
                            " Please rename and try again"
                        )
                    )
                    argList = TRANSLATIONARGLIST()
                    argList.addChild(TRANSLATIONARG(trArg=fileName))
                    statusError.addChild(argList)

                elif (
                    className == "cdb_file_record"
                    or className == "cdb_file"
                    and forceCommit
                ):
                    updateDict = {}
                    updateDict["cdb_wspitem_id"] = wspItemId
                    if "cdb_belongsto" in existingItem:
                        if existingItem["cdb_belongsto"] != belongsto:
                            # belongsto may change in conflict solving scenario
                            # or if a preview was transfered as primary file first and
                            # as belongsto later.
                            updateDict["cdb_belongsto"] = belongsto
                    existingItem.Update(**updateDict)
                    cdbObjId = existingItem.cdb_object_id
                else:
                    statusError = ERROR(
                        msg=tr(
                            "creation of file failed: "
                            "file with name %1 is already existing"
                            " with unexpected classname %2"
                        )
                    )
                    argList = TRANSLATIONARGLIST()
                    argList.addChild(TRANSLATIONARG(trArg=fileName))
                    argList.addChild(TRANSLATIONARG(trArg=className))
                    statusError.addChild(argList)
        else:
            cdbObjId = existingFile.cdb_object_id

        if cdbObjId is not None:
            # enable the generation of presigned blobs for the pdm doc
            # and ts doc by using its cdb_object_id
            self._addModifyObjIds.add((docId, wspItemId))
            wsDocId = self._docIdToWsDocId.get(docId)
            if wsDocId is not None:
                self._addModifyObjIds.add((wsDocId, wspItemId))

            if statusError is None and not belongsto:
                self._insertLinkStatus(command, docIdForSave, wspItemId)
                self._updateFileItemFileWsmAttrs(docIdForSave, wspItemId, attrs)

        return cdbObjId, statusError

    def _deleteObjects(self, theDoc, teamspaceId, cmdStatusList, delObjs):
        cntxCmdStatus = True
        for obj, command in delObjs:
            cmdStatus = self.__handleDelete(
                theDoc, teamspaceId, obj, cmdStatusList, command
            )
            if not cmdStatus:
                cntxCmdStatus = False
        return cntxCmdStatus

    def _getClassnameForCreate(self, cls):
        name = self._createCdbClassnames.get(cls)
        if name is None:
            name = cls._getClassname()
            self._createCdbClassnames[cls] = name
        return name

    def _add_lock_attributes(self, cdbf_type, updateDict, force=False):
        """
        Adds locking attributes if requested by file type configuration.
        :param cdbf_type: cdbf_type
        :param updateDict: dict receiving the resulting attributes
        """
        ft = kernel.CDBFileType(cdbf_type)
        if force or (ft and ft.doAutoLock("CDB_Create")):
            updateDict["cdb_lock"] = auth.persno
            attrs = cdb_file_record.MakeChangeControlAttributes()
            now = attrs["cdb_mdate"]
            updateDict["cdb_lock_date"] = now

    def _handleAddFolder(self, theDoc, teamspaceId, obj, attrs, commitAction):
        cdbObjId = None
        statusError = None
        docId = theDoc.cdb_object_id
        wspItemId = obj.local_id
        if commitAction in ("COPY", "NEWINDEX"):
            docIdForSave = theDoc.cdb_object_id
            existingFolder = self._queryCdbFileByWspId(
                "cdb_folder_item", docId, wspItemId
            )
        else:
            docIdForSave = teamspaceId or theDoc.cdb_object_id
            existingFolder = self._getObjectByWspId("cdb_folder_item", docId, wspItemId)

        if not existingFolder:
            folderName = attrs.get("cdbf_name", "")
            parentFolderId = attrs.get("cdb_folder", "")
            # check name is not used
            existingFolder = self._getExistingItemByName(
                theDoc, parentFolderId, "cdb_folder_item", folderName
            )

            if existingFolder is None:
                belongsto = attrs.get("cdb_belongsto", "")
                chg_ctrl = cdb_folder_item.MakeChangeControlAttributes()

                cdbObjId = cdbuuid.create_uuid()
                clsName = self._getClassnameForCreate(cdb_folder_item)
                cdb_folder_item._Create(
                    cdb_object_id=cdbObjId,
                    cdb_classname=clsName,
                    cdbf_name=folderName,
                    cdbf_object_id=docIdForSave,
                    cdb_wspitem_id=wspItemId,
                    cdbf_blob_id="",
                    cdb_folder=parentFolderId,
                    cdb_belongsto=belongsto,
                    cdb_cdate=chg_ctrl.get("cdb_cdate", ""),
                    cdb_mdate=chg_ctrl.get("cdb_mdate", ""),
                )
            else:
                statusError = ERROR(
                    msg=tr(
                        "creation of folder failed: "
                        "folder with name %1 is already existing. Please rename and try again"
                    )
                )
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=folderName))
                statusError.addChild(argList)
        else:
            cdbObjId = existingFolder.cdb_object_id
        return cdbObjId, statusError

    def _addOrModifyLinkItem(
        self, theDoc, teamspaceId, obj, attrs, commitMode, commitAction
    ):
        """
        Creates or modifies cdb_link_item
        """
        logging.debug("+++ _addOrModifyLinkItem start")
        cdb_obj = None
        statusError = None
        link = attrs.get("cdb_link", "")
        parentFolder = attrs.get("cdb_folder", "")
        docId = theDoc.cdb_object_id
        wspItemId = obj.local_id

        if commitAction in ("COPY", "NEWINDEX"):
            docIdForSave = theDoc.cdb_object_id
            existingLink = self._queryCdbFileByWspId("cdb_link_item", docId, wspItemId)
        else:
            docIdForSave = teamspaceId or theDoc.cdb_object_id
            existingLink = self._getObjectByWspId("cdb_link_item", docId, wspItemId)

        target = self._getLinkTarget(link)
        if target is None:
            statusError = ERROR(
                msg=tr(
                    "creation of the link item for document '%1' failed: "
                    "link object links to non existent target '%2'"
                )
            )
            argList = TRANSLATIONARGLIST()
            docDesignation = theDoc.ToObjectHandle().getDesignation()
            argList.addChild(TRANSLATIONARG(trArg=docDesignation))
            argList.addChild(TRANSLATIONARG(trArg=six.text_type(link)))
            statusError.addChild(argList)
            # delete invalid link
            if existingLink and existingLink.cdb_link == link:
                error = self._deleteLinkItem(existingLink)
                if error is None:
                    self._deleteDocRelEntry(theDoc, link)
            return None, statusError

        if existingLink and existingLink.cdb_link == link:
            logging.debug("link item already exists")
            # link with same id and desired attributes exists
            cdb_obj = existingLink
            self._updateLinkItemFileWsmAttrs(
                docIdForSave, cdb_obj.cdb_wspitem_id, attrs
            )
        else:
            linksWithSameTarget = self._getLinksWithSameTarget(
                docId, docIdForSave, link, wspItemId, parentFolder
            )

            for linkWithSameTarget in linksWithSameTarget:
                logging.info("link with same target but different ID exists")
                # another link with all desired attributes exists. use this
                # link instead and delete the originally requested link.
                if existingLink:
                    error = self._deleteLinkItem(existingLink)
                    if error is None and not teamspaceId:
                        self._deleteDocRelEntry(theDoc, existingLink.cdb_link)
                # there should be only one
                cdb_obj = linkWithSameTarget
                self._updateLinkItemFileWsmAttrs(
                    docIdForSave, cdb_obj.cdb_wspitem_id, attrs
                )
                break

        if not cdb_obj:
            if existingLink:
                logging.info("modifying existing link")
                # modify existing link
                cdb_obj = existingLink
                cdbObjId = cdb_obj.cdb_object_id
                oldTarget = self._getLinkTarget(existingLink.cdb_link)
                linkModifyFailed = False

                objAttributes = obj.getObjectAttributes()
                if objAttributes and self._checkModified(existingLink, objAttributes):
                    objAttributes[constants.kArgumentActiveIntegration] = "wspmanager"
                    objAttributes[constants.kArgumentActiveCAD] = "wspmanager"
                    al = self.__dict2SimpleArgList(objAttributes)
                    try:
                        with measuringPoint("DETAIL MODIFYLINK"):
                            objh = existingLink.ToObjectHandle()
                            op = Operation("CDB_Modify", objh, al)
                            op.run()
                    except Exception as ex:
                        linkModifyFailed = True
                        logging.exception(u"CDB_Modify for link failed: ")
                        statusError = ERROR(msg=tr("modification on link failed: %1"))
                        argList = TRANSLATIONARGLIST()
                        argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                        statusError.addChild(argList)
                if not linkModifyFailed:
                    if oldTarget and (
                        not teamspaceId or commitMode == "prepare_publish"
                    ):
                        if isinstance(theDoc, Document) and isinstance(
                            target, Document
                        ):
                            if not type(oldTarget) == WsDocuments:
                                self._updateDocRelEntry(theDoc, target, oldTarget)
                            else:
                                self._createDocRelEntry(
                                    theDoc, target, ignoreExists=True
                                )
                    self._updateLinkItemFileWsmAttrs(
                        docIdForSave, cdb_obj.cdb_wspitem_id, attrs
                    )

            else:
                logging.info("creating new link")
                # create new link
                chg_ctrl = cdb_link_item.MakeChangeControlAttributes()
                cdbObjId = cdbuuid.create_uuid()
                clsName = self._getClassnameForCreate(cdb_link_item)
                newLink = cdb_link_item._Create(
                    cdb_object_id=cdbObjId,
                    cdb_classname=clsName,
                    cdbf_object_id=docIdForSave,
                    cdb_wspitem_id=wspItemId,
                    cdb_folder=parentFolder,
                    cdb_link=link,
                    cdbf_blob_id="",
                    cdb_cdate=chg_ctrl.get("cdb_cdate", ""),
                    cdb_mdate=chg_ctrl.get("cdb_mdate", ""),
                )

                # update cdb_doc_rel
                if newLink is not None and not teamspaceId:
                    self._createDocRelEntry(theDoc, target)
                self._updateLinkItemFileWsmAttrs(docIdForSave, wspItemId, attrs)
        else:
            cdbObjId = cdb_obj.cdb_object_id
        if theDoc is not None and target is not None:
            if not isinstance(theDoc, Document) or not isinstance(target, Document):
                self.objects_with_modified_reference.add((theDoc, target, "Create"))
        logging.debug("+++ _addOrModifyLinkItem finish")
        return cdbObjId, statusError

    def _getLinksWithSameTarget(
        self, docId, docIdForSave, link, wspItemId, parentFolder
    ):
        cachedEntries = self.checkinFilesByWspItemId.get(docId)
        if cachedEntries is not None:
            linksWithSameTarget = []
            for entryWspItemId, entry in six.iteritems(cachedEntries):
                if (
                    entry.cdb_link == link
                    and entryWspItemId != wspItemId
                    and entry.cdb_folder == parentFolder
                ):
                    linksWithSameTarget.append(entry)
        else:
            condition = (
                "cdb_folder = '%s' AND "
                "cdbf_object_id = '%s' AND cdb_link='%s' AND "
                "cdb_wspitem_id != '%s'" % (parentFolder, docIdForSave, link, wspItemId)
            )
            linksWithSameTarget = cdb_link_item.Query(condition)
        return linksWithSameTarget

    def _getLinkTarget(self, docId):
        doc = self._checkinCache.getObjectById(docId)
        if doc is None:
            doc = ByID(docId)
        return doc

    def _updateLinkItemFileWsmAttrs(self, cdbf_object_id, link_wspitem_id, attrs):
        attrKeys = (KW_EXTERNAL_LINK, KW_MANUALLY_ASSIGNED)
        self._updateFileWsmAtrs(cdbf_object_id, link_wspitem_id, attrs, attrKeys)

    def _updateFileItemFileWsmAttrs(self, cdbf_object_id, wspitem_id, attrs):
        attrKeys = (KW_MANUALLY_ASSIGNED, KW_MANUALLY_REPLACED)
        self._updateFileWsmAtrs(cdbf_object_id, wspitem_id, attrs, attrKeys)

    def _updateFileWsmAtrs(self, cdbf_object_id, wspitem_id, attrs, attrKeys):
        """
        Filters given attrs by attrKeys and updates cdb_file_wsm entries
        """
        filteredAttrs = {}
        for cdbFileWsmAttr in attrKeys:
            value = attrs.get(cdbFileWsmAttr)
            if value is not None:
                filteredAttrs[cdbFileWsmAttr] = value
        self._insertCdbfileWsm(cdbf_object_id, wspitem_id, filteredAttrs)

    def _updateDocRelEntry(self, document, referenced, oldReferenced):
        logging.debug("+++ _updateDocRelEntry start")
        with measuringPoint("DETAIL MODIFYDOCREL"):
            if (
                not (
                    referenced.z_nummer == oldReferenced.z_nummer
                    and referenced.z_index == oldReferenced.z_index
                )
                and document.GetTableName() == "zeichnung"
                and referenced.GetTableName() == "zeichnung"
            ):
                existingEntry = sqlapi.RecordSet2(
                    "cdb_doc_rel",
                    "z_nummer = '%s' AND z_index = '%s' AND "
                    "z_nummer2 = '%s' AND z_index2 = '%s'"
                    % (
                        sqlapi.quote(document.z_nummer),
                        sqlapi.quote(document.z_index),
                        sqlapi.quote(oldReferenced.z_nummer),
                        sqlapi.quote(oldReferenced.z_index),
                    ),
                )
                if existingEntry:
                    try:
                        for record in existingEntry:
                            record.update(
                                z_nummer2=referenced.z_nummer,
                                z_index2=referenced.z_index,
                            )
                    except Exception:
                        logging.exception(
                            "cdbwsmcdmdprocessor: Error while updating data in cdb_doc_rel."
                        )
                else:
                    self._createDocRelEntry(document, referenced)
        logging.debug("+++ _updateDocRelEntry finish")

    def _updateMetaData(self, wsCmdContextObj, theDoc, teamspaceId):
        commandStatus = None
        docAttributes = wsCmdContextObj.getObjectAttributes()

        if not teamspaceId:  # don't modify attributes if user is working in teamspace
            if docAttributes and self._checkModified(theDoc, docAttributes):
                argDict = docAttributes.copy()
                argDict[constants.kArgumentActiveIntegration] = "wspmanager"
                argDict[constants.kArgumentActiveCAD] = "wspmanager"
                officeVars = argDict.pop("__office_vars__", None)
                try:
                    if officeVars:
                        jsonStructure = json.loads(
                            base64.standard_b64decode(officeVars)
                        )
                        _read_vars, write_vars = FrameBuilder.sort_office_vars(
                            jsonStructure
                        )
                        signaldocVars = sig.emit("ws_office_write")(theDoc, write_vars)
                        # this is a list of results
                        for docVarDict in signaldocVars:
                            if docVarDict:
                                # DocumentVariables.auto_write encapsulates values in a list
                                # -> this_doc_vars[dVar.attribute] = [v]
                                for var_name, var_value_list in list(
                                    six.iteritems(docVarDict)
                                ):
                                    argDict[var_name] = var_value_list[0]
                    simpleArgList = self.__dict2SimpleArgList(argDict)
                    with measuringPoint("CHECKIN MODIFYDOC"):
                        objh = theDoc.ToObjectHandle()
                        op = Operation("CDB_Modify", objh, simpleArgList)
                        op.run()
                except Exception as ex:
                    logging.exception(u"CDB_Modify for document failed:")
                    # add local command status
                    cmd = wsCmdContextObj.getFirstChildByName("COMMAND")
                    cdbObjId = self._pdmFileIdToWsFileId.get(
                        wsCmdContextObj.cdb_object_id, wsCmdContextObj.cdb_object_id
                    )
                    commandStatus = COMMANDSTATUS(
                        cdb_object_id=cdbObjId,
                        local_id="",
                        action=cmd.action,
                        value="error",
                    )
                    objectDesc = theDoc.ToObjectHandle().getDesignation()
                    statusError = ERROR(msg=tr("modify of object '%1' failed: %2"))
                    argList = TRANSLATIONARGLIST()
                    argList.addChild(TRANSLATIONARG(trArg=objectDesc))
                    argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                    statusError.addChild(argList)
                    commandStatus.addChild(statusError)
        return commandStatus

    def __folderIsEmpty(self, folderObject):
        nonTempItems = folderObject.FolderItems.Query(
            "cdb_classname <> 'cdb_file_record'"
        )
        return len(nonTempItems) == 0

    def __deleteFileRecordsInFolder(self, folderObject):
        tempItems = folderObject.FolderItems.Query("cdb_classname = 'cdb_file_record'")
        for tmpItem in tempItems:
            try:
                operation(
                    constants.kOperationDelete,
                    tmpItem,
                    system_args(
                        active_integration=u"wspmanager", activecad=u"wspmanager"
                    ),
                )
            except Exception:
                # silently ignore
                pass

    def __dict2SimpleArgList(self, dictionary):
        """
        Convert the content of dictionary to a list of SimpleArgument.
        """
        return [SimpleArgument(k, v) for k, v in six.iteritems(dictionary)]

    def _createDocRelEntry(self, document, referenced, ignoreExists=False):
        logging.debug("+++ _createDocRelEntry start")
        with measuringPoint("DETAIL MODIFYDOCREL"):
            if (
                document.GetTableName() == "zeichnung"
                and referenced.GetTableName() == "zeichnung"
            ):
                r = sqlapi.Record(
                    "cdb_doc_rel",
                    z_nummer=document.z_nummer,
                    z_index=document.z_index,
                    z_nummer2=referenced.z_nummer,
                    z_index2=referenced.z_index,
                    t_nummer2="",
                    t_index2="",
                    logischer_name="",
                    reltype="WSM",
                    owner_application="WSM",
                    cdb_link=0,
                    classname="",
                    cad_link=0,
                    cad_link_bez="",
                    checkoutname="",
                )
                try:
                    r.insert()
                except Exception:
                    if not ignoreExists:
                        logging.exception(
                            "cdbwsmcdmdprocessor: Error while inserting data into cdb_doc_rel."
                        )
        logging.debug("+++ _createDocRelEntry finish")

    def _checkModified(self, objectToModify, objAttributes):
        """
        Checks whether any value in `objAttributes` differ from the value
        that can be retrieved by calling `objectToModify`.__getitem__.
        `objAttributes` is a dictionary
        """
        result = False
        try:
            for (key, value) in six.iteritems(objAttributes):
                if "%s" % objectToModify.__getitem__(key) != value:
                    result = True
                    break
        except Exception:
            # assume there is a diff
            result = True
        return result

    def __handleModify(
        self, theDoc, teamspaceId, obj, cmdStatusList, command, commitMode, commitAction
    ):
        attrs = obj.getObjectAttributes()
        cntxCmdStatus = True
        error = ERROR(msg=tr("failed to modify %1"))
        argList = TRANSLATIONARGLIST()
        argList.addChild(TRANSLATIONARG(trArg=obj.cdb_object_id))
        error.addChild(argList)
        className = obj.cdb_classname
        cdbObjId = None
        if commitAction in ("COPY", "NEWINDEX"):
            docIdForSave = theDoc.cdb_object_id
        else:
            docIdForSave = teamspaceId or theDoc.cdb_object_id
        cmdAttrs = command.getObjectAttributes()
        keepFilename = cmdAttrs.get("keep_filename") == "yes"

        if className == "cdb_link_item":
            with measuringPoint("CHECKIN MODIFYLINKS"):
                cdbObjId, error = self._addOrModifyLinkItem(
                    theDoc, teamspaceId, obj, attrs, commitMode, commitAction
                )
                if error or cdbObjId is None:
                    cntxCmdStatus = False

        else:
            if commitAction in ("COPY", "NEWINDEX"):
                objectToModify = self._queryCdbFileByWspId(
                    className, theDoc.cdb_object_id, obj.local_id
                )
            else:
                objectToModify = self._getObjectByWspId(
                    className, theDoc.cdb_object_id, obj.local_id
                )
            if objectToModify:
                cdbObjId = objectToModify.cdb_object_id

                if className == "cdb_file":
                    # enable the generation of presigned blobs for the pdm doc
                    # and ts doc by using its cdb_object_id
                    docId = theDoc.cdb_object_id
                    wspItemId = objectToModify.cdb_wspitem_id
                    self._addModifyObjIds.add((docId, wspItemId))
                    wsDocId = self._docIdToWsDocId.get(docId)
                    if wsDocId is not None:
                        self._addModifyObjIds.add((wsDocId, wspItemId))

                    with measuringPoint("CHECKIN MODIFYFILES"):
                        conflicted = False
                        fileHashElem = obj.getFirstChildByName("HASHES")
                        if fileHashElem is not None:
                            wsmBlobId = fileHashElem.attributes["files"]
                            cdbBlobId = objectToModify.cdbf_blob_id
                            # last id from wsm must equal the current id
                            conflicted = wsmBlobId != cdbBlobId

                        forceModification = command.force == "yes"
                        if not conflicted or forceModification:
                            objAttributes = obj.getObjectAttributes()
                            if objAttributes and (
                                self._checkModified(objectToModify, objAttributes)
                                or (
                                    commitMode == "prepare_publish"
                                    and commitAction == "NEW"
                                )
                            ):
                                try:
                                    with measuringPoint("DETAIL MODIFYFILE"):
                                        objh = objectToModify.ToObjectHandle()
                                        objAttributes[
                                            constants.kArgumentActiveIntegration
                                        ] = "wspmanager"
                                        objAttributes[
                                            constants.kArgumentActiveCAD
                                        ] = "wspmanager"
                                        if (
                                            not keepFilename
                                            and commitMode == "prepare_publish"
                                            and commitAction == "NEW"
                                        ):
                                            # objectToModify == cdb_file
                                            # objectToModify parent of WsDocuments!
                                            objAttributes[
                                                "cdbf_name"
                                            ] = WsDocuments.generate_name_for_document(
                                                objectToModify,
                                                docId,
                                                original_name=attrs.get(
                                                    "cdbf_name", ""
                                                ),
                                            )
                                        al = self.__dict2SimpleArgList(objAttributes)
                                        op = Operation("CDB_Modify", objh, al)
                                        op.run()
                                except Exception as ex:
                                    logging.exception(
                                        u"CDB_Modify for cdb_file failed:"
                                    )
                                    cntxCmdStatus = False
                                    identifier = objectToModify.cdbf_name
                                    if not identifier:
                                        if "cdbf_name" in attrs:
                                            identifier = attrs["cdbf_name"]
                                    error = ERROR(
                                        msg=tr(
                                            "requested modification failed on %1: %2"
                                        )
                                    )
                                    argList = TRANSLATIONARGLIST()
                                    argList.addChild(TRANSLATIONARG(trArg=identifier))
                                    argList.addChild(
                                        TRANSLATIONARG(trArg=six.text_type(ex))
                                    )
                                    error.addChild(argList)

                            if cntxCmdStatus:
                                self._insertLinkStatus(
                                    command, docIdForSave, obj.local_id
                                )
                                self._updatePartnerName(
                                    command, docIdForSave, objectToModify.cdb_object_id
                                )
                                self._updateFileItemFileWsmAttrs(
                                    docIdForSave, obj.local_id, attrs
                                )
                        else:
                            cntxCmdStatus = False
                            identifier = (
                                objectToModify.cdbf_name
                                if objectToModify.cdbf_name
                                else obj.cdb_object_id
                            )
                            error = ERROR(
                                msg=tr(
                                    "requested modification failed on %1:"
                                    " object was modified by another user"
                                )
                            )
                            argList = TRANSLATIONARGLIST()
                            argList.addChild(TRANSLATIONARG(trArg=identifier))
                            error.addChild(argList)
            else:
                cntxCmdStatus = False
                error = ERROR(msg=tr("failed to modify %1: object does not exist"))
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=className))
                error.addChild(argList)

        if cntxCmdStatus and cdbObjId is not None:
            cmdStatusList.addChild(
                COMMANDSTATUS(
                    cdb_object_id=self._pdmFileIdToWsFileId.get(cdbObjId, cdbObjId),
                    local_id=obj.local_id,
                    action=command.action,
                    value="ok",
                )
            )
        else:
            cmdStatus = COMMANDSTATUS(
                cdb_object_id=self._pdmFileIdToWsFileId.get(
                    obj.cdb_object_id, obj.cdb_object_id
                ),
                local_id=obj.local_id,
                action=command.action,
                value="error",
            )
            cmdStatus.addChild(error)
            cmdStatusList.addChild(cmdStatus)

        return cntxCmdStatus

    def __handleDelete(self, theDoc, teamspaceId, obj, cmdStatusList, command):
        attrs = obj.getObjectAttributes()
        error = None
        # check if already deleted
        objectToDelete = self._getObjectByWspId(
            obj.cdb_classname, theDoc.cdb_object_id, obj.local_id
        )
        if objectToDelete:
            className = objectToDelete.cdb_classname
            if not className == "cdb_file_record":
                conflicted = False
                if className == "cdb_file":
                    fileHashElem = obj.getFirstChildByName("HASHES")
                    if fileHashElem is not None:
                        wsmBlobId = fileHashElem.attributes["files"]
                        cdbBlobId = objectToDelete.cdbf_blob_id
                        # last id from wsm must equal the current id
                        conflicted = wsmBlobId != cdbBlobId

                forceDelete = command.force == "yes"
                if not conflicted or forceDelete:
                    if className == "cdb_folder_item":
                        error = self._deleteFolderItem(objectToDelete)

                    elif className == "cdb_file":
                        error = self._deleteFileItem(objectToDelete)

                    elif className == "cdb_link_item":
                        error = self._deleteLinkItem(objectToDelete)
                        if error is None and not teamspaceId:
                            # try to determine the linked doc id from attrs
                            linkedDocId = attrs.get("cdb_link", objectToDelete.cdb_link)
                            self._deleteDocRelEntry(theDoc, linkedDocId)
                            if theDoc is not None and linkedDocId is not None:
                                target = self._getLinkTarget(linkedDocId)
                                if target is not None:
                                    if not isinstance(
                                        theDoc, Document
                                    ) or not isinstance(target, Document):
                                        self.objects_with_modified_reference.add(
                                            (theDoc, target, "Delete")
                                        )
                        self.potential_del_in_ts_obj_ids.add(objectToDelete.cdb_link)
                        self.potential_del_in_ts_obj_ids.add(
                            objectToDelete.cdbf_object_id
                        )
                else:
                    error = ERROR(
                        msg=tr(
                            "requested deletion failed on %1:"
                            " object was modified by another user"
                        )
                    )
                    argList = TRANSLATIONARGLIST()
                    desc = self._getFileObjectDescription(objectToDelete)
                    argList.addChild(TRANSLATIONARG(trArg=desc))
                    error.addChild(argList)

        resultValue = "error" if error else "ok"
        cmdStatus = COMMANDSTATUS(
            cdb_object_id=self._pdmFileIdToWsFileId.get(
                obj.cdb_object_id, obj.cdb_object_id
            ),
            local_id=obj.local_id,
            action=command.action,
            value=resultValue,
        )
        if error:
            cmdStatus.addChild(error)
            cntxCmdStatus = False
        else:
            cntxCmdStatus = True

        cmdStatusList.addChild(cmdStatus)
        return cntxCmdStatus

    def _getFileObjectDescription(self, fileObject):
        objectId = fileObject.cdbf_name
        if not objectId:
            objectId = fileObject.cdb_object_id
        identifier = "%s: %s" % (fileObject.cdb_classname, objectId)
        return identifier

    def _deleteFileItem(self, objectToDelete):
        error = None
        try:
            with measuringPoint("DETAIL DELETEFILE"):
                operation(
                    constants.kOperationDelete,
                    objectToDelete,
                    system_args(
                        active_integration=u"wspmanager", activecad=u"wspmanager"
                    ),
                )
        except Exception as ex:
            error = ERROR(msg=tr("requested deletion failed on %1: %2"))
            argList = TRANSLATIONARGLIST()
            desc = self._getFileObjectDescription(objectToDelete)
            argList.addChild(TRANSLATIONARG(trArg=desc))
            argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
            error.addChild(argList)
        return error

    def _deleteFolderItem(self, objectToDelete):
        error = None
        if not self.__folderIsEmpty(objectToDelete):
            # folder must be empty or sorting failed.
            # always delete bottom-up.
            error = ERROR(
                msg=tr("requested deletion failed on %1: folder is not empty")
            )
            argList = TRANSLATIONARGLIST()
            desc = self._getFileObjectDescription(objectToDelete)
            argList.addChild(TRANSLATIONARG(trArg=desc))
            error.addChild(argList)
        else:
            self.__deleteFileRecordsInFolder(objectToDelete)
            try:
                # delete empty folder
                with measuringPoint("DETAIL DELETEFOLDER"):
                    operation(
                        constants.kOperationDelete,
                        objectToDelete,
                        system_args(
                            active_integration=u"wspmanager", activecad=u"wspmanager"
                        ),
                    )
            except Exception as ex:
                error = ERROR(msg=tr("requested deletion failed on %1: %2"))
                argList = TRANSLATIONARGLIST()
                desc = self._getFileObjectDescription(objectToDelete)
                argList.addChild(TRANSLATIONARG(trArg=desc))
                argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                error.addChild(argList)
        return error

    def _deleteLinkItem(self, linkToDelete):
        error = None
        try:
            with measuringPoint("DETAIL DELETELINK"):
                operation(
                    constants.kOperationDelete,
                    linkToDelete,
                    system_args(
                        active_integration=u"wspmanager", activecad=u"wspmanager"
                    ),
                )
        except Exception as ex:
            error = ERROR(msg=tr("requested deletion of link failed: %1"))
            argList = TRANSLATIONARGLIST()
            argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
            error.addChild(argList)
        return error

    def _deleteDocRelEntry(self, theDoc, linkedDocId):
        with measuringPoint("DETAIL DELETEDOCREL"):
            targetObj = self._getLinkTarget(linkedDocId)
            # also delete cdb_doc_rel entry
            if targetObj is not None:
                if (
                    theDoc.GetTableName() == "zeichnung"
                    and targetObj.GetTableName() == "zeichnung"
                ):
                    stmt = (
                        "FROM cdb_doc_rel "
                        " WHERE z_nummer = '%s'"
                        " AND z_index = '%s'"
                        " AND z_nummer2 = '%s'"
                        " AND z_index2 = '%s'"
                        % (
                            theDoc.z_nummer,
                            theDoc.z_index,
                            targetObj.z_nummer,
                            targetObj.z_index,
                        )
                    )
                    logging.info(
                        "Deleting link ('%s', '%s') -> ('%s', '%s')",
                        theDoc.z_nummer,
                        theDoc.z_index,
                        targetObj.z_nummer,
                        targetObj.z_index,
                    )
                    logging.info("Executing stmt:\n%s", stmt)
                    sqlapi.SQLdelete(stmt)
            else:
                logging.info(
                    "cdbwsmcdmdprocessor:"
                    " Cannot remove cdb_doc_rel entry. Linked Document"
                    " with id %s cannot be found.",
                    linkedDocId,
                )

    def _deleteTSDocuments(self):
        """
        Deletes standalone team space only documents if they become standalone
        after cdb_link_items where deleted. standalone means in this case:
        team space document has no parents (there are no links pointing to this object)
        and no children (there are no links going out to other objects)
        """
        if self.potential_del_in_ts_obj_ids:
            not_deletable = set()
            for chunk in grouper(MAX_IN_ELEMENTS, self.potential_del_in_ts_obj_ids):
                valueString = u",".join(
                    u"'" + sqlapi.quote(val) + u"'" for val in chunk
                )
                # check if docs to delete are parents or children to other docs
                # query might deliver to much ids but it is ok here since those
                # ids are the used to exclude documents from deletion
                query = (
                    "SELECT cdbf_object_id, cdb_link FROM cdb_file "
                    "WHERE cdb_classname='cdb_link_item' AND"
                    " cdbf_object_id IN (%s) OR cdb_link IN (%s)"
                    % (valueString, valueString)
                )
                records = sqlapi.RecordSet2(sql=query)
                for rec in records:
                    not_deletable.add(rec.cdbf_object_id)
                    not_deletable.add(rec.cdb_link)
            ws_docs_to_del_ids = self.potential_del_in_ts_obj_ids - not_deletable
            # prefetch and cache ws_documents to be able to delete its files
            if ws_docs_to_del_ids:
                self._checkinCache.prefetchTeamspaceObjects(ws_docs_to_del_ids)
                # get TS ws_documents objects ONLY
                ws_docs_to_del = self._checkinCache.getCachedWsDocumentsById(
                    ws_docs_to_del_ids
                )
                for ws_doc_to_del in ws_docs_to_del:
                    # check if the document is TS ONLY
                    # ensure ONLY WsDocuments are deleted
                    if isinstance(ws_doc_to_del, WsDocuments):
                        if ws_doc_to_del.doc_object_id in ["", None]:
                            # delete files of ts_document
                            for ws_doc_file in ws_doc_to_del.Files:
                                ws_doc_file.delete_file()
                            # delete ts_document itself
                            ws_doc_to_del.Delete()
                        # NEAR FUTURE FOR TS/PDM TWINS
                        # else:
                        #     ws_doc_to_del.deleted_flag = 1

    def _getObjectByWspId(self, classname, cdbfObjectId, wspItemId):
        """
        cdbfObjectId: this is always the document id (never the WsDocuments id)
                      because the cache always always expects the document id
        cdb_wspitem_id is always unique for one document
        """
        # use cache
        filesOfDoc = self.checkinFilesByWspItemId.get(cdbfObjectId)
        if filesOfDoc:
            objectToReturn = filesOfDoc.get(wspItemId)
        else:
            cdbfObjectId = self._checkinCache.getTeamspaceObj(
                cdbfObjectId, cdbfObjectId
            )
            objectToReturn = self._queryCdbFileByWspId(
                classname, cdbfObjectId, wspItemId
            )
        return objectToReturn

    def _queryCdbFileByWspId(self, classname, cdbfObjectId, wspItemId):
        """
        Get cdb_file item by SQL query, without caching
        """
        objectToReturn = None
        ret = []
        condition = "cdbf_object_id = '%s' AND cdb_wspitem_id='%s'" % (
            cdbfObjectId,
            wspItemId,
        )
        if classname == "cdb_folder_item":
            ret = cdb_folder_item.Query(condition)
        elif classname == "cdb_link_item":
            ret = cdb_link_item.Query(condition)
        elif classname in ["cdb_file", "cdb_file_record"]:
            ret = cdb_file_record.Query(condition)

        try:
            objectToReturn = ret[0]
        except IndexError:
            pass
        return objectToReturn

    @timingWrapper
    @timingContext("DETAIL _getExistingItemByName")
    def _getExistingItemByName(self, doc, parentFolderId, classname, nameToCheck):
        matchingItem = None
        nameToCheck = nameToCheck.upper()
        fobject_id = doc.cdb_object_id

        # try cache first
        nameKey2item = self.checkinFilesByName.get(fobject_id)
        if nameKey2item is not None:
            nameKey = (classname, parentFolderId, nameToCheck)
            matchingItem = nameKey2item.get(nameKey)
        else:
            condition = "cdbf_object_id = '%s' AND UPPER(cdbf_name) = '%s'" % (
                fobject_id,
                sqlapi.quote(nameToCheck),
            )
            if classname == "cdb_folder_item":
                ret = cdb_folder_item.Query(condition)
            else:
                ret = cdb_file_record.Query(condition)

            for fileEntry in ret:
                if (not parentFolderId and not fileEntry.cdb_folder) or (
                    parentFolderId == fileEntry.cdb_folder
                ):
                    matchingItem = fileEntry
                    break

        return matchingItem

    def _updatePartnerName(self, command, cdbf_object_id, file_id):
        partnerNameXml = command.getFirstChildByName("PARTNERNAME")
        if partnerNameXml is not None:
            org = partnerNameXml.organization_id
            partner_filename = partnerNameXml.filename
            existing = PartnerFilename.ByKeys(file_id, org)
            if existing:
                existing.Update(partner_filename=partner_filename, generated=0)
            else:
                PartnerFilename.Create(
                    file_id=file_id,
                    organization_id=org,
                    document_id=cdbf_object_id,
                    partner_filename=partner_filename,
                    generated=0,
                )

    @timingWrapper
    @timingContext("DETAIL _insertLinkStatus")
    def _insertLinkStatus(self, command, cdbf_object_id, file_wspitem_id):
        """
        Inserts links status from command for given cdb_file.
        Deletes all old records for the cdb_file.

        :Parameters:
            command : XmlMapper
                command object from request
            cdbf_object_id : string
                a zeichnung object id
            file_wspitem_id : string
                a cdb_file wspitem id
        """
        logging.debug("+++ insertLinkStatus start")
        linksStatus = command.getLinksStatus()
        # check if update is needed
        updateAttrs = False
        currStatus = self._checkinCache.linkStatusOf(
            cdbf_object_id, file_wspitem_id, forceCaching=True
        )
        if currStatus:
            if currStatus != linksStatus:
                updateAttrs = True
        else:
            updateAttrs = bool(linksStatus)

        if updateAttrs:
            if currStatus is not None:
                sqlapi.SQLdelete(
                    "FROM cdb_file_links_status WHERE cdbf_object_id = '%s' AND file_wspitem_id = '%s'"
                    % (sqlapi.quote(cdbf_object_id), sqlapi.quote(file_wspitem_id))
                )
            # insert new entries
            for link_id, relevant in six.iteritems(linksStatus):
                rec = sqlapi.Record(
                    "cdb_file_links_status",
                    cdbf_object_id=cdbf_object_id,
                    file_wspitem_id=file_wspitem_id,
                    link_id=link_id,
                    relevant=relevant,
                )
                rec.insert()
        logging.debug("+++ insertLinkStatus finish")

    def _insertCdbfileWsm(self, cdbf_object_id, file_wspitem_id, attrs):
        """
        Inserts wsm additional data for cdb_files into cdb_file_wsm,
        e.g. manually assigned to cad-document status.

        :Parameters:
            cdbf_object_id : string
                a zeichnung object id
            file_wspitem_id : string
                a cdb_file wspitem id
            attrs : dict with values to insert into cdb_file_wsm
        """
        logging.debug("+++ _insertCdbfileWsm start")
        # delete old entries
        fileAttrs = self._checkinCache.wsmAttributesOfFile(
            cdbf_object_id, file_wspitem_id, forceCaching=True
        )
        # check if update is needed
        updateAttrs = False
        if fileAttrs:
            if attrs:
                for key, currVal in six.iteritems(fileAttrs):
                    newVal = attrs.get(key)
                    # new values are strings, current values int or None
                    if newVal == "1":
                        if not currVal:
                            updateAttrs = True
                            break
                    elif currVal:
                        updateAttrs = True
                        break
            else:
                if any(fileAttrs.values()):
                    # replace old non empty attrs by empty new attrs
                    # deleting old attrs is sufficient
                    updateAttrs = True
        else:
            updateAttrs = bool(attrs)

        if updateAttrs:
            if fileAttrs is not None:
                sqlapi.SQLdelete(
                    "FROM cdb_file_wsm WHERE cdbf_object_id = '%s' AND file_wspitem_id = '%s'"
                    % (sqlapi.quote(cdbf_object_id), sqlapi.quote(file_wspitem_id))
                )
            try:
                if attrs:
                    dbi = DBInserter("cdb_file_wsm")
                    dbi.add("cdbf_object_id", cdbf_object_id)
                    dbi.add("file_wspitem_id", file_wspitem_id)
                    for key, value in six.iteritems(attrs):
                        dbi.add(key, value)
                    dbi.insert()
            except ValueError:
                logging.exception("+++ error inserting cdb_file wsm data")

        logging.debug("+++ _insertCdbfileWsm finish")

    def inform_other_modules_link_action_performed(self):
        """
        Emits a "wsd_reference_action" signal if cdb_link_item action
        is performed creating/deleting a reference between two pdm objects.
        This signal allows other modules to maintain own references between objects
        e.g. References between cs.sdm Variants and CAE Documents or other Variants

        :param src_object: object framework object
        :param dst_object: object framework object
        :param action_name: String describing the performed action Create/Delete
        """
        sig.emit("ws_reference_action")(self.objects_with_modified_reference)
