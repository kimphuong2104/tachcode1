#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import itertools
import logging

from collections import defaultdict

import six

from cdb import sqlapi, util
from cdb import auth, CADDOK
from cdb.objects import ByID
from cdb.objects.cdb_file import cdb_file_base
from cs.platform.cad import Frame
from cs.documents import Document
from cs.vp.items import Item
from cdb.platform.acs import RelshipAccessProfileMapping
from cdb.platform.olc import StateDefinition
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cdbwrapc import Query

from cs.workspaces import WsDocuments
from cs.workspaces.sqlutils import MAX_IN_ELEMENTS, MAX_PAIRS, partionedSqlQuery

sdm_modules_installed = False
try:
    from cs.sdm.document import CAEDocument
    from cs.sdm.variant import Variant, Variant2CAEDocument

    sdm_modules_installed = True
except ImportError:
    pass


def grouper(n, iterable):
    """
    Yields n length chunks from given iterable

    https://docs.python.org/2/library/itertools.html
    https://stackoverflow.com/questions/8991506/iterate-an-iterator-by-chunks-of-n-in-python
    """
    it = iter(iterable)
    if n is not None:
        n = int(n)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


class WsObjectCache(object):
    """
    A cache for Object Framework objects.
    Only valid during one user exit run.

    The difference to the normal object cache:
      - can retrieve multiple objects at once (given a list of ids)
      - always retrieves all files of retrieved business objects at once
      - optionally retrieves access rights in a more efficient but less general
        way

    Note: the access to files and rights is only cached
          if the associated business objects (mostly documents) were cached before
          with calls to getObjectsById or prefetchObjects.
    """

    IGNORED_CDBFILEWSM_KEYS = ["cdb_object_id", "cdbf_object_id", "file_wspitem_id"]

    def __init__(
        self,
        simplifiedRightsCheck,
        doRightsCheck=True,
        extendedCaching=False,
        fileCaching=True,
        lang=None,
        workspaceId=None,
        persno=None,
    ):
        """
        :param simplifiedRightsCheck: Boolean
          If True, rights are indirectly checked using a RecordSet2. This
           does not support every configuration. Files inherit the rights from
           their document/business object.
          If False, every object (business objects and files) is checked
           in isolation, using Object.CheckAccess.
        :param doRightsCheck: Boolean
          If True rights checks are processed, else no rights checks are processed
        :param extendedCaching: Boolean
          If True, also caches linked documents, items of documents, indexes and
           extended information about files
        :param: fileCaching: Boolean
           caches cdb_files if true
        :param workspaceId: string
           optional cdb_object_id of Workspace; if given, teamspace contents (WsDocuments) will be considered
        :param persno: string
          Optional name of the user; if not given, the current user will be taken (cdb.auth.persno)
        """
        self._objects = {}  # cdb_object_id -> Object
        self._files = defaultdict(list)  # cdb_object_id -> list(cdb_file_base)
        self._objectRights = {}  # cdb_object_id -> dict(access->Bool)
        self._simplifiedRightsCheck = simplifiedRightsCheck
        self._doRightsCheck = doRightsCheck
        self.updateObjectHandles = True

        # cache part data and document indexes
        self._extendedCaching = extendedCaching
        # cache cdb_file entries
        self._fileCaching = fileCaching
        # cache additional cdb_file attributes, e.g. 'manual assigned'
        # or 'additional cad reference' flag
        self._fileAttributesCaching = extendedCaching
        # cache additional cdb_link_item information, e.g. the relevance of
        # a additional cad reference
        self._linkStatusCaching = extendedCaching
        self._workspaceId = workspaceId

        # cache Items/part objects
        self.cacheItems = True
        # keeps Items to prevent GC. Needed e.g. if accessing obj.Item
        self._items = []

        # cache Item cdb_mdates
        self.cacheItemMDates = False
        self._itemMDates = {}

        self._indexes = defaultdict(
            list
        )  # z_nummer -> list(Record), sorted by ixsm property
        self._fileAttributes = {}  # (cdb_object_id, cdb_wspitem_id) -> dict

        self._linkStatus = {}  # (cdb_object_id, cdb_wspitem_id) -> (linkId -> "0"|"1")
        self._indexFilterResults = (
            {}
        )  # dict with z_nummer to list of tuples with filter results

        # if self._workspaceId is given, this will contains the "teamspace" contents
        # (mapping from the cdb_object_id of a BObject to the ws_documents entry including the lock attribute)
        self._pdmDocIdToWsDocId = {}  # cdb_object_id -> WsDocuments cdb_object_id
        self._wsDocIdToPdmDocId = {}  # WsDocument cdb_object_id -> cdb_objet_id
        self._wsDocIds = (
            set()
        )  # WsDocuments cdb_object_id (all WsDocuments, even those without PDM document)
        self._lockInfo = (
            {}
        )  # cdb_object_id of Document -> cdb_object_id of file -> dict

        # maps WSM object right names to CDB object right names
        self._objectRightsMapping = {
            "save": "save",
            "index": "index",
            "get": "read_file",
            "delete": "delete",
        }
        # "WSM file right names" -> "CDB object right name"
        # only needed for simplified rights checking
        self._fileRightsMapping = self._calculateFileRightMapping()

        self._rightsToRetrieve = set(
            list(six.itervalues(self._objectRightsMapping))
            + list(six.itervalues(self._fileRightsMapping))
        )
        self._status_name_cache = dict()  # (status, kind) -> string
        self._frames = {}  # framename, framegroup -> Frame

        self.lang = lang or CADDOK.ISOLANG
        # iterable with cdb_file attribute names. if set, cache uses
        # FileAttributes instead of cdb.object instances
        self.limitedFileAttrs = ()

        # the user which will access the documents by persno,
        # basically used for testing
        if persno is None:
            persno = auth.persno
        self.access_persno = persno

    def setUpdateObjectHandles(self, updateObjectHandles):
        self.updateObjectHandles = updateObjectHandles

    def setFileAttributesCaching(self, fileAttributesCaching):
        self._fileAttributesCaching = fileAttributesCaching

    def setLinkStatusCaching(self, linkStatusCaching):
        self._linkStatusCaching = linkStatusCaching

    def getObjectsByID(self, ids, alsoFetchLinkedObjects=False):
        """
        @param ids list(cdb_object_id)
        :returns: list of Objects, in no particular order
        """
        result = []
        missing = []
        for objId in ids:
            obj = self._objects.get(objId)
            if obj is not None:
                result.append(obj)
            else:
                missing.append(objId)
        if missing:
            result.extend(
                six.itervalues(self._fetchObjectsByID(missing, alsoFetchLinkedObjects))
            )

        return result

    def getObjectById(self, objId):
        ret = None
        objs = self.getObjectsByID([objId])
        if len(objs) == 1:
            ret = objs[0]
        return ret

    def prefetchObjects(self, ids, alsoFetchLinkedObjects=True):
        """
        Make sure all objects for the given id are in the cache.
        This method is for documents or document-like objects.
        @param ids list(cdb_object_id)
        @param alsoFetchLinkedObjects whether to cache all linked docs (transitively)
        :returns None
        """
        _ = self.getObjectsByID(ids, alsoFetchLinkedObjects=alsoFetchLinkedObjects)

    def _updateCacheWithTeamspaceObjects(self, wsDocs):
        if wsDocs:
            self._objects.update(wsDocs)
            self._wsDocIds.update(set(wsDocs))
            for objId, wsDoc in six.iteritems(wsDocs):
                pdmDocId = wsDoc.doc_object_id
                if pdmDocId:
                    self._pdmDocIdToWsDocId[pdmDocId] = objId
                    self._wsDocIdToPdmDocId[objId] = pdmDocId

    def prefetchAllTeamspaceObjects(self):
        if self._workspaceId:
            wsDocs = getAllWsDocuments(self._workspaceId)
            self._updateCacheWithTeamspaceObjects(wsDocs)

    def prefetchTeamspaceObjects(self, ids):
        if self._workspaceId:
            wsDocs = getWsDocumentsById(ids, self._workspaceId)
            self._updateCacheWithTeamspaceObjects(wsDocs)

    def prefetchTeamspaceObjectsByDocId(self, ids):
        if self._workspaceId:
            unknownIds = set(ids) - set(self._pdmDocIdToWsDocId)
            wsDocs = getWsDocumentsById(
                list(unknownIds), self._workspaceId, idAttr="doc_object_id"
            )
            self._updateCacheWithTeamspaceObjects(wsDocs)

    def _getCachedObjects(self, ids):
        objs = []
        for objId in ids:
            obj = self.getCachedObject(objId)
            if obj is not None:
                objs.append(obj)
        return objs

    def getCachedWsDocuments(self):
        return self._getCachedObjects(self._wsDocIds)

    def getCachedWsDocumentsById(self, ids):
        return self._getCachedObjects(ids)

    def getCachedWsDocumentsByDocId(self, ids):
        wsDocIds = set()
        for docId in ids:
            wsDocId = self.getTeamspaceObj(docId)
            if wsDocId is not None:
                wsDocIds.add(wsDocId)
        return self._getCachedObjects(wsDocIds)

    def getCachedObject(self, objId):
        """
        @param id cdb_object_id
        :returns Object or None
        """
        return self._objects.get(objId)

    def getTeamspaceObj(self, objId, default=""):
        """
        If a teamspace object exists for the given business object,
         and teamspace contents were requested,
        returns the id of the teamspace object.

        :param objId: cdb_object_id of BObject
        :return: cdb_object_id of WsDocuments or default
        """
        return self._pdmDocIdToWsDocId.get(objId, default)

    def getLockInfo(self, doc_object_id, file_object_id, wspLockId):
        """
        :param doc_object_id: str
        :param file_object_id: str
        :param wspLockId: str
        :return: dict or None
        """
        lockInfo = None
        lockInfoOfDoc = self._lockInfo.get(doc_object_id)
        if lockInfoOfDoc is None:
            self.getLockInfoOfNonDerivedFiles([doc_object_id], wspLockId)
            lockInfoOfDoc = self._lockInfo.get(doc_object_id)
        if lockInfoOfDoc:
            lockInfo = lockInfoOfDoc.get(file_object_id)
        return lockInfo

    def workspaceItemsOf(self, objId):
        """
        @param id cdb_object_id of a business object
            the business object is expected to be in the cache;
            otherwise a warning is logged and the object is added to the cache
        :returns list(cdb_file_base) or list(LimitedFileItem)
        """
        self._ensureCached(objId)
        if objId not in self._files:
            self._retrieveWorkspaceItemsOf([objId])
        return self._files[objId]

    def getCachedWorkspaceItems(self):
        return self._files

    def rightsOfBusinessObject(self, obj):
        """
        :param obj Document, Frame or similar
        :returns dict(access->Bool)
        """
        wsmRights = {}

        if self._doRightsCheck:
            cdbRights = self._cdbRightsOfBusinessObject(obj)
            wsmRights = self.mapToWsmObjectRights(cdbRights)

        return wsmRights

    def rightsOfFile(self, fileObj):
        """
        :param fileObj: cdb_file_base (or derived)
        :return: dict(access->Bool)
        """
        wsmRights = {}
        if self._doRightsCheck:
            cdbf_object_id = fileObj.cdbf_object_id
            self._ensureCached(cdbf_object_id)

            if self._simplifiedRightsCheck:
                bobj = self._objects[cdbf_object_id]
                cdbRights = self._cdbRightsOfBusinessObject(bobj)
            else:
                objectId = fileObj.cdb_object_id
                cdbRights = self._objectRights.get(objectId)
                if cdbRights is None:
                    cdbRights = self._rightsOfObject(fileObj)
                    self._objectRights[objectId] = cdbRights

            wsmRights = self.mapToWsmFileRights(cdbRights)

        return wsmRights

    def indexesOfDocument(self, doc):
        """
        :param doc: Document or Workspace
        :return: list of Document (or None if extended caching disabled)
        """
        indexes = []
        zNum = doc.z_nummer
        if zNum not in self._indexes:
            self._retrieveIndexesOf([doc])
        all_indexes = self._indexes[zNum]
        # return only readable indexes
        for index in all_indexes:
            if index.cdb_object_id in self._objectRights:
                cdbRights = self._objectRights.get(index.cdb_object_id)
                wsmRights = self.mapToWsmObjectRights(cdbRights)
                isReadable = wsmRights.get("get", False)
                if isReadable:
                    indexes.append(index)
            else:
                # without rights check: add all indexes
                indexes.append(index)
        return indexes

    def wsmAttributesOfFile(self, cdbf_object_id, cdb_wspitem_id, forceCaching=False):
        """
        :return: dict (or None if caching disabled or not existing)
        """
        if self._fileAttributesCaching or forceCaching:
            if self._linkStatusCaching:
                self._ensureCached(cdbf_object_id)
            elif forceCaching:
                mappedIds = {cdbf_object_id: cdbf_object_id}
                self._retrieveFileAttributesOf(
                    mappedIds,
                    addtl="AND file_wspitem_id='%s'" % sqlapi.quote(cdb_wspitem_id),
                )
            return self._fileAttributes.get(
                (cdbf_object_id, cdb_wspitem_id),
            )
        else:
            return None

    def linkStatusOf(self, cdbf_object_id, cdb_wspitem_id, forceCaching=False):
        """
        :return: dict(link_id -> "0"|"1") (or None if caching disabled or not existing)
        """
        if self._linkStatusCaching or forceCaching:
            if self._linkStatusCaching:
                self._ensureCached(cdbf_object_id)
            elif forceCaching:
                mappedIds = {cdbf_object_id: cdbf_object_id}
                self._retrieveLinkStatusOf(
                    mappedIds,
                    addtl="AND file_wspitem_id='%s'" % sqlapi.quote(cdb_wspitem_id),
                )
            return self._linkStatus.get(
                (cdbf_object_id, cdb_wspitem_id),
            )
        else:
            return None

    def getCdbObjectRightsAndStatusTextByID(self, ids):
        """
        Specialized method for fast server rights requests.

        @param ids list(cdb_object_id)

        :returns: tuple of
                1. nested dict cdb_object_id -> access right -> Bool
                2. dict cdb_object_id -> (attribute name,
                                          attribute value,
                                          second attribute name,
                                          second attribute value)
        """
        rights = {}
        status = {}
        if ids:
            rights = self._getRightsOfDocuments(ids, status)
            # docIds may not contain all valid document ids.
            # documents without a single access right
            # are missing or of unknown type
            # collect confirmed document ids
            # _getRightsOfDocuments gets right for "zeichnung" only
            # all other objects have only False values in rights tuple
            docIds = [
                docId
                for docId, objRights in six.iteritems(rights)
                if True in six.itervalues(objRights)
            ]
            otherIds = set(ids) - set(docIds)
            for nonDocumentId in otherIds:
                # THINKABOUT: object might already been cached
                #             could be worthwhile to look up
                #             before using ByID
                obj = ByID(nonDocumentId)
                if obj:
                    rights[nonDocumentId] = self._rightsOfObject(obj)
                    if status is not None:
                        # the object may or may not have a status text attribute
                        try:
                            statusName = self.get_status_name(
                                obj.status, obj.cdb_objektart
                            )
                            status[nonDocumentId] = (
                                "cdb_status_txt",
                                "joined_status_name",
                                statusName,
                                "status",
                                obj.status,
                            )
                        except AttributeError:
                            pass
                else:
                    logging.error(
                        "WsObjectCache.getObjectRightsByID: unknown object id '%s'.",
                        nonDocumentId,
                    )
        return rights, status

    def getLockInfoOfNonDerivedFiles(self, ids, wspLockId, includeFileRecords=False):
        """
        @param ids list(cdb_object_id of business objects)
        :returns: nested dict (bo cdb_object_id -> file cdb_object_id -> status/locker/locker_teamspace -> string)
        """
        originalIds = set(ids)
        mappedIds = self._retrieveTeamspaceContents(ids)
        allIds = list(originalIds | set(mappedIds.keys()))
        sql = """
        SELECT f.cdb_lock,
               f.cdb_lock_id,
               f.cdbf_object_id,
               f.cdb_object_id,
               f_angestellter.name AS mapped_cdb_lock_name,
               wsdoc_file.cdb_object_id AS wsdoc_file_id,
               wsdoc_file.cdb_lock AS wsdoc_cdb_lock,
               wsdoc_file.cdb_lock_id AS wsdoc_cdb_lock_id,
               wsdoc_angestellter.name AS wsdoc_mapped_cdb_lock_name
        FROM
               cdb_file f
        LEFT JOIN
               angestellter f_angestellter
        ON
               f.cdb_lock = f_angestellter.personalnummer
          --- if there is a WsDocument, we want to know the file of the the equivalent file
          LEFT JOIN
                 ws_documents ws_docs
          ON
                 ws_docs.ws_object_id = '%s' AND ws_docs.doc_object_id = f.cdbf_object_id
          LEFT JOIN
                 cdb_file wsdoc_file
          ON
                 wsdoc_file.cdbf_object_id = ws_docs.cdb_object_id
                 AND wsdoc_file.cdb_wspitem_id = f.cdb_wspitem_id
                 AND wsdoc_file.cdb_classname = 'cdb_file'
                 AND (wsdoc_file.cdb_belongsto='' OR wsdoc_file.cdb_belongsto IS NULL)
          LEFT JOIN
                 angestellter wsdoc_angestellter
          ON
                 wsdoc_file.cdb_lock = wsdoc_angestellter.personalnummer
        WHERE
               f.cdb_classname IN %s
               AND (f.cdb_belongsto='' OR f.cdb_belongsto IS NULL)
        """ % (
            sqlapi.quote(self._workspaceId or ""),
            "('cdb_file', 'cdb_file_record')" if includeFileRecords else "('cdb_file')",
        )
        records = partionedSqlQuery(sql, "f.cdbf_object_id", allIds)
        res = defaultdict(lambda: defaultdict(dict))
        for r in records:
            status = u"not"
            lockerName = u""
            locker = r.cdb_lock
            if locker:
                lockerName = r.mapped_cdb_lock_name
                if lockerName is None:
                    logging.warning(
                        "WsObjectCache, warning: file '%s' of document '%s' is locked"
                        " by unknown user '%s' (no matching name in 'angestellter')",
                        r.cdb_object_id,
                        r.cdbf_object_id,
                        locker,
                    )
                    lockerName = u""
                if locker == self.access_persno:
                    status = u"self"
                    lockId = r.cdb_lock_id
                    if lockId and wspLockId:
                        if lockId != wspLockId:
                            status = u"other_ws"
                else:
                    status = u"other"
            lockerTeamspace = r.wsdoc_cdb_lock
            if lockerTeamspace:
                lockerNameTeamspace = r.wsdoc_mapped_cdb_lock_name
                if lockerNameTeamspace is None:
                    logging.warning(
                        "WsObjectCache, warning: file '%s' of document '%s' is locked"
                        " by unknown user '%s' (no matching name in 'angestellter')",
                        r.cdb_object_id,
                        r.cdbf_object_id,
                        lockerTeamspace,
                    )
                    lockerNameTeamspace = u""
                if lockerTeamspace == self.access_persno:
                    statusTeamspace = u"self"
                    lockId = r.wsdoc_cdb_lock_id
                    if lockId and wspLockId:
                        if lockId != wspLockId:
                            statusTeamspace = u"other_ws"
                else:
                    statusTeamspace = u"other"
            else:
                statusTeamspace = None
                lockerNameTeamspace = None
            if r.cdbf_object_id in originalIds:
                # file belongs to a normal document
                # use file id from WsDocuments if it exists
                file_id = r.cdb_object_id
                if r.wsdoc_file_id:
                    file_id = r.wsdoc_file_id
                res[r.cdbf_object_id][file_id]["status"] = status
                res[r.cdbf_object_id][file_id]["locker"] = lockerName
                res[r.cdbf_object_id][file_id]["status_teamspace"] = statusTeamspace
                res[r.cdbf_object_id][file_id]["locker_teamspace"] = lockerNameTeamspace
            else:
                # file belongs to WsDocuments (teamspace)
                doc_id = mappedIds[r.cdbf_object_id]
                file_id = r.cdb_object_id
                res[doc_id][file_id]["status_teamspace"] = status
                res[doc_id][file_id]["locker_teamspace"] = lockerName
        # update cache
        self._lockInfo.update(res)
        return res

    def mapToWsmFileRights(self, cdbRights):
        """
        :param cdbRights: dict of CDB object rights -> bool
        :return: dict of WSM file rights -> bool
        """
        wsmRights = {}
        for wsmRightName, cdbRightName in six.iteritems(self._fileRightsMapping):
            wsmRights[wsmRightName] = cdbRights[cdbRightName]
        return wsmRights

    def mapToWsmObjectRights(self, cdbRights):
        """
        :param cdbRights: dict of CDB object rights -> bool
        :return: dict of WSM object rights -> bool
        """
        wsmRights = {}
        for wsmRightName, cdbRightName in six.iteritems(self._objectRightsMapping):
            wsmRights[wsmRightName] = cdbRights[cdbRightName]
        return wsmRights

    def getFrame(self, framename, framegroup):
        """
        Returns Frame object by keys
        """
        key = (framename, framegroup)
        if key in self._frames:
            frameObj = self._frames.get(key)
        else:
            frameObj = Frame.ByKeys(framename, framegroup)
            self._frames[key] = frameObj
        return frameObj

    def getItemMDate(self, teilenummer, t_index):
        return self._itemMDates.get((teilenummer, t_index))

    def getIndexFilterResult(self, zNum):
        return self._indexFilterResults.get(zNum)

    def setIndexFilterResult(self, zNum, filterResult):
        self._indexFilterResults[zNum] = filterResult

    def _ensureCached(self, objId):
        """
        If the object with the given cdb_object_id is not cached, load it
        into cache and log a warning.

        :param objId: cdb_object_id
        """
        if objId not in self._objects:
            self._fetchObjectsByID([objId])
            logging.warning(
                "WsObjectCache: object with id '%s' unexpectedly not cached.", objId
            )

    def _fetchObjectsByID(self, ids, alsoFetchLinkedObjects=False):
        if alsoFetchLinkedObjects:
            ids = self._extendWithLinkedDocuments(set(ids))
            ids = list(ids)
        # retrieving documents in one go
        docs = getDocumentsById(ids)

        if self.updateObjectHandles:
            # refresh all document object handles in the internal cache (CDB)
            # (otherwise we may get outdated values for joined attributes)
            getObjectHandlesFromObjectIDs(ids, True)

        self._objects.update(docs)

        # prefetch cdb_file objects
        if not self._fileCaching:
            # always follow links. even if ignore_links is yes,
            # the wsm needs them, e.g. for checkout
            self._retrieveWorkspaceItemsOf(ids, ("cdb_link_item",))
        else:
            self._retrieveWorkspaceItemsOf(ids)

        docIds = list(docs)
        # prefetch rights of documents in one go
        if not self._doRightsCheck:
            pass  # pass the rights checks
        elif self._simplifiedRightsCheck:
            self._retrieveRightsOf(docIds)
        # in all other cases, use CheckAccess on single objects.
        # its the most secure way to get all cases

        if self._extendedCaching:
            docObjects = list(six.itervalues(docs))

            if self.cacheItems:
                self._retrieveItemsOf(docObjects)
            elif self.cacheItemMDates:
                self.retrieveItemMDates(docObjects)

            self._retrieveIndexesOf(docObjects)

        result = docs
        nonDocIds = set(ids) - set(docIds)
        # retrieve non-documents (frames, cdb_file_base objects etc.)
        for nonDocId in nonDocIds:
            obj = ByID(nonDocId)
            if obj is not None:
                self._objects[obj.cdb_object_id] = obj
                result[obj.cdb_object_id] = obj
        return result

    def _extendWithLinkedDocuments(self, ids, visited=None):
        if visited is None:
            visited = ids
        linkedIds = getLinkedIds(ids)
        newIds = linkedIds - visited
        result = ids | newIds
        if newIds:
            result |= self._extendWithLinkedDocuments(newIds, visited | newIds)
        return result

    def _rightsOfObject(self, obj):
        rs = {}
        for cdbRight in self._rightsToRetrieve:
            if cdbRight == "read_file":
                cl = obj.GetClassDef()
                if cl and not cl.hasFiles():
                    val = obj.CheckAccess("read", self.access_persno)
                else:
                    val = obj.CheckAccess(cdbRight, self.access_persno)
            else:
                val = obj.CheckAccess(cdbRight, self.access_persno)
            rs[cdbRight] = val
        return rs

    def _cdbRightsOfBusinessObject(self, obj):
        objectId = obj.cdb_object_id
        self._ensureCached(objectId)

        cdbRights = self._objectRights.get(objectId)
        if cdbRights is None:
            cdbRights = self._rightsOfObject(obj)
            self._objectRights[objectId] = cdbRights
        return cdbRights

    def _retrieveTeamspaceContents(self, objIds):
        """
        :param objIds:  list of cdb_object_ids (of BObjects)
        :return: dict(updated cdb_object_id -> old cdb_object_id) (using the WsDocuments id if it exists)
        """
        mappedIds = {}
        if self._workspaceId:
            self.prefetchTeamspaceObjectsByDocId(objIds)
            mappedIds = self._wsDocIdToPdmDocId.copy()
        # also add a noop-mapping for BObjects without teamspace contents
        # for easier handling
        remainingIds = set(objIds) - set(self._pdmDocIdToWsDocId)
        for oldId in remainingIds:
            mappedIds[oldId] = oldId
        return mappedIds

    def _retrieveWorkspaceItemsOf(self, objIds, classNames=None):
        """
        Fills cache with cdb_file objects or LimitedFileItem
        """
        fileDict = None

        mappedIds = self._retrieveTeamspaceContents(objIds)
        updatedIds = list(mappedIds)
        if self.limitedFileAttrs:
            try:
                fileDict = self._retrieveLimitedFileItems(updatedIds, classNames)
            except Exception:
                logging.exception(
                    "WsObjectCache: fast file attributes access failed,"
                    " fallback to slow routine:"
                )
        if fileDict is None:
            fileDict = getWorkspaceItems(updatedIds, classNames)

        fileDict = {
            mappedIds[objId]: workspaceItems
            for objId, workspaceItems in fileDict.items()
        }
        self._files.update(fileDict)

        if self._fileAttributesCaching:
            self._retrieveFileAttributesOf(mappedIds)
        if self._linkStatusCaching:
            self._retrieveLinkStatusOf(mappedIds)

    def _retrieveLimitedFileItems(self, ids, classNames=None):
        """
        Collects LimitedFileItem for given business object ids

        :param ids list of cdb_object_id of business objects or WsDocuments
        :return: dict(business object id -> list(LimitedFileItem))
        """
        colStr = ", ".join(["cdb_file." + a for a in self.limitedFileAttrs])
        sql = (
            """SELECT %s, angestellter.name AS mapped_cdb_lock_name
        FROM cdb_file LEFT JOIN angestellter ON cdb_file.cdb_lock = angestellter.personalnummer
        WHERE (cdb_file.cdbf_derived_from='' OR cdb_file.cdbf_derived_from IS NULL)
        """
            % colStr
        )

        if classNames:
            clsStr = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in classNames)
            sql += u" AND cdb_classname IN (%s)" % clsStr

        fileDict = defaultdict(list)
        for chunk in grouper(MAX_IN_ELEMENTS, ids):
            valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
            condition = sql + " AND cdb_file.cdbf_object_id IN (%s)" % valueString
            records = sqlapi.RecordSet2(sql=condition)
            for rec in records:
                fAttrs = LimitedFileItem(rec)
                fileDict[fAttrs.cdbf_object_id].append(  # pylint: disable=no-member
                    fAttrs
                )

        return fileDict

    def _retrieveItemsOf(self, docs):
        """
        :param docs: list of Document
        """
        self._items.extend(getItems(docs))

    def retrieveItemMDates(self, docs):
        """
        Efficiently retrieves Item.cdb_mdate of the given documents.

        :param docs: list of Document
        """
        itemKeys = _getItemKeysFromDocs(docs)

        # for 500 max elements with a length of 10 for both teilenummer and t_index
        # the condition takes around 27.500 chars
        for chunk in grouper(MAX_PAIRS, itemKeys):
            condition = u""
            conds = []
            for teilenummer, t_index in chunk:
                conds.append(
                    "teilenummer='%s' AND t_index='%s'"
                    % (sqlapi.quote(teilenummer), sqlapi.quote(t_index))
                )
            condition = " OR ".join(conds)

            records = sqlapi.RecordSet2(
                "teile_stamm",
                condition,
                columns=["teilenummer", "t_index", "cdb_mdate"],
            )
            for r in records:
                self._itemMDates[(r.teilenummer, r.t_index)] = r.cdb_mdate

    def _retrieveIndexesOf(self, docs):
        z_nummers = {d.z_nummer for d in docs}
        z_nummers = z_nummers - set(self._indexes.keys())

        if z_nummers:
            uncachedId2Doc = {}

            indexes = getIndexes(z_nummers)
            for doc in indexes:
                self._indexes[doc.z_nummer].append(doc)

                # check if already added to objects cache
                indexObjectId = doc.cdb_object_id
                if indexObjectId not in self._objects:
                    uncachedId2Doc[indexObjectId] = doc

            # add index versions to default objects cache too (objects of type
            # Document) without retrieving indices again
            if uncachedId2Doc:
                uncachedIds = list(uncachedId2Doc)
                # Document objects and rights are always needed for indizes filtering
                self._objects.update(uncachedId2Doc)
                uncachedRightIds = set(uncachedIds) - set(self._objectRights.keys())
                if uncachedRightIds:
                    self._retrieveRightsOf(uncachedRightIds)

    def completeVersionCaching(self, doc):
        # complete a previous partial caching for a index version
        objId = doc.cdb_object_id
        objIdList = [objId]
        if objId not in self._files:
            self._retrieveWorkspaceItemsOf(objIdList)

        if self.cacheItems:
            self._retrieveItemsOf([doc])
        elif self.cacheItemMDates:
            self.retrieveItemMDates([doc])

    def get_status_name(self, status, kind):
        """
        :param status: str, z_status
        :param kind: str, z_art
        :return: str i18n status text
        """
        key = (status, kind)
        res = self._status_name_cache.get(key, "")
        if not res:
            sd = StateDefinition.ByKeys(status, kind)
            if sd:
                res = sd.StateText[self.lang]
                self._status_name_cache[key] = res
        return res

    def _retrieveFileAttributesOf(self, mappedIds, addtl=""):
        """
        Additional attributes, e.g. if a file is manual assigned
        or cdb_link_item represents a additional cad reference
        :param mappedIds dict(current id -> original id)
               addtl: SQL forwarded to RecordSet2
        """
        records = getRecordsByAttributeIn(
            "cdb_file_wsm", "cdbf_object_id", list(mappedIds), addtl
        )
        for r in records:
            original_id = mappedIds.get(r.cdbf_object_id, r.cdbf_object_id)
            key = original_id, r.file_wspitem_id
            attrs = {}
            for attrKey in r.keys():
                if attrKey not in WsObjectCache.IGNORED_CDBFILEWSM_KEYS:
                    attrs[attrKey] = r.get(attrKey)
            self._fileAttributes[key] = attrs

    def _retrieveLinkStatusOf(self, mappedIds, addtl=""):
        """
        Contains information about the relevance of a additional cad reference
        :param mappedIds dict(current id -> original id)
               addtl: SQL forwarded to RecordSet2
        """
        records = getRecordsByAttributeIn(
            "cdb_file_links_status", "cdbf_object_id", list(mappedIds), addtl
        )
        for r in records:
            original_id = mappedIds.get(r.cdbf_object_id, r.cdbf_object_id)
            key = original_id, r.file_wspitem_id
            linkStatusDict = self._linkStatus.get(key)
            if linkStatusDict is None:
                linkStatusDict = {}
                self._linkStatus[key] = linkStatusDict
            linkStatusDict[r.link_id] = r.relevant

    def _retrieveRightsOf(self, ids):
        """
        Retrieves access rights for the given documents and remembers them in
        self._object_rights.

        :param ids: list of cdb_object_ids of documents
        """
        if ids:
            self._objectRights.update(self._getRightsOfDocuments(ids))

    def _getRightsOfDocuments(self, ids, status=None):
        """
        :param ids: list of cdb_object_ids of documents
        :param status: optional dict that will receive the values of the status
                       text and status attributes for every document
                    (this is part of this method purely for performance reasons,
                     i.e. to limit the number of SQL statements)
        :return nested dict(cdb_object_id -> access right -> bool)
        """
        res = defaultdict(dict)

        tableName = "zeichnung"
        ti = util.tables[tableName]
        header = None
        attrs = set([u"cdb_object_id", u"z_status", u"z_art"])
        attrs.update(util.ACAccessSystem(tableName).get_relevant_attributes())
        joinedAttrs = u",".join(attrs)

        for chunk in grouper(MAX_IN_ELEMENTS, ids):
            idsStr = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
            stmt = u"%s FROM zeichnung WHERE cdb_object_id IN (%s)" % (
                joinedAttrs,
                idsStr,
            )
            table = sqlapi.SQLselect(stmt)
            if header is None:
                header = sqlapi.TableHeader(table, tableName)
            objIdIdx = header.colname2index.get(u"cdb_object_id")

            if status is not None:
                statusIdx = header.colname2index.get(u"z_status")
                zartTxtIdx = header.colname2index.get(u"z_art")

                for i in six.moves.range(sqlapi.SQLrows(table)):
                    objId = sqlapi.SQLstring(table, objIdIdx, i)
                    z_status = sqlapi.SQLstring(table, statusIdx, i)
                    z_art = sqlapi.SQLstring(table, zartTxtIdx, i)

                    status[objId] = (
                        "joined_status_name",
                        self.get_status_name(z_status, z_art),
                        "z_status",
                        z_status,
                    )

            for right in self._rightsToRetrieve:
                objIds = set()
                # see RecordSet implementation
                if Query.can_handle_access(tableName, right):
                    query_object = Query(ti, right, self.access_persno)
                    reduced_table = query_object.reduce_table(table)
                    for i in six.moves.range(sqlapi.SQLrows(reduced_table)):
                        objId = sqlapi.SQLstring(reduced_table, objIdIdx, i)
                        objIds.add(objId)
                # table contains object ids with access right
                for objId in objIds:
                    res[objId][right] = True
                # no access right
                for objId in set(chunk).difference(objIds):
                    res[objId][right] = False
                    if right == "read_file":
                        obj = self._objects.get(objId)
                        if obj is not None:
                            access = obj.CheckAccess(right, self.access_persno)
                            res[objId][right] = access
        return res

    def _calculateFileRightMapping(self):
        """
        Find out how to map WSM file rights to CDB object rights, using
        the Beziehungsrechteprofil of document.
        """
        res = {"save": "save", "get": "read_file", "delete": "delete", "index": "index"}
        if self._doRightsCheck:
            if self._simplifiedRightsCheck:
                profile = "Files"
                rs = sqlapi.RecordSet2(
                    "cdb_relships", "reference='cdb_file' AND referer='document'"
                )
                if rs:
                    profile = rs[0].rs_acc_prof  # pylint: disable=no-member
                res["delete"] = "save"

                # "WSM file right name" -> "CDB file right name"
                wsmFileRightToCdbFileRight = {
                    "save": u"save",
                    "get": u"read_file",
                    "delete": u"delete_file",
                }

                mappings = RelshipAccessProfileMapping.KeywordQuery(
                    rs_acc_prof=profile,
                    reference_allow=list(six.itervalues(wsmFileRightToCdbFileRight)),
                )

                for wsmFileRight, cdbFileRight in six.iteritems(
                    wsmFileRightToCdbFileRight
                ):
                    for rapMapping in mappings:
                        if rapMapping.reference_allow == cdbFileRight:
                            cdbObjectRight = rapMapping.referer_allow
                            res[wsmFileRight] = cdbObjectRight
                            break
                    else:
                        logging.info(
                            "WsObjectCache: no relationship access mapping found for file access right '%s'",
                            cdbFileRight,
                        )
        return res


def queryByAttributeIn(table, attribute, values, addtl="", columns=None):
    """
    Retrieve a list of records (contained in a list of RecordSet2s) with a

     "WHERE attribute IN (value1, ..., valueN)"

    query. Automatically splits the query if more than MAX_IN_ELEMENTS values
    are given.

    :param table unicode
      name of database table
    :param attribute: unicode
      name of attribute to check for (should probably be indexed in the db!)
    :param values: list(unicode)
      list of values to check for
    :param addtl: forwarded to RecordSet2
    :return: list of RecordsSet2
    """
    if len(values) > MAX_IN_ELEMENTS:
        values1 = values[:MAX_IN_ELEMENTS]
        values2 = values[MAX_IN_ELEMENTS:]
        records1 = queryByAttributeIn(table, attribute, values1, addtl)
        records2 = queryByAttributeIn(table, attribute, values2, addtl)
        records1.extend(records2)
        return records1

    valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in values)
    condition = u"%s IN (%s)" % (attribute, valueString)
    records = sqlapi.RecordSet2(table, condition, addtl=addtl, columns=columns)
    return [records]


def getRecordsByAttributeIn(table, attribute, values, addtl="", columns=None):
    """
    Like queryByAttributeIn but returns a list of records instead.
    """
    recordSets = queryByAttributeIn(table, attribute, values, addtl, columns)
    records = []
    for recordSet in recordSets:
        records.extend(list(recordSet))
    return records


def getObjectsById(ids, clss, idAttr="cdb_object_id", workspaceId=None):
    """
    Retrieves objects via the object framework and returns them as a dict
    (cdb_object_id -> Object).

    :param ids: A list of cdb_object_id's of the objects.
    :type ids: list(str)
    :param clss: The class which will be used to query the objects.
    :type clss: Object
    :param idAttr: Select the objects by the given id attribute.
    :type idAttr: str
    :param workspaceId: The id of the current workspace must match the teamspace
        documents.
    :type workspaceId: str
    :return: dict
    """
    docDict = {}
    for chunk in grouper(MAX_IN_ELEMENTS, ids):
        valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
        condition = u"%s IN (%s)" % (idAttr, valueString)
        if workspaceId is not None:
            condition += " AND ws_object_id='%s'" % sqlapi.quote(workspaceId)
        docs = clss.Query(condition=condition, lazy=0).Execute()
        for d in docs:
            docDict[d.cdb_object_id] = d
    return docDict


def getDocumentsById(ids):
    return getObjectsById(ids, clss=Document)


def getAllWsDocuments(wspId):
    docDict = {}
    raw_condition = "ws_object_id='%s' "
    raw_condition += "AND (doc_object_id='' OR doc_object_id IS NULL)"
    condition = raw_condition % wspId
    docs = WsDocuments.Query(condition, lazy=0).Execute()
    for d in docs:
        docDict[d.cdb_object_id] = d
    return docDict


def getWsDocumentsById(ids, workspaceId, idAttr="cdb_object_id"):
    return getObjectsById(ids, clss=WsDocuments, idAttr=idAttr, workspaceId=workspaceId)


def getWorkspaceItems(ids, classNames=None):
    """
    :param ids list of cdb_object_id of business objects
    :param classNames optional sequence of class names; otherwise, all entries are returned
    :return: dict(business object id -> list(cdb_file_base))
    """
    fileDict = defaultdict(list)
    addtl = u" AND (cdbf_derived_from IS NULL or cdbf_derived_from='')"
    if classNames:
        addtl += u" AND cdb_classname IN (%s)" % u",".join(
            u"'" + sqlapi.quote(className) + u"'" for className in classNames
        )

    for chunk in grouper(MAX_IN_ELEMENTS, ids):
        valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
        condition = u"cdbf_object_id IN (%s)" % valueString
        condition += addtl
        # not lazy to avoid a possible COUNT statement
        files = cdb_file_base.Query(condition=condition, lazy=0)
        for f in files:
            fileDict[f.cdbf_object_id].append(f)
    return fileDict


class LimitedFileItem(object):
    def __init__(self, rec):
        self.__dict__.update(six.iteritems(rec))

    def __getitem__(self, item):
        return self.__dict__[item]


def getItems(docs):
    """
    Efficiently retrieves all items of the given documents.

    :param docs: list of Document
    :return: list of Item
    """
    itemKeys = _getItemKeysFromDocs(docs)

    items = []
    # for 500 max elements with a length of 10 for both teilenummer and t_index
    # the condition takes around 27.500 chars
    for chunk in grouper(MAX_PAIRS, itemKeys):
        condition = u""
        conds = []
        for teilenummer, t_index in chunk:
            conds.append(
                "teilenummer='%s' AND t_index='%s'"
                % (sqlapi.quote(teilenummer), sqlapi.quote(t_index))
            )
        condition = " OR ".join(conds)
        # not lazy avoids a COUNT statement caused by the following list.extend
        queryResult = Item.Query(condition=condition, lazy=0)
        items.extend(queryResult)
    return items


def _getItemKeysFromDocs(docs):
    keys = set()
    for d in docs:
        teilenummer = d.teilenummer
        if teilenummer:
            t_index = d.t_index or ""
            keys.add((teilenummer, t_index))
    return keys


def getIndexes(z_nummers):
    """
    Get all indexes of the given documents.
    Sorted first by document, then by "ixsm" property.

    :param z_nummers: non-empty list of z_nummer strings
    :return: list of Document
    """
    sortCriteria = util.get_prop("ixsm")
    if not sortCriteria:
        sortCriteria = "z_index"
    sortCriteria = "ORDER BY z_nummer, %s" % sortCriteria

    indexDocs = []
    for chunk in grouper(MAX_IN_ELEMENTS, z_nummers):
        valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
        condition = u"z_nummer IN (%s)" % valueString

        docs = Document.Query(condition=condition, addtl=sortCriteria, lazy=0)
        indexDocs.extend(docs)
    return indexDocs


def getLinkedIds(ids):
    """
    :param ids: set of cdb_objects_ids of documents
    :return: set of cdb_objects_ids of documents directly linked
    """
    onlyLinks = " AND cdb_classname = 'cdb_link_item'"
    linkItems = getRecordsByAttributeIn(
        "cdb_file", "cdbf_object_id", list(ids), addtl=onlyLinks, columns=["cdb_link"]
    )
    linkedIds = {l.cdb_link for l in linkItems if l.cdb_link}
    return linkedIds


def retrieveWsDocuments(wspId, objIds, idAttr=None):
    """
    :param wspId: string
    :param objIds: list of Document cdb_object_id
    :return: dict(WsDocuments cdb_object_id -> (Document cdb_object_id, WsDocuments create_object_id)
    """
    wsDocs = {}
    if idAttr is None:
        idAttr = "doc_object_id"
    raw_condition = "ws_object_id='%s' AND " + idAttr + " IN (%s)"
    for chunk in grouper(MAX_IN_ELEMENTS, objIds):
        valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in chunk)
        condition = raw_condition % (sqlapi.quote(wspId), valueString)
        wsdocs = WsDocuments.Query(condition, lazy=0).Execute()
        wsDocs.update(wsdocs)
    return wsDocs
