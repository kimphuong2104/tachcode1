#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module getdrwformodels

Search drawings for models
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []

import logging
import six

from cs.wsm.pkgs.pkgsutils import getCdbClassname
from cs.wsm.pkgs.cdbobj2xml import buildElementWithAttributes
from cs.wsm.pkgs.attributesaccessor import AttributesCollector, ReducedAttributes
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.xmlmapper import WSCOMMANDS_CONTEXTOBJECT
from cs.wsm.pkgs.xmlmapper import WSCOMMANDRESULT, ATTRIBUTES
from cs.wsm.pkgs.drw_helper import queryDrawingDocuments


class GetdrwformodelsProcessor(CmdProcessorBase):
    """
    Handler class for getdrwformodels command.

    This class is used to fetch drawings from the PDM server.
    """

    name = u"getdrwformodels"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self.lang = self._rootElement.lang

    def call(self, resultStream, request):
        """
        The alternative protocol version to TalkAPI. Obtains object containing
        Drawing files for a given model (respectively models document) via
        sqlapi.
        """
        errCode = 0
        (
            modelCdbObjectIds,
            useModelArticle,
            requestedDocAttributes,
            minimumDrawingVersions,
        ) = self._parseInput()

        if len(modelCdbObjectIds) > 0:
            modelId2Drws = queryDrawingDocuments(
                modelCdbObjectIds,
                useModelArticle,
                minimumDrawingVersions=minimumDrawingVersions,
            )
            if modelId2Drws:
                xmlStr = self._buildReply(modelId2Drws, requestedDocAttributes)
                resultStream.write(xmlStr)
        else:
            logging.warning(u"GetdrwformodelsProcessor.call: no cdb_object_ids given")
        return errCode

    def _buildReply(self, modelId2Drws, requestedDocAttributes):
        wsCmdResult = WSCOMMANDRESULT(primary_object="")
        attrCollector = AttributesCollector(self.lang)
        attrCollector.setRequestedDocAttributes(requestedDocAttributes)

        for modelCdbObjId, drws in six.iteritems(modelId2Drws):
            for drw in drws:
                # check the rights. No need to send back
                # documents without read right.
                if drw.CheckAccess("read"):
                    cdb_classname = getCdbClassname(drw)
                    ctxElement = WSCOMMANDS_CONTEXTOBJECT(
                        cdb_object_id="%s" % drw.cdb_object_id,
                        cdb_classname=cdb_classname,
                    )
                    # no reduced attributes - the wsm may need all attributes
                    # for building a BObject name
                    tmpFields = attrCollector.getDocumentAttributes(
                        drw, ReducedAttributes.REDUCED_ATTRIBUTES
                    )
                    if tmpFields is not None:
                        # the model id from the request
                        tmpFields["model_cdb_object_id"] = modelCdbObjId
                        attributesElement = buildElementWithAttributes(
                            ATTRIBUTES, tmpFields
                        )
                        ctxElement.addChild(attributesElement)

                    wsCmdResult.addChild(ctxElement)
        reply = wsCmdResult.toEncodedString()
        return reply

    def _parseInput(self):
        useModelArticle = None
        options = self._rootElement.etreeElem.find("options")
        if options is not None:
            useModelArticle = options.attrib.get("use_model_article", None)
            if useModelArticle is not None:
                useModelArticle = bool(int(useModelArticle))

        requestedDocAttributes = None
        additionalAttributesElem = self._rootElement.etreeElem.find(
            "additional_attributes"
        )
        if additionalAttributesElem is not None:
            requestedDocAttributes = set()
            for attr in additionalAttributesElem:
                if attr.tag == "attribute":
                    nameAttr = attr.attrib.get("name", None)
                    if nameAttr is not None:
                        requestedDocAttributes.add(nameAttr)

        # the cdb_object_ids of the models
        modelCdbObjectIds = set()
        # The client can send the locally available drawings with the highest
        # index version, that exists. Make sure, that the client retrieve versions,
        # that are lower/older than the given ones.
        # The dict consists of z_nummer -> locally available highest index order.
        minimumDrawingVersions = dict()
        models = self._rootElement.etreeElem.find("models")
        if models is not None:
            for model in models:
                if model.tag == "model":
                    cdbObjId = model.attrib.get("cdb_object_id", None)
                    if cdbObjId is not None:
                        modelCdbObjectIds.add(cdbObjId)
                        localDrws = model.getchildren()
                        for localDrw in localDrws:
                            localDrwDocNumber = localDrw.attrib.get("z_nummer")
                            localDrwIndexOrder = int(localDrw.attrib.get("index_order"))
                            minimumDrawingVersions[
                                localDrwDocNumber
                            ] = localDrwIndexOrder
                        logging.info(
                            u"GetdrwformodelsProcessor._parseInput. model id: %s",
                            cdbObjId,
                        )

        logging.info(
            u"GetdrwformodelsProcessor._parseInput. use model article: %s",
            useModelArticle,
        )
        return (
            modelCdbObjectIds,
            useModelArticle,
            requestedDocAttributes,
            minimumDrawingVersions,
        )
