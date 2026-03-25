#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     cdbobj2xml.py
# Author:   jro
# Creation: 08.12.09


"""
Module cdbobj2xml.py

Handles xml representation for file and business objects
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import hashlib
import json
import base64
import logging
import six
import datetime

from io import BytesIO

from cs.workspaces import WsDocuments
from cs.wsm.pkgs.xmlfile import xmlfile

# need this import to connect
# the method to sig module
# from cs.wsm.pkgs import generatevariantproperties

from cdb import sqlapi, ue, sig, ddl
from cdb.cad import get_data, get_bom_data, getCADConfValue
from cs.documents import Document
from cdb.objects import NULL
from cdb.objects.cdb_file import cdb_file_base
from cdb.sig import emit
from cs.vp.cad import CADVariant
from cs.wsm.pkgserrors import KnownException
from cdb import util, auth
from cdb import typeconversion
from cdb.objects.operations import operation, system_args
from cdb.constants import kOperationDelete
from cs.wsm.pkgs.xmlmapper import (
    WSCOMMANDS_CONTEXTOBJECT,
    WSCOMMANDS_OBJECT,
    ATTRIBUTES,
    HASHES,
    LOCKINFO,
    RIGHTS,
    INFO,
    NEWINDEXVERSIONS,
    NEWINDEX,
    FRAMEDATA,
    LINKSSTATUS,
    LINKSTATUS,
    BOMLIST,
    BOM,
    BOM_ITEM,
    BOM_ITEM_OCCURRENCE,
    TRANSLATIONARGLIST,
    TRANSLATIONARG,
    VARIANTPROPERTIES,
    ERROR,
    SEARCH_REFERER_RESULT,
    REFERER,
    SHEETS,
    SHEET,
    PRIOBLOBS,
)
from cs.wsm.pkgs.servertimingwrapper import timingContext, timingWrapper
from cs.wsm.pkgs.attributesaccessor import AttributesCollector, ReducedAttributes
from cs.wsm.pkgs.pkgsutils import toStringTuple, null2EmptyString, getCdbClassname, tr
from cs.wsm.pkgs.drw_helper import queryDrawingDocuments
from cs.wsm.wssrvutils import json_to_b64_str
from cs.wsm.index_helper import getIndexes
from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator.assemblycomponentoccurrence import AssemblyComponentOccurrence


NoneTypes = [NULL, None]


class DummyContext:
    action = "wsm_get_variant_attrs"
    mode = "pre"


def getLockInfoByLocker(cdbFileObj, wspLockId):
    """
    Return lock information for the given cdb_object_id

    :Parameters:
       cdbFileObj: cdbObject of class cdb_file

       wspLockId: unicode string

    :Return:
        status : lock state
        locker : string
            lockers personal id

    lock state has one of the following values
    cdbwrapc.lockStateNo = not locked
    cdbwrapc.lockStateOther = locked by another person
    cdbwrapc.lockStateOtherWspInstance = locked in another workspace
    cdbwrapc.lockStateSelf = locked by self
    cdbwrapc.lockStateWspInstance = locked by self in this workspace
    """
    logging.debug("+++ getLockInfoByLocker  start")
    locker = cdbFileObj.cdb_lock

    lockState = None
    lockName = u""
    if locker:
        lockName = cdbFileObj.mapped_cdb_lock_name
        if locker == auth.persno:
            lockId = cdbFileObj.cdb_lock_id
            if lockId and wspLockId:
                if lockId != wspLockId:
                    lockState = u"other_ws"
                else:
                    lockState = u"self"
            else:
                lockState = u"self"
        else:
            lockState = u"other"
    logging.debug("+++ getLockInfoByLocker  end")
    return lockState, lockName


def buildElementWithAttributes(elementType, nameValDict):
    """
    Build an XML node containing attributes from recordDict.

    :Parameters:
        nameValDict : dictionary
            dictionary string -> string or NULL
    :Return:
        XmlMapper instance
            node of type elementType
    """
    attributesElement = elementType()
    for key, val in six.iteritems(nameValDict):
        if val in NoneTypes:
            val = u""
        elif type(val) == six.binary_type:
            val = val.decode("utf-8")
        else:
            # hope this is only int,float,
            val = six.text_type(val)
        try:
            attributesElement.setAttr(key, val)
        except ValueError:
            # value may contain control chars
            # lxml does not like control chars
            raise KnownException(
                "Forbidden character in attribute:\n"
                "Attribute: '%s'\n"
                "Value: '%s'\n\n"
                "Object: \n%s" % (key, val, nameValDict)
            )

    return attributesElement


def writeIndexes(ctx, indexes, additionalIndexAttributes):
    docsIndexVersion = NEWINDEXVERSIONS()
    with ctx.element(docsIndexVersion.etreeElem.tag, docsIndexVersion.etreeElem.attrib):
        docsIndexVersion = None
        for (
            cdbObjectId,
            zNummer,
            sortValue,
            zIndex,
            isDefault,
            status,
            statusText,
        ), doc in indexes:
            index = NEWINDEX(cdb_object_id=cdbObjectId)
            with ctx.element(index.etreeElem.tag, index.etreeElem.attrib):
                index = None
                attrVals = {
                    "z_nummer": zNummer,
                    "z_index": zIndex,
                    "sort_value": sortValue,
                    "status": status,
                    "status_text": statusText,
                    "is_default": "1" if isDefault else "0",
                }
                for additionalIndexAttr in additionalIndexAttributes:
                    try:
                        if additionalIndexAttr not in attrVals and doc is not None:
                            attrVal = doc[additionalIndexAttr]
                            attrVals[additionalIndexAttr] = attrVal
                    except AttributeError:
                        logging.error(
                            "Cannot find value for index attributes '%s'. Ignoring attribute.",
                            additionalIndexAttr,
                        )
                attributes = buildElementWithAttributes(ATTRIBUTES, attrVals)
                ctx.write(attributes.etreeElem)


class HashTypes:
    HTObject = u"object"
    HTFiles = u"files"
    HTLinkAggregateFiles = u"link_aggregate_files"
    HTLinkAggregateObjects = u"'link_aggregate_objects"


class SubTypes:
    Files = u"cdb_file"
    Links = u"cdb_link_item"
    Folder = u"cdb_folder_item"
    FileRecords = u"cdb_file_record"


class HashBuilder(object):
    def __init__(self, wsObjectCache):
        self._cache = wsObjectCache
        self._useArticleHash = self._useArticleForObjectHash()

    def getHash(self, obj):
        """
        :params:
            obj:  FObj (rootObject)

        :return: hash for given FObj
        """
        objHashValue = ""
        try:
            objHashValue = obj.cdb_mdate
            if self._useArticleHash:
                teilenummer = obj.teilenummer
                if teilenummer:
                    cdb_mdate = self._cache.getItemMDate(teilenummer, obj.t_index)

                    if cdb_mdate is None:
                        item = obj.Item
                        if item is not None:
                            cdb_mdate = obj.Item.cdb_mdate

                    if cdb_mdate is not None:
                        objHashValue = "%s %s" % (objHashValue, cdb_mdate)

        except AttributeError:
            pass

        objHash = "%s" % objHashValue
        return objHash

    def useArticleForObjectHash(self):
        return self._useArticleHash

    def _useArticleForObjectHash(self):
        try:
            mode = util.getSysKey("wsm_doc_change_detection_mode")
            return mode == "1"
        except KeyError:
            # system property does not exist
            return False


class TreeFObject(object):
    """
    Tree containing Object instances.
    """

    __slots__ = [
        "fObj",
        "indexes",
        "ownNumberKey",
        "ownSortValue",
        "objHash",
        "searchReferrerResult",
        "incomplete",
        "teamspace_obj",
    ]

    def __init__(self, fObj, allIndexes, ownNumberKey, ownSortValue, teamspace_obj):
        self.fObj = fObj
        self.indexes = allIndexes
        self.ownNumberKey = ownNumberKey
        self.ownSortValue = ownSortValue
        self.objHash = u""
        self.searchReferrerResult = None
        # integer. 1 for incomplete, if link items have been cut off
        self.incomplete = 0
        self.teamspace_obj = teamspace_obj


class XmlGenerator(object):
    CadVariantsViewName = "ws_cad_variants"
    CadVariantsViewNameFor158 = "ws_cad_variants_v"

    def __init__(
        self,
        contextStatusDict,
        skipRecordsWhileCheckout,
        ignoreLinksWhileCheckout,
        reducedAttributes,
        indexUpdateRule,
        wsLockId,
        indexLoadRule,
        cache,
        indexFilterRule,
        additionalAttributes,
        additionalIndexAttributes,
        ignoreExternalLinks,
        withBom,
        objId2BomAttrs,
        forceCheckout,
        filterFilename,
        fileCounterOnly,
        searchReferrers,
        lang,
        incompleteLinkTargets,
        webrequest,
        autoVariantConfig,
    ):
        """
        contextStatusDict: dict cdb_object_id->localStatusList)
            insert COMMANDSTATUSLIST element if cdb_object_id
            is contained in the list

        skipRecordsWhileCheckout : boolean
            if true there will be no cdb_file_records in protocol.
            needed if a real checkout is going on

        ignoreLinksWhileCheckout : boolean
            if True there will be no links followed while checking out.

        ignoreExternalLinks : boolean
            if True there will be no external links followed while checking out.

        reducedAttributes: integer
            if ReducedAttributes.ALL_ATTRIBUTES, both the returned business objects
            and file-related objects will have the total set of attributes

            if ReducedAttributes.REDUCED_ATTRIBUTES, both the returned business objects
            and file-related objects will have a reduced set of attributes
            (only those needed for a status update)

            if ReducedAttributes.LEAST_ATTRIBUTES, both the returned business objects
            and file-related objects will have the least possible set of attributes
            (cdb_object_id, cdb_wspitem_id, cdb_classname)

        indexUpdateRule : cdb_object_id of the current index update rule or empty string

        wsLockId : cdb_object_id of a workspace. needed to determine whether
            an object is locked inside of another workspace

        indexLoadRule : cdb_object_id of the current index load rule or empty string

        cache : WsObjectCache cache to be able to optimize performance

        indexFilterRule : cdb_object_id of the current index filter rule or empty string

        additionalAttributes: tuple of two sets of strings
                pdm attribute names of attributes needed by wsm (-settings).
                first entry: document attributes, second: file attributes

        filterFilename: string
            The filename to filter for when getting all files from a document.

        fileCounterOnly : bool
            Generates no elements for file objects if True, appends a file count attribute only.

        lang: string or None
            The language of Workspaces Desktop as two literals like "de" or "en".

        searchReferrers : dict
            Search additional referrer documents using this mapping (z_num of target to z_nums of referrers)

        incompleteLinkTargets : bool
            If true and argument ignoreLinksWhileCheckout is true, the server response will
            contain next level link targets too. These target objects will be
            incomplete, without having link items themselves.

        webrequest: Morepath request object may be None

        autoVariantConfig: str base64 encoded json: Configuration for automatic variant
                           generation cdbf_type to dict cadattr ->(formatstr, attrs)
        """
        self.contextStatusDict = contextStatusDict
        self.skipRecordsWhileCheckout = skipRecordsWhileCheckout
        self.ignoreLinksWhileCheckout = ignoreLinksWhileCheckout
        self.incompleteLinkTargets = incompleteLinkTargets
        self.ignoreExternalLinks = ignoreExternalLinks
        self.reducedAttributes = reducedAttributes
        self.indexRule = indexUpdateRule or indexLoadRule
        self.loadNewestIndexes = bool(indexLoadRule)
        self.indexFilterRule = indexFilterRule
        self.wsLockId = wsLockId
        self.cache = cache
        self.withBom = withBom
        self.filterFilename = filterFilename
        self.fileCounterOnly = fileCounterOnly
        self.objId2BomAttrs = objId2BomAttrs
        # set of cdb_object_id
        self._visitedFObjects = set()

        self.skippedDueInsufficientRights = set()
        self.forceCheckout = forceCheckout
        self._webrequest = webrequest
        self.attrCollector = AttributesCollector(lang, webrequest)
        if additionalAttributes:
            docAttributes, fileAttributes = additionalAttributes
            self.attrCollector.setRequestedDocAttributes(docAttributes)
            self.attrCollector.setRequestedFileAttributes(fileAttributes)
        self.additionalIndexAttributes = additionalIndexAttributes or []
        self._searchTarget2Referrers = searchReferrers
        # ids of linked documents that should be skipped, e.g. because they
        # are based on a external/additional reference. keep them to generate
        # incomplete document presentations later.
        self._skippedLinkTargets = set()
        # as requested from client: targets that should be skipped
        self._predefinedTargetsToSkip = set()
        # all MS office docs with 'frames' to fill
        # values of this dict provide requested attributes
        # as JSON
        self._docId_to_office_vars = dict()
        self._hashBuilder = HashBuilder(cache)
        self._frameBuilder = FrameBuilder(
            cache, self.attrCollector, self.reducedAttributes
        )
        self.autoVariantConfig = None
        if autoVariantConfig:
            self.autoVariantConfig = json.loads(base64.b64decode(autoVariantConfig))
            logging.debug(
                "XMLGenerator: Auto variant config: %s", self.autoVariantConfig
            )
            self._variantViewName = None
            for viewName in [self.CadVariantsViewNameFor158, self.CadVariantsViewName]:
                if ddl.View(viewName).exists():
                    self._variantViewName = viewName
                    break

    def setPredefinedTargetsToSkip(self, predefinedTargetsToSkip):
        self._predefinedTargetsToSkip = predefinedTargetsToSkip

    def setOfficeVars(self, docId_to_office_vars):
        self._docId_to_office_vars = docId_to_office_vars
        self._frameBuilder.setOfficeVars(docId_to_office_vars)

    def clearGeneratedElements(self):
        self._visitedFObjects.clear()
        self._skippedLinkTargets.clear()
        self._predefinedTargetsToSkip.clear()
        self._skippedLinkTargets = []

    @timingWrapper
    @timingContext("DETAIL generateElements")
    def generateElements(self, rootFobj, simplified=False):
        """
        Generate ElementTree.Element instances from the given rootFobj.

        :Parameters:
            rootFobj : an Object instance
                the object to generate the tree from
            simplified : bool
                use simple results, e.g. for checkout preview

        :returns: list of Elements. First element is the Element that belongs to rootFobj
        """
        logging.debug("+++ generateElements start")
        followLinks = not self.ignoreLinksWhileCheckout

        visitedKey = rootFobj.cdb_object_id
        if visitedKey not in self._visitedFObjects:

            withIndexes = not simplified
            treeObjs = self.generateObjectTree(
                rootFobj, followLinks, rootFobj, withIndexes=withIndexes
            )

            for treeObj in treeObjs:
                if simplified:
                    fObjElem = self.buildFObjectElementSimplified(treeObj)
                else:
                    treeObj.objHash = self._hashBuilder.getHash(treeObj.fObj)
                    fObjElem = self.buildFObjectElement(treeObj)

                if fObjElem is not None:
                    yield fObjElem
                    fObjElem = None

        logging.debug("+++ generateElements end")

    def generateElementsForSkippedExternalLinked(self, simplified):
        """
        Generates XML nodes for documents that should be skipped because
        of link items based on a external/additional CAD reference

        :Parameters:
            simplified : bool
                use simple results, e.g. for checkout preview
        """
        # dont follow links of incomplete targets
        self.incompleteLinkTargets = False

        # the link destination may have been added already, e.g.
        # if occurrence links exist too
        missingTargets = self._skippedLinkTargets - self._visitedFObjects

        if missingTargets:
            for linkDst in self.cache.getObjectsByID(
                missingTargets, alsoFetchLinkedObjects=False
            ):
                treeObjs = self.generateObjectTree(
                    linkDst, False, linkDst, withIndexes=False
                )
                for treeObj in treeObjs:
                    # mark incomplete. link items have been cut off.
                    treeObj.incomplete = 1

                    if simplified:
                        fObjElem = self.buildFObjectElementSimplified(treeObj)
                    else:
                        treeObj.objHash = self._hashBuilder.getHash(treeObj.fObj)
                        fObjElem = self.buildFObjectElement(treeObj)

                    if fObjElem is not None:
                        yield fObjElem
                        fObjElem = None

    def _linkIsExternal(self, linkItem):
        """
        Returns True, if document link is based on a external/additional
        CAD reference
        """
        ret = False
        if linkItem is not None:
            try:
                attrs = self.cache.wsmAttributesOfFile(
                    linkItem.cdbf_object_id, linkItem.cdb_wspitem_id
                )
                if attrs and "is_external_link" in attrs:
                    val = attrs["is_external_link"]
                    ret = val in ["1", 1]
            except Exception:
                logging.exception(
                    "cdbobj2xml._linkIsExternal: Error while"
                    " retrieving information about"
                    " cdb_link_item:"
                )
        return ret

    def generateObjectTree(
        self, fObj, followLinks, rootFobj, treeObjects=None, withIndexes=True
    ):
        """
        Creates hierarchy of business objects. Used for calculating hashes.
        :Parameters:
            treeObjects : None
                Returned list. Must not be given.

        :returns: list of TreeFObject
        """
        logging.debug("+++ generateObjectTree start")
        fObjCdbId = fObj.cdb_object_id
        self._visitedFObjects.add(fObjCdbId)
        if treeObjects is None:
            treeObjects = []

        if withIndexes:
            indexList, ownNumKey, ownIdxSortValue = getIndexes(
                fObj,
                self.indexRule,
                self.indexFilterRule,
                self.cache,
                withRecords=True,
                compatibilityMode=False,
                optimizeGivenObjectChecks=True,
            )
        else:
            indexList = []
            ownNumKey = "0"
            ownIdxSortValue = 0

        if isinstance(fObj, WsDocuments):
            teamspace_obj = fObjCdbId
        else:
            teamspace_obj = self.cache.getTeamspaceObj(fObjCdbId)

        treeObj = TreeFObject(
            fObj, indexList, ownNumKey, ownIdxSortValue, teamspace_obj
        )
        # even if a newer version will be loaded, always collect old and new index
        # version for revisions completeness
        treeObjects.append(treeObj)

        if not self.canReadDocument(fObj):
            if fObjCdbId not in self.skippedDueInsufficientRights:
                self.skippedDueInsufficientRights.add(fObjCdbId)
                rootObjKey = rootFobj.cdb_object_id
                docDesc = self._getObjectDescription(fObj)
                infoMsg = tr(
                    "The document '%1' was skipped, because no read-access rights are given. You "
                    "might have an inconsistent state, because not all documents were "
                    "checked out."
                )
                accessInfo = INFO(msg=infoMsg)
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=docDesc))
                accessInfo.addChild(argList)

                rootObjContextStatusList = self.contextStatusDict.get(rootObjKey)
                if rootObjContextStatusList is not None:
                    rootObjContextStatusList.addChild(accessInfo)

        if self.loadNewestIndexes:
            versionByLoadRule = self._getVersionByLoadRule(rootFobj, treeObj)
            if versionByLoadRule:
                versionByLoadRuleId = versionByLoadRule.cdb_object_id
                if versionByLoadRuleId not in self._visitedFObjects:
                    # Follow all links of new index version (setting followLinks to True).
                    # The new version may have new links (resp. links to documents, that
                    # are not linked from the old version) that will go missing otherwise (because
                    # not directly queried).
                    self.generateObjectTree(
                        versionByLoadRule, True, rootFobj, treeObjects
                    )

        # ignore links when getting chunks of xml
        if followLinks or self.incompleteLinkTargets:
            # collect cdb_object_id of links
            links = set()
            for wsItem in self.cache.workspaceItemsOf(fObjCdbId):
                clName = wsItem.cdb_classname
                if clName == SubTypes.Links:
                    skipLink = False
                    linkDst = wsItem.cdb_link

                    if self._predefinedTargetsToSkip:
                        if linkDst in self._predefinedTargetsToSkip:
                            # specific links should be skipped
                            skipLink = True

                    elif self.incompleteLinkTargets:
                        # all links should be skipped
                        skipLink = True

                    elif self.ignoreExternalLinks:
                        if self._linkIsExternal(wsItem):
                            # external links should be skipped
                            skipLink = True

                    if skipLink:
                        self._skippedLinkTargets.add(linkDst)
                    else:
                        if linkDst not in self._visitedFObjects:
                            links.add(linkDst)

            if links:
                # fetch linked objects
                linkedObjs = self.cache.getObjectsByID(
                    links, alsoFetchLinkedObjects=True
                )

                # add object tree of objects we have not yet seen
                for subFsObj in linkedObjs:
                    objId = subFsObj.cdb_object_id

                    if objId not in self._visitedFObjects:
                        self.generateObjectTree(
                            subFsObj, followLinks, rootFobj, treeObjects, withIndexes
                        )

        # search for referrers/drawings
        if self._searchTarget2Referrers and isinstance(fObj, Document):
            referrers = self._searchTarget2Referrers.get(fObj.z_nummer, None)
            if referrers:
                treeObj.searchReferrerResult = []
                filterCondition = "drw.z_nummer IN %s" % toStringTuple(referrers)
                modelId2Drws = queryDrawingDocuments(
                    (fObjCdbId,), drwFilterCondition=filterCondition
                )
                for drws in six.itervalues(modelId2Drws):
                    for drwDoc in drws:
                        objId = drwDoc.cdb_object_id
                        treeObj.searchReferrerResult.append(objId)
                        if objId not in self._visitedFObjects:
                            self.generateObjectTree(
                                drwDoc, followLinks, rootFobj, treeObjects, withIndexes
                            )

        logging.debug("+++ generateObjectTree start")
        return treeObjects

    def _getObjectDescription(self, doc):
        if "z_nummer" in doc:
            if doc.z_index:
                descr = u"%s - %s" % (doc.z_nummer, doc.z_index)
            else:
                descr = u"%s" % doc.z_nummer
        else:
            descr = doc.ToObjectHandle().getDesignation()
        return descr

    def _getVersionByLoadRule(self, rootFobj, treeObj):
        """
        Returns a different index version to load instead of given tree
        object, decided by index load rule
        """
        otherVersion = None
        errorMsgs = dict()

        for indexInfo, doc in treeObj.indexes:
            if (
                indexInfo.is_default
                and indexInfo.object_id != treeObj.fObj.cdb_object_id
            ):

                # ensure complete caching
                self.cache.completeVersionCaching(doc)

                errors = self._checkVersionsAnchorFileNames(
                    treeObj.fObj.cdb_object_id, indexInfo.object_id
                )
                if len(errors) == 0:
                    # expect indexes to be initialized with its Document object
                    otherVersion = doc
                else:
                    errorMsgs[indexInfo.object_id] = errors
                break

        if errorMsgs:
            self._insertLoadRuleErrorMessages(rootFobj, treeObj, errorMsgs)

        return otherVersion

    def _checkVersionsAnchorFileNames(self, versionObjId, otherVersionObjId):
        """
        Check if name of anchor files has changed between versions
        """
        errors = []
        otherVersionWspItemId2Filename = {}

        for cdbFile in self.cache.workspaceItemsOf(otherVersionObjId):
            if cdbFile.cdbf_primary == "1":
                otherVersionWspItemId2Filename[
                    cdbFile.cdb_wspitem_id
                ] = cdbFile.cdbf_name

        for cdbFile in self.cache.workspaceItemsOf(versionObjId):
            if cdbFile.cdbf_primary == "1":
                otherVersionFileName = otherVersionWspItemId2Filename.get(
                    cdbFile.cdb_wspitem_id
                )
                if (
                    otherVersionFileName is not None
                    and otherVersionFileName.lower() != cdbFile.cdbf_name.lower()
                ):
                    errors.append((cdbFile.cdbf_name, otherVersionFileName))
        return errors

    def _insertLoadRuleErrorMessages(self, rootFobj, treeObj, errorMsgs):
        rootObjKey = rootFobj.cdb_object_id
        for idxObjectId, fileList in six.iteritems(errorMsgs):
            try:
                srcDoc = treeObj.fObj
                srcDocDescription = self._getObjectDescription(srcDoc)
                idxDoc = self.cache.getObjectById(idxObjectId)
                idxDocDescription = self._getObjectDescription(idxDoc)

                fileNameLines = []
                for srcFileName, idxFileName in fileList:
                    fileNameLines.append(srcFileName + " - > " + idxFileName)
                fileNamesStr = "\n  ".join(fileNameLines)

                msg = tr(
                    "Index load rule was selected but renamed"
                    " files were found in the indexed versions.\n"
                    "Indexed version '%1' of '%2'"
                    " contains renamed files:\n\n  %3\n\n"
                    "In order to load this document,"
                    ' please select to load "as saved". '
                )

                statusError = INFO(msg=msg)
                argList = TRANSLATIONARGLIST()
                argList.addChild(TRANSLATIONARG(trArg=idxDocDescription))
                argList.addChild(TRANSLATIONARG(trArg=srcDocDescription))
                argList.addChild(TRANSLATIONARG(trArg=fileNamesStr))
                statusError.addChild(argList)

                errList = self.contextStatusDict.get(rootObjKey)
                if errList:
                    errList.addChild(statusError)
            except Exception:
                msg = tr(
                    "Index load rule was selected but renamed"
                    " files were found in the indexed versions."
                )
                statusError = INFO(msg=msg)
                errList = self.contextStatusDict.get(rootObjKey)
                if errList:
                    errList.addChild(statusError)

    @timingWrapper
    @timingContext("DETAIL getBom")
    def getBomList(self, obj):
        bomList = None
        attrs = self.objId2BomAttrs.get(obj.cdb_object_id, None)
        if attrs:
            itemsAttrNames, bomItemAttrNames = attrs
            # teilenummer and t_index of main assembly or
            # main drawing
            item = Item.ByKeys(obj.teilenummer, obj.t_index)
            if item and (itemsAttrNames or bomItemAttrNames):
                bomList = BOMLIST()
                bomElem = self.createBomForItem(
                    item.teilenummer, item.t_index, itemsAttrNames, bomItemAttrNames
                )
                if bomElem is not None:
                    bomList.addChild(bomElem)

                for variant in obj.CADVariants:
                    # also get items from variants
                    # variant_id has to be considered as well
                    if variant.teilenummer not in [NULL, None, ""]:
                        bomVarElem = self.createBomForItem(
                            variant.teilenummer,
                            null2EmptyString(variant.t_index),
                            itemsAttrNames,
                            bomItemAttrNames,
                            variant.variant_id,
                        )
                        if bomVarElem is not None:
                            bomList.addChild(bomVarElem)
        return bomList

    def _get_parsed_value(self, rec, format_str, required_attrs):
        """
        :param rec: sqlapi.Record
        :param format_str: pythpn format string
        :param required_attrs: List of attributes required attributes

        :returns string with replacements
        """
        values = self._build_format_dict(rec, required_attrs)
        logging.debug(
            "XMLGenerator:parsed_values: %s values: %s required_attrs: %s",
            format_str,
            values,
            required_attrs,
        )
        return format_str.format(**values)

    def _build_format_dict(self, db_rec, list_of_attrnames):
        format_dict = {}
        for attr in list_of_attrnames:
            format_dict[attr] = self._rec_to_string(db_rec, attr)
        return format_dict

    def _rec_to_string(self, rec, attr):
        """
        request vaulue from dbrecord and convert the value
        to string
        """
        value = rec.get(attr)
        if value is None:
            value = ""
        elif type(value) == datetime.datetime:
            value = typeconversion.to_user_repr_date_format(value)
        return value

    def _getVariantConfigValues(self, obj):
        """
        Wrapper around getVariantKonfigAttrs, to rtrieve
        correct values if auto update is configured
        """
        if self.autoVariantConfig:
            logging.debug(
                "XMLGenerator: CAD variant: Using autovariant config for %s",
                obj.erzeug_system,
            )
            variantInfos = dict()
            encodedDump = None
            # request from database
            fileTypeConfig = self.autoVariantConfig.get(obj.erzeug_system)
            if fileTypeConfig is not None:
                if self._variantViewName is not None:
                    db_recs = sqlapi.RecordSet2(
                        self._variantViewName,
                        "z_nummer='%s' and z_index='%s'"
                        % (sqlapi.quote(obj.z_nummer), sqlapi.quote(obj.z_index)),
                    )
                else:
                    # if no view is available, use a default SQL query
                    stmt = (
                        "SELECT variant_id, z_nummer, z_index, variant_name, t.*"
                        " FROM cad_variant c"
                        " LEFT JOIN teile_stamm t ON (c.teilenummer=t.teilenummer and c.t_index=t.t_index)"
                        " WHERE z_nummer='%s' AND z_index='%s'"
                    )
                    db_recs = sqlapi.RecordSet2(
                        sql=stmt
                        % (sqlapi.quote(obj.z_nummer), sqlapi.quote(obj.z_index)),
                    )
                for rec in db_recs:
                    variant_id = rec["variant_id"]
                    vproperties = []
                    for cadattr, (format_str, list_of_attrs) in fileTypeConfig.items():
                        value_str = self._get_parsed_value(
                            rec, format_str, list_of_attrs
                        )
                        vproperties.append(
                            {"id": cadattr, "type": "string", "value": value_str}
                        )
                    variantInfos[variant_id] = {"properties": vproperties}
                logging.debug("XMLGenerator: variantinfos: %s", variantInfos)
                encodedDump = json_to_b64_str(variantInfos)
            return encodedDump
        else:
            logging.debug("XMLGenerator: CAD variant: Using UE mode")
            # old by userexit call only for a single request
            return self.getVariantKonfigAttrs(obj)

    def getVariantKonfigAttrs(self, obj):
        """
        Emits a signal and collects information.
        methods connecting to this signal should return tuples:
        (
         variantId,
         list(
              {"id": name,       # name -> cad configuration name
               "value": value,   # value to be writen to cad
               "type": "string"  # json conform type
              }
             )
        )
        Wraps collected information
        in dicts/lists to be able to dump them as json and match the defined
        protocol. Json string will be encoded with base64.

        We have to match defined integration protocol.
        Json has to be as following:
          {"VariantID1":
             {"properties":
                [{"id":"value", "value":"value", "type":"string"},
                 {"id":"value", "value":"value", "type":"integer"},
                 ...]}

           "VariantID_N":
             {"properties":
                [{"id":"value", "value":"value", "type":"float"},
                 {"id":"value", "value":"value", "type":"string"},
                 ...]}
          }
          example:
          {"v1":
            {"properties":
              [{"type": "string", "id": "variant_name", "value": "v1name"},
               {"type": "int", "id": "status", "value": 100}]},

           "v2":
            {"properties":
              [{"type": "string", "id": "variant_name", "value": "v2name"},
               {"type": "int", "id": "status", "value": 100}]}}
        :Parameters: obj Document instance to get the variants for.
        :Return: base64 encoded json dump
        """
        idAndProps = []
        encodedDump = None
        if isinstance(obj, Document):
            # get variants and emit signal
            for variant in obj.CADVariants:
                # emit the signal
                idAndProps.extend(
                    emit(Document, CADVariant, "wsm_get_variant_attrs")(
                        obj, variant, DummyContext()
                    )
                )
        # wrap collected information in dicts and lists
        idToPropsDict = dict()
        for (varId, props) in idAndProps:
            if varId and props:
                propslist = [d for d in props]
                propsDict = {"properties": propslist}
                idToPropsDict[varId] = propsDict
        try:
            # dump and encode
            encodedDump = json_to_b64_str(idToPropsDict)
        except Exception:
            logging.exception(
                "Workspaces: failed to serialize requested variant properties."
                " Properties: '%s'",
                idAndProps,
            )
        return encodedDump

    def createBomForItem(
        self, tNummer, tIndex, itemsAttrNames, bomItemAttrNames, variant_id=""
    ):
        bomElem = BOM()
        bomElem.setAttr("variant_id", variant_id)

        # now get entries from einzelteile
        bomItems = AssemblyComponent.KeywordQuery(baugruppe=tNummer, b_index=tIndex)
        if not bomItems:
            # break if there are no bom_items
            return None
        for bomItem in bomItems:
            # first get attributes of einzelteile for this bomItem
            bomCompAttrs = self.extractAttrs(bomItem, bomItemAttrNames)
            # now the teile_stamm attributes for this bomItem
            items = Item.KeywordQuery(
                teilenummer=bomItem.teilenummer, t_index=bomItem.t_index
            )
            if items and len(items) == 1:
                bomCompItem = self.extractAttrs(items[0], itemsAttrNames)
                bomCompAttrs.update(bomCompItem)
            bomItemElem = buildElementWithAttributes(BOM_ITEM, bomCompAttrs)
            bomItemOccs = bomItem.Occurrences
            if not bomItemOccs:
                logging.warning(
                    "No BOM item occurrences found in bom_item_occurrence "
                    "for BOM item '%s'",
                    bomItem,
                )
            for bomOcc in bomItemOccs:
                # deliver only the difference in keys
                occAttrNames = set()
                for occAttrName in bomOcc.keys():
                    if occAttrName not in bomItem.keys():
                        occAttrNames.add(occAttrName)
                bomItemOccurrenceElem = buildElementWithAttributes(
                    BOM_ITEM_OCCURRENCE, self.extractAttrs(bomOcc, occAttrNames)
                )
                bomItemElem.addChild(bomItemOccurrenceElem)
            bomElem.addChild(bomItemElem)
        return bomElem

    def extractAttrs(self, obj, attrNames):
        nameValDict = dict()
        keys = obj.keys()
        missingAttributes = set()
        objHandle = None
        for k in attrNames:
            if k in keys:
                nameValDict[k] = obj[k]
            else:
                if objHandle is None:
                    objHandle = obj.ToObjectHandle()
                try:
                    attrVal = objHandle.getValue(k, False)
                    nameValDict[k] = attrVal
                except KeyError:
                    missingAttributes.add(k)
        if missingAttributes:
            logging.warning(
                "Workspaces: requested PDM attributes '%s' on object '%s'"
                " were not found",
                ",".join(missingAttributes),
                obj,
            )
        return nameValDict

    def canReadDocument(self, obj, className=None):
        canReadDocument = True
        if self.forceCheckout:
            if className is None:
                className = getCdbClassname(obj)
            if className != u"cdb_wsp":
                rs = self.cache.rightsOfBusinessObject(obj)
                canReadDocument = rs.get("get")
                if not canReadDocument:
                    canReadDocument = False
        return canReadDocument

    @timingWrapper
    @timingContext("DETAIL buildFObjectElementSimplified")
    def buildFObjectElementSimplified(self, treeFObj):
        """
        Generate XML nodes from given tree objects.

        This method is a shorter version of self.buildFObjectElement
        """
        logging.debug("+++ buildFObjectElementSimplified start")
        obj = treeFObj.fObj
        fObjectId = obj.cdb_object_id
        cdbClassname = getCdbClassname(obj)
        canReadDocument = self.canReadDocument(obj, cdbClassname)
        if not canReadDocument:
            return None

        ret = BytesIO()
        with xmlfile(ret, encoding="utf-8") as ctx:
            # ------------------------------------------------------------------------ #
            #  create WSCOMMANDS_CONTEXTOBJECT node                                    #
            # ------------------------------------------------------------------------ #
            filesCount = None
            if self.fileCounterOnly:
                filesCount = self.getFileCount(fObjectId, self.skipRecordsWhileCheckout)
            ctxElement = WSCOMMANDS_CONTEXTOBJECT(
                cdb_object_id=str(fObjectId),
                file_count=filesCount,
                incomplete=treeFObj.incomplete,
                teamspace_obj=treeFObj.teamspace_obj,
                cdb_classname=cdbClassname,
            )
            with ctx.element(ctxElement.etreeElem.tag, ctxElement.etreeElem.attrib):
                ctxElement = None
                # ------------------------------------------------------------------------ #
                # create ATTRIBUTES node                                                   #
                # ------------------------------------------------------------------------ #
                nameValDict = {"cdb_object_id": fObjectId}
                try:
                    nameValDict["erzeug_system"] = treeFObj.fObj["erzeug_system"]
                except Exception:
                    pass
                attributesElement = buildElementWithAttributes(ATTRIBUTES, nameValDict)
                ctx.write(attributesElement.etreeElem)
                # ------------------------------------------------------------------------ #
                # create SEARCH_REFERER_RESULT node                                        #
                # ------------------------------------------------------------------------ #
                self._writeCollectedTarget2Referrers(treeFObj, ctx)

                if not self.fileCounterOnly:
                    # ------------------------------------------------------------------------ #
                    #  create WSCOMMANDS_OBJECT node(s)                                        #
                    # ------------------------------------------------------------------------ #
                    tmpItems = self.cache.workspaceItemsOf(fObjectId)

                    for item in tmpItems:
                        className = getCdbClassname(item)

                        if className == SubTypes.Links:
                            if not self.ignoreLinksWhileCheckout:
                                linkedObject = self.cache.getObjectById(item.cdb_link)

                                if linkedObject is None:
                                    self._deleteLeftoverLinkItem(obj, item)

                                elif self.forceCheckout:
                                    linkedBoRights = self.cache.rightsOfBusinessObject(
                                        linkedObject
                                    )
                                    if not linkedBoRights.get("get"):
                                        continue

                        if (
                            self.filterFilename
                            and not item.cdbf_name == self.filterFilename
                        ):
                            continue

                        if not (
                            self.skipRecordsWhileCheckout
                            and className == SubTypes.FileRecords
                        ):
                            try:
                                fields = self.attrCollector.getFileAttributes(
                                    item, self.reducedAttributes
                                )
                            except ue.Exception as e:
                                self._addExceptionMsg(fObjectId, treeFObj, e)
                                ret = None
                                break

                            # -------------------------------------------------------------- #
                            #  add WSCOMMANDS_OBJECT to CONTEXT_OBJECT                       #
                            # -------------------------------------------------------------- #
                            newObject = WSCOMMANDS_OBJECT(
                                cdb_object_id=item.cdb_object_id,
                                cdb_classname=className,
                            )
                            with ctx.element(
                                newObject.etreeElem.tag, newObject.etreeElem.attrib
                            ):
                                newObject = None
                                # -------------------------------------------------------------- #
                                #  create ATTRIBUTES node for WSCOMMANDS_OBJECTs                 #
                                # -------------------------------------------------------------- #
                                if fields:
                                    attributesElement = buildElementWithAttributes(
                                        ATTRIBUTES, fields
                                    )
                                    ctx.write(attributesElement.etreeElem)

                self._createCommandStatus(ctx, fObjectId)

        if ret is not None:
            ret = ret.getvalue()
        logging.debug("+++ buildFObjectElementSimplified end")
        return ret

    @timingWrapper
    @timingContext("DETAIL buildFObjectElement")
    def buildFObjectElement(self, treeFObj):
        """
        Generate XML nodes from given tree objects.
        """
        logging.debug("+++ buildFObjectElement start")
        obj = treeFObj.fObj

        cdbClassname = getCdbClassname(obj)
        canReadDocument = self.canReadDocument(obj, cdbClassname)
        if not canReadDocument:
            return None

        ret = BytesIO()
        with xmlfile(ret, encoding="utf-8") as ctx:
            fObjectId = obj.cdb_object_id
            ctxElement = WSCOMMANDS_CONTEXTOBJECT(
                cdb_object_id=str(fObjectId),
                numberkey=str(treeFObj.ownNumberKey),
                indexsortval=str(treeFObj.ownSortValue),
                incomplete=treeFObj.incomplete,
                teamspace_obj=treeFObj.teamspace_obj,
                cdb_classname=cdbClassname,
            )
            with ctx.element(ctxElement.etreeElem.tag, ctxElement.etreeElem.attrib):
                ctxElement = None

                rs = self.cache.rightsOfBusinessObject(obj)
                canReadItems = True
                canReadDocument = rs.get("get")

                # collect items first as it may generate command status messages
                try:
                    fObjectItems, infoXmlElems = self.getFObjectItems(fObjectId)
                except ue.Exception as e:
                    fObjectItems = []
                    infoXmlElems = []
                    self._addExceptionMsg(fObjectId, treeFObj, e)
                    canReadItems = False

                if not self.forceCheckout:
                    # when not skipping documents, that cannot be loaded, we
                    # want to cancel the operation and the reading of a document
                    # is dependend on the reading of its items
                    canReadDocument = canReadDocument and canReadItems
                if canReadItems or not self.forceCheckout:
                    # cancel the load operation, when force checkout is
                    # deactivated and an error occurred when loading
                    self._checkReadAccess(
                        fObjectId, treeFObj, cdbClassname, canReadDocument
                    )

                if canReadDocument:
                    frameHash = None
                    sheetsFramesHash = None
                    if isinstance(obj, Document):
                        if treeFObj.indexes:
                            self._createIndexes(ctx, treeFObj)

                        (
                            frameHash,
                            sheetsFramesHash,
                        ) = self._frameBuilder.createFrameRelated(ctx, obj)

                        if self.withBom:
                            self._createBomRelated(ctx, obj)
                        elif self.autoVariantConfig:
                            jDump = self._getVariantConfigValues(obj)
                            if jDump:
                                variantPropsElem = buildElementWithAttributes(
                                    VARIANTPROPERTIES, {"encodedproperties": jDump}
                                )
                                ctx.write(variantPropsElem.etreeElem)
                    self._createHashes(ctx, treeFObj, frameHash, sheetsFramesHash)

                rights = buildElementWithAttributes(RIGHTS, rs)
                ctx.write(rights.etreeElem)

                self._createFObjectAttributes(ctx, obj, canReadDocument, cdbClassname)

                if canReadDocument:
                    self._writeCollectedTarget2Referrers(treeFObj, ctx)
                    self._createWsCommandsObjects(ctx, obj, fObjectId, fObjectItems)

                self._createCommandStatus(ctx, fObjectId, infoXmlElems)

        fObjElem = ret.getvalue()
        logging.debug("+++ buildFObjectElement end")
        return fObjElem

    def _addExceptionMsg(self, fObjectId, treeFObj, exc):
        # When an exception occurred for a document it and will not be loaded,
        # return this exception as XML message
        errList = self.contextStatusDict.get(fObjectId)
        if errList:
            docId = self._getObjectDescription(treeFObj.fObj)
            infoMsg = tr("The document '%1' could not be loaded: %2")
            info = INFO(msg=infoMsg)
            argList = TRANSLATIONARGLIST()
            argList.addChild(TRANSLATIONARG(trArg=docId))
            argList.addChild(TRANSLATIONARG(trArg=str(exc)))
            info.addChild(argList)
            errList.addChild(info)

    def _checkReadAccess(self, fObjectId, treeFObj, cdbClassname, canReadDocument):
        if cdbClassname != u"cdb_wsp" and not canReadDocument:
            objId = self._getObjectDescription(treeFObj.fObj)
            errMsg = tr(
                "The document '%1' does not exist anymore "
                "or no read-access rights are given."
            )
            readAccessError = ERROR(msg=errMsg)
            argList = TRANSLATIONARGLIST()
            argList.addChild(TRANSLATIONARG(trArg=objId))
            readAccessError.addChild(argList)

            errList = self.contextStatusDict.get(fObjectId)
            if errList:
                errList.addChild(readAccessError)

    def _createIndexes(self, ctx, treeFObj):
        # create NEWINDEXVERSIONS node
        ownSortValue = treeFObj.ownSortValue
        newIndexes = []
        for idxInfo, doc in treeFObj.indexes:
            idxSortVal = idxInfo.sort_value
            if (idxSortVal > ownSortValue) or (
                idxInfo.is_default and idxSortVal != ownSortValue
            ):
                newIndexes.append((idxInfo, doc))
        if newIndexes:
            writeIndexes(ctx, newIndexes, self.additionalIndexAttributes)

    def _createBomRelated(self, ctx, fObj):
        # create BOM node and VARIANTPROPERTIES
        bomListElem = self.getBomList(fObj)
        if bomListElem is not None:
            with ctx.element(bomListElem.etreeElem.tag, bomListElem.etreeElem.attrib):
                for bomElem in bomListElem.etreeElem:
                    with ctx.element(bomElem.tag, bomElem.attrib):
                        for bomItemElem in bomElem:
                            with ctx.element(bomItemElem.tag, bomItemElem.attrib):
                                for occ in bomItemElem:
                                    ctx.write(occ)
                                    occ = None
                                bomItemElem = None
                        bomElem = None

        # try to get configuration properties of variants
        jDump = self._getVariantConfigValues(fObj)
        if jDump:
            variantPropsElem = buildElementWithAttributes(
                VARIANTPROPERTIES, {"encodedproperties": jDump}
            )
            ctx.write(variantPropsElem.etreeElem)

    def _createHashes(self, ctx, treeFObj, frameHash, sheetsFramesHash):
        # create HASHES node
        objHash = treeFObj.objHash
        if frameHash is not None:
            objHash = objHash + frameHash
        if sheetsFramesHash is not None:
            objHash = objHash + sheetsFramesHash
        hashesDict = {"object": objHash}
        if sheetsFramesHash:
            hashesDict["sheets_frames_hash"] = sheetsFramesHash
        hashesElem = buildElementWithAttributes(HASHES, hashesDict)
        ctx.write(hashesElem.etreeElem)

    def _createCommandStatus(self, ctx, fObjectId, infoXmlElems=None):
        # COMMANDSTATUSLIST node
        localStatusList = self.contextStatusDict.get(fObjectId)
        if localStatusList is not None:
            if infoXmlElems is not None:
                for infoXmlElem in infoXmlElems:
                    localStatusList.addChild(infoXmlElem)
            if len(localStatusList.etreeElem) > 0:
                with ctx.element(
                    localStatusList.etreeElem.tag, localStatusList.etreeElem.attrib
                ):
                    for localStatus in localStatusList.etreeElem:
                        ctx.write(localStatus)

    def _createFObjectAttributes(self, ctx, fObj, canReadDocument, cdbClassname):
        tmpFields = None

        # create ATTRIBUTES node
        if canReadDocument and cdbClassname != "ws_documents":
            requestedAttrs = self.reducedAttributes
        else:
            requestedAttrs = ReducedAttributes.LEAST_ATTRIBUTES

        if cdbClassname == "cdb_frame":
            tmpFields = self.attrCollector.getFrameAttributes(fObj, requestedAttrs)
        else:
            if cdbClassname == "ws_documents":
                objType = "WsDocument"
            elif cdbClassname == "cs_sdm_variant":
                objType = "Variant"
            else:
                objType = None
            tmpFields = self.attrCollector.getDocumentAttributes(
                fObj, requestedAttrs, objType
            )
        if tmpFields is not None:
            attributesElement = buildElementWithAttributes(ATTRIBUTES, tmpFields)
            ctx.write(attributesElement.etreeElem)

    def _createWsCommandsObjects(self, ctx, fObj, fObjectId, fObjectItems):
        # create WSCOMMANDS_OBJECT node(s)
        for item, fields, className, localId in fObjectItems:
            rights = {}

            if className == SubTypes.Files:
                rights = self.cache.rightsOfFile(item)
                canReadFile = rights.get("get")
                if not canReadFile:
                    continue

            # treat cdb_file_record as cdb_file without blob
            elif className == SubTypes.FileRecords:
                className = SubTypes.Files

            elif className == SubTypes.Links:
                if not self.ignoreLinksWhileCheckout:
                    linkedObject = self.cache.getObjectById(item.cdb_link)

                    if linkedObject is None:
                        self._deleteLeftoverLinkItem(fObj, item)

                    elif self.forceCheckout:
                        linkedBoRights = self.cache.rightsOfBusinessObject(linkedObject)
                        if not linkedBoRights.get("get"):
                            continue

            self._createWsCommandsObject(
                ctx, fObjectId, rights, item, fields, className, localId
            )

    def _createWsCommandsObject(
        self, ctx, fObjectId, rights, item, fields, className, localId
    ):
        # create WSCOMMANDS_OBJECT reply
        newObject = WSCOMMANDS_OBJECT(
            cdb_classname=className, local_id=localId, cdb_object_id=item.cdb_object_id
        )
        with ctx.element(newObject.etreeElem.tag, newObject.etreeElem.attrib):
            newObject = None
            # -------------------------------------------------------------- #
            #  create LOCKINFO/RIGHTS/HASHES nodes for FILES                 #
            # -------------------------------------------------------------- #
            if className == SubTypes.Files:
                # LOCKINFO
                if not fields.get("cdb_belongsto"):
                    lockInfo = self.cache.getLockInfo(
                        fObjectId, item.cdb_object_id, self.wsLockId
                    )
                    if lockInfo is not None:
                        lockInfo = LOCKINFO(
                            status=lockInfo.get("status", "not"),
                            locker=lockInfo.get("locker", ""),
                            status_teamspace=lockInfo.get("status_teamspace", ""),
                            locker_teamspace=lockInfo.get("locker_teamspace", ""),
                        )
                        ctx.write(lockInfo.etreeElem)

                # RIGHTS
                fileRights = buildElementWithAttributes(RIGHTS, rights)
                ctx.write(fileRights.etreeElem)

                # HASHES
                blobId = item["cdbf_blob_id"]
                if blobId:
                    hashesElement = buildElementWithAttributes(
                        HASHES, {HashTypes.HTFiles: blobId}
                    )
                    ctx.write(hashesElement.etreeElem)

                # LINKSSTATUS
                linksStatus = self.cache.linkStatusOf(fObjectId, localId)
                if linksStatus:
                    linksStatusElement = LINKSSTATUS()
                    with ctx.element(
                        linksStatusElement.etreeElem.tag,
                        linksStatusElement.etreeElem.attrib,
                    ):
                        linksStatusElement = None
                        for link_id, relevant in six.iteritems(linksStatus):
                            newElement = LINKSTATUS(link_id=link_id, relevant=relevant)
                            ctx.write(newElement.etreeElem)
                            newElement = None

            # -------------------------------------------------------------- #
            #  create ATTRIBUTES node for WSCOMMANDS_OBJECTs                 #
            # -------------------------------------------------------------- #
            # only for cdb_file and cdb_links so far
            if className in (SubTypes.Files, SubTypes.Links):
                cdbfileWsmAttrs = self.cache.wsmAttributesOfFile(fObjectId, localId)
                if cdbfileWsmAttrs:
                    fields.update(cdbfileWsmAttrs)

            if fields:
                # remove doubled information, that is present in WSCOMMANDS_OBJECT
                # xml attributes
                if localId == fields.get("cdb_wspitem_id"):
                    del fields["cdb_wspitem_id"]
                attributesElement = buildElementWithAttributes(ATTRIBUTES, fields)
                ctx.write(attributesElement.etreeElem)

    def getFObjectItems(self, fObjectId):
        """
        Collect items of given context object.

        :Parameters:
            fObjectId : string
                id of context object
        :Return:
            tuple with (tuple with item values, list of info messages)
        """
        # contains return values with tuples with item and relevant itemvalues
        tmpItemData = {}
        infoXmlElems = []
        wspItemId2FName = {}
        belongsToItems = []
        filePathTuple2Item = {}

        # The ``workspaceItemsOf`` method might return objects, that are not
        # referenced by ``fObjectId`` (cdbf_object_id is different), because
        # the method does also return Teamspace file objects, which might
        # be referenced by the Teamspace business object only.
        tmpItems = self.cache.workspaceItemsOf(fObjectId)
        for item in tmpItems:
            className = getCdbClassname(item)
            if not (
                self.skipRecordsWhileCheckout and className == SubTypes.FileRecords
            ):

                fields = self.attrCollector.getFileAttributes(
                    item, self.reducedAttributes
                )
                wspItemId = item.cdb_wspitem_id
                fName = fields.get("cdbf_name")
                wspItemId2FName[wspItemId] = fName

                if fName:
                    folder = fields.get("cdb_folder")
                    if not folder:
                        folder = u""
                    filePathTuple = (folder, fName)
                    if filePathTuple in filePathTuple2Item:
                        filePathTuple2Item[filePathTuple].append(item)
                    else:
                        filePathTuple2Item[filePathTuple] = [item]

                belongsTo = fields.get("cdb_belongsto")
                if belongsTo:
                    belongsToItems.append((item, belongsTo, fName))

                tmpItemData[item.cdb_object_id] = (item, fields, className, wspItemId)

        # cleanup leftover cdb_file_records
        for items in six.itervalues(filePathTuple2Item):
            if len(items) > 1:
                cdbFiles = []
                cdbfileRecords = []
                for item in items:
                    if getCdbClassname(item) == SubTypes.FileRecords:
                        cdbfileRecords.append(item)
                    else:
                        cdbFiles.append(item)
                if cdbfileRecords:
                    # remove if a regular cdb_file with same name
                    # exists or if multiple cdb_file_record with same
                    # name exist
                    if cdbFiles or len(cdbfileRecords) > 1:
                        for cdbFileRecord in cdbfileRecords:
                            itemObjId = cdbFileRecord.cdb_object_id
                            infoXmlElem = self.deleteLeftoverCdbFileRecord(
                                cdbFileRecord
                            )
                            infoXmlElems.append(infoXmlElem)
                            item, fields, className, wspItemId = tmpItemData[itemObjId]
                            del tmpItemData[itemObjId]
                            del wspItemId2FName[wspItemId]

        # all cdb_wspitem_id are collected - check for valid belongsto ids
        for item, belongsTo, fName in belongsToItems:
            primaryFName = wspItemId2FName.get(belongsTo)
            # if subfolders are involved, dont check on filenames
            if primaryFName is None or (
                fName
                and not item.cdb_folder
                and item.cdb_classname != SubTypes.Folder
                and not fName.lower().startswith(primaryFName.split(".", 1)[0].lower())
            ):
                # orphaned belongsto item. cdb_belongsto contains
                # a cdb_wspitem_id but there is no file with this id.
                # try to delete the item, otherwise skip it. generate
                # a user message.
                itemObjId = item.cdb_object_id
                infoXmlElem = self.deleteLeftOverBelongsTo(item)
                # because ``workspaceItemsOf`` might return file objects, that
                # are not referenced by the business object with ``fObjectId``
                # (cdbf_object_id), we need to check, if the file object belongs
                # to the business object here. Otherwise it might be a Teamspace
                # file object. For these, we do not want to generate warnings.
                if item.cdbf_object_id == fObjectId:
                    infoXmlElems.append(infoXmlElem)
                if itemObjId in tmpItemData:
                    del tmpItemData[itemObjId]

        fObjectItems = six.itervalues(tmpItemData)
        return fObjectItems, infoXmlElems

    def deleteLeftOverBelongsTo(self, belongsToItem):
        ident = self._getCdbFileIdent(belongsToItem)
        msg = ""
        try:
            self._deleteFileRecord(belongsToItem)
            msg = tr(
                "Leftover file %1 deleted on the server. The main file of this"
                " preview or .appinfo no longer exists. This is for your"
                " information only. You can proceed as normal."
            )
        except Exception:
            msg = tr(
                "Leftover file %1 found on the server. The main file of this"
                " preview or .appinfo no longer exists. Please contact"
                " the system administrator to delete this file. This is for"
                " your information only. You can proceed as normal."
            )
        infoXmlElem = INFO(msg=msg)
        argList = TRANSLATIONARGLIST()
        argList.addChild(TRANSLATIONARG(trArg=ident))
        infoXmlElem.addChild(argList)
        return infoXmlElem

    def deleteLeftoverCdbFileRecord(self, cdbFileRecord):
        ident = self._getCdbFileIdent(cdbFileRecord)
        msg = ""
        try:
            self._deleteFileRecord(cdbFileRecord)
            msg = tr(
                "Leftover file entry %1 (cdb_file_record) deleted on the server. A"
                " valid file with same name exists. This is for your"
                " information only. You can proceed as normal."
            )
        except Exception:
            msg = tr(
                "Leftover file entry %1 (cdb_file_record) found on the server. A"
                " valid file with same name exists. Please contact"
                " the system administrator to delete this file. This is for"
                " your information only. You can proceed as normal."
            )
        infoXmlElem = INFO(msg=msg)
        argList = TRANSLATIONARGLIST()
        argList.addChild(TRANSLATIONARG(trArg=ident))
        infoXmlElem.addChild(argList)
        return infoXmlElem

    def _deleteLeftoverLinkItem(self, sourceObj, linkItem):
        """
        :param sourceObj: Document
        :param linkItem: cdb_link_item
        """
        targetId = linkItem.cdb_link
        sourceDesc = self._getObjectDescription(sourceObj)
        logging.error(
            "Document '%s' has a link to an object that does not exist anymore."
            " The id of the missing object is '%s'.",
            sourceDesc,
            targetId,
        )
        try:
            self._deleteFileRecord(linkItem)

            errMsg = tr(
                "Leftover link (cdb_link_item) from document '%1' deleted on the server."
                " The target object does not exist anymore (Id: %2). This is for your"
                " information only. You can proceed as normal."
            )
        except Exception:
            errMsg = tr(
                "Document '%1' has a link to an object that does not exist anymore."
                " The id of the missing object is '%2'. Please contact"
                " the system administrator to delete this file entry from the database."
            )
        linkError = ERROR(msg=errMsg)
        argList = TRANSLATIONARGLIST()
        argList.addChild(TRANSLATIONARG(trArg=sourceDesc))
        argList.addChild(TRANSLATIONARG(trArg=targetId))
        linkError.addChild(argList)
        errList = self.contextStatusDict.get(sourceObj.cdb_object_id)
        if errList:
            errList.addChild(linkError)

    def _deleteFileRecord(self, cdbFile):
        # may be an optimized type, e.g. LimitedFileItem
        if not isinstance(cdbFile, cdb_file_base):
            cdbFile = cdb_file_base.ByKeys(cdbFile.cdb_object_id)

        operation(
            kOperationDelete,
            cdbFile,
            system_args(active_integration=u"wspmanager", activecad=u"wspmanager"),
        )

    def _getCdbFileIdent(self, cdbFileItem):
        if hasattr(cdbFileItem, "cdbf_name"):
            return cdbFileItem.cdbf_name
        return cdbFileItem.cdb_object_id

    def getFileCount(self, fObjectId, skipRecords):
        """
        Count files using WsObjectCache.

        Even for a fileCounterOnly-commando the cache is filled (see
        WsObjectCache.fileCaching and triggerReplication).
        """
        classNames = [SubTypes.Files]
        if not skipRecords:
            classNames.append(SubTypes.FileRecords)

        fileCount = 0

        tmpItems = self.cache.workspaceItemsOf(fObjectId)
        for item in tmpItems:
            className = getCdbClassname(item)
            if className in classNames:
                fileCount += 1
        return fileCount

    def _writeCollectedTarget2Referrers(self, treeFObj, ctx):
        """
        Create SEARCH_REFERER_RESULT node

        :Parameters:
            treeFObj : an Object instance
                the object to generate the tree from
        """
        if treeFObj.searchReferrerResult:
            searchResult = SEARCH_REFERER_RESULT()
            for referrerObjId in treeFObj.searchReferrerResult:
                referrer = REFERER(id=referrerObjId)
                searchResult.addChild(referrer)
            ctx.write(searchResult.etreeElem)

    def getPrioBlobsElement(self, prioBlobs):
        blobsList = PRIOBLOBS()
        blobsList.etreeElem.text = json_to_b64_str(list(prioBlobs))
        return blobsList


class FrameBuilder(object):
    def __init__(self, cache, attrCollector, reducedAttributes):
        """
        Generate frame and sheet xml

        :parameters:
            cache : WsObjectCache cache to be able to optimize performance
            attrCollector : AttributesCollector
            reducedAttributes: integer, ReducedAttributes constant
        """
        self.cache = cache
        self.attrCollector = attrCollector
        self.reducedAttributes = reducedAttributes
        # docId_to_office_vars: dict, cdb_object_id = > office_vars as json
        self.docId_to_office_vars = dict()

    def setOfficeVars(self, docId_to_office_vars):
        # docId_to_office_vars: dict, cdb_object_id = > office_vars as json
        self.docId_to_office_vars = docId_to_office_vars

    def createFrameRelated(self, ctx, fObj):
        # FRAME METADATA
        frameHash, frameElement = self.addFrameData(fObj)
        if frameElement is not None:
            with ctx.element(frameElement.etreeElem.tag, frameElement.etreeElem.attrib):
                for frameElem in frameElement.etreeElem:
                    ctx.write(frameElem)
                    frameElem = None
                frameElement = None
        # SHEETS DATA
        sheetsFramesHash, sheetsElem = self.get_sheets_data(fObj)
        if sheetsElem is not None:
            with ctx.element(sheetsElem.etreeElem.tag, sheetsElem.etreeElem.attrib):
                for sheetElem in sheetsElem.etreeElem:
                    ctx.write(sheetElem)
                    sheetElem = None
                sheetsElem = None
        return frameHash, sheetsFramesHash

    @timingWrapper
    @timingContext("DETAIL addFrameData")
    def addFrameData(self, doc):
        """
        Creates framedata xml element for given document

        :Parameters:
            doc : instance of Document
        """
        logging.debug("+++ addFrameData start")
        frameHash = None
        fData = None
        framegroup = null2EmptyString(doc.z_format_gruppe)
        framename = null2EmptyString(doc.z_format)
        if framegroup and framename:
            frameObj = self.cache.getFrame(framename, framegroup)
            if frameObj:
                frameData = None
                bomData = None
                try:
                    frameData = get_data(doc.z_nummer, doc.z_index)
                    # newlines from multiline-fields
                    frameData = frameData.replace("\\\\n", "\\n")
                    # bom data isnt used yet in wsm. keep it for hash calculation though.
                    bomData = get_bom_data(doc.z_nummer, doc.z_index)
                except Exception:
                    logging.exception("Error in <WSCOMMANDS>: addFrameData: ")
                if frameData is not None and bomData is not None:
                    hasher = hashlib.md5()
                    schriftfeldlayer = getCADConfValue(
                        "ZVS Schriftfeld Layer", doc.erzeug_system
                    )
                    rahmenlayer = getCADConfValue("ZVS Rahmen Layer", doc.erzeug_system)
                    fData = FRAMEDATA(
                        cdb_object_id=frameObj.cdb_object_id,
                        framedata=frameData,
                        bomdata=bomData,
                        framelayer=rahmenlayer,
                        textlayer=schriftfeldlayer,
                    )
                    tmpFields = self.attrCollector.getFrameAttributes(
                        frameObj, self.reducedAttributes
                    )
                    if tmpFields:
                        attributesElement = buildElementWithAttributes(
                            ATTRIBUTES, tmpFields
                        )
                        fData.addChild(attributesElement)
                    if six.PY3:
                        hasher.update(frameData.encode("utf-8"))
                        hasher.update(bomData.encode("utf-8"))
                    else:
                        hasher.update(frameData)
                        hasher.update(bomData)
                    frameHash = hasher.hexdigest()
        elif framename == "" and framegroup == "":
            erzeug_system = doc.erzeug_system
            if erzeug_system and erzeug_system.startswith(u"MS-"):
                emitResults = []
                if doc.cdb_object_id in self.docId_to_office_vars:
                    office_vars = self.docId_to_office_vars.get(doc.cdb_object_id)
                    if office_vars:
                        read_vars, _write_vars = self.sort_office_vars(office_vars)
                        emitResults = sig.emit("ws_office_read")(doc, read_vars)
                    if not emitResults:
                        # try to get vars from appinfo as fallback
                        emitResults = sig.emit("ws_office_read_from_appinfo")(doc)
                # we assume only one or no result
                fstr = None
                for fstr in emitResults:
                    if fstr:
                        break
                if fstr is not None:
                    hasher = hashlib.md5()
                    # we got an office result
                    fData = FRAMEDATA(
                        cdb_object_id="",
                        framedata=fstr,
                        bomdata="",
                        framelayer="office",
                        textlayer="office",
                    )
                    if six.PY3:
                        hasher.update(fstr.encode("utf-8"))
                        hasher.update("".encode("utf-8"))
                        frameHash = hasher.hexdigest()
                    else:
                        hasher.update(fstr)
                        hasher.update("")
                    frameHash = hasher.hexdigest()
        logging.debug("+++ addFrameData end")
        return frameHash, fData

    @staticmethod
    def sort_office_vars(officeVars):
        """
        :param officeVars: dict varible config as string => value as string
        e.g.: {"cdb.r.this.werkstoff_nr.1.string": "",
               "cdb.rs.cdbpco_comp2result_val.value.N.string.QUANT": "3000000",
               "cdb.w.this.fek.1.numeric": "10",
               "cdb.ws.cdbpco_comp2para_val.value.N.numeric.AOR": "0,05"}
        """
        read_vars = dict()
        write_vars = dict()
        for var_id, var_value in list(six.iteritems(officeVars)):
            as_list = var_id.split(".")
            if len(as_list) > 3 and as_list[0] == "cdb":
                if as_list[1].find("r") >= 0:
                    read_vars[var_id] = None
                elif as_list[1].find("w") >= 0:
                    write_vars[var_id] = var_value
        return read_vars, write_vars

    @timingWrapper
    @timingContext("DETAIL get_sheets_data")
    def get_sheets_data(self, main_sheet_doc):
        """
        Creates sheets xml element for given document

        :parameters:
            main_sheet_doc : instance of Document
        :returns:
            pair (sheets_hash, sheets_element)
                 sheets_hash: md5 hash of data in xml sheets structure
                 sheets_element: xmlmapper sheets structure containing
                                 sheets/frame data from database
        """
        sheets_hash = ""
        sheets_element = None
        additional_document_type = None
        try:
            additional_document_type = main_sheet_doc.additional_document_type
        except AttributeError:
            pass
        if additional_document_type == "1":
            sheets = main_sheet_doc.DrawingSheets
            if sheets:
                sorted_sheets = sorted(sheets, key=lambda s: s.blattnr)
                sheets_element = SHEETS()
                sheets_hash_calc = hashlib.md5()
                for sheet_doc in sorted_sheets:
                    if sheet_doc.additional_document_type == "2":
                        sheet_element = SHEET(
                            id=sheet_doc.sheet_id,
                            number=sheet_doc.blattnr,
                            cdb_object_id=sheet_doc.cdb_object_id,
                        )
                        _, frame_data = self.addFrameData(sheet_doc)
                        if frame_data:
                            sheet_element.addChild(frame_data)
                        rights = self.cache.rightsOfBusinessObject(sheet_doc)
                        if rights:
                            rightsElem = buildElementWithAttributes(RIGHTS, rights)
                            sheet_element.addChild(rightsElem)
                        sheets_element.addChild(sheet_element)
                xmlStr = sheets_element.toEncodedString()
                sheets_hash_calc.update(xmlStr)
                sheets_hash = sheets_hash_calc.hexdigest()
        return sheets_hash, sheets_element
