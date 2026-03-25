#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from collections import OrderedDict
import logging

from lxml import etree

from cs.documents import Document

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext
import six


class FindObjectsProcessor(CmdProcessorBase):
    """
    Searches for unique objects described by a mapping from keys to values.
    """

    name = u"findobjects"

    @timingWrapper
    @timingContext("FINDOBJECTS")
    def call(self, resultStream, request):
        queries = self._parseInput()
        reply = OrderedDict()  # queryId -> (numHits, uniqueResult)

        for queryId, query in six.iteritems(queries):
            logging.info("FindObjectsProcessor: query is %s", query)
            num_hits = 0
            unique_result = None

            if query:
                collection = Document.KeywordQuery(**query)
                num_hits = len(collection)
                if num_hits == 1:
                    unique_result = collection[0].cdb_object_id

            logging.info(
                "FindObjectsProcessor: found %s results, unique_result is %s",
                num_hits,
                unique_result,
            )
            reply[queryId] = (num_hits, unique_result)

        self._writeReply(reply, resultStream)
        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        res = OrderedDict()  # query id -> query dict
        queryNodes = self._rootElement.getChildrenByName("SEARCH_QUERY")
        for queryNode in queryNodes:
            queryId = queryNode.etreeElem.attrib["query_id"]
            attributesNodes = queryNode.getChildrenByName("SEARCH_ATTRIBUTES")
            if len(attributesNodes) == 1:
                attrs = attributesNodes[0].attributes
                res[queryId] = attrs
        return res

    def _writeReply(self, results, resultStream):
        reply = etree.Element("REPLY")
        for queryId, (num_hits, unique_result) in six.iteritems(results):
            searchResult = etree.Element(
                "SEARCH_RESULT",
                {
                    "query_id": queryId,
                    "number_of_hits": u"%s" % num_hits,
                    "unique_result": unique_result if unique_result else "",
                },
            )
            reply.append(searchResult)

        replyString = etree.tostring(reply, encoding="utf-8")
        resultStream.write(replyString)
