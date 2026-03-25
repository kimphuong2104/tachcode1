# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

import logging
import six

from cdb import sqlapi
from cdb.objects.cdb_file import cdb_file_base
from cdb.objects.cdb_file import cdb_file_record
from cdb.objects.operations import operation, system_args
from cdb.constants import kOperationDelete, kOperationNew  # @UnresolvedImport

from cs.documents import Document
from cs.workspaces import WsDocuments
from cs.wsm.cdbfilewsm import Cdb_file_wsm
from cs.wsm.cdbfilelinksstatus import Cdb_file_links_status
from cs.wsm.pkgs.checkincommand_utils import copyFileObjectsToTeamspace
from cs.wsm.pkgs.pkgsutils import tr
from cs.wsm.pkgs.xmlmapper import (
    COMMANDSTATUS,
    ERROR,
    TRANSLATIONARGLIST,
    TRANSLATIONARG,
)


class CheckinCommandPublisher(object):
    """
    This class publishes teamspace objects (WsDocuments) with their files, links and folders
    to the "real" PDM documents.

    This class is mutually dependent on class CheckinCommand.
    """

    def __init__(self, checkinCommand, checkinCache, wsObj):
        """
        :param checkinCommand: CheckinCommand
        :param checkinCache: WsObjectCache
        """
        self.checkinCommand = checkinCommand
        self._checkinCache = checkinCache
        self._wsObj = wsObj

    def publishTeamspaceObject(
        self, wsCmdContextObj, theDoc, teamspaceId, commandStatusList, commitAction
    ):
        """
        Publish a single teamspace document.

        :param wsCmdContextObj: XML mapper element for document
        :param theDoc: Document
        :param teamspaceId: WsDocuments id
        :param commandStatusList: XML mapper element receiving publishing command errors
        :return: bool (success)
        """
        if commitAction == "COPY":
            fullSuccess = True
        else:
            fullSuccess, _mappedFileIds = self._syncFromTeamspace(
                wsCmdContextObj, theDoc, teamspaceId, commandStatusList
            )
        if fullSuccess:
            self._deleteTeamspaceContent(teamspaceId)
        return fullSuccess

    def _syncFromTeamspace(
        self, wsCmdContextObj, theDoc, teamspaceId, commandStatusList
    ):
        """
        :param wsCmdContextObj: XML mapper element for document
        :param theDoc: Document
        :param teamspaceId: WsDocuments id
        :param commandStatusList: XML mapper element receiving publishing command errors
        :return: bool (success), dict(cdb_object_id of TS file -> cdb_object_id of PDM file)
        """
        if theDoc.Files:
            # cdb_file
            fullSuccess, mappedFileIds = self._syncFileBasedObjects(
                theDoc, teamspaceId, commandStatusList
            )
        else:
            # copy cdb_file entries from teamspace doc to pdm doc;
            # this happens only when new PDM document was created
            mappedFileIds = copyFileObjectsToTeamspace(
                teamspaceId, theDoc.cdb_object_id, cache=self._checkinCache
            )
            fullSuccess = True
        # cdb_file_wsm
        self._syncRelation(Cdb_file_wsm, "file_wspitem_id", theDoc, teamspaceId)
        # cdb_file_links_status
        self._syncRelation(
            Cdb_file_links_status, "file_wspitem_id", theDoc, teamspaceId
        )
        # create new link for newly created pdm objects from teamspace objects
        self._linkToWorkspace(teamspaceId, theDoc)
        self._updateLinks(teamspaceId, theDoc)
        # update document attributes, now without teamspaceId to write directly to PDM
        commandStatusError = self.checkinCommand._updateMetaData(
            wsCmdContextObj, theDoc, teamspaceId=None
        )
        if commandStatusError is not None:
            commandStatusList.addChild(commandStatusError)
            fullSuccess = False
        return fullSuccess, mappedFileIds

    def _deleteTeamspaceContent(self, teamspaceId):
        """
        :param teamspaceId: WsDocuments cdb_object_id
        """
        # TODO: Think about how to delete more data in batch
        if self._checkinCache is not None:
            wsDoc = self._checkinCache.getCachedObject(teamspaceId)
        else:
            wsDoc = WsDocuments.ByKeys(cdb_object_id=teamspaceId)
        if wsDoc is not None:
            sqlapi.SQLdelete(
                "FROM cdb_file WHERE cdbf_object_id = '%s'"
                % sqlapi.quote(wsDoc.cdb_object_id)
            )
            sqlapi.SQLdelete(
                "FROM cdb_file_wsm WHERE cdbf_object_id = '%s'"
                % sqlapi.quote(wsDoc.cdb_object_id)
            )
            sqlapi.SQLdelete(
                "FROM cdb_file_links_status WHERE cdbf_object_id = '%s'"
                % sqlapi.quote(wsDoc.cdb_object_id)
            )
            wsDoc.Delete()

    def _syncFileBasedObjects(self, theDoc, teamspaceId, commandStatusList):
        """
        Sync files, folders and links.
        :return: bool, dict(teamspace file object id -> PDM file object id)
        """
        fullSuccess = True
        mappedFileIds = {}
        newObjs, deletedObjs, changedObjs = self._compareObjects(
            cdb_file_base, "cdb_wspitem_id", theDoc.cdb_object_id, teamspaceId
        )
        # sync modified objects
        for pdmObj, (tsObj, changedAttrs) in changedObjs.items():
            try:
                mappedFileIds[tsObj.cdb_object_id] = pdmObj.cdb_object_id
                operation(
                    "CDB_Modify",
                    pdmObj.ToObjectHandle(),
                    system_args(
                        active_integration=u"wspmanager", activecad=u"wspmanager"
                    ),
                    **changedAttrs
                )
                if pdmObj.cdb_classname == "cdb_link_item":
                    if "cdb_link" in changedAttrs:
                        self.checkinCommand._updateDocRelEntry(
                            theDoc, tsObj.cdb_link, pdmObj._cdb_link
                        )
            except Exception as ex:
                fullSuccess = False
                logging.exception(
                    u"CDB_Modify for %s failed: ", pdmObj["cdb_classname"]
                )
                cmdStatus = COMMANDSTATUS(
                    cdb_object_id=pdmObj.cdb_object_id,
                    local_id=pdmObj["cdb_wspitem_id"],
                    action="modify",
                    value="error",
                )
                statusError = ERROR(
                    msg=tr("Publishing modified file-based object failed: %1")
                )
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                statusError.addChild(argList)
                cmdStatus.addChild(statusError)
                commandStatusList.addChild(cmdStatus)

        # create new objects in PDM
        newObjs = self._sortFileObjectsByPath(newObjs, key=lambda o: o[0])
        for (tsObj, newObj) in newObjs:
            cls = newObj["cdb_classname"]
            try:
                if cls != "cdb_file":
                    # workaround: some attributes are deliverd by GetFieldNames
                    # even when they are not approbiate for the class
                    for attr in [
                        "cdbf_blob_id",
                        "cdbf_hidden",
                        "cdbf_derived_from",
                    ]:
                        newObj.pop(attr, None)
                    # end of workaround
                newObj["cdbf_object_id"] = theDoc.cdb_object_id
                if cls == "cdb_file_record":
                    # file records are always created without operations
                    fileObj = cdb_file_record.Create(**newObj)
                else:
                    fileObj = operation(
                        kOperationNew,
                        cls,
                        system_args(
                            active_integration=u"wspmanager", activecad=u"wspmanager"
                        ),
                        **newObj
                    )
                mappedFileIds[tsObj.cdb_object_id] = fileObj.cdb_object_id
                if cls == "cdb_link_item":
                    cdb_link = newObj["cdb_link"]
                    target = self.checkinCommand._getLinkTarget(cdb_link)
                    if target:
                        self.checkinCommand._createDocRelEntry(theDoc, target)
            except Exception as ex:
                fullSuccess = False
                logging.exception(u"CBB_Create for %s failed: ", cls)
                cmdStatus = COMMANDSTATUS(
                    cdb_object_id="",
                    local_id=newObj["cdb_wspitem_id"],
                    action="add",
                    value="error",
                )
                statusError = ERROR(
                    msg=tr("Publishing new file-based object failed: %1")
                )
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                statusError.addChild(argList)
                cmdStatus.addChild(statusError)
                commandStatusList.addChild(cmdStatus)
                if cls == "cdb_folder_item":
                    # if we could not create the folder, don't try to create subelements
                    break

        # delete objects in PDM
        deletedObjs = self._sortFileObjectsByPath(deletedObjs, reverse=True)
        for deletedObj in deletedObjs:
            try:
                classname = deletedObj.cdb_classname
                target = deletedObj.cdb_link
                operation(
                    kOperationDelete,
                    deletedObj,
                    system_args(
                        active_integration=u"wspmanager", activecad=u"wspmanager"
                    ),
                )
                if classname == "cdb_link_item":
                    self.checkinCommand._deleteDocRelEntry(theDoc, target)
            except Exception as ex:
                fullSuccess = False
                cmdStatus = COMMANDSTATUS(
                    cdb_object_id=deletedObj["cdb_object_id"],
                    local_id=deletedObj["cdb_wspitem_id"],
                    action="delete",
                    value="error",
                )
                statusError = ERROR(
                    msg=tr("Publishing of deleted file-based object %1 failed: %2")
                )
                argList = TRANSLATIONARGLIST()
                desc = self.checkinCommand._getFileObjectDescription(deletedObj)
                argList.addChild(TRANSLATIONARG(trArg=desc))
                argList.addChild(TRANSLATIONARG(trArg=six.text_type(ex)))
                statusError.addChild(argList)
                cmdStatus.addChild(statusError)
                commandStatusList.addChild(cmdStatus)
        return fullSuccess, mappedFileIds

    def _sortFileObjectsByPath(self, objs, key=lambda o: o, reverse=False):
        """
        Sort cdb_file_base objects so that they will be created/deleted in the right order.
        """
        fileObjByWspItemId = {key(o).cdb_wspitem_id: key(o) for o in objs}
        cache = {}  # cdb_wspitem_id -> relpath

        def getRelPath(cdb_wspitem_id):
            relPath = cache.get(cdb_wspitem_id)
            if relPath is not None:
                return relPath
            o = fileObjByWspItemId[cdb_wspitem_id]
            relPath = (o.cdbf_name or "",)
            if o.cdb_folder:
                parentRelPath = getRelPath(o.cdb_folder)
                relPath = parentRelPath + relPath
            cache[cdb_wspitem_id] = relPath
            return relPath

        ret = sorted(
            objs, key=lambda o: getRelPath(key(o).cdb_wspitem_id), reverse=reverse
        )
        return ret

    def _linkToWorkspace(self, teamspaceId, theDoc):
        # Update the cdb_link_item and create a new cdb_doc_rel entry
        # to link from the workspace to the document
        linkObj = cdb_file_base.ByKeys(
            cdb_link=teamspaceId, cdbf_object_id=self._wsObj.cdb_object_id
        )
        if linkObj is not None:
            args = {k: linkObj[k] for k in linkObj.keys()}
            args["cdb_link"] = theDoc.cdb_object_id
            linkObj.Update(**args)
            self.checkinCommand._createDocRelEntry(self._wsObj, theDoc)

    def _updateLinks(self, teamspaceId, theDoc):
        """
        Update all links for all parent documents and parent files,
        because we have changed the document from Teamspace document to PDM
        document for all files of the Teamspace document. Parents must link
        to the newly created PDM document and not to the Teamspace document,
        regardless if these are from Teamspace or PDM.

        Also update `cdb_doc_rel` entries if these do not yet exist
        when referencing to PDM documents.
        """
        # change all links, because cdbf_object_id of files changes and
        # thus the link targets also change
        for originalLink in cdb_file_base.KeywordQuery(
            cdb_classname="cdb_link_item", cdb_link=teamspaceId
        ):
            originalLink.Update(cdb_link=theDoc.cdb_object_id)
        # if currently published document has links, we need to create
        # cdb_doc_rel if not existing
        for originalLink in cdb_file_base.KeywordQuery(
            cdb_classname="cdb_link_item", cdbf_object_id=theDoc.cdb_object_id
        ):
            target = originalLink["cdb_link"]
            targetDocs = self._checkinCache.getObjectsByID([target])
            for targetDoc in targetDocs:
                # no links in cdb_doc_rel from pdm to teamspace!
                if isinstance(targetDoc, Document):
                    self.checkinCommand._createDocRelEntry(
                        theDoc, targetDoc, ignoreExists=True
                    )

    def _syncRelation(self, cls, idAttr, theDoc, teamspaceId):
        """
        Generic sync for DB relation.
         The relation must have the columns  cdb_object_id and cdbf_object_id,
         and some "idAttr" which identifies objects independently of the document.

        :param cls: Object Framework class
        :param idAttr: name of an attribute like "cdb_wspitem_id"
        :param theDoc: Document
        :param teamspaceId: WsDocuments id
        """
        newObjs, deletedObjs, changedObjs = self._compareObjects(
            cls, idAttr, theDoc.cdb_object_id, teamspaceId
        )
        for changedObj, (_, changedAttrs) in changedObjs.items():
            changedObj.Update(**changedAttrs)
        for (_, attrs) in newObjs:
            attrs["cdbf_object_id"] = theDoc.cdb_object_id
            cls.Create(**attrs)
        for deletedObj in deletedObjs:
            deletedObj.Delete()

    def _compareObjects(self, cls, idAttr, pdmId, teamspaceId):
        """Generic comparison for DB relation.

        The relation must have the columns ``cdb_object_id`` and
        ``cdbf_object_id``, plus some `idAttr` which identifies objects
        independently of the document.
        """
        newObjects = []  # list of tuple(teamspace obj, attribute dicts)
        deletedObjects = []  # list of objects
        changedObjects = {}  # object -> tuple(teamspace obj, dict of changed attrs)
        specialAttrs = ["cdbf_object_id", "cdb_object_id"]
        teamspaceObjects = {
            f[idAttr]: f for f in cls.KeywordQuery(cdbf_object_id=teamspaceId)
        }
        pdmObjects = {f[idAttr]: f for f in cls.KeywordQuery(cdbf_object_id=pdmId)}

        for objIdOfNew in set(teamspaceObjects) - set(pdmObjects):
            obj = teamspaceObjects[objIdOfNew]
            attrs = {
                k: obj[k]
                for k in cls.GetFieldNames()
                if k not in specialAttrs and obj[k] is not None
            }
            newObjects.append((obj, attrs))

        for objIdOfDeleted in set(pdmObjects) - set(teamspaceObjects):
            obj = pdmObjects[objIdOfDeleted]
            deletedObjects.append(obj)

        for objIdOfCommon in set(teamspaceObjects) & set(pdmObjects):
            changedAttrs = {}
            pdmObj = pdmObjects[objIdOfCommon]
            tsObj = teamspaceObjects[objIdOfCommon]
            pdmAttrs = {
                k: pdmObj[k] for k in cls.GetFieldNames() if k not in specialAttrs
            }
            tsAttrs = {
                k: tsObj[k] for k in cls.GetFieldNames() if k not in specialAttrs
            }
            for tsKey, tsVal in tsAttrs.items():
                pdmVal = pdmAttrs[tsKey]
                if tsKey not in pdmAttrs or tsVal != pdmVal:
                    if {tsVal, pdmVal} != {
                        None,
                        "",
                    }:  # None and "" should be considered equal
                        changedAttrs[tsKey] = tsVal
            if changedAttrs:
                changedObjects[pdmObj] = tsObj, changedAttrs

        return newObjects, deletedObjects, changedObjects
