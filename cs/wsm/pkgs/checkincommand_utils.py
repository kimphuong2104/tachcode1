#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

from cdb.objects.cdb_file import cdb_file_base

from cs.wsm.cdbfilewsm import Cdb_file_wsm
from cs.wsm.cdbfilelinksstatus import Cdb_file_links_status


def copyFileObjectsToTeamspace(srcId, dstId, cache=None, newCdbLock=None):
    """
    Copy file objects from a source business object to a
    destination business object, e.g. from a PDM document to a
    Teamspace document.

    :param srcId: The id of a document record used as source.
    :type srcId: str
    :param dstId: The id of a document record used as destination.
    :type dstId: str
    :param cache: A cache to query the objects.
    :type cache: WsObjectCache
    :param newCdbLock: Set this as new ``cdb_lock`` attribute for primary files.
    :type newCdbLock: str
    :return: Mapping of source id to destination id for newly created objects.
    :returntype: dict(str: str)
    """
    mappedFileIds = {}
    # TODO: Use cache to retrieve the files here.
    #       E060652: Bei Verwendung des Teamspace: Dateien aus dem Cache laden
    # copy cdb_file_base objects
    for originalFile in cdb_file_base.KeywordQuery(cdbf_object_id=srcId):
        args = {k: originalFile[k] for k in originalFile.keys()}
        srcObjId = args.pop("cdb_object_id", None)
        args["cdbf_object_id"] = dstId
        cdbfPrimary = args.get("cdbf_primary", "0") == "1"
        if cdbfPrimary and newCdbLock is not None:
            args["cdb_lock"] = newCdbLock
        fileObj = cdb_file_base.Create(**args)
        dstObjId = fileObj.cdb_object_id
        mappedFileIds[srcObjId] = dstObjId
    # copy cdb_file_wsm
    for originalFileAttrs in Cdb_file_wsm.KeywordQuery(cdbf_object_id=srcId):
        args = {k: originalFileAttrs[k] for k in originalFileAttrs.keys()}
        srcObjId = args.pop("cdb_object_id", None)
        args["cdbf_object_id"] = dstId
        fileObj = Cdb_file_wsm.Create(**args)
        dstObjId = fileObj.cdb_object_id
        mappedFileIds[srcObjId] = dstObjId
    # copy links status
    for originalLinksStatus in Cdb_file_links_status.KeywordQuery(cdbf_object_id=srcId):
        args = {k: originalLinksStatus[k] for k in originalLinksStatus.keys()}
        srcObjId = args.pop("cdb_object_id", None)
        args["cdbf_object_id"] = dstId
        fileObj = Cdb_file_links_status.Create(**args)
        dstObjId = fileObj.cdb_object_id
        mappedFileIds[srcObjId] = dstObjId
    return mappedFileIds
