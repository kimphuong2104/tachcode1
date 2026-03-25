# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module wscommand

Base class for workspaces server commands
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import six
import json
import base64
from cdb import auth

from cs.wsm.pkgs.xmlfile import xmlfile
from cs.wsm.pkgs.cdbobj2xml import XmlGenerator, HashBuilder
from cs.wsm.pkgs.attributesaccessor import AttributesCollector, ReducedAttributes
from cs.wsm.pkgs.servertimingwrapper import measuringPoint
from cs.wsm.pkgs.filereplication import FileReplication
from cs.wsm.pkgs.xmlmapper import COMMANDSTATUSLIST, COMMANDSTATUS, WSCOMMANDRESULT

from cs.wsm.wsobjectcache import WsObjectCache


class WsCommand(object):
    NAME = ""

    def __init__(self, request):
        self._request = request
        self._contextObjs = request.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        self._resultStream = None

        self._cache = None

        # contextStatusDict: dict cdb_object_id -> localStatusList
        self._contextStatusDict = {}
        self._globalCmdStatusList = COMMANDSTATUSLIST()

        self._ignoreLinksWhileCheckout = self._request.only_command_bos == "1"
        # only if ignoreLinksWhileCheckout is True. Ignore links but
        # return the linked documents in a incomplete way.
        self._incompleteLinkTargets = False
        self._ignoreExternalLinks = False
        self._skipRecordsWhileCheckout = False
        # cache parameters
        self._doRightsChecks = True
        self._extendedCaching = True

        self._forceCheckout = self._request.force_checkout == "1"
        self._withBom = False
        self._filterFilename = self._request.filter_filename
        self._fileCounterOnly = self._request.file_counter_only == "1"
        # apply command to additional documents, e.g. drawings
        self._searchReferrers = None
        # simplified xml result, e.g. for getbolist command
        self._simplifiedReply = False
        # update server status command
        self._isStatusRequest = False
        self._webrequest = None
        # Configuration for CAD Variant sync
        self.autoVariantConfig = self._request.autovariant_config

        # for reply hash comparison
        self._getReplyHash = False
        self._lastReplyHash = None
        # e.g. edger server: replicated blobs that should be loaded first
        self._prioBlobs = None

    def setResultStream(self, stream):
        self._resultStream = stream

    def executeCommand(self):
        pass

    def setupCaching(self, webrequest):
        self._webrequest = webrequest
        self._setupCaching()
        self._performCaching()

    def _setupCaching(self, doRightsChecks=True, extendedCaching=True):
        logging.info(u"cdbwsmcmdprocessor: caching...")
        simplifiedRightsCheck = self._request.simplified_rights_check == "1"
        # file caching is always true for now, even for fileCounterOnly (counts objects in cache)
        self._cache = WsObjectCache(
            simplifiedRightsCheck,
            doRightsChecks,
            extendedCaching,
            fileCaching=True,
            lang=self._request.lang,
            workspaceId=self._request.ws_id,
        )
        # Item/parts caching. withBom needs all Item objects,
        # simplifiedReply doesnt need Item cdb_mdates for hashes calculation
        if not self._withBom:
            self._cache.cacheItems = False
            if (
                not self._simplifiedReply
                and HashBuilder(self._cache).useArticleForObjectHash()
            ):
                self._cache.cacheItemMDates = True

        if simplifiedRightsCheck:
            # fast collect file attributes
            attrCollector = AttributesCollector(self._request.lang)
            _, fileAttributes = self._request.getAdditionalAttributes()
            attrCollector.setRequestedFileAttributes(fileAttributes)

            limitedFileAttrs = attrCollector.getStatusRelevantFileAttributes()
            if limitedFileAttrs:
                self._cache.limitedFileAttrs = limitedFileAttrs

    def _performCaching(self, cacheLockInfos=True):
        with measuringPoint("REPLY CACHE PREFETCH"):
            ids = list(self._contextStatusDict)
            self._cache.prefetchObjects(
                ids, alsoFetchLinkedObjects=not self._ignoreLinksWhileCheckout
            )
            self._cache.prefetchAllTeamspaceObjects()
            if cacheLockInfos:
                self._cache.getLockInfoOfNonDerivedFiles(
                    ids, self._request.wsplock_id, includeFileRecords=True
                )

    def triggerReplicationIfActive(self):
        if self._request.trigger_replication == "1":
            logging.info(u"cdbwsmcmdprocessor: triggering replication...")

            blobIds = set()
            for cdb_files in six.itervalues(self._cache.getCachedWorkspaceItems()):
                for cdb_file in cdb_files:
                    blobId = cdb_file.cdbf_blob_id
                    if blobId:
                        blobIds.add(blobId)
            if blobIds:
                user = auth.persno
                mac_address = self._request.mac_address
                windows_session_id = self._request.windows_session_id
                repl = FileReplication(user, mac_address, windows_session_id)
                self._prioBlobs = repl.trigger(blobIds)
            else:
                logging.info(u"cdbwsmcmdprocessor: no files for replication")

    def generateReply(self):
        logging.info(u"cdbwsmcmdprocessor: generating reply...")
        self._setupXmlGenerator()
        self._generateReply()

    def _generateReply(self):

        if self._getReplyHash:
            self._resultStream.enableHasher()

        if self._lastReplyHash is not None:
            self._resultStream.setCompareHash(self._lastReplyHash)

        # set the primary_object attribute for the WSCOMMANDRESULT
        primaryContextObj = self._contextObjs[0]
        wsCmdResult = WSCOMMANDRESULT(primary_object=primaryContextObj.cdb_object_id)

        with xmlfile(self._resultStream, encoding="utf-8") as ctx:
            with ctx.element(wsCmdResult.etreeElem.tag, wsCmdResult.etreeElem.attrib):
                wsCmdResult = None
                with ctx.element(
                    self._globalCmdStatusList.etreeElem.tag,
                    self._globalCmdStatusList.etreeElem.attrib,
                ):
                    for globalCmdStatus in self._globalCmdStatusList.etreeElem:
                        ctx.write(globalCmdStatus)
                    self._globalCmdStatusList = None

                elements = self.buildElements()
                for elem in elements:
                    self._resultStream.write(elem)
                    elem = None

                if self._prioBlobs:
                    replBlobsElem = self._xmlGenerator.getPrioBlobsElement(
                        self._prioBlobs
                    )
                    ctx.write(replBlobsElem.etreeElem)

    def _setupXmlGenerator(self):
        objId2BomAttrs = self._getBomAttrs(self._contextObjs)

        # read additional pdm attributes
        additionalAttributes = self._request.getAdditionalAttributes()
        additionalIndexAttributes = self._request.getAdditionalIndexAttributes()

        self._xmlGenerator = XmlGenerator(
            self._contextStatusDict,
            self._skipRecordsWhileCheckout,
            self._ignoreLinksWhileCheckout,
            ReducedAttributes.REDUCED_ATTRIBUTES,
            self._request.index_update_rule,
            self._request.wsplock_id,
            self._request.index_load_rule,
            self._cache,
            self._request.index_filter_rule,
            additionalAttributes,
            additionalIndexAttributes,
            self._ignoreExternalLinks,
            self._withBom,
            objId2BomAttrs,
            self._forceCheckout,
            self._filterFilename,
            self._fileCounterOnly,
            self._searchReferrers,
            self._request.lang,
            self._incompleteLinkTargets,
            self._webrequest,
            self.autoVariantConfig,
        )

        # get incomplete ids from request. those are documents that
        # should stay incomplete. their links must not be followed.
        incompletePdmIds = set()
        incompleteLists = self._request.getChildrenByName("INCOMPLETE_CONTEXTOBJECTS")
        for incompleteList in incompleteLists:
            for incompleteObj in incompleteList.getChildren():
                incompletePdmIds.add(incompleteObj.id)
        self._xmlGenerator.setPredefinedTargetsToSkip(incompletePdmIds)
        self.getOfficeVars(self._contextObjs)

    def getOfficeVars(self, contextObjs):
        """
        Check whether context objects have requested
        office variables to be processed. Store extracted
        office variable inside XmlGenerator to further use
        __office_vars__ is a base64 encoded json dump of a dict
        """
        docId_to_office_vars = dict()
        for ctxObj in contextObjs:
            docAttributes = ctxObj.getObjectAttributes()
            if docAttributes:
                officeVars = docAttributes.get("__office_vars__", None)
                ctxObjectId = ctxObj.cdb_object_id
                if officeVars and ctxObjectId:
                    office_vars = json.loads(base64.standard_b64decode(officeVars))
                    docId_to_office_vars[ctxObjectId] = office_vars
        self._xmlGenerator.setOfficeVars(docId_to_office_vars)

    def buildElements(self):
        for cntxCdbObjectId in six.iterkeys(self._contextStatusDict):
            cdbObject = self._cache.getCachedObject(cntxCdbObjectId)
            if cdbObject:
                for ctxObj in self._xmlGenerator.generateElements(
                    cdbObject, self._simplifiedReply
                ):
                    yield ctxObj
                    ctxObj = None

        for ctxObj in self._xmlGenerator.generateElementsForSkippedExternalLinked(
            self._simplifiedReply
        ):
            yield ctxObj

        ignoredAttributes = self._xmlGenerator.attrCollector.getIgnoredAttributes()
        for objType, attrs in six.iteritems(ignoredAttributes):
            if len(attrs):
                joinedAttrs = ", ".join(attrs)
                logging.warning(
                    "Inaccessible PDM attributes for '%s': %s", objType, joinedAttrs
                )
        self._xmlGenerator.clearGeneratedElements()

    def _addCtxObjectCmdStatus(self, cntxCdbObjectId, value):
        commandStatus = COMMANDSTATUS(
            cdb_object_id=cntxCdbObjectId, local_id="", action=self.NAME, value=value
        )
        self._globalCmdStatusList.addChild(commandStatus)

    def _readIgnoreLinkParams(self, xmlCmd):
        commandAttributes = xmlCmd.getObjectAttributes()
        if commandAttributes:
            ignoreLinks = commandAttributes.get("ignore_links", None)
            if ignoreLinks:
                self._ignoreLinksWhileCheckout = ignoreLinks == "yes"
                if self._ignoreLinksWhileCheckout:
                    if commandAttributes.get("incomplete_link_targets") == "yes":
                        self._incompleteLinkTargets = True

            ignoreExternalLinks = commandAttributes.get("ignore_external_links", None)
            if ignoreExternalLinks:
                self._ignoreExternalLinks = ignoreExternalLinks == "yes"

    def _getBomAttrs(self, contextObjs):
        retDict = {}
        for ctxObj in contextObjs:
            itemAttrs, bomItemAttrs = ctxObj.getBomAttrs()
            if itemAttrs or bomItemAttrs:
                objId = ctxObj.cdb_object_id
                retDict[objId] = (itemAttrs, bomItemAttrs)
        return retDict
