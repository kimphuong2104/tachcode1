#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import six

from cs.wsm.pkgs.pkgsutils import getCdbClassname
from cs.wsm.index_helper import getIndexes
from cs.wsm.wsobjectcache import WsObjectCache, getDocumentsById
from cs.wsm.pkgs.xmlmapper import WSCOMMANDS_CONTEXTOBJECT

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.xmlfile import xmlfile
from cs.wsm.pkgs.cdbobj2xml import writeIndexes


class IndexVersionsProcessor(CmdProcessorBase):
    """
    Retrieves a list of all indexes (even older indexes) for BObjects.
    """

    name = u"indexversions"

    def call(self, resultStream, request):
        coids = self._parseInput()
        if coids is None:
            return WsmCmdErrCodes.invalidCommandRequest

        indexUpdateRule = self._rootElement.index_update_rule
        indexFilterRule = self._rootElement.index_filter_rule
        additionalIndexAttributes = self._rootElement.getAdditionalIndexAttributes()
        cache = WsObjectCache(simplifiedRightsCheck=True, doRightsCheck=False)

        with xmlfile(resultStream, encoding="utf-8") as ctx:
            with ctx.element("WSCOMMANDRESULT", None):
                # frames dont have indexes
                docs = getDocumentsById(coids)
                for coid, doc in six.iteritems(docs):
                    indexList, ownNumKey, ownIdxSortValue = getIndexes(
                        doc,
                        indexUpdateRule,
                        indexFilterRule,
                        cache,
                        withRecords=True,
                        compatibilityMode=False,
                    )
                    cdb_classname = getCdbClassname(doc)
                    ctxElement = WSCOMMANDS_CONTEXTOBJECT(
                        cdb_object_id=str(coid),
                        numberkey=str(ownNumKey),
                        indexsortval=str(ownIdxSortValue),
                        cdb_classname=cdb_classname,
                    )
                    with ctx.element(
                        ctxElement.etreeElem.tag, ctxElement.etreeElem.attrib
                    ):
                        writeIndexes(ctx, indexList, additionalIndexAttributes)

        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        res = None
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            res = []
            for context in contexts:
                res.append(context.cdb_object_id)
        return res
