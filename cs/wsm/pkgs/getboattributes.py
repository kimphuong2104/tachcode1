# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module checkoutcommand

Implements checkout command
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging
import six
import json
import base64

from io import BytesIO

from cs.wsm.pkgs.pkgsutils import getCdbClassname
from cs.wsm.pkgs.xmlfile import xmlfile
from cdb.platform.mom import getObjectHandlesFromObjectIDs
from cs.wsm.wsobjectcache import WsObjectCache
from cs.wsm.pkgs.cdbobj2xml import (
    buildElementWithAttributes,
    HashBuilder,
    FrameBuilder,
    SubTypes,
)
from cs.wsm.pkgs.attributesaccessor import AttributesCollector, ReducedAttributes
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.xmlmapper import (
    WSCOMMANDS_CONTEXTOBJECT,
    WSCOMMANDRESULT,
    ATTRIBUTES,
    HASHES,
    WSCOMMANDS_OBJECT,
    LOCKINFO,
)


class GetBoAttributesProcessor(CmdProcessorBase):
    """
    Collects pure document metadata, without files, links and other content.
    """

    name = u"getboattributes"

    def call(self, resultStream, request):
        errCode = 0
        (
            objIds,
            requestedAttributes,
            lang,
            wsId,
            wspLockId,
            docId_to_office_vars,
        ) = self._parseInput()
        idsLen = len(objIds)
        logging.debug("GetBoAttributesProcessor got %s IDs)", idsLen)

        if idsLen > 0:
            reply = self._buildReply(
                objIds, requestedAttributes, lang, wsId, wspLockId, docId_to_office_vars
            )
            resultStream.write(reply)
        return errCode

    def _buildReply(
        self,
        objIds,
        requestedAttributes,
        lang,
        wsId,
        wspLockId,
        docId_to_office_vars=None,
    ):
        attrCollector = AttributesCollector(lang)
        (docAttributes, fileAttributes) = requestedAttributes
        attrCollector.setRequestedDocAttributes(docAttributes)
        attrCollector.setRequestedFileAttributes(fileAttributes)
        cache = WsObjectCache(
            simplifiedRightsCheck=True, doRightsCheck=False, workspaceId=wsId
        )
        docs = cache.getObjectsByID(objIds)
        docs = {d.cdb_object_id: d for d in docs}

        # prefetch lock infos
        cache.getLockInfoOfNonDerivedFiles(objIds, wspLockId, includeFileRecords=True)

        hb = HashBuilder(cache)
        if hb.useArticleForObjectHash():
            cache.retrieveItemMDates(six.itervalues(docs))

        fb = FrameBuilder(cache, attrCollector, ReducedAttributes.REDUCED_ATTRIBUTES)
        if docId_to_office_vars:
            fb.setOfficeVars(docId_to_office_vars)
        getObjectHandlesFromObjectIDs(objIds, True)

        ret = BytesIO()
        with xmlfile(ret, encoding="utf-8") as ctx:
            wsCmdResult = WSCOMMANDRESULT(primary_object="")
            with ctx.element(wsCmdResult.etreeElem.tag, wsCmdResult.etreeElem.attrib):

                for objId, doc in six.iteritems(docs):
                    attrs = attrCollector.getDocumentAttributes(
                        doc, ReducedAttributes.REDUCED_ATTRIBUTES
                    )
                    cdbClassname = getCdbClassname(doc)
                    ctxElement = WSCOMMANDS_CONTEXTOBJECT(
                        cdb_object_id=objId, cdb_classname=cdbClassname
                    )
                    with ctx.element(
                        ctxElement.etreeElem.tag, ctxElement.etreeElem.attrib
                    ):

                        attributesElement = buildElementWithAttributes(
                            ATTRIBUTES, attrs
                        )
                        ctx.write(attributesElement.etreeElem)

                        fb.createFrameRelated(ctx, doc)

                        objHash = hb.getHash(doc)
                        hashesDict = {"object": objHash}
                        hashesElem = buildElementWithAttributes(HASHES, hashesDict)
                        ctx.write(hashesElem.etreeElem)

                        # lock-info only for non-anchor files
                        # if more is needed, we need to extend this
                        items = cache.workspaceItemsOf(objId)
                        for item in items:
                            className = getCdbClassname(item)

                            wspItemId = item.cdb_wspitem_id
                            cdbObjId = item.cdb_object_id

                            fields = attrCollector.getFileAttributes(
                                item, ReducedAttributes.REDUCED_ATTRIBUTES
                            )
                            if not fields.get("cdb_belongsto"):

                                # create WSCOMMANDS_OBJECT reply
                                newObject = WSCOMMANDS_OBJECT(
                                    cdb_classname=className,
                                    local_id=wspItemId,
                                    cdb_object_id=cdbObjId,
                                )
                                with ctx.element(
                                    newObject.etreeElem.tag, newObject.etreeElem.attrib
                                ):
                                    newObject = None
                                    # -------------------------------------------------------------- #
                                    #  create LOCKINFO nodes for FILES                               #
                                    # -------------------------------------------------------------- #

                                    # LOCKINFO
                                    lockInfo = cache.getLockInfo(
                                        objId, cdbObjId, wspLockId
                                    )
                                    if lockInfo is not None:
                                        lockInfo = LOCKINFO(
                                            status=lockInfo.get("status", "not"),
                                            locker=lockInfo.get("locker", ""),
                                            status_teamspace=lockInfo.get(
                                                "status_teamspace", ""
                                            ),
                                            locker_teamspace=lockInfo.get(
                                                "locker_teamspace", ""
                                            ),
                                        )
                                        ctx.write(lockInfo.etreeElem)

                                    # -------------------------------------------------------------- #
                                    #  create ATTRIBUTES node for WSCOMMANDS_OBJECTs                 #
                                    # -------------------------------------------------------------- #
                                    # only for cdb_file and cdb_links so far
                                    if className in (SubTypes.Files, SubTypes.Links):
                                        cdbfileWsmAttrs = cache.wsmAttributesOfFile(
                                            objId, wspItemId
                                        )
                                        if cdbfileWsmAttrs:
                                            fields.update(cdbfileWsmAttrs)

                                    if fields:
                                        # remove doubled information, that is present in WSCOMMANDS_OBJECT
                                        # xml attributes
                                        if wspItemId == fields.get("cdb_wspitem_id"):
                                            del fields["cdb_wspitem_id"]
                                        attributesElement = buildElementWithAttributes(
                                            ATTRIBUTES, fields
                                        )
                                        ctx.write(attributesElement.etreeElem)

        return ret.getvalue()

    def _parseInput(self):
        objIds = []
        docId_to_office_vars = dict()
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            for context in contexts:
                objIds.append(context.cdb_object_id)
                docAttributes = context.getObjectAttributes()
                if docAttributes:
                    officeVars = docAttributes.get("__office_vars__", None)
                    ctxObjectId = context.cdb_object_id
                    if officeVars and ctxObjectId:
                        office_vars = json.loads(base64.standard_b64decode(officeVars))
                        docId_to_office_vars[ctxObjectId] = office_vars

        docAttributes = set()
        fileAttributes = set()
        attrsLists = self._rootElement.getChildrenByName("ADDITIONALATTRIBUTES")
        for attrsList in attrsLists:
            attrs = attrsList.getChildrenByName("ADDITIONALDOCATTRIBUTE")
            for attr in attrs:
                docAttributes.add(attr.name)

            attrs = attrsList.getChildrenByName("ADDITIONALFILEATTRIBUTE")
            for attr in attrs:
                fileAttributes.add(attr.name)
        requestedAttributes = (docAttributes, fileAttributes)

        lang = self._rootElement.lang
        wspLockId = self._rootElement.wsplock_id
        wsId = self._rootElement.ws_id or None
        return objIds, requestedAttributes, lang, wsId, wspLockId, docId_to_office_vars
