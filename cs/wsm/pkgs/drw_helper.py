#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from __future__ import absolute_import

import logging
from collections import defaultdict

from cdb import sqlapi
from cdb.objects import Rule

from cs.wsm.index_helper import getIndexOrder
from cs.wsm.pkgs.pkgsutils import grouper, toStringTuple

from cs.documents import Document


def queryDrawingDocuments(
    modelCdbObjectIds,
    useModelArticle=False,
    drwFilterCondition=None,
    minimumDrawingVersions=None,
):
    """
    Uses the object rule "2D Drawings",
    unless a value for "drwFilterCondition" is given.

    Query all drawings for the given ``cdb_object_id`` attribute of the model
    objects.

    Filter drawings by using the rule "2D Drawings", unless a value for
    ``drwFilterCondition`` is given.

    :param modelCdbObjectIds: Query drawings for these models.
    :type modelCdbObjectIds: list(str)
    :param useModelArticle: Model and drawing MUST have the same part number?
    :type useModelArticle: bool
    :param drwFilterCondition: optional; must be a constant string; using a user-supplied value would be a security error
    :type drwFilterCondition: str
    :param minimumDrawingVersions: Return higher versions than this. Contains
        z_nummer -> index order.
    :type minimumDrawingVersions: dict(str: int)
    """
    # always the same condition:
    # a link item must exist with target id equal
    # to one of the models cdb_object_id
    stmt = (
        "select drw.cdb_object_id, mdl.cdb_object_id as model_cdb_object_id FROM"
        " zeichnung drw, zeichnung mdl, cdb_file WHERE"
        " cdb_file.cdb_classname='cdb_link_item' AND"
        " (cdb_file.cdb_folder='' OR cdb_file.cdb_folder IS NULL) AND"
        " cdb_file.cdbf_object_id=drw.cdb_object_id AND"
        " cdb_file.cdb_link=mdl.cdb_object_id AND"
        " mdl.cdb_object_id IN MODELIDS_REPLACEMENT"
    )
    if useModelArticle:
        stmt = stmt + " AND drw.teilenummer=mdl.teilenummer"
    if drwFilterCondition:
        stmt = stmt + " AND %s" % drwFilterCondition

    drawingsRule = None
    if drwFilterCondition is None:
        drawingsRule = Rule.ByKeys(name="2D Drawings")
        if drawingsRule is None:
            logging.error(
                u"GetdrwformodelsProcessor.call"
                u" object rule '2D Drawings' not found. Result may contain too many documents."
            )

    # Calculated index order for all indexes of the given drawing by z_nummer.
    # The dict consists of z_nummer -> z_index -> index order
    drawingsIndexOrder = {}
    if minimumDrawingVersions:
        zNummerList = list(minimumDrawingVersions)
        drawingsIndexOrder = getIndexOrder(zNummerList)

    # model cdb_object_id to drawing documents
    modelId2Drws = defaultdict(list)

    for chunk in grouper(500, modelCdbObjectIds):

        # collect cdb_object_ids of referencing drawings for each model
        modelIds = toStringTuple(chunk)
        finalStmt = stmt.replace("MODELIDS_REPLACEMENT", modelIds)
        logging.info(u"GetdrwformodelsProcessor.call" u" SQL statement: %s", finalStmt)

        # now collect full documents, filter doubles
        recs = sqlapi.RecordSet2(sql=finalStmt)

        # collect drawing ids and remember corresponding modelId
        drwIds = set()
        drwId2ModelId = defaultdict(list)
        for rec in recs:
            drwIds.add(rec.cdb_object_id)
            drwId2ModelId[rec.cdb_object_id] = rec.model_cdb_object_id

        # collect doc objects, needed for xml generation
        if drwIds:
            if drawingsRule is not None:
                # get matching drawing docs efficiently, using Rule.getObjects
                docs = []
                # in some cases, this can be more than 500 drawings, so chunk it
                for drawingsChunk in grouper(500, drwIds):
                    drwIdTuple = toStringTuple(drawingsChunk)
                    drwSql = "cdb_object_id IN %s" % drwIdTuple
                    docs.extend(drawingsRule.getObjects(Document, add_expr=drwSql))
            else:
                docs = Document.KeywordQuery(cdb_object_id=drwIds)

            for doc in docs:
                includeThisDoc = True
                docNumber = doc.z_nummer
                docIndex = doc.z_index
                if minimumDrawingVersions:
                    if (
                        docNumber in drawingsIndexOrder
                        and docNumber in minimumDrawingVersions
                    ):
                        if docIndex in drawingsIndexOrder[docNumber]:
                            thisIndexOrder = drawingsIndexOrder[docNumber][docIndex]
                            clientIndexOrder = minimumDrawingVersions[docNumber]
                            includeThisDoc = thisIndexOrder > clientIndexOrder
                if includeThisDoc:
                    modelId = drwId2ModelId.get(doc.cdb_object_id)
                    modelId2Drws[modelId].append(doc)
                else:
                    logging.info(
                        u"GetdrwformodelsProcessor.call: " u"Filtered drawing '%s-%s'",
                        docNumber,
                        docIndex,
                    )
    return modelId2Drws
