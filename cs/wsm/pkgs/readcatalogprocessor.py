#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import

from cdb.platform.mom import SimpleArguments
from cdb.platform import gui
from lxml import etree

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext

from cs.wsm.wssrvutils import json_to_b64_str


class ReadCatalogProcessor(CmdProcessorBase):
    """
    For reading the contents of catalogs.
    Either completely, or limited by a filtering query and/or max number of hits.
    The catalog contents are returned as a b64 encoded JSON list containing JSON dicts.

    Note: the query supports the full CDB search syntax.
    """

    name = u"readcatalog"

    @timingWrapper
    @timingContext("READCATALOG")
    def call(self, resultStream, request):
        data = []
        cdbClass, maxHits, attrs = self._parseInput()
        if cdbClass is None:
            return WsmCmdErrCodes.invalidCommandRequest

        catalog = gui.RestCatalog(cdbClass, "", [])
        t = catalog.do_table_browse(SimpleArguments(**attrs))
        wasTruncated = False
        for i in range(t.getNumberOfRows()):
            if maxHits and i >= maxHits:
                wasTruncated = True
                break
            oh = t.getObjectHandle(i)
            entry = {}
            for attrDef in oh.getClassDef().getAttributeDefs():
                identifier = attrDef.getName()
                entry[identifier] = oh[identifier]
            data.append(entry)
        replyData = json_to_b64_str(data)

        reply = etree.Element("REPLY")
        reply.attrib["wastruncated"] = "1" if wasTruncated else "0"
        reply.text = replyData
        replyString = etree.tostring(reply, encoding="utf-8")
        resultStream.write(replyString)
        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        catalog = None
        maxHits = None
        attrs = None

        queryNodes = self._rootElement.getChildrenByName("CATALOG_QUERY")
        if len(queryNodes) == 1:
            queryNode = queryNodes[0]
            catalog = queryNode.etreeElem.attrib["catalog"]
            maxHits = queryNode.etreeElem.attrib.get("maxHits")
            if maxHits:
                maxHits = int(maxHits)
            attributesNodes = queryNode.getChildrenByName("SEARCH_ATTRIBUTES")
            attrs = []
            if len(attributesNodes) == 1:
                attrs = attributesNodes[0].attributes
        return catalog, maxHits, attrs
